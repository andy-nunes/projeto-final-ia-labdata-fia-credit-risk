"""Testes das transformações usadas para construir a camada Gold."""

import numpy as np
import pandas as pd
import pytest

from scripts.gold_transformations import (
    _safe_ratio,
    aggregate_bureau,
    aggregate_bureau_balance,
    aggregate_credit_card,
    aggregate_installments,
    aggregate_pos_cash,
    aggregate_previous_application,
    build_abt_train,
    enrich_application,
    filter_train_clients,
)


def bureau_source() -> pd.DataFrame:
    """Cria contratos bureau de treino e de teste para os agregados."""
    return pd.DataFrame(
        {
            "SK_ID_CURR": [1, 1, 2],
            "SK_ID_BUREAU": [10, 11, 20],
            "CREDIT_ACTIVE": ["ACTIVE", "CLOSED", "BAD DEBT"],
            "AMT_CREDIT_SUM": [100.0, 200.0, 900.0],
            "AMT_CREDIT_SUM_DEBT": [50.0, 0.0, 400.0],
            "AMT_CREDIT_SUM_OVERDUE": [5.0, 0.0, 10.0],
            "CREDIT_DAY_OVERDUE": [2, 0, 4],
            "DAYS_CREDIT": [-100, -200, -300],
        }
    )


def balance_source() -> pd.DataFrame:
    """Cria meses bureau balance com atraso, fechamento e desconhecido."""
    return pd.DataFrame(
        {
            "SK_ID_BUREAU": [10, 10, 11, 11, 20],
            "MONTHS_BALANCE": [-1, -2, -1, -2, -1],
            "STATUS": ["0", "1", "C", "X", "5"],
        }
    )


def bureau_map() -> pd.DataFrame:
    """Mapeia contratos bureau para seus clientes."""
    return bureau_source()[["SK_ID_BUREAU", "SK_ID_CURR"]]


def test_enrich_application_creates_base_features_without_mutating_source() -> None:
    """Cria features condicionais e preserva o DataFrame de entrada."""
    source = pd.DataFrame(
        {
            "SK_ID_CURR": [1, 2],
            "EXT_SOURCE_1": [0.2, np.nan],
            "EXT_SOURCE_2": [0.4, 0.6],
            "AMT_CREDIT": [100.0, 200.0],
            "AMT_INCOME_TOTAL": [50.0, 0.0],
            "AMT_ANNUITY": [10.0, 20.0],
            "DAYS_EMPLOYED": [-365.25, -730.5],
        }
    )
    original = source.copy(deep=True)

    result = enrich_application(source)

    np.testing.assert_allclose(result["EXT_SOURCE_MEAN"], [0.3, 0.6])
    assert result["EXT_SOURCE_CNT"].tolist() == [2, 1]
    assert result["FLAG_EXT_SOURCE_1_MISSING"].tolist() == [0, 1]
    assert result["FLAG_EXT_SOURCE_2_MISSING"].tolist() == [0, 0]
    assert result["FLAG_EXT_SOURCE_1_MISSING"].dtype == np.dtype("int8")
    np.testing.assert_allclose(result["CREDIT_INCOME_RATIO"].iloc[0], 2.0)
    assert np.isnan(result["CREDIT_INCOME_RATIO"].iloc[1])
    np.testing.assert_allclose(result["ANNUITY_INCOME_RATIO"].iloc[0], 0.2)
    assert np.isnan(result["ANNUITY_INCOME_RATIO"].iloc[1])
    np.testing.assert_allclose(result["LOG_AMT_CREDIT"], np.log1p([100.0, 200.0]))
    np.testing.assert_allclose(result["DAYS_EMPLOYED_YEARS"], [1.0, 2.0])
    pd.testing.assert_frame_equal(source, original)


