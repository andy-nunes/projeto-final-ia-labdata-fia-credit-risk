"""Carrega e expõe a configuração central do modelo LightGBM."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "model_config.yaml"


@dataclass(frozen=True)
class ModelConfig:
    """Snapshot imutável da configuração do modelo."""

    raw: dict[str, Any]
    config_path: Path

    @property
    def target_column(self) -> str:
        return str(self.raw["project"]["target_column"])

    @property
    def id_column(self) -> str:
        return str(self.raw["project"]["id_column"])

    @property
    def random_state(self) -> int:
        return int(self.raw["reproducibility"]["random_state"])

    @property
    def full_dataset_rows(self) -> int:
        return int(self.raw["reproducibility"]["full_dataset_rows"])

    @property
    def split_train(self) -> float:
        return float(self.raw["splits"]["train"])

    @property
    def split_test(self) -> float:
        return float(self.raw["splits"]["test"])

    @property
    def split_demo(self) -> float:
        return float(self.raw["splits"]["demo_holdout"])

    @property
    def business_threshold(self) -> float:
        """Threshold de negócio para classificação binária (0 ou 1)."""
        business_rules = self.raw.get("business_rules", {})
        if "business_threshold" in business_rules:
            return float(business_rules["business_threshold"])
        return float(self.raw["business"]["threshold"])

    @property
    def f_beta(self) -> float:
        return float(self.raw["business"]["f_beta"])

    @property
    def drop_cols(self) -> list[str]:
        return list(self.raw["features"]["drop_cols"])

    @property
    def categorical_features(self) -> list[str]:
        return list(self.raw["features"]["categorical_features"])

    @property
    def editable_features(self) -> list[str]:
        return list(self.raw["features"]["editable_features"])

    @property
    def readonly_features(self) -> list[str]:
        return list(self.raw["features"]["readonly_features"])

    @property
    def feature_set(self) -> str:
        return str(self.raw["features"]["set"])

    @property
    def model_params(self) -> dict[str, Any]:
        return dict(self.raw["model"])

    @property
    def api_base_url(self) -> str:
        env_url = os.getenv("API_BASE_URL", "").strip()
        if env_url:
            return env_url
        return str(self.raw.get("api", {}).get("base_url", "http://localhost:8000"))

    def _resolve_path_key(self, primary: str, legacy: str) -> str:
        paths = self.raw["paths"]
        if primary in paths:
            return str(paths[primary])
        return str(paths[legacy])

    def resolve_abt_path(self) -> str:
        """Retorna caminho local da ABT se existir; caso contrário, S3."""
        env_path = os.getenv("ABT_PATH", "").strip()
        if env_path:
            return env_path
        local_rel = self._resolve_path_key("abt_path", "abt")
        local_path = REPO_ROOT / local_rel
        if local_path.exists():
            return str(local_path)
        return self._resolve_path_key("abt_path_s3", "abt_s3")

    def resolve_demo_holdout_path(self) -> Path:
        env_path = os.getenv("DEMO_HOLDOUT_PATH", "").strip()
        if env_path:
            return Path(env_path)
        return REPO_ROOT / self._resolve_path_key("demo_holdout_path", "demo_holdout")

    def resolve_model_artifact_path(self, prefer_s3: bool = False) -> str:
        env_path = os.getenv("MODEL_PATH", "").strip()
        if env_path:
            return env_path
        if prefer_s3:
            return self._resolve_path_key("model_artifact_path_s3", "model_artifact_s3")
        local_rel = self._resolve_path_key("model_artifact_path", "model_artifact")
        local_path = REPO_ROOT / local_rel
        if local_path.parent.exists():
            return str(local_path)
        return self._resolve_path_key("model_artifact_path_s3", "model_artifact_s3")

    def resolve_metadata_path(self, prefer_s3: bool = False) -> str:
        env_path = os.getenv("MODEL_METADATA_PATH", "").strip()
        if env_path:
            return env_path
        local_rel = self._resolve_path_key("metadata_path", "metadata")
        local_path = REPO_ROOT / local_rel
        if not prefer_s3:
            return str(local_path)
        return self._resolve_path_key("metadata_path_s3", "metadata_s3")

    def feature_columns(self, available_columns: list[str]) -> list[str]:
        """Resolve colunas de features conforme trilho configurado."""
        drop = set(self.drop_cols)
        available = [col for col in available_columns if col not in drop]
        feature_set = self.feature_set.lower()

        if feature_set == "full":
            return available

        core = list(self.raw["features"]["core"])
        extended_extra = list(self.raw["features"]["extended_extra"])

        if feature_set == "core":
            requested = core
        elif feature_set == "extended":
            requested = core + extended_extra
        else:
            raise ValueError(f"Trilho de features desconhecado: {self.feature_set}")

        missing = [col for col in requested if col not in available_columns]
        if missing:
            raise ValueError(f"Colunas ausentes na ABT para trilho {feature_set}: {missing}")
        return requested


def load_model_config(config_path: str | Path | None = None) -> ModelConfig:
    """Carrega YAML de configuração do modelo."""
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    with path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    _validate_splits(raw)
    return ModelConfig(raw=raw, config_path=path)


@lru_cache(maxsize=1)
def get_model_config() -> ModelConfig:
    """Retorna configuração cacheada (padrão do repositório)."""
    return load_model_config()


def _validate_splits(raw: dict[str, Any]) -> None:
    splits = raw["splits"]
    total = float(splits["train"]) + float(splits["test"]) + float(splits["demo_holdout"])
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"Splits devem somar 1.0; recebido {total:.6f}")


def write_metadata(path: str | Path, metadata: dict[str, Any]) -> None:
    """Persiste metadados do treino em JSON."""
    target = Path(path)
    if str(path).startswith("s3://"):
        raise ValueError("Use export_metadata para caminhos S3")
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = deepcopy(metadata)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def export_metadata(path: str, metadata: dict[str, Any], fs: Any | None = None) -> None:
    """Grava metadados localmente ou no MinIO."""
    payload = json.dumps(metadata, ensure_ascii=False, indent=2).encode("utf-8")
    if str(path).startswith("s3://"):
        if fs is None:
            raise ValueError("Filesystem S3 obrigatório para metadados remotos")
        with fs.open(path, "wb") as handle:
            handle.write(payload)
        return
    write_metadata(path, metadata)


def _is_s3_path(path: str) -> bool:
    return str(path).startswith("s3://")


def load_model_metadata(
    config: ModelConfig | None = None,
    *,
    fs: Any | None = None,
) -> dict[str, Any]:
    """Carrega metadados do treino (local primeiro; S3 como fallback)."""
    cfg = config or get_model_config()
    candidates: list[str] = [cfg.resolve_metadata_path(prefer_s3=False)]
    s3_path = cfg.resolve_metadata_path(prefer_s3=True)
    if s3_path not in candidates:
        candidates.append(s3_path)

    errors: list[Exception] = []
    for path in candidates:
        try:
            if _is_s3_path(path):
                if fs is None:
                    import s3fs

                    fs = s3fs.S3FileSystem(
                        key=os.getenv("MINIO_ROOT_USER", "minioadmin"),
                        secret=os.getenv("MINIO_ROOT_PASSWORD", "minioadmin"),
                        client_kwargs={
                            "endpoint_url": os.getenv(
                                "MINIO_ENDPOINT_URL", "http://minio:9000"
                            )
                        },
                    )
                with fs.open(path, "rb") as handle:
                    return json.loads(handle.read().decode("utf-8"))
            target = Path(path)
            if target.is_file() and target.stat().st_size > 0:
                with target.open(encoding="utf-8") as handle:
                    return json.load(handle)
        except Exception as exc:  # noqa: BLE001 — tenta próximo candidato
            errors.append(exc)

    detail = f" Último erro: {errors[-1]}" if errors else ""
    raise FileNotFoundError(
        "Metadados do modelo indisponíveis em artifacts/model_metadata.json "
        f"(e fallback S3). Re-execute a DAG de treino.{detail}"
    )


def performance_from_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Extrai matriz de confusão e KPIs do split de teste a partir do metadata."""
    metrics = dict(metadata.get("metrics_test") or {})
    if not metrics:
        raise ValueError("metadata sem metrics_test")

    rows = metadata.get("splits", {}).get("rows", {})
    test_rows = int(rows.get("test") or 0)
    if test_rows <= 0:
        raise ValueError("metadata sem splits.rows.test")

    fn = int(round(float(metrics["fn"])))
    fp = int(round(float(metrics["fp"])))
    recall = float(metrics["recall_inadimplente"])
    threshold = float(metrics.get("threshold", metadata.get("business", {}).get("threshold", 0.0)))

    if "tn" in metrics and "tp" in metrics:
        tn = int(round(float(metrics["tn"])))
        tp = int(round(float(metrics["tp"])))
    else:
        # Compatível com metadados antigos que só gravavam fn/fp.
        if recall >= 1.0:
            tp = max(0, int(round(float(metrics.get("taxa_reprovacao", 0.0)) * test_rows)) - fp)
        elif recall <= 0.0:
            tp = 0
        else:
            tp = int(round(fn * recall / (1.0 - recall)))
        tn = test_rows - fp - fn - tp

    defaults_total = tp + fn
    approved = tn + fn
    base_default_rate = defaults_total / test_rows if test_rows else 0.0
    post_model_default_rate = fn / approved if approved else 0.0
    default_reduction = (
        1.0 - (post_model_default_rate / base_default_rate) if base_default_rate > 0 else 0.0
    )
    precision = float(metrics.get("precision_inadimplente", 0.0))
    if precision <= 0.0 and (tp + fp) > 0:
        precision = tp / (tp + fp)

    return {
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "tp": tp,
        "test_rows": test_rows,
        "defaults_total": defaults_total,
        "approved": approved,
        "recall": recall,
        "precision": precision,
        "threshold": threshold,
        "base_default_rate": base_default_rate,
        "post_model_default_rate": post_model_default_rate,
        "default_reduction": default_reduction,
        "pr_auc": float(metrics.get("pr_auc", 0.0)),
        "roc_auc": float(metrics.get("roc_auc", 0.0)),
        "f2": float(metrics.get("f2", 0.0)),
        "taxa_reprovacao": float(metrics.get("taxa_reprovacao", 0.0)),
        "f_beta": float(metadata.get("business", {}).get("f_beta", 2.0)),
    }
