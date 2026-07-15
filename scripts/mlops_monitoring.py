"""Monitoramento de MLOps (item iii): saúde, artefatos, drift e baseline.

Gera relatório JSON no Data Lake (`s3://artifacts/monitoring/`) sem alterar
o fluxo de treino. Pensado para a DAG ``05_monitor_health`` e para inspeção
manual na banca.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import s3fs
import yaml

from scripts.integrations_config import get_integrations_config
from scripts.model_config import get_model_config, load_model_metadata


LOGGER = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_CONFIG_PATH = REPO_ROOT / "DataPipeline" / "pipeline_config.yaml"

MINIO_ROOT_USER = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_ROOT_PASSWORD = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
API_HEALTH_URL = os.getenv("API_HEALTH_URL", "http://api:8000/")
MONITORING_LATEST_PATH = os.getenv(
    "MONITORING_LATEST_PATH",
    "s3://artifacts/monitoring/latest.json",
)

DEFAULT_DRIFT_NUMERIC = (
    "EXT_SOURCE_1",
    "EXT_SOURCE_2",
    "EXT_SOURCE_3",
    "AMT_CREDIT",
    "AMT_ANNUITY",
)
DEFAULT_DRIFT_CATEGORICAL = ("NAME_INCOME_TYPE",)
DEFAULT_PSI_WARN = 0.10
DEFAULT_PSI_FAIL = 0.25
DEFAULT_DRIFT_SAMPLE = 5000


def load_pipeline_monitoring_config() -> dict[str, Any]:
    """Carrega parâmetros de drift do pipeline_config.yaml quando disponível."""
    if not PIPELINE_CONFIG_PATH.is_file():
        return {}
    with PIPELINE_CONFIG_PATH.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    return dict(raw.get("monitoring", {}))


def get_drift_settings() -> dict[str, Any]:
    """Resolve features e limiares de PSI (env > yaml > default)."""
    yaml_cfg = load_pipeline_monitoring_config()
    numeric = yaml_cfg.get("drift_features_numeric", DEFAULT_DRIFT_NUMERIC)
    categorical = yaml_cfg.get("drift_features_categorical", DEFAULT_DRIFT_CATEGORICAL)
    return {
        "numeric": list(numeric),
        "categorical": list(categorical),
        "psi_warn": float(os.getenv("PSI_WARN_THRESHOLD", yaml_cfg.get("psi_warn", DEFAULT_PSI_WARN))),
        "psi_fail": float(os.getenv("PSI_FAIL_THRESHOLD", yaml_cfg.get("psi_fail", DEFAULT_PSI_FAIL))),
        "sample_size": int(os.getenv("DRIFT_SAMPLE_SIZE", yaml_cfg.get("sample_size", DEFAULT_DRIFT_SAMPLE))),
    }


def read_parquet_sample(
    path: str,
    *,
    sample_size: int,
    random_state: int,
    fs: s3fs.S3FileSystem,
) -> pd.DataFrame:
    """Lê Parquet local/remoto e devolve amostra estratificada por tamanho."""
    with fs.open(path, "rb") as handle:
        frame = pd.read_parquet(handle, engine="pyarrow")
    if len(frame) <= sample_size:
        return frame
    return frame.sample(n=sample_size, random_state=random_state)


def compute_psi(
    expected: pd.Series,
    actual: pd.Series,
    *,
    bins: int = 10,
) -> float:
    """Calcula Population Stability Index entre duas amostras numéricas."""
    expected_num = pd.to_numeric(expected, errors="coerce").dropna()
    actual_num = pd.to_numeric(actual, errors="coerce").dropna()
    if expected_num.empty or actual_num.empty:
        return float("nan")

    breakpoints = np.unique(np.percentile(expected_num, np.linspace(0, 100, bins + 1)))
    if len(breakpoints) < 2:
        return 0.0

    expected_counts = np.histogram(expected_num, bins=breakpoints)[0]
    actual_counts = np.histogram(actual_num, bins=breakpoints)[0]
    expected_pct = expected_counts / max(expected_counts.sum(), 1)
    actual_pct = actual_counts / max(actual_counts.sum(), 1)

    epsilon = 1e-6
    expected_pct = np.clip(expected_pct, epsilon, None)
    actual_pct = np.clip(actual_pct, epsilon, None)
    return float(np.sum((actual_pct - expected_pct) * np.log(actual_pct / expected_pct)))


def compute_categorical_psi(expected: pd.Series, actual: pd.Series) -> float:
    """Calcula PSI para variável categórica via proporções de categorias."""
    expected_counts = expected.astype("string").fillna("__MISSING__").value_counts(normalize=True)
    actual_counts = actual.astype("string").fillna("__MISSING__").value_counts(normalize=True)
    categories = sorted(set(expected_counts.index).union(actual_counts.index))
    if not categories:
        return float("nan")

    epsilon = 1e-6
    psi = 0.0
    for category in categories:
        exp_pct = max(float(expected_counts.get(category, 0.0)), epsilon)
        act_pct = max(float(actual_counts.get(category, 0.0)), epsilon)
        psi += (act_pct - exp_pct) * np.log(act_pct / exp_pct)
    return float(psi)


def _psi_status(psi_value: float, *, psi_warn: float, psi_fail: float) -> str:
    """Classifica PSI em ok/warn/fail."""
    if np.isnan(psi_value):
        return "warn"
    if psi_value >= psi_fail:
        return "fail"
    if psi_value >= psi_warn:
        return "warn"
    return "ok"


def check_data_drift(fs: s3fs.S3FileSystem | None = None) -> dict[str, Any]:
    """Compara distribuição do holdout demo vs. amostra da ABT (data drift)."""
    config = get_model_config()
    active_fs = fs or get_s3_filesystem()
    settings = get_drift_settings()
    random_state = config.random_state

    try:
        reference = read_parquet_sample(
            config.resolve_abt_path(),
            sample_size=settings["sample_size"],
            random_state=random_state,
            fs=active_fs,
        )
        actual = read_parquet_sample(
            config.resolve_demo_holdout_path(),
            sample_size=min(settings["sample_size"], 500),
            random_state=random_state,
            fs=active_fs,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "name": "data_drift",
            "status": "fail",
            "detail": f"Falha ao carregar ABT/holdout para PSI: {exc}",
            "features": [],
        }

    feature_results: list[dict[str, Any]] = []
    for feature in settings["numeric"]:
        if feature not in reference.columns or feature not in actual.columns:
            feature_results.append(
                {
                    "feature": feature,
                    "type": "numeric",
                    "psi": None,
                    "status": "warn",
                    "detail": "Coluna ausente na ABT ou no holdout",
                }
            )
            continue
        psi_value = compute_psi(reference[feature], actual[feature])
        status = _psi_status(
            psi_value,
            psi_warn=settings["psi_warn"],
            psi_fail=settings["psi_fail"],
        )
        feature_results.append(
            {
                "feature": feature,
                "type": "numeric",
                "psi": round(psi_value, 4) if not np.isnan(psi_value) else None,
                "status": status,
                "detail": f"PSI={psi_value:.4f}" if not np.isnan(psi_value) else "PSI indisponível",
            }
        )

    for feature in settings["categorical"]:
        if feature not in reference.columns or feature not in actual.columns:
            feature_results.append(
                {
                    "feature": feature,
                    "type": "categorical",
                    "psi": None,
                    "status": "warn",
                    "detail": "Coluna ausente na ABT ou no holdout",
                }
            )
            continue
        psi_value = compute_categorical_psi(reference[feature], actual[feature])
        status = _psi_status(
            psi_value,
            psi_warn=settings["psi_warn"],
            psi_fail=settings["psi_fail"],
        )
        feature_results.append(
            {
                "feature": feature,
                "type": "categorical",
                "psi": round(psi_value, 4) if not np.isnan(psi_value) else None,
                "status": status,
                "detail": f"PSI={psi_value:.4f}" if not np.isnan(psi_value) else "PSI indisponível",
            }
        )

    overall = "ok"
    for item in feature_results:
        overall = merge_status(overall, str(item["status"]))

    max_psi = max(
        (item["psi"] for item in feature_results if item["psi"] is not None),
        default=0.0,
    )
    return {
        "name": "data_drift",
        "status": overall,
        "reference": config.resolve_abt_path(),
        "actual": config.resolve_demo_holdout_path(),
        "psi_warn_threshold": settings["psi_warn"],
        "psi_fail_threshold": settings["psi_fail"],
        "max_psi": max_psi,
        "features": feature_results,
        "detail": (
            f"PSI máximo={max_psi:.4f} "
            f"(warn≥{settings['psi_warn']}, fail≥{settings['psi_fail']})"
        ),
    }


def check_feature_schema(fs: s3fs.S3FileSystem | None = None) -> dict[str, Any]:
    """Valida contrato de features entre metadata, config e colunas da ABT."""
    config = get_model_config()
    active_fs = fs or get_s3_filesystem()
    try:
        metadata = load_model_metadata(config, fs=active_fs)
        meta_features = list(metadata.get("feature_columns", []))
        with active_fs.open(config.resolve_abt_path(), "rb") as handle:
            abt_columns = list(pd.read_parquet(handle, engine="pyarrow").columns)

        expected_features = config.feature_columns(abt_columns)
        missing_in_abt = [col for col in meta_features if col not in abt_columns]
        extra_vs_config = [col for col in meta_features if col not in expected_features]

        status = "ok"
        if missing_in_abt or extra_vs_config:
            status = "warn"
        if not meta_features:
            status = "fail"

        return {
            "name": "feature_schema",
            "status": status,
            "metadata_feature_count": len(meta_features),
            "config_feature_count": len(expected_features),
            "missing_in_abt": missing_in_abt[:10],
            "unexpected_vs_config": extra_vs_config[:10],
            "detail": (
                "Contrato de features alinhado"
                if status == "ok"
                else "Divergência entre metadata, config e ABT"
            ),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "name": "feature_schema",
            "status": "fail",
            "detail": f"Falha na validação de schema: {exc}",
        }


def check_performance_baseline(fs: s3fs.S3FileSystem | None = None) -> dict[str, Any]:
    """Verifica linha de base de métricas no metadata (proxy de performance decay)."""
    config = get_model_config()
    try:
        metadata = load_model_metadata(config, fs=fs)
        metrics = metadata.get("metrics_test", {})
        required = ("pr_auc", "recall_inadimplente", "fn", "fp", "threshold")
        missing = [key for key in required if key not in metrics]
        if missing:
            return {
                "name": "performance_baseline",
                "status": "fail",
                "detail": f"Métricas ausentes no metadata: {missing}",
            }

        pr_auc = float(metrics["pr_auc"])
        recall = float(metrics["recall_inadimplente"])
        fn = int(metrics["fn"])
        status = "ok"
        detail = (
            f"PR-AUC={pr_auc:.4f} | Recall={recall:.1%} | FN={fn:,} "
            "(linha de base registrada no treino)"
        )
        if pr_auc < 0.10 or recall < 0.40:
            status = "warn"
            detail += "; métricas abaixo do esperado para o problema"

        return {
            "name": "performance_baseline",
            "status": status,
            "metrics_test": {key: metrics[key] for key in required},
            "trained_at": metadata.get("trained_at"),
            "detail": detail,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "name": "performance_baseline",
            "status": "fail",
            "detail": f"Falha ao ler baseline de performance: {exc}",
        }


def get_s3_filesystem() -> s3fs.S3FileSystem:
    """Cria filesystem S3 apontando para o MinIO."""
    endpoint_url = get_integrations_config().minio.endpoint_url
    return s3fs.S3FileSystem(
        key=MINIO_ROOT_USER,
        secret=MINIO_ROOT_PASSWORD,
        client_kwargs={"endpoint_url": endpoint_url},
    )


def _status_rank(status: str) -> int:
    order = {"ok": 0, "warn": 1, "fail": 2}
    return order.get(status, 2)


def merge_status(*statuses: str) -> str:
    """Combina vários status no pior resultado."""
    return max(statuses, key=_status_rank)


def check_api_health(url: str | None = None, timeout: float = 5.0) -> dict[str, Any]:
    """Verifica disponibilidade e payload básico do health check da API."""
    target = (url or API_HEALTH_URL).rstrip("/") + "/"
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(target, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
            latency_ms = (time.perf_counter() - started) * 1000
            threshold = body.get("business_threshold")
            status = "ok"
            detail = f"HTTP {response.status}; latency_ms={latency_ms:.1f}"
            if threshold is None:
                status = "warn"
                detail += "; business_threshold ausente na resposta"
            return {
                "name": "api_health",
                "status": status,
                "url": target,
                "latency_ms": round(latency_ms, 1),
                "payload": body,
                "detail": detail,
            }
    except Exception as exc:  # noqa: BLE001 — monitoramento registra falha
        return {
            "name": "api_health",
            "status": "fail",
            "url": target,
            "latency_ms": None,
            "payload": None,
            "detail": f"API indisponível: {exc}",
        }


def check_s3_object(path: str, fs: s3fs.S3FileSystem | None = None) -> dict[str, Any]:
    """Confirma que um objeto existe e tem tamanho > 0 no MinIO."""
    active_fs = fs or get_s3_filesystem()
    try:
        info = active_fs.info(path)
        size = int(info.get("size") or info.get("Size") or 0)
        if size <= 0:
            return {
                "name": f"artifact:{path}",
                "status": "fail",
                "path": path,
                "size": size,
                "detail": "Objeto vazio",
            }
        return {
            "name": f"artifact:{path}",
            "status": "ok",
            "path": path,
            "size": size,
            "detail": f"Objeto presente ({size} bytes)",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "name": f"artifact:{path}",
            "status": "fail",
            "path": path,
            "size": None,
            "detail": f"Objeto ausente ou inacessível: {exc}",
        }


def check_threshold_coherence(fs: s3fs.S3FileSystem | None = None) -> dict[str, Any]:
    """Compara business_threshold do config com o salvo em model_metadata."""
    config = get_model_config()
    config_threshold = float(config.business_threshold)
    try:
        metadata = load_model_metadata(config, fs=fs)
        meta_threshold = float(
            metadata.get("metrics_test", {}).get("threshold")
            or metadata.get("business", {}).get("threshold")
        )
        coherent = abs(config_threshold - meta_threshold) < 1e-9
        return {
            "name": "threshold_coherence",
            "status": "ok" if coherent else "warn",
            "config_threshold": config_threshold,
            "metadata_threshold": meta_threshold,
            "detail": (
                "Threshold alinhado entre config e metadata"
                if coherent
                else "Threshold diverge entre Model/model_config.yaml e metadata"
            ),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "name": "threshold_coherence",
            "status": "fail",
            "config_threshold": config_threshold,
            "metadata_threshold": None,
            "detail": f"Falha ao ler metadata: {exc}",
        }


def build_monitoring_report(
    *,
    api_url: str | None = None,
    fs: s3fs.S3FileSystem | None = None,
) -> dict[str, Any]:
    """Executa todas as checagens e monta o relatório consolidado."""
    config = get_model_config()
    active_fs = fs or get_s3_filesystem()

    checks = [
        check_api_health(api_url),
        check_s3_object(config.resolve_abt_path(), active_fs),
        check_s3_object(config.resolve_demo_holdout_path(), active_fs),
        check_s3_object(config.resolve_model_artifact_path(), active_fs),
        check_s3_object(config.resolve_metadata_path(), active_fs),
        check_threshold_coherence(active_fs),
        check_feature_schema(active_fs),
        check_data_drift(active_fs),
        check_performance_baseline(active_fs),
    ]
    overall = "ok"
    for check in checks:
        overall = merge_status(overall, str(check["status"]))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall_status": overall,
        "checks": checks,
        "runbook": {
            "fail": "Não escorar em produção até restaurar artefatos/API; investigar MinIO/Airflow.",
            "warn": "Investigar drift (PSI), divergência de threshold ou degradação parcial; manter humano no loop.",
            "ok": "Serviço, artefatos e distribuições coerentes com a linha de base.",
        },
    }


def write_monitoring_report(
    report: dict[str, Any],
    *,
    fs: s3fs.S3FileSystem | None = None,
    latest_path: str | None = None,
) -> dict[str, str]:
    """Persiste latest.json e uma cópia versionada por timestamp no MinIO."""
    active_fs = fs or get_s3_filesystem()
    target_latest = latest_path or MONITORING_LATEST_PATH
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    versioned = f"s3://artifacts/monitoring/runs/{stamp}.json"
    payload = json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8")

    for path in (target_latest, versioned):
        parent = path.rsplit("/", 1)[0]
        active_fs.makedirs(parent, exist_ok=True)
        with active_fs.open(path, "wb") as handle:
            handle.write(payload)

    LOGGER.info(
        "Relatório de monitoramento gravado: overall=%s latest=%s",
        report.get("overall_status"),
        target_latest,
    )
    return {"latest": target_latest, "versioned": versioned}


def run_monitoring(*, fail_on_error: bool = True) -> dict[str, Any]:
    """Ponto de entrada CLI/DAG: checa, grava e opcionalmente falha."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    report = build_monitoring_report()
    paths = write_monitoring_report(report)
    report["artifacts"] = paths
    if fail_on_error and report["overall_status"] == "fail":
        raise RuntimeError(
            "Monitoramento falhou: "
            + "; ".join(
                f"{c['name']}={c['status']}"
                for c in report["checks"]
                if c["status"] == "fail"
            )
        )
    return report


def main() -> int:
    """Executa monitoramento e devolve código de saída para o shell."""
    try:
        report = run_monitoring(fail_on_error=True)
    except Exception:
        LOGGER.exception("Falha no monitoramento MLOps")
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["overall_status"] != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