def test_build_abt_train_preserves_clients_target_and_missing_aggregates() -> None:
    """Faz left merge, zera apenas flags HAS_ e mantém demais ausências."""
    application = pd.DataFrame(
        {"SK_ID_CURR": [1, 2], "TARGET": [0, 1], "AMT_CREDIT": [100.0, 200.0]}
    )
    bureau = pd.DataFrame(
        {"SK_ID_CURR": [1], "HAS_BUREAU": [1], "BUREAU_CNT_CREDITS": [3]}
    )

    result = build_abt_train(application, {"bureau": bureau})

    assert result["SK_ID_CURR"].tolist() == [1, 2]
    assert result["TARGET"].tolist() == [0, 1]
    assert result["HAS_BUREAU"].tolist() == [1, 0]
    assert result["HAS_BUREAU"].dtype == np.dtype("int8")
    assert np.isnan(result.loc[result["SK_ID_CURR"] == 2, "BUREAU_CNT_CREDITS"].iloc[0])


def test_build_abt_train_rejects_duplicate_client_in_aggregate() -> None:
    """Impede que um agregado multiplique silenciosamente as linhas da ABT."""
    application = pd.DataFrame({"SK_ID_CURR": [1, 2], "TARGET": [0, 1]})
    bureau = pd.DataFrame(
        {"SK_ID_CURR": [1, 1], "HAS_BUREAU": [1, 1]}
    )

    with pytest.raises(ValueError, match="bureau.*SK_ID_CURR.*duplicad"):
        build_abt_train(application, {"bureau": bureau})


@pytest.mark.parametrize("invalid_flag", [257, 1.5])
def test_build_abt_train_rejects_non_binary_has_flag(invalid_flag: float) -> None:
    """Rejeita flags HAS_ inválidas antes da conversão para int8."""
    application = pd.DataFrame({"SK_ID_CURR": [1], "TARGET": [0]})
    bureau = pd.DataFrame(
        {"SK_ID_CURR": [1], "HAS_BUREAU": [invalid_flag]}
    )

    with pytest.raises(ValueError, match="HAS_BUREAU.*0.*1"):
        build_abt_train(application, {"bureau": bureau})


def test_safe_ratio_replaces_zero_denominator_with_nan() -> None:
    """Evita infinito quando o denominador da razão é zero."""
    result = _safe_ratio(pd.Series([4.0, 2.0]), pd.Series([2.0, 0.0]))

    np.testing.assert_allclose(result.iloc[0], 2.0)
    assert np.isnan(result.iloc[1])
    assert not np.isinf(result).any()


def test_filter_train_clients_returns_copy_without_mutating_source() -> None:
    """Filtra clientes de treino e não modifica a origem."""
    source = pd.DataFrame(
        {"SK_ID_CURR": [1, 2, 3], "FEATURE": [10.0, 20.0, 30.0]}
    )
    original = source.copy(deep=True)

    result = filter_train_clients(source, pd.Index([1, 3]), "bureau")
    result.loc[result.index[0], "FEATURE"] = -1.0

    assert result["SK_ID_CURR"].tolist() == [1, 3]
    pd.testing.assert_frame_equal(source, original)


def test_aggregate_bureau_reproduces_contract_metrics() -> None:
    """Agrega contratos, status e montantes por cliente de treino."""
    result = aggregate_bureau(bureau_source(), {1})

    assert result["SK_ID_CURR"].tolist() == [1]
    row = result.iloc[0]
    assert row["BUREAU_CNT_CREDITS"] == 2
    assert row["BUREAU_CNT_ACTIVE"] == 1
    assert row["BUREAU_CNT_CLOSED"] == 1
    assert row["BUREAU_CNT_BAD_DEBT"] == 0
    assert row["BUREAU_AMT_CREDIT_SUM_SUM"] == 300.0
    assert row["BUREAU_AMT_DEBT_SUM"] == 50.0
    assert row["HAS_BUREAU"] == 1


def test_aggregate_bureau_balance_bridges_contract_to_client() -> None:
    """Sobe métricas mensais do contrato bureau para o cliente de treino."""
    result = aggregate_bureau_balance(balance_source(), bureau_map(), {1})

    assert result["SK_ID_CURR"].tolist() == [1]
    row = result.iloc[0]
    assert row["BB_CNT_MONTHS"] == 4
    assert row["BB_CNT_OVERDUE"] == 1
    assert row["BB_CNT_CLOSED"] == 1
    assert row["BB_CNT_UNKNOWN"] == 1
    assert row["BB_CONTRACTS_WITH_OVERDUE"] == 1
    assert row["BB_RATE_OVERDUE_MAX"] == 0.5
    assert row["BB_RATE_OVERDUE_MEAN"] == 0.25
    assert row["HAS_BUREAU_BALANCE"] == 1


