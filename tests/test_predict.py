"""Testes das utilidades de predição e compatibilidade do dashboard."""

import pandas as pd
import numpy as np

from scripts import predict as predict_module
from scripts.predict import apply_features_override, normalize_prediction_input


class DummyBooster:
    """Booster fake com categorias pandas preservadas pelo modelo."""

    def __init__(self):
        """Inicializa categorias esperadas para duas features categoricas."""
        self.pandas_categorical = [["CASH LOANS", "REVOLVING LOANS"], ["N", "Y"]]


class DummyModel:
    """Modelo fake usado para validar normalizacao categorica."""

    def __init__(self):
        """Inicializa o booster fake do modelo."""
        self.booster_ = DummyBooster()

    def get_params(self):
        """Retorna parametros minimos esperados pela normalizacao."""
        return {"categorical_feature": ["NAME_CONTRACT_TYPE", "FLAG_OWN_CAR"]}


def test_normalize_prediction_input_matches_model_categories():
    """Verifica que categorias informadas pela UI seguem as categorias do modelo."""
    model = DummyModel()
    input_df = pd.DataFrame(
        {
            "NAME_CONTRACT_TYPE": ["Cash loans"],
            "FLAG_OWN_CAR": [1],
            "AMT_CREDIT": [100000.0],
        }
    )

    normalized_df = normalize_prediction_input(model, input_df)

    assert normalized_df.loc[0, "NAME_CONTRACT_TYPE"] == "CASH LOANS"
    assert normalized_df.loc[0, "FLAG_OWN_CAR"] == "Y"
    assert str(normalized_df["NAME_CONTRACT_TYPE"].dtype).startswith("category")
    assert str(normalized_df["FLAG_OWN_CAR"].dtype).startswith("category")


def test_apply_features_override_updates_existing_columns_only():
    """Verifica que overrides atualizam apenas colunas existentes no dossie."""
    input_df = pd.DataFrame(
        {
            "AMT_CREDIT": [100000.0],
            "AMT_ANNUITY": [5000.0],
            "NAME_INCOME_TYPE": ["WORKING"],
        }
    )

    updated = apply_features_override(
        input_df,
        {
            "AMT_CREDIT": 250000.0,
            "NAME_INCOME_TYPE": "PENSIONER",
            "COLUNA_INEXISTENTE": 1,
        },
    )

    assert updated.loc[0, "AMT_CREDIT"] == 250000.0
    assert updated.loc[0, "AMT_ANNUITY"] == 5000.0
    assert updated.loc[0, "NAME_INCOME_TYPE"] == "PENSIONER"
    assert "COLUNA_INEXISTENTE" not in updated.columns


def test_apply_features_override_noop_when_empty():
    """Verifica que overrides vazios preservam o dataframe original."""
    input_df = pd.DataFrame({"AMT_CREDIT": [1.0]})
    assert apply_features_override(input_df, None) is input_df
    assert apply_features_override(input_df, {}) is input_df


class PredictByClientConfig:
    """Configuracao fake minima para validar o contrato da resposta da API."""

    drop_cols = ["SK_ID_CURR", "TARGET"]
    business_threshold = 0.08

    def feature_columns(self, available_columns):
        """Retorna todas as colunas disponiveis como features do modelo."""
        return list(available_columns)


class PredictByClientModel:
    """Modelo fake minimo para validar payload de entrada e resposta."""

    def get_params(self):
        """Retorna configuracao sem features categoricas."""
        return {"categorical_feature": []}

    def predict_proba(self, input_df):
        """Retorna probabilidade fixa de inadimplencia."""
        assert list(input_df.columns) == ["AMT_CREDIT", "AMT_ANNUITY"]
        assert float(input_df.loc[0, "AMT_CREDIT"]) == 250000.0
        return np.array([[0.7, 0.3]])

    def predict(self, input_df, pred_contrib=False):
        """Retorna contribuicoes compativeis com as features e bias."""
        assert pred_contrib is True
        return [[0.2, -0.1, 0.0]]


