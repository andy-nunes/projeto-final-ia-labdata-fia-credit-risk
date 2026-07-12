"""Testes pytest dos resultados e logs de validação Silver."""

import logging

import numpy as np
import pandas as pd
import pytest

from scripts.silver_validations import (
    SilverValidationError,
    ValidationLevel,
    log_validation_results,
    validate_dataframe,
    validate_or_raise,
)


def test_application_accumulates_all_failures() -> None:
    """Retorna todas as reprovações da application sem interrupção antecipada."""
    dirty = pd.DataFrame(
        {
            "DAYS_EMPLOYED": [365243],
            "FLAG_EMPLOYED": [np.nan],
            "CODE_GENDER": ["XNA"],
            "FLAG_OWN_CAR": ["N"],
            "OWN_CAR_AGE": [3.0],
            "NAME_EDUCATION_TYPE": [" school "],
        }
    )

    results = validate_dataframe("application_test", dirty)
    failures = [result for result in results if result.level is ValidationLevel.FAIL]

    assert len(failures) >= 6
    assert any("48.744" in result.message for result in failures)
    assert any("DAYS_EMPLOYED" in result.message for result in failures)
    assert any("CODE_GENDER" in result.message for result in failures)


def test_missing_notebook_columns_emit_warnings_without_failure() -> None:
    """Mantém a semântica do notebook para colunas ausentes."""
    results = validate_dataframe("POS_CASH_balance", pd.DataFrame({"OTHER": [1]}))

    assert results
    assert all(result.level is ValidationLevel.WARNING for result in results)


def test_clean_bureau_balance_emits_only_pass_results() -> None:
    """Aprova todas as regras presentes em bureau balance limpa."""
    clean = pd.DataFrame(
        {"SK_ID_BUREAU": [1], "MONTHS_BALANCE": [-1], "STATUS": ["C"]}
    )

    results = validate_dataframe("bureau_balance", clean)

    assert results
    assert all(result.level is ValidationLevel.PASS for result in results)


def test_validation_logs_notebook_format(caplog) -> None:
    """Registra cabeçalho, níveis e fechamento semelhantes ao notebook."""
    results = validate_dataframe("POS_CASH_balance", pd.DataFrame({"OTHER": [1]}))

    with caplog.at_level(logging.INFO):
        log_validation_results(
            "POS_CASH_balance",
            "POS_CASH_balance_silver.parquet",
            results,
        )

    output = caplog.text
    assert "[QA] POS_CASH_balance_silver.parquet" in output
    assert "-> [WARNING]" in output
    assert "--- Fim QA POS_CASH_balance ---" in output


def test_validate_or_raise_logs_every_result_before_failure(caplog) -> None:
    """Emite todos os logs antes de reprovar a task."""
    dirty = pd.DataFrame(
        {"MONTHS_BALANCE": [1], "SK_DPD": [-1], "SK_DPD_DEF": [-2]}
    )

    with caplog.at_level(logging.INFO), pytest.raises(SilverValidationError) as raised:
        validate_or_raise("POS_CASH_balance", dirty)

    assert len(raised.value.failures) == 3
    assert caplog.text.count("-> [FAIL]") == 3
    assert "--- Fim QA POS_CASH_balance ---" in caplog.text
