"""Limpeza e padronização dos dados (data_sanitization): raw → clean."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import re
import shutil
from tempfile import TemporaryDirectory

import pandas as pd

from scripts.silver_transformations import (
    CLEAN_BUCKET,
    RAW_BUCKET,
    SILVER_TABLES,
    get_minio_client,
    transform_bureau_balance_file,
    transform_dataframe,
)
from scripts.silver_validations import (
    SilverValidationError,
    ValidationLevel,
    validate_or_raise,
)


LOGGER = logging.getLogger(__name__)
DEFAULT_DATA_DIR = Path(os.getenv("DATA_DIR", "Dados"))

TRANSFORMATION_DESCRIPTIONS = {
    "application_train": "padronização textual, emprego, idade, gênero, carro e renda",
    "application_test": "padronização textual, emprego, idade, gênero, carro e renda",
    "bureau": "padronização textual, datas impossíveis, cap P99.9 e negativos",
    "bureau_balance": "deduplicação global em chunks, mês e domínio STATUS",
    "POS_CASH_balance": "deduplicação, textos, mês e dias de atraso",
    "credit_card_balance": "deduplicação, mês, financeiros e saques nulos",
    "previous_application": "deduplicação, textos, datas e montantes",
    "installments_payments": "deduplicação conservadora, datas, montantes e atraso",
}


def _safe_run_id(run_id: str) -> str:
    """Normaliza um run_id para uso seguro como nome de diretório."""
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "_", run_id).strip("._")
    if not normalized:
        raise ValueError("run_id não produz um caminho de staging válido")
    return normalized


def staging_path(
    run_id: str,
    table_id: str,
    data_dir: Path | None = None,
) -> Path:
    """Retorna o Parquet intermediário isolado por execução e tabela."""
    if table_id not in SILVER_TABLES:
        raise ValueError(f"Tabela Silver desconhecida: {table_id}")
    root = data_dir or DEFAULT_DATA_DIR
    table = SILVER_TABLES[table_id]
    return root / ".silver_staging" / _safe_run_id(run_id) / table_id / table.clean_key


def collect_and_process(
    table_id: str,
    run_id: str,
    client=None,
    data_dir: Path | None = None,
) -> dict[str, object]:
    """Baixa uma entrada raw e grava somente o Parquet de staging."""
    if table_id not in SILVER_TABLES:
        raise ValueError(f"Tabela Silver desconhecida: {table_id}")
    table = SILVER_TABLES[table_id]
    minio = client or get_minio_client()
    output_path = staging_path(run_id, table_id, data_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    LOGGER.info("[ETL] Início da coleta e processamento de %s", table_id)
    LOGGER.info(" -> Origem: %s/%s", RAW_BUCKET, table.raw_key)
    LOGGER.info(" -> Regras: %s", TRANSFORMATION_DESCRIPTIONS[table_id])

    try:
        with TemporaryDirectory(prefix="raw-", dir=output_path.parent) as temporary:
            raw_path = Path(temporary) / table.raw_key
            LOGGER.info(" -> Baixando objeto raw")
            minio.download_file(RAW_BUCKET, table.raw_key, str(raw_path))
            LOGGER.info(" -> Download concluído: %s bytes", raw_path.stat().st_size)
            if table_id == "bureau_balance":
                rows = transform_bureau_balance_file(raw_path, output_path)
            else:
                source = pd.read_csv(raw_path)
                LOGGER.info(
                    " -> Carregado: %s linhas x %s colunas", len(source), source.shape[1]
                )
                transformed = transform_dataframe(table_id, source)
                transformed.to_parquet(output_path, index=False)
                rows = len(transformed)
                del source, transformed
    except Exception as error:
        raise RuntimeError(
            f"Falha na coleta/processamento de {table_id} a partir de "
            f"{RAW_BUCKET}/{table.raw_key}: {error}"
        ) from error

    LOGGER.info(
        " -> Staging gerado: %s (%s linhas, %s bytes)",
        output_path,
        rows,
        output_path.stat().st_size,
    )
    LOGGER.info("[ETL] Fim da coleta e processamento de %s", table_id)
    return {
        "table_id": table_id,
        "run_id": run_id,
        "raw_key": table.raw_key,
        "clean_key": table.clean_key,
        "staging_path": str(output_path.resolve()),
        "rows": rows,
    }


def validate_staged(metadata: dict[str, object]) -> dict[str, object]:
    """Valida o Parquet de staging e devolve metadados pequenos para XCom."""
    table_id = str(metadata["table_id"])
    staged = Path(str(metadata["staging_path"]))
    if not staged.is_file():
        raise FileNotFoundError(f"Staging ausente para {table_id}: {staged}")
    try:
        frame = pd.read_parquet(staged)
        results = validate_or_raise(table_id, frame, staged.name, LOGGER)
    except Exception as error:
        if isinstance(error, FileNotFoundError):
            raise
        if isinstance(error, SilverValidationError):
            raise
        raise RuntimeError(f"Falha ao validar staging de {table_id} em {staged}: {error}") from error

    validated = dict(metadata)
    validated.update(
        {
            "qa_status": "passed",
            "qa_passes": sum(
                result.level is ValidationLevel.PASS for result in results
            ),
            "qa_warnings": sum(
                result.level is ValidationLevel.WARNING for result in results
            ),
        }
    )
    return validated


def write_clean(
    metadata: dict[str, object],
    client=None,
) -> dict[str, object]:
    """Publica um staging validado no clean e remove apenas sua pasta."""
    table_id = str(metadata["table_id"])
    if metadata.get("qa_status") != "passed":
        raise ValueError(f"Tabela {table_id} não possui aprovação de QA")
    staged = Path(str(metadata["staging_path"]))
    clean_key = str(metadata["clean_key"])
    if not staged.is_file():
        raise FileNotFoundError(f"Staging ausente para upload de {table_id}: {staged}")
    minio = client or get_minio_client()

    LOGGER.info("[LOAD] Início da escrita de %s", table_id)
    LOGGER.info(" -> Origem staging: %s", staged)
    LOGGER.info(" -> Destino: %s/%s", CLEAN_BUCKET, clean_key)
    try:
        minio.upload_file(str(staged), CLEAN_BUCKET, clean_key)
    except Exception as error:
        raise RuntimeError(
            f"Falha ao publicar {table_id} em {CLEAN_BUCKET}/{clean_key}: {error}"
        ) from error
    shutil.rmtree(staged.parent)
    LOGGER.info(" -> Upload concluído e staging removido: %s", staged.parent)
    LOGGER.info("[LOAD] Fim da escrita de %s", table_id)

    result = dict(metadata)
    result["status"] = "uploaded"
    result["destination"] = f"{CLEAN_BUCKET}/{clean_key}"
    return result


def run_table_pipeline(
    table_id: str,
    run_id: str,
    client=None,
    data_dir: Path | None = None,
) -> dict[str, object]:
    """Executa sequencialmente as três etapas para uma tabela."""
    collected = collect_and_process(table_id, run_id, client, data_dir)
    validated = validate_staged(collected)
    return write_clean(validated, client)


def build_parser() -> argparse.ArgumentParser:
    """Cria o parser da execução direta do pipeline completo."""
    parser = argparse.ArgumentParser(
        description="Processa, valida e publica tabelas Silver no bucket clean."
    )
    parser.add_argument(
        "tables",
        nargs="*",
        choices=tuple(SILVER_TABLES),
        metavar="TABLE",
        help="Tabelas a processar; sem argumentos, processa todas.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Executa a CLI completa e lista falhas sem interromper outras tabelas."""
    arguments = build_parser().parse_args(argv)
    selected = arguments.tables or list(SILVER_TABLES)
    run_id = datetime.now(timezone.utc).strftime("cli__%Y%m%dT%H%M%S.%fZ")
    failures: list[tuple[str, str]] = []
    for table_id in selected:
        try:
            run_table_pipeline(table_id, run_id)
            print(f"[OK] {table_id} publicado no clean")
        except Exception as error:  # noqa: BLE001 - fronteira da execução CLI
            failures.append((table_id, str(error)))
            print(f"[FAIL] {table_id}: {error}")
    return 1 if failures else 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main())