def test_predict_by_client_id_includes_model_input(monkeypatch) -> None:
    """Verifica que a resposta inclui o JSON de entrada efetiva do modelo."""
    monkeypatch.setattr(predict_module, "get_model_config", lambda: PredictByClientConfig())
    monkeypatch.setattr(
        predict_module,
        "fetch_client_data_by_id",
        lambda client_id, config: pd.DataFrame(
            {
                "SK_ID_CURR": [client_id],
                "TARGET": [0],
                "AMT_CREDIT": [100000.0],
                "AMT_ANNUITY": [5000.0],
            }
        ),
    )

    result = predict_module.predict_by_client_id(
        139767,
        model=PredictByClientModel(),
        overrides={"AMT_CREDIT": 250000.0},
    )

    assert result["input"] == {
        "AMT_CREDIT": 250000.0,
        "AMT_ANNUITY": 5000.0,
    }
    assert result["applied_overrides"] == {
        "AMT_CREDIT": {
            "original": 100000.0,
            "applied": 250000.0,
        }
    }


class PredictByClientDerivedConfig:
    """Configuracao fake com derivadas financeiras no contrato do modelo."""

    drop_cols = ["SK_ID_CURR", "TARGET"]
    business_threshold = 0.08

    def feature_columns(self, available_columns):
        """Retorna todas as colunas disponiveis como features do modelo."""
        return list(available_columns)


class PredictByClientDerivedModel:
    """Modelo fake que valida derivadas recalculadas apos overrides."""

    def get_params(self):
        """Retorna configuracao sem features categoricas."""
        return {"categorical_feature": []}

    def predict_proba(self, input_df):
        """Confere consistencia matematica antes de retornar probabilidade."""
        assert float(input_df.loc[0, "AMT_CREDIT"]) == 250000.0
        assert float(input_df.loc[0, "AMT_ANNUITY"]) == 12000.0
        assert float(input_df.loc[0, "CREDIT_INCOME_RATIO"]) == 2.5
        assert float(input_df.loc[0, "ANNUITY_INCOME_RATIO"]) == 0.12
        np.testing.assert_allclose(
            float(input_df.loc[0, "LOG_AMT_CREDIT"]),
            np.log1p(250000.0),
        )
        return np.array([[0.7, 0.3]])

    def predict(self, input_df, pred_contrib=False):
        """Retorna contribuicoes compativeis com as features e bias."""
        assert pred_contrib is True
        return [[0.1] * (len(input_df.columns) + 1)]


def test_predict_by_client_id_recalculates_financial_derivatives(monkeypatch) -> None:
    """Verifica que overrides financeiros atualizam derivadas antes da inferencia."""
    monkeypatch.setattr(
        predict_module, "get_model_config", lambda: PredictByClientDerivedConfig()
    )
    monkeypatch.setattr(
        predict_module,
        "fetch_client_data_by_id",
        lambda client_id, config: pd.DataFrame(
            {
                "SK_ID_CURR": [client_id],
                "TARGET": [0],
                "AMT_INCOME_TOTAL": [100000.0],
                "AMT_CREDIT": [100000.0],
                "AMT_ANNUITY": [5000.0],
                "CREDIT_INCOME_RATIO": [1.0],
                "ANNUITY_INCOME_RATIO": [0.05],
                "LOG_AMT_CREDIT": [np.log1p(100000.0)],
            }
        ),
    )

    result = predict_module.predict_by_client_id(
        139767,
        model=PredictByClientDerivedModel(),
        overrides={"AMT_CREDIT": 250000.0, "AMT_ANNUITY": 12000.0},
    )

    assert result["input"]["CREDIT_INCOME_RATIO"] == 2.5
    assert result["input"]["ANNUITY_INCOME_RATIO"] == 0.12
