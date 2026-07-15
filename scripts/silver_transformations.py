"""Transformações da camada Silver para dados Home Credit no MinIO."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable

import boto3
import numpy as np
import pandas as pd
from botocore.client import Config
import pyarrow as pa
import pyarrow.parquet as pq

from scripts.integrations_config import get_integrations_config


DAYS_EMPLOYED_ANOMALY = 365243
MAX_EMPLOYMENT_DAYS = 18250
BUREAU_STATUS_VALID = frozenset({"C", "X", "0", "1", "2", "3", "4", "5"})
INTEGRATIONS = get_integrations_config()
RAW_BUCKET = INTEGRATIONS.minio.raw_bucket
CLEAN_BUCKET = os.getenv("CLEAN_BUCKET", "clean")
MINIO_ENDPOINT_URL = INTEGRATIONS.minio.endpoint_url
MINIO_ROOT_USER = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_ROOT_PASSWORD = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")

DataFrameTransformer = Callable[[pd.DataFrame], pd.DataFrame]


@dataclass(frozen=True)
class SilverTable:
    """Descreve uma entrada raw e sua saída Parquet na camada clean."""

    table_id: str
    raw_key: str
    clean_key: str
    transformer: DataFrameTransformer
    expected_rows: int | None = None


def _standardize_strings(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica remoção de espaços e caixa alta em todas as colunas textuais."""
    for column in df.select_dtypes(include=["object", "string"]).columns:
        df[column] = df[column].str.strip().str.upper().replace({"": np.nan})
    return df


def _cap_numeric_percentile(
    df: pd.DataFrame,
    column: str,
    percentile: float = 99.9,
) -> None:
    """Limita uma coluna numérica ao percentil informado quando ele existe."""
    if column not in df.columns:
        return
    numeric = pd.to_numeric(df[column], errors="coerce")
    cap = numeric.quantile(percentile / 100.0)
    if pd.notna(cap):
        df[column] = numeric.clip(upper=cap)


def _zero_negative_numeric_columns(df: pd.DataFrame, columns: list[str]) -> None:
    """Substitui por zero valores negativos de colunas numéricas existentes."""
    for column in columns:
        if column in df.columns and pd.api.types.is_numeric_dtype(df[column]):
            df[column] = df[column].clip(lower=0)


def transform_application(df: pd.DataFrame) -> pd.DataFrame:
    """Higieniza application train ou test com regras idênticas."""
    df = _standardize_strings(df)

    if "DAYS_EMPLOYED" in df.columns:
        employed = np.where(
            df["DAYS_EMPLOYED"] == DAYS_EMPLOYED_ANOMALY,
            0,
            np.where(df["DAYS_EMPLOYED"].notna(), 1, np.nan),
        )
        df["FLAG_EMPLOYED"] = pd.Series(employed, index=df.index, dtype="Int64")
        anomaly = (
            (df["DAYS_EMPLOYED"] == DAYS_EMPLOYED_ANOMALY)
            | (df["DAYS_EMPLOYED"] > 0)
            | (df["DAYS_EMPLOYED"] < -MAX_EMPLOYMENT_DAYS)
        )
        df["DAYS_EMPLOYED"] = df["DAYS_EMPLOYED"].mask(anomaly)

    if "DAYS_BIRTH" in df.columns:
        ages = np.floor(df["DAYS_BIRTH"].abs() / 365)
        df["AGE_YEARS"] = ages.astype("Int64")

    if "CODE_GENDER" in df.columns:
        df["CODE_GENDER"] = df["CODE_GENDER"].mask(df["CODE_GENDER"] == "XNA")

    if {"FLAG_OWN_CAR", "OWN_CAR_AGE"}.issubset(df.columns):
        df["OWN_CAR_AGE"] = df["OWN_CAR_AGE"].mask(df["FLAG_OWN_CAR"] == "N")

    if "AMT_INCOME_TOTAL" in df.columns:
        df["AMT_INCOME_TOTAL"] = df["AMT_INCOME_TOTAL"].mask(
            df["AMT_INCOME_TOTAL"] <= 0
        )

    return df


