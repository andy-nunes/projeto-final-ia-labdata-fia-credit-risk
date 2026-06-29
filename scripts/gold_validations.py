"""Resultados, schemas e logs compartilhados pelas validações Gold."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import logging

import numpy as np
import pandas as pd


LOGGER = logging.getLogger(__name__)


class ValidationLevel(str, Enum):
    """Níveis possíveis para uma verificação da camada Gold."""

    PASS = "PASS"
    FAIL = "FAIL"
    INFO = "INFO"


@dataclass(frozen=True)
class ValidationResult:
    """Resultado imutável de uma regra individual de QA."""

    level: ValidationLevel
    message: str


class GoldValidationError(RuntimeError):
    """Representa todas as regras reprovadas em um estágio Gold."""

    def __init__(self, stage: str, failures: list[str]) -> None:
        """Preserva o estágio e todas as mensagens de reprovação."""
        self.stage = stage
        self.failures = failures
        super().__init__(
            f"Validação Gold reprovada em {stage}: {'; '.join(failures)}"
        )


REQUIRED_COLUMNS: dict[str, set[str]] = {
    "application": {"SK_ID_CURR", "TARGET"},
    "bureau": {
        "SK_ID_CURR",
        "SK_ID_BUREAU",
        "CREDIT_ACTIVE",
        "AMT_CREDIT_SUM",
        "AMT_CREDIT_SUM_DEBT",
        "AMT_CREDIT_SUM_OVERDUE",
        "CREDIT_DAY_OVERDUE",
        "DAYS_CREDIT",
    },
    "bureau_balance": {"SK_ID_BUREAU", "MONTHS_BALANCE", "STATUS"},
    "pos_cash": {"SK_ID_CURR", "SK_ID_PREV", "MONTHS_BALANCE", "SK_DPD"},
    "credit_card": {
        "SK_ID_CURR",
        "MONTHS_BALANCE",
        "SK_DPD",
        "AMT_BALANCE",
        "AMT_CREDIT_LIMIT_ACTUAL",
        "CNT_DRAWINGS_ATM_CURRENT",
    },
    "previous_application": {
        "SK_ID_CURR",
        "SK_ID_PREV",
        "NAME_CONTRACT_STATUS",
        "AMT_APPLICATION",
        "AMT_CREDIT",
        "DAYS_DECISION",
    },
    "installments": {
        "SK_ID_CURR",
        "SK_ID_PREV",
        "NUM_INSTALMENT_NUMBER",
        "AMT_INSTALMENT",
        "AMT_PAYMENT",
        "DIAS_DE_ATRASO",
    },
}


def validation_result(
    condition: bool,
    pass_message: str,
    fail_message: str,
) -> ValidationResult:
    """Cria um resultado PASS ou FAIL de acordo com uma condição."""
    if condition:
        return ValidationResult(ValidationLevel.PASS, pass_message)
    return ValidationResult(ValidationLevel.FAIL, fail_message)


def info_result(message: str) -> ValidationResult:
    """Cria um resultado informativo que não bloqueia o estágio."""
    return ValidationResult(ValidationLevel.INFO, message)


def log_and_raise_on_failures(
    stage: str,
    results: list[ValidationResult],
    logger: logging.Logger | None = None,
) -> list[ValidationResult]:
    """Registra todo o QA e levanta uma exceção após os resultados FAIL."""
    active_logger = logger or LOGGER
    failures: list[str] = []

    active_logger.info("[QA] %s", stage)
    for result in results:
        active_logger.info(" -> [%s] %s", result.level.value, result.message)
        if result.level is ValidationLevel.FAIL:
            failures.append(result.message)
    active_logger.info("--- Fim QA %s ---", stage)

    if failures:
        raise GoldValidationError(stage, failures)
    return results


def ensure_required_columns(
    stage: str,
    frame: pd.DataFrame,
    required: set[str] | None = None,
) -> None:
    """Valida e registra as colunas mínimas exigidas por um estágio Gold."""
    if stage not in REQUIRED_COLUMNS:
        raise ValueError(f"Etapa Gold desconhecida: {stage}")
    expected = REQUIRED_COLUMNS[stage] if required is None else required
    missing = sorted(expected.difference(frame.columns))
    failure = f"Colunas obrigatorias ausentes: {', '.join(missing)}"
    result = validation_result(
        not missing,
        "Todas as colunas obrigatorias estao presentes",
        failure,
    )
    log_and_raise_on_failures(f"schema {stage}", [result])


def _unique_and_train_results(
    frame: pd.DataFrame,
    train_ids: set[int],
) -> list[ValidationResult]:
    """Cria verificações comuns de chave única e universo de treino."""
    return [
        validation_result(
            frame["SK_ID_CURR"].is_unique,
            "SK_ID_CURR unico",
            "duplicatas em SK_ID_CURR",
        ),
        validation_result(
            bool(frame["SK_ID_CURR"].isin(train_ids).all()),
            "Somente clientes do train",
            "SK_ID fora do train",
        ),
    ]


def _unit_interval_result(frame: pd.DataFrame, column: str) -> ValidationResult:
    """Valida valores não nulos de uma coluna no intervalo unitário."""
    valid = bool(frame[column].dropna().between(0, 1, inclusive="both").all())
    return validation_result(
        valid,
        f"{column} em [0,1]",
        f"{column} fora da faixa [0,1]",
    )


def validate_application(frame: pd.DataFrame) -> list[ValidationResult]:
    """Valida features Gold derivadas da application de treino."""
    results: list[ValidationResult] = []
    if "EXT_SOURCE_MEAN" in frame.columns:
        results.append(_unit_interval_result(frame, "EXT_SOURCE_MEAN"))
        nulls = int(frame["EXT_SOURCE_MEAN"].isna().sum())
        if nulls:
            results.append(info_result(f"{nulls:,} clientes sem EXT_SOURCE_MEAN"))
    for column in ("CREDIT_INCOME_RATIO", "ANNUITY_INCOME_RATIO"):
        if column in frame.columns:
            infinite = int(np.isinf(frame[column]).sum())
            results.append(
                validation_result(
                    infinite == 0,
                    f"{column} sem inf",
                    f"{column}: {infinite} inf",
                )
            )
    classes = frame["TARGET"].dropna().nunique()
    results.append(
        validation_result(
            classes == 2,
            "TARGET com 2 classes",
            f"TARGET com {classes} classes",
        )
    )
    duplicates = int(frame.duplicated(subset=["SK_ID_CURR"]).sum())
    results.append(
        validation_result(
            duplicates == 0,
            "SK_ID_CURR unico na base",
            f"{duplicates} duplicatas em SK_ID_CURR",
        )
    )
    return log_and_raise_on_failures("Features derivadas — application_train", results)


def validate_bureau(
    frame: pd.DataFrame,
    train_ids: set[int],
) -> list[ValidationResult]:
    """Valida o agregado bureau por cliente."""
    results = _unique_and_train_results(frame, train_ids)
    results.extend(
        [
            validation_result(
                bool((frame["BUREAU_CNT_CREDITS"] >= 1).all()),
                "BUREAU_CNT_CREDITS >= 1",
                "contagem bureau invalida",
            ),
            validation_result(
                bool((frame["HAS_BUREAU"] == 1).all()),
                "HAS_BUREAU = 1",
                "flag HAS_BUREAU inconsistente",
            ),
            validation_result(
                int((frame["BUREAU_AMT_CREDIT_SUM_MAX"] < 0).sum()) == 0,
                "Sem montantes negativos agregados",
                "montantes bureau negativos",
            ),
        ]
    )
    return log_and_raise_on_failures("bureau_gold", results)


def validate_bureau_balance(
    frame: pd.DataFrame,
    train_ids: set[int],
) -> list[ValidationResult]:
    """Valida o agregado bureau balance por cliente."""
    results = _unique_and_train_results(frame, train_ids)
    results.append(_unit_interval_result(frame, "BB_RATE_OVERDUE_MAX"))
    results.append(
        validation_result(
            bool((frame["BB_CNT_MONTHS"] >= 1).all()),
            "BB_CNT_MONTHS >= 1",
            "contagem de meses bureau balance invalida",
        )
    )
    return log_and_raise_on_failures("bureau_balance_gold", results)


def validate_pos_cash(
    frame: pd.DataFrame,
    train_ids: set[int],
) -> list[ValidationResult]:
    """Valida o agregado POS/CASH por cliente."""
    results = _unique_and_train_results(frame, train_ids)
    results.append(
        validation_result(
            bool((frame["POS_SK_DPD_MAX"] >= 0).all()),
            "POS_SK_DPD_MAX >= 0",
            "POS_SK_DPD_MAX negativo",
        )
    )
    results.append(_unit_interval_result(frame, "POS_RATE_DPD"))
    return log_and_raise_on_failures("POS_CASH_gold", results)


def validate_credit_card(
    frame: pd.DataFrame,
    train_ids: set[int],
) -> list[ValidationResult]:
    """Valida o agregado de cartão de crédito por cliente."""
    results = _unique_and_train_results(frame, train_ids)
    infinite = int(np.isinf(frame["CC_UTILIZATION_MAX"]).sum())
    results.append(
        validation_result(
            infinite == 0,
            "CC_UTILIZATION sem inf",
            f"CC_UTILIZATION possui {infinite} inf",
        )
    )
    return log_and_raise_on_failures("credit_card_gold", results)


def validate_previous_application(
    frame: pd.DataFrame,
    train_ids: set[int],
) -> list[ValidationResult]:
    """Valida o agregado de propostas anteriores por cliente."""
    results = _unique_and_train_results(frame, train_ids)
    status_sum = (
        frame["PREV_CNT_APPROVED"]
        + frame["PREV_CNT_REFUSED"]
        + frame["PREV_CNT_CANCELED"]
    )
    results.append(
        validation_result(
            bool((status_sum <= frame["PREV_CNT_APPS"]).all()),
            "Contagens de status coerentes",
            "contagens de status maiores que total de propostas",
        )
    )
    results.append(_unit_interval_result(frame, "PREV_APPROVAL_RATE"))
    return log_and_raise_on_failures("previous_application_gold", results)


def validate_installments(
    frame: pd.DataFrame,
    train_ids: set[int],
) -> list[ValidationResult]:
    """Valida parcelas agregadas e mantém pagamentos a maior informativos."""
    results = _unique_and_train_results(frame, train_ids)
    non_negative = bool(
        (frame["INST_AMT_PAYMENT_SUM"] >= 0).all()
        and (frame["INST_AMT_INSTALMENT_SUM"] >= 0).all()
    )
    results.append(
        validation_result(
            non_negative,
            "Montantes agregados de pagamento/parcela nao negativos",
            "valores negativos em installments agregado",
        )
    )
    overpayment = int(
        (
            frame["INST_AMT_PAYMENT_SUM"]
            > frame["INST_AMT_INSTALMENT_SUM"] * 1.05
        ).sum()
    )
    if overpayment:
        results.append(
            info_result(
                f"{overpayment:,} clientes com pagamento total > 105% das parcelas"
            )
        )
    for column in (
        "INST_RATE_ATRASO",
        "INST_RATE_CALOTE",
        "INST_RATE_UNDERPAY",
    ):
        results.append(_unit_interval_result(frame, column))
    ratio = frame["INST_PAYMENT_RATIO"].dropna()
    valid_ratio = bool((~np.isinf(ratio)).all() and (ratio >= 0).all())
    results.append(
        validation_result(
            valid_ratio,
            "INST_PAYMENT_RATIO finito e >= 0",
            "INST_PAYMENT_RATIO invalido",
        )
    )
    over_ratio = int((ratio > 1.05).sum())
    if over_ratio:
        results.append(
            info_result(f"{over_ratio:,} clientes com INST_PAYMENT_RATIO > 1.05")
        )
    return log_and_raise_on_failures("installments_gold", results)


def _format_count(value: int) -> str:
    """Formata contagens com ponto como separador de milhar."""
    return f"{value:,}".replace(",", ".")


def validate_abt_final(
    abt: pd.DataFrame,
    application: pd.DataFrame,
    expected_rows: int = 307_511,
) -> list[ValidationResult]:
    """Executa o QA estrutural e de negócio completo da ABT de treino."""
    results: list[ValidationResult] = []
    rows = len(abt)
    results.append(
        validation_result(
            rows == expected_rows,
            f"Linhas = {_format_count(expected_rows)}",
            f"Linhas = {_format_count(rows)} (esperado {_format_count(expected_rows)})",
        )
    )
    results.append(
        validation_result(
            rows == len(application),
            "Linhas iguais a application_train",
            f"{rows} linhas na ABT vs {len(application)} na application",
        )
    )
    results.append(
        validation_result(
            abt["SK_ID_CURR"].is_unique,
            "SK_ID_CURR unico na ABT",
            "duplicatas na chave SK_ID_CURR",
        )
    )
    duplicate_columns = abt.columns[abt.columns.duplicated()].tolist()
    results.append(
        validation_result(
            not duplicate_columns,
            "Sem colunas duplicadas",
            f"colunas duplicadas: {duplicate_columns}",
        )
    )
    target = abt.set_index("SK_ID_CURR")["TARGET"]
    original_target = application.set_index("SK_ID_CURR")["TARGET"]
    results.append(
        validation_result(
            target.equals(original_target.reindex(target.index)),
            "TARGET identico ao application_train_silver",
            "TARGET alterado no merge",
        )
    )
    target_rate = float(abt["TARGET"].mean())
    results.append(
        validation_result(
            0.05 < target_rate < 0.12,
            f"Taxa TARGET ~{target_rate:.1%} (faixa 5-12%)",
            f"Taxa TARGET fora do esperado: {target_rate:.1%}",
        )
    )
    numeric = abt.select_dtypes(include=[np.number])
    infinite = int(np.isinf(numeric).sum().sum())
    results.append(
        validation_result(
            infinite == 0,
            "Sem valores inf em colunas numericas",
            f"{infinite} valores inf em colunas numericas",
        )
    )
    has_columns = [column for column in abt.columns if column.startswith("HAS_")]
    if has_columns:
        flags_valid = bool(abt[has_columns].isin([0, 1]).all().all())
        results.append(
            validation_result(
                flags_valid,
                f"Flags HAS_* em {{0,1}} ({len(has_columns)} cols)",
                "flag HAS_* fora do dominio",
            )
        )
    if {"HAS_BUREAU", "BUREAU_CNT_CREDITS"}.issubset(abt.columns):
        has_bureau = abt["HAS_BUREAU"] == 1
        results.append(
            validation_result(
                bool(abt.loc[has_bureau, "BUREAU_CNT_CREDITS"].notna().all()),
                "HAS_BUREAU=1 implica BUREAU_CNT_CREDITS preenchido",
                "incoerencia bureau presente",
            )
        )
        no_bureau = abt["HAS_BUREAU"] == 0
        results.append(
            validation_result(
                bool(abt.loc[no_bureau, "BUREAU_CNT_CREDITS"].isna().all()),
                "HAS_BUREAU=0 implica features bureau nulas",
                "incoerencia bureau ausente",
            )
        )
    for flag in (
        "HAS_CREDIT_CARD",
        "HAS_POS_CASH",
        "HAS_INSTALLMENTS",
        "HAS_BUREAU",
    ):
        if flag in abt.columns:
            results.append(info_result(f"Cobertura {flag}: {abt[flag].mean():.1%}"))
    for column in (
        "EXT_SOURCE_MEAN",
        "CREDIT_INCOME_RATIO",
        "LOG_AMT_CREDIT",
    ):
        if column in abt.columns:
            results.append(
                info_result(f"{column}: {abt[column].isna().mean():.1%} nulos")
            )
    return log_and_raise_on_failures("FINAL abt_train — validacao completa", results)
