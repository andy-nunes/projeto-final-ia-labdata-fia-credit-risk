"""Transformação clean → ABT de modelagem (abt_transform)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import re
import shutil
from tempfile import TemporaryDirectory

import pandas as pd

from scripts.gold_transformations import (
    aggregate_bureau,
    aggregate_bureau_balance,
    aggregate_credit_card,
    aggregate_installments,
    aggregate_pos_cash,
    aggregate_previous_application,
    build_abt_train,
    enrich_application,
)
from scripts.gold_validations import (
    GoldValidationError,
    ensure_required_columns,
    validate_abt_final,
    validate_application,
    validate_bureau,
    validate_bureau_balance,
    validate_credit_card,
    validate_installments,
    validate_pos_cash,
    validate_previous_application,
)
from scripts.silver_transformations import get_minio_client


LOGGER = logging.getLogger(__name__)
CLEAN_BUCKET = os.getenv("CLEAN_BUCKET", "clean")
ABT_BUCKET = os.getenv("ABT_BUCKET", "abt")
ABT_KEY = "abt_train.parquet"
DEFAULT_DATA_DIR = Path(os.getenv("DATA_DIR", "Dados"))

CLEAN_KEYS = {
    "application": "application_train_silver.parquet",
    "bureau": "bureau_silver.parquet",
    "bureau_balance": "bureau_balance_silver.parquet",
    "pos_cash": "POS_CASH_balance_silver.parquet",
    "credit_card": "credit_card_balance_silver.parquet",
    "previous_application": "previous_application_silver.parquet",
    "installments": "installments_payments_silver.parquet",
}

STAGE_FILES = {
    "application": "application_gold.parquet",
    "bureau": "bureau_gold.parquet",
    "bureau_balance": "bureau_balance_gold.parquet",
    "pos_cash": "pos_cash_gold.parquet",
    "credit_card": "credit_card_gold.parquet",
    "previous_application": "previous_application_gold.parquet",
    "installments": "installments_gold.parquet",
    "abt_final": ABT_KEY,
}


def _safe_run_id(run_id: str) -> str:
    """Normaliza o identificador da execução para um caminho seguro."""
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "_", run_id).strip("._")
    if not normalized:
        raise ValueError("run_id não produz um caminho Gold válido")
    return normalized


def stage_path(
    run_id: str,
    stage: str,
    data_dir: Path | None = None,
) -> Path:
    """Retorna o caminho determinístico de um artefato Gold intermediário."""
    if stage not in STAGE_FILES:
        raise ValueError(f"Etapa Gold desconhecida: {stage}")
    root = data_dir or DEFAULT_DATA_DIR
    return root / ".gold_staging" / _safe_run_id(run_id) / stage / STAGE_FILES[stage]


def _metadata(stage: str, run_id: str, path: Path, rows: int) -> dict[str, object]:
    """Cria metadados pequenos e serializáveis para Airflow XCom."""
    return {
        "stage": stage,
        "run_id": run_id,
        "staging_path": str(path.resolve()),
        "rows": rows,
    }


def _download_clean_frame(stage: str, client, destination: Path) -> pd.DataFrame:
    """Baixa e lê uma origem clean sem manter uma cópia local extra."""
    key = CLEAN_KEYS[stage]
    with TemporaryDirectory(prefix="clean-", dir=destination.parent) as temporary:
        source = Path(temporary) / key
        LOGGER.info(" -> Baixando %s/%s", CLEAN_BUCKET, key)
        client.download_file(CLEAN_BUCKET, key, str(source))
        return pd.read_parquet(source)


def _write_stage(
    stage: str,
    run_id: str,
    frame: pd.DataFrame,
    data_dir: Path | None,
) -> dict[str, object]:
    """Grava um DataFrame no staging e devolve somente seus metadados."""
    path = stage_path(run_id, stage, data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)
    LOGGER.info(" -> Staging %s: %s linhas", path, len(frame))
    return _metadata(stage, run_id, path, len(frame))


def _read_stage(metadata: dict[str, object]) -> pd.DataFrame:
    """Lê um artefato indicado por metadados e falha se estiver ausente."""
    path = Path(str(metadata["staging_path"]))
    if not path.is_file():
        raise FileNotFoundError(f"Staging Gold ausente: {path}")
    return pd.read_parquet(path)


def _train_ids(run_id: str, data_dir: Path | None) -> set[int]:
    """Carrega o universo de clientes a partir da application enriquecida."""
    application = pd.read_parquet(stage_path(run_id, "application", data_dir))
    return set(application["SK_ID_CURR"].tolist())


def process_application(
    run_id: str,
    client=None,
    data_dir: Path | None = None,
) -> dict[str, object]:
    """Baixa application, confere schema, cria features e grava staging."""
    LOGGER.info("[GOLD] Processando application_train_silver")
    target = stage_path(run_id, "application", data_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    frame = _download_clean_frame("application", client or get_minio_client(), target)
    ensure_required_columns("application", frame)
    return _write_stage("application", run_id, enrich_application(frame), data_dir)


def validate_application_stage(metadata: dict[str, object]) -> dict[str, object]:
    """Valida as features application gravadas no staging."""
    validate_application(_read_stage(metadata))
    return {**metadata, "qa_status": "passed"}


def _process_aggregate(
    stage: str,
    run_id: str,
    transform: Callable[[pd.DataFrame, set[int]], pd.DataFrame],
    client=None,
    data_dir: Path | None = None,
) -> dict[str, object]:
    """Executa o padrão comum de download, schema, agregado e staging."""
    LOGGER.info("[GOLD] Processando %s", stage)
    target = stage_path(run_id, stage, data_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    frame = _download_clean_frame(stage, client or get_minio_client(), target)
    ensure_required_columns(stage, frame)
    aggregated = transform(frame, _train_ids(run_id, data_dir))
    return _write_stage(stage, run_id, aggregated, data_dir)


def process_bureau(run_id: str, client=None, data_dir: Path | None = None) -> dict[str, object]:
    """Produz o agregado bureau no staging Gold."""
    return _process_aggregate("bureau", run_id, aggregate_bureau, client, data_dir)


def process_bureau_balance(run_id: str, client=None, data_dir: Path | None = None) -> dict[str, object]:
    """Produz bureau balance usando a ponte obtida da Silver bureau."""
    active_client = client or get_minio_client()
    target = stage_path(run_id, "bureau_balance", data_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    balance = _download_clean_frame("bureau_balance", active_client, target)
    ensure_required_columns("bureau_balance", balance)
    bureau = _download_clean_frame("bureau", active_client, target)
    ensure_required_columns("bureau", bureau)
    aggregated = aggregate_bureau_balance(
        balance,
        bureau[["SK_ID_BUREAU", "SK_ID_CURR"]],
        _train_ids(run_id, data_dir),
    )
    return _write_stage("bureau_balance", run_id, aggregated, data_dir)


def process_pos_cash(run_id: str, client=None, data_dir: Path | None = None) -> dict[str, object]:
    """Produz o agregado POS/CASH no staging Gold."""
    return _process_aggregate("pos_cash", run_id, aggregate_pos_cash, client, data_dir)


def process_credit_card(run_id: str, client=None, data_dir: Path | None = None) -> dict[str, object]:
    """Produz o agregado de cartão no staging Gold."""
    return _process_aggregate("credit_card", run_id, aggregate_credit_card, client, data_dir)


def process_previous_application(run_id: str, client=None, data_dir: Path | None = None) -> dict[str, object]:
    """Produz o agregado de propostas anteriores no staging Gold."""
    return _process_aggregate(
        "previous_application", run_id, aggregate_previous_application, client, data_dir
    )


def process_installments(run_id: str, client=None, data_dir: Path | None = None) -> dict[str, object]:
    """Produz o agregado de parcelas no staging Gold."""
    return _process_aggregate("installments", run_id, aggregate_installments, client, data_dir)


def _validate_aggregate_stage(
    metadata: dict[str, object],
    validator: Callable[[pd.DataFrame, set[int]], object],
    data_dir: Path | None,
) -> dict[str, object]:
    """Valida um agregado local contra o universo de treino."""
    validator(
        _read_stage(metadata),
        _train_ids(str(metadata["run_id"]), data_dir),
    )
    return {**metadata, "qa_status": "passed"}


def validate_bureau_stage(metadata: dict[str, object], data_dir: Path | None = None) -> dict[str, object]:
    """Valida o staging bureau."""
    return _validate_aggregate_stage(metadata, validate_bureau, data_dir)


def validate_bureau_balance_stage(metadata: dict[str, object], data_dir: Path | None = None) -> dict[str, object]:
    """Valida o staging bureau balance."""
    return _validate_aggregate_stage(metadata, validate_bureau_balance, data_dir)


def validate_pos_cash_stage(metadata: dict[str, object], data_dir: Path | None = None) -> dict[str, object]:
    """Valida o staging POS/CASH."""
    return _validate_aggregate_stage(metadata, validate_pos_cash, data_dir)


def validate_credit_card_stage(metadata: dict[str, object], data_dir: Path | None = None) -> dict[str, object]:
    """Valida o staging de cartão."""
    return _validate_aggregate_stage(metadata, validate_credit_card, data_dir)


def validate_previous_application_stage(metadata: dict[str, object], data_dir: Path | None = None) -> dict[str, object]:
    """Valida o staging de propostas anteriores."""
    return _validate_aggregate_stage(metadata, validate_previous_application, data_dir)


def validate_installments_stage(metadata: dict[str, object], data_dir: Path | None = None) -> dict[str, object]:
    """Valida o staging de parcelas."""
    return _validate_aggregate_stage(metadata, validate_installments, data_dir)


def build_abt_stage(run_id: str, data_dir: Path | None = None) -> dict[str, object]:
    """Monta a ABT a partir de todos os agregados aprovados no staging."""
    application = pd.read_parquet(stage_path(run_id, "application", data_dir))
    aggregates = {
        stage: pd.read_parquet(stage_path(run_id, stage, data_dir))
        for stage in (
            "bureau",
            "bureau_balance",
            "pos_cash",
            "credit_card",
            "previous_application",
            "installments",
        )
    }
    return _write_stage(
        "abt_final", run_id, build_abt_train(application, aggregates), data_dir
    )


def validate_abt_stage(
    metadata: dict[str, object],
    data_dir: Path | None = None,
) -> dict[str, object]:
    """Executa o QA final contra a application original enriquecida."""
    run_id = str(metadata["run_id"])
    application = pd.read_parquet(stage_path(run_id, "application", data_dir))
    validate_abt_final(_read_stage(metadata), application)
    return {**metadata, "qa_status": "passed"}


def write_abt(metadata: dict[str, object], client=None) -> dict[str, object]:
    """Publica a ABT aprovada e remove todo o staging da execução."""
    if metadata.get("qa_status") != "passed":
        raise ValueError("ABT não possui aprovação de QA")
    staged = Path(str(metadata["staging_path"]))
    if not staged.is_file():
        raise FileNotFoundError(f"Staging ABT ausente: {staged}")
    active_client = client or get_minio_client()
    LOGGER.info("[LOAD] Publicando %s/%s", ABT_BUCKET, ABT_KEY)
    active_client.upload_file(str(staged), ABT_BUCKET, ABT_KEY)
    run_root = staged.parents[1]
    shutil.rmtree(run_root)
    return {
        **metadata,
        "status": "uploaded",
        "destination": f"{ABT_BUCKET}/{ABT_KEY}",
    }


def run_gold_pipeline(
    run_id: str,
    client=None,
    data_dir: Path | None = None,
) -> dict[str, object]:
    """Executa todas as etapas Gold em sequência e publica a ABT final."""
    application = validate_application_stage(
        process_application(run_id, client, data_dir)
    )
    validate_bureau_stage(process_bureau(run_id, client, data_dir), data_dir)
    validate_bureau_balance_stage(
        process_bureau_balance(run_id, client, data_dir), data_dir
    )
    validate_pos_cash_stage(process_pos_cash(run_id, client, data_dir), data_dir)
    validate_credit_card_stage(
        process_credit_card(run_id, client, data_dir), data_dir
    )
    validate_previous_application_stage(
        process_previous_application(run_id, client, data_dir), data_dir
    )
    validate_installments_stage(
        process_installments(run_id, client, data_dir), data_dir
    )
    del application
    abt = validate_abt_stage(build_abt_stage(run_id, data_dir), data_dir)
    return write_abt(abt, client)


def main(argv: list[str] | None = None) -> int:
    """Executa a Gold completa e converte falhas em código para o shell."""
    if argv:
        print("[FAIL] O pipeline Gold não aceita seleção parcial de etapas")
        return 2
    run_id = datetime.now(timezone.utc).strftime("cli__%Y%m%dT%H%M%S.%fZ")
    try:
        result = run_gold_pipeline(run_id)
    except Exception as error:  # noqa: BLE001 - fronteira da CLI
        stage = error.stage if isinstance(error, GoldValidationError) else "pipeline"
        print(f"[FAIL] Gold interrompida na etapa {stage}: {error}")
        return 1
    print(f"[OK] ABT publicada em {result['destination']}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main())