def transform_bureau(df: pd.DataFrame) -> pd.DataFrame:
    """Higieniza bureau com regras temporais, financeiras e de cauda."""
    df = _standardize_strings(df)

    for column in ("DAYS_CREDIT", "DAYS_ENDDATE_FACT"):
        if column in df.columns:
            df[column] = df[column].mask(df[column] > 0)

    if "DAYS_CREDIT_ENDDATE" in df.columns:
        df["DAYS_CREDIT_ENDDATE"] = df["DAYS_CREDIT_ENDDATE"].mask(
            df["DAYS_CREDIT_ENDDATE"] > MAX_EMPLOYMENT_DAYS
        )

    _cap_numeric_percentile(df, "AMT_CREDIT_SUM")
    for column in (
        "CNT_CREDIT_DAY_OVERDUE",
        "CNT_CREDIT_DAY_DPD",
        "AMT_CREDIT_DAY_OVERDUE",
        "AMT_CREDIT_DAY_DPD",
    ):
        _cap_numeric_percentile(df, column)
    _zero_negative_numeric_columns(df, ["AMT_CREDIT_SUM"])
    return df


def transform_bureau_balance(df: pd.DataFrame) -> pd.DataFrame:
    """Deduplica bureau balance e normaliza mês e domínio de status."""
    if {"SK_ID_BUREAU", "MONTHS_BALANCE"}.issubset(df.columns):
        df = df.drop_duplicates(
            subset=["SK_ID_BUREAU", "MONTHS_BALANCE"], keep="first"
        ).copy()
    df = _standardize_strings(df)
    if "MONTHS_BALANCE" in df.columns:
        df["MONTHS_BALANCE"] = df["MONTHS_BALANCE"].clip(upper=0)
    if "STATUS" in df.columns:
        df["STATUS"] = df["STATUS"].where(df["STATUS"].isin(BUREAU_STATUS_VALID))
    return df


def transform_pos_cash(df: pd.DataFrame) -> pd.DataFrame:
    """Higieniza o histórico mensal POS/CASH."""
    df = df.drop_duplicates(keep="first").copy()
    df = _standardize_strings(df)
    if "MONTHS_BALANCE" in df.columns:
        df["MONTHS_BALANCE"] = df["MONTHS_BALANCE"].clip(upper=0)
    _zero_negative_numeric_columns(df, ["SK_DPD", "SK_DPD_DEF"])
    return df


def transform_credit_card(df: pd.DataFrame) -> pd.DataFrame:
    """Higieniza o extrato mensal de cartão de crédito."""
    df = df.drop_duplicates(keep="first").copy()
    df = _standardize_strings(df)
    if "MONTHS_BALANCE" in df.columns:
        df["MONTHS_BALANCE"] = df["MONTHS_BALANCE"].clip(upper=0)
    _zero_negative_numeric_columns(df, ["SK_DPD"])
    financial = [
        column
        for column in df.columns
        if column.startswith("AMT_") or column.startswith("CNT_")
    ]
    _zero_negative_numeric_columns(df, financial)
    drawing_columns = (
        "AMT_DRAWINGS_ATM_CURRENT",
        "AMT_DRAWINGS_CURRENT",
        "AMT_DRAWINGS_POS_CURRENT",
        "AMT_DRAWINGS_OTHER_CURRENT",
        "CNT_DRAWINGS_ATM_CURRENT",
        "CNT_DRAWINGS_CURRENT",
        "CNT_DRAWINGS_POS_CURRENT",
        "CNT_DRAWINGS_OTHER_CURRENT",
    )
    for column in drawing_columns:
        if column in df.columns:
            df[column] = df[column].fillna(0)
    return df


def transform_previous_application(df: pd.DataFrame) -> pd.DataFrame:
    """Higieniza solicitações anteriores da Home Credit."""
    if "SK_ID_PREV" in df.columns:
        df = df.drop_duplicates(subset=["SK_ID_PREV"], keep="first").copy()
    df = _standardize_strings(df)
    if "DAYS_DECISION" in df.columns:
        df["DAYS_DECISION"] = df["DAYS_DECISION"].mask(df["DAYS_DECISION"] > 0)
    for column in [name for name in df.columns if name.startswith("DAYS_")]:
        anomaly = (df[column] == DAYS_EMPLOYED_ANOMALY) | (
            df[column] > MAX_EMPLOYMENT_DAYS
        )
        df[column] = df[column].mask(anomaly)
    amounts = [name for name in df.columns if name.startswith("AMT_")]
    _zero_negative_numeric_columns(df, amounts)
    return df


