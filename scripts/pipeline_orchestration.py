"""Orquestra a esteira de dados e treino (equivalente ao pipeline_orchestration do PDF).

Em produção local a orquestração oficial fica nas DAGs Airflow:
``01_bronze_ingest_kaggle`` → ``02_silver_clean_data`` → ``03_gold_abt_features``
→ ``04_model_train_lightgbm``.

Este script permite executar a mesma cadeia fora do Airflow, na ordem:
ingestão Kaggle (opcional) → data_sanitization → abt_transform → train.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone

from scripts.abt_transform import main as run_abt_transform
from scripts.data_sanitization import main as run_data_sanitization
from scripts.kaggle_to_minio import replace_kaggle_raw_files
from scripts.train import run_training


LOGGER = logging.getLogger(__name__)


def run_orchestration(*, skip_ingest: bool = False, run_id: str | None = None) -> dict[str, object]:
    """Executa a cadeia completa e devolve um resumo por etapa.

    Args:
        skip_ingest: Se True, não baixa/substitui CSVs no MinIO (assume raw pronto).
        run_id: Identificador do run; quando omitido, gera timestamp UTC.

    Returns:
        Dicionário com status e detalhes de cada etapa.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    effective_run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    summary: dict[str, object] = {"run_id": effective_run_id, "steps": {}}

    if not skip_ingest:
        LOGGER.info("Etapa 1/4: ingestão Kaggle → MinIO raw")
        ingest_result = replace_kaggle_raw_files()
        summary["steps"]["ingest"] = ingest_result
    else:
        LOGGER.info("Etapa 1/4: ingestão omitida (--skip-ingest)")
        summary["steps"]["ingest"] = {"skipped": True}

    LOGGER.info("Etapa 2/4: data_sanitization (raw → clean)")
    sanitize_code = run_data_sanitization([])
    if sanitize_code != 0:
        raise RuntimeError(f"data_sanitization falhou com código {sanitize_code}")
    summary["steps"]["data_sanitization"] = {"exit_code": sanitize_code}

    LOGGER.info("Etapa 3/4: abt_transform (clean → abt)")
    transform_code = run_abt_transform([])
    if transform_code != 0:
        raise RuntimeError(f"abt_transform falhou com código {transform_code}")
    summary["steps"]["abt_transform"] = {"exit_code": transform_code}

    LOGGER.info("Etapa 4/4: train (LightGBM)")
    model_path = run_training()
    summary["steps"]["train"] = {"model_path": model_path}

    LOGGER.info("Orquestração concluída: %s", summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    """Monta o parser CLI da orquestração."""
    parser = argparse.ArgumentParser(
        description=(
            "Orquestra ingestão, limpeza (data_sanitization), ABT (abt_transform) "
            "e treino (train) fora do Airflow."
        )
    )
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="Não executa o download Kaggle; usa o bucket raw já existente.",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Identificador opcional do run (default: timestamp UTC).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Ponto de entrada CLI da orquestração."""
    args = build_parser().parse_args(argv)
    try:
        run_orchestration(skip_ingest=args.skip_ingest, run_id=args.run_id)
    except Exception:
        LOGGER.exception("Falha na orquestração do pipeline")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
