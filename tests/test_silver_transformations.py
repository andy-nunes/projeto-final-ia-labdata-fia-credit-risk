"""Testes pytest das transformações da camada Silver."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.silver_transformations import (
    SILVER_TABLES,
    main,
    transform_bureau_balance_file,
    transform_dataframe,
    transform_table,
)


class FakeMinioClient:
    """Simula downloads e uploads S3 usando arquivos temporários reais."""

    def __init__(self, source: pd.DataFrame) -> None:
        """Armazena o DataFrame entregue como CSV raw."""
        self.source = source
        self.downloads: list[tuple[str, str]] = []
        self.uploads: list[tuple[str, str]] = []
        self.uploaded_frame: pd.DataFrame | None = None

    def download_file(self, bucket: str, key: str, filename: str) -> None:
        """Materializa o CSV no caminho solicitado."""
        self.downloads.append((bucket, key))
        self.source.to_csv(filename, index=False)

    def upload_file(self, filename: str, bucket: str, key: str) -> None:
        """Lê o Parquet antes da remoção do diretório temporário."""
        self.uploads.append((bucket, key))
        self.uploaded_frame = pd.read_parquet(filename)


def test_catalog_contains_the_eight_notebook_tables() -> None:
    """Mantém somente as oito tabelas tratadas no notebook."""
    assert set(SILVER_TABLES) == {
        "application_train",
        "application_test",
        "bureau",
        "bureau_balance",
        "POS_CASH_balance",
        "credit_card_balance",
        "previous_application",
        "installments_payments",
    }


def test_application_applies_all_business_rules() -> None:
    """Higieniza application e cria features derivadas."""
    source = pd.DataFrame(
        {
            "DAYS_EMPLOYED": [365243, -3650, 2, -20000, np.nan],
            "DAYS_BIRTH": [-7300, -10950, -14600, -18250, -21900],
            "CODE_GENDER": [" xna ", " f ", "M", "F", "M"],
            "FLAG_OWN_CAR": [" n ", "Y", "N", "Y", "N"],
            "OWN_CAR_AGE": [5.0, 2.0, np.nan, 4.0, 1.0],
            "AMT_INCOME_TOTAL": [0.0, 100.0, -1.0, 200.0, 300.0],
            "NAME_EDUCATION_TYPE": [" higher ", "School", None, "X", "Y"],
        }
    )

    result = transform_dataframe("application_train", source)

    assert result["FLAG_EMPLOYED"].tolist()[:4] == [0, 1, 1, 1]
    assert result.loc[[0, 2, 3], "DAYS_EMPLOYED"].isna().all()
    assert result["AGE_YEARS"].tolist() == [20, 30, 40, 50, 60]
    assert pd.isna(result.loc[0, "CODE_GENDER"])
    assert result.loc[[0, 4], "OWN_CAR_AGE"].isna().all()
    assert result.loc[[0, 2], "AMT_INCOME_TOTAL"].isna().all()
    assert result.loc[1, "NAME_EDUCATION_TYPE"] == "SCHOOL"


@pytest.mark.parametrize(
    ("table_id", "source", "assertions"),
    [
        (
            "bureau_balance",
            pd.DataFrame(
                {
                    "SK_ID_BUREAU": [1, 1, 2],
                    "MONTHS_BALANCE": [1, 1, -1],
                    "STATUS": [" c ", "C", "invalid"],
                }
            ),
            lambda frame: (
                len(frame) == 2
                and frame.iloc[0]["MONTHS_BALANCE"] == 0
                and pd.isna(frame.iloc[1]["STATUS"])
            ),
        ),
        (
            "POS_CASH_balance",
            pd.DataFrame(
                {
                    "MONTHS_BALANCE": [2, 2, -1],
                    "SK_DPD": [-1, -1, 3],
                    "SK_DPD_DEF": [-2, -2, 4],
                }
            ),
            lambda frame: (
                len(frame) == 2
                and frame.iloc[0]["MONTHS_BALANCE"] == 0
                and frame.iloc[0]["SK_DPD"] == 0
                and frame.iloc[0]["SK_DPD_DEF"] == 0
            ),
        ),
        (
            "credit_card_balance",
            pd.DataFrame(
                {
                    "MONTHS_BALANCE": [1],
                    "SK_DPD": [-1],
                    "AMT_BALANCE": [-5.0],
                    "CNT_DRAWINGS_CURRENT": [np.nan],
                    "AMT_DRAWINGS_ATM_CURRENT": [np.nan],
                }
            ),
            lambda frame: (
                frame.loc[0, "MONTHS_BALANCE"] == 0
                and frame.loc[0, "SK_DPD"] == 0
                and frame.loc[0, "AMT_BALANCE"] == 0
                and frame.loc[0, "CNT_DRAWINGS_CURRENT"] == 0
            ),
        ),
    ],
)
def test_monthly_tables_apply_notebook_rules(
    table_id: str,
    source: pd.DataFrame,
    assertions,
) -> None:
    """Aplica deduplicação e limites das tabelas mensais."""
    assert assertions(transform_dataframe(table_id, source))


def test_bureau_cleans_dates_tail_and_negative_amounts() -> None:
    """Aplica regras temporais e financeiras da bureau."""
    source = pd.DataFrame(
        {
            "CREDIT_ACTIVE": [" active ", "Closed", "Active", "Closed"],
            "DAYS_CREDIT": [1, -10, -20, -30],
            "DAYS_ENDDATE_FACT": [2, -1, -2, -3],
            "DAYS_CREDIT_ENDDATE": [18251, 10, -20, -30],
            "AMT_CREDIT_SUM": [-5.0, 10.0, 20.0, 1_000_000.0],
        }
    )

    result = transform_dataframe("bureau", source)

    assert pd.isna(result.loc[0, "DAYS_CREDIT"])
    assert pd.isna(result.loc[0, "DAYS_ENDDATE_FACT"])
    assert pd.isna(result.loc[0, "DAYS_CREDIT_ENDDATE"])
    assert result["AMT_CREDIT_SUM"].min() >= 0
    assert result["AMT_CREDIT_SUM"].max() < 1_000_000
    assert result.loc[0, "CREDIT_ACTIVE"] == "ACTIVE"


def test_previous_application_and_installments_rules() -> None:
    """Preserva granularidade legítima e limpa anomalias das tabelas históricas."""
    previous = transform_dataframe(
        "previous_application",
        pd.DataFrame(
            {
                "SK_ID_PREV": [1, 1, 2],
                "DAYS_DECISION": [2, 2, -10],
                "DAYS_FIRST_DRAWING": [365243, 365243, 18251],
                "AMT_APPLICATION": [-1.0, -1.0, 20.0],
            }
        ),
    )
    installments = transform_dataframe(
        "installments_payments",
        pd.DataFrame(
            {
                "SK_ID_PREV": [1, 1, 1],
                "DAYS_ENTRY_PAYMENT": [-8.0, -8.0, np.nan],
                "DAYS_INSTALMENT": [-10.0, -10.0, -10.0],
                "AMT_PAYMENT": [50.0, 50.0, np.nan],
            }
        ),
    )

    assert len(previous) == 2
    assert previous["DAYS_FIRST_DRAWING"].isna().all()
    assert previous.iloc[0]["AMT_APPLICATION"] == 0
    assert len(installments) == 2
    assert installments.iloc[0]["DIAS_DE_ATRASO"] == 2
    assert installments.iloc[1]["AMT_PAYMENT"] == 0


def test_bureau_balance_file_deduplicates_across_chunks(tmp_path: Path) -> None:
    """Remove duplicatas globais mesmo em chunks diferentes."""
    raw_path = tmp_path / "bureau_balance.csv"
    clean_path = tmp_path / "bureau_balance.parquet"
    pd.DataFrame(
        {
            "SK_ID_BUREAU": [10, 11, 10, 12],
            "MONTHS_BALANCE": [-1, -2, -1, 3],
            "STATUS": [" c ", "0", "C", "invalid"],
        }
    ).to_csv(raw_path, index=False)

    rows = transform_bureau_balance_file(raw_path, clean_path, chunk_size=2)
    result = pd.read_parquet(clean_path)

    assert rows == 3
    assert result.duplicated(["SK_ID_BUREAU", "MONTHS_BALANCE"]).sum() == 0
    assert result.loc[result["SK_ID_BUREAU"] == 12, "MONTHS_BALANCE"].iloc[0] == 0


def test_transform_table_downloads_and_uploads() -> None:
    """Mantém compatibilidade da fronteira MinIO existente durante a migração."""
    client = FakeMinioClient(
        pd.DataFrame(
            {
                "DAYS_EMPLOYED": [-10],
                "DAYS_BIRTH": [-7300],
                "AMT_INCOME_TOTAL": [100.0],
            }
        )
    )
    result = transform_table("application_test", client=client)

    assert client.downloads == [("raw", "application_test.csv")]
    assert client.uploads == [("clean", "application_test_silver.parquet")]
    assert result["rows"] == 1


def test_legacy_transformations_cli_delegates_to_complete_pipeline(mocker) -> None:
    """Impede que a CLI antiga publique dados sem executar o QA."""
    mocked_pipeline = mocker.patch("scripts.silver_pipeline.main", return_value=0)
    mocker.patch(
        "scripts.silver_transformations.transform_table",
        return_value={"rows": 1, "destination": "clean/test.parquet"},
    )

    assert main(["bureau"]) == 0

    mocked_pipeline.assert_called_once_with(["bureau"])