def test_pos_cash_rate_uses_overdue_months() -> None:
    """Calcula atraso mensal e quantidade de contratos POS por cliente."""
    source = pd.DataFrame(
        {
            "SK_ID_CURR": [1, 1, 2],
            "SK_ID_PREV": [10, 10, 20],
            "MONTHS_BALANCE": [-1, -2, -1],
            "SK_DPD": [0, 2, 9],
        }
    )

    result = aggregate_pos_cash(source, {1})

    assert result.loc[0, "POS_CNT_MONTHS"] == 2
    assert result.loc[0, "POS_CNT_DPD_GT0"] == 1
    assert result.loc[0, "POS_RATE_DPD"] == 0.5
    assert result.loc[0, "POS_CNT_CONTRACTS"] == 1
    assert result.loc[0, "HAS_POS_CASH"] == 1


def test_credit_card_ignores_zero_limit_in_utilization() -> None:
    """Evita infinito ao agregar utilização de cartão com limite zero."""
    source = pd.DataFrame(
        {
            "SK_ID_CURR": [1, 1],
            "MONTHS_BALANCE": [-1, -2],
            "SK_DPD": [0, 1],
            "AMT_BALANCE": [50.0, 20.0],
            "AMT_CREDIT_LIMIT_ACTUAL": [100.0, 0.0],
            "CNT_DRAWINGS_ATM_CURRENT": [1.0, 2.0],
        }
    )

    result = aggregate_credit_card(source, {1})

    assert result.loc[0, "CC_UTILIZATION_MAX"] == 0.5
    assert not np.isinf(result.select_dtypes(include=[np.number])).any().any()
    assert result.loc[0, "CC_RATE_DPD"] == 0.5
    assert result.loc[0, "HAS_CREDIT_CARD"] == 1


def test_previous_application_builds_status_rates() -> None:
    """Agrega propostas anteriores e suas taxas de aprovação e recusa."""
    source = pd.DataFrame(
        {
            "SK_ID_CURR": [1, 1],
            "SK_ID_PREV": [10, 11],
            "NAME_CONTRACT_STATUS": ["APPROVED", "REFUSED"],
            "AMT_APPLICATION": [100.0, 200.0],
            "AMT_CREDIT": [90.0, 180.0],
            "DAYS_DECISION": [-10, -20],
        }
    )

    result = aggregate_previous_application(source, {1})

    assert result.loc[0, "PREV_CNT_APPS"] == 2
    assert result.loc[0, "PREV_APPROVAL_RATE"] == 0.5
    assert result.loc[0, "PREV_REFUSAL_RATE"] == 0.5
    assert result.loc[0, "PREV_AMT_APPLICATION_MEAN"] == 150.0
    assert result.loc[0, "HAS_PREVIOUS_APP"] == 1


def test_installments_collapses_fractional_payments() -> None:
    """Soma pagamentos fracionados antes de agregar parcelas por cliente."""
    source = pd.DataFrame(
        {
            "SK_ID_CURR": [1, 1],
            "SK_ID_PREV": [10, 10],
            "NUM_INSTALMENT_NUMBER": [1, 1],
            "AMT_INSTALMENT": [100.0, 100.0],
            "AMT_PAYMENT": [40.0, 60.0],
            "DIAS_DE_ATRASO": [1.0, 2.0],
        }
    )

    result = aggregate_installments(source, {1})

    assert result.loc[0, "INST_CNT_PARCELAS"] == 1
    assert result.loc[0, "INST_AMT_INSTALMENT_SUM"] == 100.0
    assert result.loc[0, "INST_AMT_PAYMENT_SUM"] == 100.0
    assert result.loc[0, "INST_CNT_ATRASO"] == 1
    assert result.loc[0, "INST_CNT_UNDERPAY"] == 0
    assert result.loc[0, "INST_PAYMENT_RATIO"] == 1.0
    assert result.loc[0, "HAS_INSTALLMENTS"] == 1
