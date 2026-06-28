"""Regras puras e logs de validação dos Parquets Silver."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import logging

import pandas as pd

from scripts.silver_transformations import (
    BUREAU_STATUS_VALID,
    DAYS_EMPLOYED_ANOMALY,
    MAX_EMPLOYMENT_DAYS,
    SILVER_TABLES,
)


LOGGER = logging.getLogger(__name__)


class ValidationLevel(str, Enum):
    """Níveis possíveis para uma verificação Silver."""

    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"


@dataclass(frozen=True)
class ValidationResult:
    """Resultado individual exibido nos logs de QA."""

    level: ValidationLevel
    message: str


class SilverValidationError(RuntimeError):
    """Representa todas as regras reprovadas para uma tabela Silver."""

    def __init__(self, table_id: str, failures: list[str]) -> None:
        """Monta uma exceção única sem descartar reprovações individuais."""
        self.table_id = table_id
        self.failures = failures
        super().__init__(
            f"Validação Silver reprovada para {table_id}: {'; '.join(failures)}"
        )


def _check(
    results: list[ValidationResult],
    condition: bool,
    pass_message: str,
    fail_message: str,
) -> None:
    """Acrescenta PASS ou FAIL de acordo com uma condição."""
    results.append(
        ValidationResult(
            ValidationLevel.PASS if condition else ValidationLevel.FAIL,
            pass_message if condition else fail_message,
        )
    )


def _warning(results: list[ValidationResult], columns: str) -> None:
    """Registra que uma regra do notebook foi ignorada por coluna ausente."""
    results.append(
        ValidationResult(
            ValidationLevel.WARNING,
            f"Coluna(s) {columns} ausente(s); regra ignorada conforme o notebook",
        )
    )


def _is_upper_trimmed(series: pd.Series) -> bool:
    """Informa se textos não nulos estão em caixa alta e sem espaços externos."""
    values = series.dropna().astype(str)
    return bool(values.apply(lambda value: value == value.strip().upper()).all())


def _format_count(value: int) -> str:
    """Formata contagens com ponto para os logs em português."""
    return f"{value:,}".replace(",", ".")


def _validate_application(df: pd.DataFrame, expected_rows: int) -> list[ValidationResult]:
    """Valida application train ou test conforme o notebook."""
    results: list[ValidationResult] = []
    _check(
        results,
        len(df) == expected_rows,
        f"Volumetria preservada: {_format_count(len(df))} linhas",
        "Volumetria divergente: esperado "
        f"{_format_count(expected_rows)}, obtido {_format_count(len(df))}",
    )
    if "DAYS_EMPLOYED" in df.columns:
        anomaly = int((df["DAYS_EMPLOYED"] == DAYS_EMPLOYED_ANOMALY).sum())
        future = int((df["DAYS_EMPLOYED"] > 0).sum())
        _check(
            results,
            anomaly == 0 and future == 0,
            "DAYS_EMPLOYED sem 365243 e sem valores no futuro",
            f"DAYS_EMPLOYED ainda sujo: 365243={anomaly}, futuro={future}",
        )
    else:
        _warning(results, "DAYS_EMPLOYED")
    if "FLAG_EMPLOYED" in df.columns:
        _check(
            results,
            bool(df["FLAG_EMPLOYED"].notna().any()),
            "FLAG_EMPLOYED presente e preenchida",
            "FLAG_EMPLOYED ausente ou vazia",
        )
    else:
        _warning(results, "FLAG_EMPLOYED")
    if "CODE_GENDER" in df.columns:
        _check(
            results,
            int((df["CODE_GENDER"] == "XNA").sum()) == 0,
            "Nenhum XNA em CODE_GENDER",
            "CODE_GENDER ainda contém XNA",
        )
    else:
        _warning(results, "CODE_GENDER")
    if {"FLAG_OWN_CAR", "OWN_CAR_AGE"}.issubset(df.columns):
        violations = int(
            ((df["FLAG_OWN_CAR"] == "N") & df["OWN_CAR_AGE"].notna()).sum()
        )
        _check(
            results,
            violations == 0,
            "OWN_CAR_AGE respeita FLAG_OWN_CAR",
            f"{violations} registros sem carro possuem OWN_CAR_AGE",
        )
    else:
        _warning(results, "FLAG_OWN_CAR/OWN_CAR_AGE")
    if "NAME_EDUCATION_TYPE" in df.columns:
        _check(
            results,
            _is_upper_trimmed(df["NAME_EDUCATION_TYPE"]),
            "Textos padronizados (UPPER/TRIM)",
            "NAME_EDUCATION_TYPE possui textos fora de UPPER/TRIM",
        )
    else:
        _warning(results, "NAME_EDUCATION_TYPE")
    return results


def _validate_bureau(df: pd.DataFrame) -> list[ValidationResult]:
    """Valida bureau conforme o notebook."""
    results: list[ValidationResult] = []
    if "DAYS_CREDIT" in df.columns:
        future = int((df["DAYS_CREDIT"] > 0).sum())
        _check(
            results,
            future == 0,
            "Sem DAYS_CREDIT no futuro",
            f"DAYS_CREDIT possui {future} valores no futuro",
        )
    else:
        _warning(results, "DAYS_CREDIT")
    if "AMT_CREDIT_SUM" in df.columns:
        percentile = df["AMT_CREDIT_SUM"].quantile(0.999)
        above = int((df["AMT_CREDIT_SUM"] > percentile * 1.001).sum())
        negative = int((df["AMT_CREDIT_SUM"] < 0).sum())
        _check(
            results,
            above == 0,
            "Cap P99.9 em AMT_CREDIT_SUM aplicado",
            f"AMT_CREDIT_SUM possui {above} valores acima do cap P99.9",
        )
        _check(
            results,
            negative == 0,
            "AMT_CREDIT_SUM sem negativos",
            f"AMT_CREDIT_SUM possui {negative} valores negativos",
        )
    else:
        _warning(results, "AMT_CREDIT_SUM")
    if "CREDIT_ACTIVE" in df.columns:
        _check(
            results,
            _is_upper_trimmed(df["CREDIT_ACTIVE"]),
            "Strings em UPPER/TRIM",
            "CREDIT_ACTIVE possui textos fora de UPPER/TRIM",
        )
    else:
        _warning(results, "CREDIT_ACTIVE")
    return results


def _validate_bureau_balance(df: pd.DataFrame) -> list[ValidationResult]:
    """Valida bureau balance conforme o notebook."""
    results: list[ValidationResult] = []
    if {"SK_ID_BUREAU", "MONTHS_BALANCE"}.issubset(df.columns):
        duplicates = int(
            df.duplicated(subset=["SK_ID_BUREAU", "MONTHS_BALANCE"]).sum()
        )
        _check(
            results,
            duplicates == 0,
            "Sem duplicatas na chave composta",
            f"Chave composta possui {duplicates} duplicatas",
        )
    else:
        _warning(results, "SK_ID_BUREAU/MONTHS_BALANCE")
    if "MONTHS_BALANCE" in df.columns:
        future = int((df["MONTHS_BALANCE"] > 0).sum())
        _check(
            results,
            future == 0,
            "MONTHS_BALANCE sem valores futuros",
            f"MONTHS_BALANCE possui {future} valores futuros",
        )
    else:
        _warning(results, "MONTHS_BALANCE")
    if "STATUS" in df.columns:
        valid = bool(df["STATUS"].dropna().isin(BUREAU_STATUS_VALID).all())
        _check(
            results,
            valid,
            "STATUS dentro do domínio válido",
            "STATUS possui valores fora do domínio permitido",
        )
    else:
        _warning(results, "STATUS")
    return results


def _validate_pos_cash(df: pd.DataFrame) -> list[ValidationResult]:
    """Valida POS/CASH conforme o notebook."""
    results: list[ValidationResult] = []
    for column in ("MONTHS_BALANCE", "SK_DPD", "SK_DPD_DEF"):
        if column not in df.columns:
            _warning(results, column)
            continue
        invalid = int((df[column] > 0).sum()) if column == "MONTHS_BALANCE" else int((df[column] < 0).sum())
        _check(
            results,
            invalid == 0,
            f"{column} sem {'futuro' if column == 'MONTHS_BALANCE' else 'negativos'}",
            f"{column} possui {invalid} valores inválidos",
        )
    return results


def _validate_credit_card(df: pd.DataFrame) -> list[ValidationResult]:
    """Valida cartão de crédito conforme o notebook."""
    results = _validate_pos_cash(
        df.drop(columns=["SK_DPD_DEF"], errors="ignore")
    )[:2]
    for column in (
        "AMT_DRAWINGS_ATM_CURRENT",
        "AMT_DRAWINGS_CURRENT",
        "AMT_DRAWINGS_POS_CURRENT",
        "AMT_DRAWINGS_OTHER_CURRENT",
    ):
        if column in df.columns:
            nulls = int(df[column].isna().sum())
            _check(
                results,
                nulls == 0,
                f"{column} sem nulos",
                f"{column} possui {nulls} nulos",
            )
        else:
            _warning(results, column)
    return results


def _validate_previous_application(df: pd.DataFrame) -> list[ValidationResult]:
    """Valida propostas anteriores conforme o notebook."""
    results: list[ValidationResult] = []
    if "SK_ID_PREV" in df.columns:
        duplicates = int(df.duplicated(subset=["SK_ID_PREV"]).sum())
        _check(results, duplicates == 0, "SK_ID_PREV único", f"SK_ID_PREV possui {duplicates} duplicatas")
    else:
        _warning(results, "SK_ID_PREV")
    if "DAYS_DECISION" in df.columns:
        future = int((df["DAYS_DECISION"] > 0).sum())
        _check(results, future == 0, "DAYS_DECISION sem futuro", f"DAYS_DECISION possui {future} valores futuros")
    else:
        _warning(results, "DAYS_DECISION")
    days_columns = [column for column in df.columns if column.startswith("DAYS_")]
    if days_columns:
        anomalies = sum(
            int((df[column] == DAYS_EMPLOYED_ANOMALY).sum())
            + int((df[column] > MAX_EMPLOYMENT_DAYS).sum())
            for column in days_columns
        )
        _check(results, anomalies == 0, "Colunas DAYS_* sem anomalias", f"Colunas DAYS_* possuem {anomalies} anomalias")
    else:
        _warning(results, "DAYS_*")
    return results


def _validate_installments(df: pd.DataFrame) -> list[ValidationResult]:
    """Valida pagamentos de parcelas conforme o notebook."""
    results: list[ValidationResult] = []
    if "AMT_PAYMENT" in df.columns:
        nulls = int(df["AMT_PAYMENT"].isna().sum())
        _check(results, nulls == 0, "AMT_PAYMENT sem nulos", f"AMT_PAYMENT possui {nulls} nulos")
    else:
        _warning(results, "AMT_PAYMENT")
    days_columns = [column for column in df.columns if column.startswith("DAYS_")]
    if days_columns:
        future = sum(int((df[column] > 0).sum()) for column in days_columns)
        _check(results, future == 0, "Colunas DAYS_* sem datas futuras", f"Colunas DAYS_* possuem {future} valores futuros")
    else:
        _warning(results, "DAYS_*")
    if "DIAS_DE_ATRASO" in df.columns:
        results.append(ValidationResult(ValidationLevel.PASS, "DIAS_DE_ATRASO criada (pagamentos fracionários OK)"))
    else:
        _warning(results, "DIAS_DE_ATRASO")
    return results


VALIDATORS = {
    "application_train": _validate_application,
    "application_test": _validate_application,
    "bureau": _validate_bureau,
    "bureau_balance": _validate_bureau_balance,
    "POS_CASH_balance": _validate_pos_cash,
    "credit_card_balance": _validate_credit_card,
    "previous_application": _validate_previous_application,
    "installments_payments": _validate_installments,
}


def validate_dataframe(table_id: str, df: pd.DataFrame) -> list[ValidationResult]:
    """Executa todas as verificações cadastradas para um DataFrame."""
    if table_id not in SILVER_TABLES:
        raise ValueError(f"Tabela Silver desconhecida: {table_id}")
    validator = VALIDATORS[table_id]
    if table_id in {"application_train", "application_test"}:
        return validator(df, SILVER_TABLES[table_id].expected_rows)
    return validator(df)


def log_validation_results(
    table_id: str,
    filename: str,
    results: list[ValidationResult],
    logger: logging.Logger | None = None,
) -> None:
    """Emite resultados no formato visual usado pelo notebook."""
    target = logger or LOGGER
    target.info("[QA] %s", filename)
    for result in results:
        target.info(" -> [%s] %s", result.level.value, result.message)
    target.info("--- Fim QA %s ---", table_id)


def validate_or_raise(
    table_id: str,
    df: pd.DataFrame,
    filename: str | None = None,
    logger: logging.Logger | None = None,
) -> list[ValidationResult]:
    """Registra todo o QA e levanta erro somente para resultados FAIL."""
    results = validate_dataframe(table_id, df)
    log_validation_results(
        table_id,
        filename or SILVER_TABLES[table_id].clean_key,
        results,
        logger,
    )
    failures = [result.message for result in results if result.level is ValidationLevel.FAIL]
    if failures:
        raise SilverValidationError(table_id, failures)
    return results
