"""Testes do núcleo de validação da camada Gold."""

import logging

import numpy as np
import pandas as pd
import pytest

from scripts.gold_validations import (
    REQUIRED_COLUMNS,
    GoldValidationError,
    ValidationLevel,
    ensure_required_columns,
    info_result,
    log_and_raise_on_failures,
    validate_abt_final,
    validate_bureau,
    validate_installments,
    validate_pos_cash,
    validation_result,
)


def test_required_columns_match_gold_contract() -> None:
    """Mantém os schemas mínimos das fontes usadas pela camada Gold."""
    assert REQUIRED_COLUMNS == {
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


def test_ensure_required_columns_reports_sorted_failures(caplog) -> None:
    """Lista colunas ausentes em ordem e registra o QA de schema completo."""
    frame = pd.DataFrame({"SK_ID_CURR": [1]})
    required = {"SK_ID_CURR", "SK_ID_BUREAU", "CREDIT_ACTIVE"}

    with caplog.at_level(logging.INFO), pytest.raises(GoldValidationError) as raised:
        ensure_required_columns("bureau", frame, required)

    assert raised.value.stage == "schema bureau"
    assert raised.value.failures == [
        "Colunas obrigatorias ausentes: CREDIT_ACTIVE, SK_ID_BUREAU"
    ]
    assert "[QA] schema bureau" in caplog.text
    assert "[FAIL]" in caplog.text


def test_log_and_raise_emits_every_failure_before_raising(caplog) -> None:
    """Registra todas as reprovações antes de levantar a exceção agregada."""
    results = [
        validation_result(True, "volume correto", "volume incorreto"),
        validation_result(False, "taxa correta", "taxa invalida"),
        validation_result(False, "valores finitos", "valores infinitos"),
    ]

    with caplog.at_level(logging.INFO), pytest.raises(GoldValidationError) as raised:
        log_and_raise_on_failures("metricas", results)

    assert raised.value.failures == ["taxa invalida", "valores infinitos"]
    assert caplog.text.count("-> [FAIL]") == 2
    assert caplog.text.index("taxa invalida") < caplog.text.index("valores infinitos")
    assert "--- Fim QA metricas ---" in caplog.text


def test_info_result_is_non_blocking(caplog) -> None:
    """Permite resultados informativos sem reprovar o estágio."""
    result = info_result("amostra sem TARGET")

    with caplog.at_level(logging.INFO):
        log_and_raise_on_failures("amostra", [result])

    assert result.level is ValidationLevel.INFO
    assert "-> [INFO] amostra sem TARGET" in caplog.text
    assert "--- Fim QA amostra ---" in caplog.text


def test_approved_results_return_the_same_list() -> None:
    """Devolve a própria lista de resultados quando o estágio é aprovado."""
    results = [
        validation_result(True, "volume correto", "volume incorreto"),
        info_result("TARGET não aplicável"),
    ]

    returned = log_and_raise_on_failures("amostra", results)

    assert returned is results


def test_unknown_stage_without_required_raises_value_error() -> None:
    """Explica o estágio inválido antes de consultar o schema padrão."""
    with pytest.raises(ValueError, match="^Etapa Gold desconhecida: historico$"):
        ensure_required_columns("historico", pd.DataFrame())


def test_unknown_stage_with_required_raises_value_error() -> None:
    """Rejeita estágio inválido mesmo quando um schema explícito é informado."""
    with pytest.raises(ValueError, match="^Etapa Gold desconhecida: historico$"):
        ensure_required_columns("historico", pd.DataFrame(), {"SK_ID_CURR"})


def test_intermediate_validation_accumulates_pos_failures(caplog) -> None:
    """Exibe todas as falhas POS antes de reprovar a etapa."""
    dirty = pd.DataFrame(
        {
            "SK_ID_CURR": [2, 3],
            "POS_SK_DPD_MAX": [-1, -1],
            "POS_RATE_DPD": [2.0, 2.0],
        }
    )

    with caplog.at_level(logging.INFO), pytest.raises(GoldValidationError) as raised:
        validate_pos_cash(dirty, {1})

    assert len(raised.value.failures) == 3
    assert caplog.text.count("-> [FAIL]") == 3
    assert "--- Fim QA POS_CASH_gold ---" in caplog.text


def test_final_validation_rejects_partial_volume_even_when_base_matches() -> None:
    """Reprova uma ABT parcial mesmo quando preserva a application carregada."""
    application = pd.DataFrame({"SK_ID_CURR": [1, 2], "TARGET": [0, 1]})

    with pytest.raises(GoldValidationError) as raised:
        validate_abt_final(application.copy(), application, expected_rows=307_511)

    assert any("307.511" in failure for failure in raised.value.failures)


def test_installments_overpayment_is_info_not_failure(caplog) -> None:
    """Mantém pagamentos acima de 105% como informação do notebook."""
    aggregate = pd.DataFrame(
        {
            "SK_ID_CURR": [1],
            "INST_AMT_PAYMENT_SUM": [120.0],
            "INST_AMT_INSTALMENT_SUM": [100.0],
            "INST_RATE_ATRASO": [0.0],
            "INST_RATE_CALOTE": [0.0],
            "INST_RATE_UNDERPAY": [0.0],
            "INST_PAYMENT_RATIO": [1.2],
        }
    )

    with caplog.at_level(logging.INFO):
        validate_installments(aggregate, {1})

    assert "-> [INFO]" in caplog.text
    assert "pagamento" in caplog.text.lower()
    assert not np.isinf(aggregate.select_dtypes(include=[np.number])).any().any()


def test_bureau_validation_ignores_null_when_counting_negative_amounts() -> None:
    """Replica o notebook: nulo não é contado como montante negativo."""
    aggregate = pd.DataFrame(
        {
            "SK_ID_CURR": [1],
            "BUREAU_CNT_CREDITS": [1],
            "HAS_BUREAU": [1],
            "BUREAU_AMT_CREDIT_SUM_MAX": [np.nan],
        }
    )

    validate_bureau(aggregate, {1})