def transform_installments_payments(df: pd.DataFrame) -> pd.DataFrame:
    """Higieniza parcelas sem eliminar pagamentos fracionados legítimos."""
    df = df.drop_duplicates(keep="first").copy()
    for column in [name for name in df.columns if name.startswith("DAYS_")]:
        df[column] = df[column].mask(df[column] > 0)
    amounts = [name for name in df.columns if name.startswith("AMT_")]
    _zero_negative_numeric_columns(df, amounts)
    if "AMT_PAYMENT" in df.columns:
        df["AMT_PAYMENT"] = df["AMT_PAYMENT"].fillna(0.0)
    if {"DAYS_ENTRY_PAYMENT", "DAYS_INSTALMENT"}.issubset(df.columns):
        df["DIAS_DE_ATRASO"] = (
            df["DAYS_ENTRY_PAYMENT"] - df["DAYS_INSTALMENT"]
        )
    return df


SILVER_TABLES: dict[str, SilverTable] = {
    "application_train": SilverTable(
        "application_train",
        "application_train.csv",
        "application_train_silver.parquet",
        transform_application,
        307_511,
    ),
    "application_test": SilverTable(
        "application_test",
        "application_test.csv",
        "application_test_silver.parquet",
        transform_application,
        48_744,
    ),
    "bureau": SilverTable(
        "bureau", "bureau.csv", "bureau_silver.parquet", transform_bureau
    ),
    "bureau_balance": SilverTable(
        "bureau_balance",
        "bureau_balance.csv",
        "bureau_balance_silver.parquet",
        transform_bureau_balance,
    ),
    "POS_CASH_balance": SilverTable(
        "POS_CASH_balance",
        "POS_CASH_balance.csv",
        "POS_CASH_balance_silver.parquet",
        transform_pos_cash,
    ),
    "credit_card_balance": SilverTable(
        "credit_card_balance",
        "credit_card_balance.csv",
        "credit_card_balance_silver.parquet",
        transform_credit_card,
    ),
    "previous_application": SilverTable(
        "previous_application",
        "previous_application.csv",
        "previous_application_silver.parquet",
        transform_previous_application,
    ),
    "installments_payments": SilverTable(
        "installments_payments",
        "installments_payments.csv",
        "installments_payments_silver.parquet",
        transform_installments_payments,
    ),
}


def transform_dataframe(table_id: str, source: pd.DataFrame) -> pd.DataFrame:
    """Aplica a transformação cadastrada sem modificar o DataFrame de entrada."""
    try:
        table = SILVER_TABLES[table_id]
    except KeyError as error:
        raise ValueError(f"Tabela Silver desconhecida: {table_id}") from error
    return table.transformer(source.copy(deep=True))


def _bureau_balance_key_bounds(
    raw_path: Path,
    chunk_size: int,
) -> tuple[int, int, int, int]:
    """Obtém limites compactos da chave mensal sem carregar o CSV inteiro."""
    minimum_id: int | None = None
    maximum_id: int | None = None
    minimum_month: int | None = None
    maximum_month: int | None = None
    for keys in pd.read_csv(
        raw_path,
        usecols=["SK_ID_BUREAU", "MONTHS_BALANCE"],
        chunksize=chunk_size,
    ):
        if keys[["SK_ID_BUREAU", "MONTHS_BALANCE"]].isna().any().any():
            raise ValueError("bureau_balance possui chave mensal nula")
        chunk_min_id = int(keys["SK_ID_BUREAU"].min())
        chunk_max_id = int(keys["SK_ID_BUREAU"].max())
        chunk_min_month = int(keys["MONTHS_BALANCE"].min())
        chunk_max_month = int(keys["MONTHS_BALANCE"].max())
        minimum_id = chunk_min_id if minimum_id is None else min(minimum_id, chunk_min_id)
        maximum_id = chunk_max_id if maximum_id is None else max(maximum_id, chunk_max_id)
        minimum_month = (
            chunk_min_month
            if minimum_month is None
            else min(minimum_month, chunk_min_month)
        )
        maximum_month = (
            chunk_max_month
            if maximum_month is None
            else max(maximum_month, chunk_max_month)
        )
    if None in (minimum_id, maximum_id, minimum_month, maximum_month):
        raise ValueError("bureau_balance está vazia")
    return minimum_id, maximum_id, minimum_month, maximum_month


def transform_bureau_balance_file(
    raw_path: Path,
    clean_path: Path,
    chunk_size: int = 500_000,
) -> int:
    """Transforma bureau balance em chunks com deduplicação global compacta."""
    minimum_id, maximum_id, minimum_month, maximum_month = (
        _bureau_balance_key_bounds(raw_path, chunk_size)
    )
    month_span = maximum_month - minimum_month + 1
    possible_keys = (maximum_id - minimum_id + 1) * month_span
    seen = np.zeros((possible_keys + 7) // 8, dtype=np.uint8)
    rows_written = 0
    writer: pq.ParquetWriter | None = None
    schema: pa.Schema | None = None

    try:
        for chunk in pd.read_csv(raw_path, chunksize=chunk_size):
            chunk = chunk.drop_duplicates(
                subset=["SK_ID_BUREAU", "MONTHS_BALANCE"], keep="first"
            ).copy()
            codes = (
                (chunk["SK_ID_BUREAU"].to_numpy(dtype=np.int64) - minimum_id)
                * month_span
                + (chunk["MONTHS_BALANCE"].to_numpy(dtype=np.int64) - minimum_month)
            )
            byte_indexes = np.right_shift(codes, 3)
            masks = np.left_shift(
                np.uint8(1), np.bitwise_and(codes, 7).astype(np.uint8)
            )
            duplicate = np.bitwise_and(seen[byte_indexes], masks) != 0
            np.bitwise_or.at(seen, byte_indexes, masks)
            unique_chunk = chunk.loc[~duplicate].copy()
            if unique_chunk.empty:
                continue

            transformed = transform_bureau_balance(unique_chunk).reset_index(drop=True)
            arrow_table = pa.Table.from_pandas(transformed, preserve_index=False)
            if writer is None:
                schema = arrow_table.schema
                writer = pq.ParquetWriter(clean_path, schema, compression="snappy")
            elif arrow_table.schema != schema:
                arrow_table = arrow_table.cast(schema, safe=False)
            writer.write_table(arrow_table)
            rows_written += len(transformed)
    finally:
        if writer is not None:
            writer.close()

    if writer is None:
        raise ValueError("bureau_balance não produziu linhas após a deduplicação")
    return rows_written


def get_minio_client():
    """Cria um cliente S3 configurado para o MinIO do projeto."""
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT_URL,
        aws_access_key_id=MINIO_ROOT_USER,
        aws_secret_access_key=MINIO_ROOT_PASSWORD,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def transform_table(table_id: str, client=None) -> dict[str, object]:
    """Baixa uma tabela raw, transforma e substitui seu Parquet no clean."""
    try:
        table = SILVER_TABLES[table_id]
    except KeyError as error:
        raise ValueError(f"Tabela Silver desconhecida: {table_id}") from error

    minio = client or get_minio_client()
    with TemporaryDirectory(prefix=f"silver-{table_id}-") as temporary:
        raw_path = Path(temporary) / table.raw_key
        clean_path = Path(temporary) / table.clean_key
        minio.download_file(RAW_BUCKET, table.raw_key, str(raw_path))
        if table_id == "bureau_balance":
            rows = transform_bureau_balance_file(raw_path, clean_path)
        else:
            source = pd.read_csv(raw_path)
            transformed = transform_dataframe(table_id, source)
            transformed.to_parquet(clean_path, index=False)
            rows = len(transformed)
            del source, transformed
        minio.upload_file(str(clean_path), CLEAN_BUCKET, table.clean_key)

    return {
        "table_id": table_id,
        "source": f"{RAW_BUCKET}/{table.raw_key}",
        "destination": f"{CLEAN_BUCKET}/{table.clean_key}",
        "rows": rows,
    }


def build_parser() -> argparse.ArgumentParser:
    """Cria o parser da execução direta das transformações Silver."""
    parser = argparse.ArgumentParser(
        description="Transforma tabelas do bucket raw em Parquets no bucket clean."
    )
    parser.add_argument(
        "tables",
        nargs="*",
        choices=tuple(SILVER_TABLES),
        metavar="TABLE",
        help="Tabelas a transformar; sem argumentos, processa todas.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Delega a CLI legada ao pipeline completo com validação obrigatória."""
    from scripts.data_sanitization import main as pipeline_main

    return pipeline_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
