"""Lógica de previsão do modelo LightGBM para o dashboard de crédito."""

from __future__ import annotations

import json
import os
import pickle
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import s3fs

from scripts.model_config import ModelConfig, get_model_config

MINIO_ENDPOINT_URL = os.getenv("MINIO_ENDPOINT_URL", "http://minio:9000")
MINIO_ROOT_USER = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_ROOT_PASSWORD = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
MODEL_PATH = get_model_config().resolve_model_artifact_path()
ABT_PATH = get_model_config().resolve_abt_path()


def get_model_path() -> str:
    """Resolve caminho do artefato do modelo (env sobrescreve config)."""
    return os.getenv("MODEL_PATH", MODEL_PATH)


def get_abt_path() -> str:
    """Resolve caminho da ABT (env sobrescreve config)."""
    return os.getenv("ABT_PATH", ABT_PATH)


def is_s3_path(path: str) -> bool:
    return isinstance(path, str) and path.startswith("s3://")


def get_s3_filesystem() -> s3fs.S3FileSystem:
    """Cria filesystem S3 apontando para o MinIO local."""
    return s3fs.S3FileSystem(
        key=MINIO_ROOT_USER,
        secret=MINIO_ROOT_PASSWORD,
        client_kwargs={"endpoint_url": MINIO_ENDPOINT_URL},
    )


def resolve_local_model_path(config: ModelConfig | None = None) -> Path | None:
    """Fallback local quando o caminho configurado (ex.: S3) não está acessível."""
    if config is None:
        config = get_model_config()

    candidates: list[Path] = []
    configured = Path(config.resolve_model_artifact_path())
    if not is_s3_path(str(configured)):
        candidates.append(configured)

    # Sempre tenta o artefato local do repositório, mesmo com MODEL_PATH=s3://...
    local_rel = config._resolve_path_key("model_artifact_path", "model_artifact")
    candidates.append(Path(__file__).resolve().parents[1] / local_rel)

    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        if candidate.is_file() and candidate.stat().st_size > 0:
            return candidate
    return None


def load_model() -> Any:
    """Carrega o modelo LightGBM a partir de MinIO ou do arquivo local."""
    try:
        import lightgbm  # noqa: F401
    except ModuleNotFoundError as exc:
        raise ImportError(
            "O pacote lightgbm não está instalado. "
            "Instale-o no ambiente do Streamlit ou inclua-o nas dependências do projeto."
        ) from exc

    def _pickle_load(path: str, fs: s3fs.S3FileSystem | None = None) -> Any:
        if is_s3_path(path):
            if fs is None:
                fs = get_s3_filesystem()
            with fs.open(path, "rb") as handle:
                return pickle.load(handle)
        with open(path, "rb") as handle:
            return pickle.load(handle)

    primary_error: Exception | None = None
    try:
        model_path = get_model_path()
        if is_s3_path(model_path):
            fs = get_s3_filesystem()
            return _pickle_load(model_path, fs)
        return _pickle_load(model_path)
    except ModuleNotFoundError as exc:
        raise ImportError(
            "Falha ao deserializar o modelo. É necessário o pacote lightgbm para carregar o arquivo pickle."
        ) from exc
    except Exception as exc:
        primary_error = exc

    local_model_path = resolve_local_model_path()
    if local_model_path is None:
        raise FileNotFoundError(
            f"Modelo indisponível em {get_model_path()} e sem fallback local "
            "em artifacts/. Re-execute a DAG 04_model_train_lightgbm ou restaure o .pkl."
        ) from primary_error
    return _pickle_load(str(local_model_path))


def _normalize_category_token(value: Any) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, (bool, np.bool_)):
        return "true" if bool(value) else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(int(value))
    return re.sub(r"[^a-z0-9]+", " ", str(value).strip().lower()).strip()


def _map_categorical_value(value: Any, categories: list[Any]) -> Any:
    if pd.isna(value):
        return pd.NA

    if isinstance(value, (bool, np.bool_)):
        value = int(bool(value))

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        truthy_values = {1, "1", "y", "yes", "true"}
        falsy_values = {0, "0", "n", "no", "false"}
        normalized_value = _normalize_category_token(value)
        for category in categories:
            category_token = _normalize_category_token(category)
            if category_token in {"y", "yes", "true"} and normalized_value in truthy_values:
                return category
            if category_token in {"n", "no", "false"} and normalized_value in falsy_values:
                return category

    normalized_value = _normalize_category_token(value)
    if not normalized_value:
        return pd.NA

    for category in categories:
        if _normalize_category_token(category) == normalized_value:
            return category

    return pd.NA


def normalize_prediction_input(model: Any, input_df: pd.DataFrame) -> pd.DataFrame:
    categorical_features = model.get_params().get("categorical_feature", [])
    if isinstance(categorical_features, str):
        categorical_features = [categorical_features]

    categories_map: dict[str, list[Any]] = {}
    pandas_categorical = getattr(getattr(model, "booster_", None), "pandas_categorical", None)
    if pandas_categorical is not None:
        for index, feature in enumerate(categorical_features):
            if index < len(pandas_categorical):
                categories_map[feature] = list(pandas_categorical[index])

    normalized_df = input_df.copy()
    for feature in categorical_features:
        if feature not in normalized_df.columns:
            continue

        if feature in categories_map:
            mapped_values = [
                _map_categorical_value(value, categories_map[feature])
                for value in normalized_df[feature]
            ]
            normalized_df[feature] = pd.Categorical(
                mapped_values,
                categories=categories_map[feature],
            )
        else:
            normalized_df[feature] = normalized_df[feature].astype(str)

    return normalized_df


def get_business_threshold() -> float:
    """Retorna threshold de negócio da configuração central."""
    return get_model_config().business_threshold


def risk_band(probability: float, threshold: float | None = None) -> str:
    cutoff = get_business_threshold() if threshold is None else threshold
    if probability < cutoff * 0.4:
        return "Baixo risco"
    if probability < cutoff:
        return "Risco moderado"
    return "Alto risco"


def build_prediction_matrix(input_df: pd.DataFrame, config: ModelConfig) -> pd.DataFrame:
    """Monta a matriz de predição removendo colunas configuradas e aplicando trilho de features."""
    working_df = input_df.copy()
    drop_cols = [col for col in config.drop_cols if col in working_df.columns]
    if drop_cols:
        working_df = working_df.drop(columns=drop_cols)

    feature_cols = config.feature_columns(list(working_df.columns))
    return working_df[feature_cols].copy()


def fetch_client_data_by_id(client_id: int, config: ModelConfig | None = None) -> pd.DataFrame:
    """
    Busca o dossiê do cliente na base de holdout usando o identificador configurado.
    Retorna o dataframe completo (incluindo TARGET) para auditoria no frontend.
    """
    if config is None:
        config = get_model_config()

    demo_path = config.resolve_demo_holdout_path()

    if is_s3_path(str(demo_path)):
        fs = get_s3_filesystem()
        with fs.open(demo_path, "rb") as handle:
            df_holdout = pd.read_parquet(handle, engine="pyarrow")
    else:
        df_holdout = pd.read_parquet(demo_path)

    id_column = config.id_column
    client_df = df_holdout[df_holdout[id_column] == client_id].copy()

    if client_df.empty:
        raise ValueError(
            f"Cliente com {id_column}={client_id} não encontrado na base de holdout."
        )

    return client_df.reset_index(drop=True)


def apply_features_override(
    input_df: pd.DataFrame,
    features_override: dict[str, Any] | None,
) -> pd.DataFrame:
    """
    Aplica overrides de features sobre a linha do cliente ANTES da normalização/escoragem.
    Apenas colunas existentes no dataframe são atualizadas.
    """
    if not features_override:
        return input_df

    updated = input_df.copy()
    for feature, value in features_override.items():
        if feature not in updated.columns:
            continue
        updated.loc[:, feature] = value
    return updated


def recalculate_derived_features(input_df: pd.DataFrame) -> pd.DataFrame:
    """Recalcula derivadas online impactadas por overrides financeiros."""
    updated = input_df.copy()

    def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
        ratio = numerator / denominator.replace({0: np.nan})
        return ratio.replace([np.inf, -np.inf], np.nan)

    if {"AMT_CREDIT", "AMT_INCOME_TOTAL", "CREDIT_INCOME_RATIO"}.issubset(
        updated.columns
    ):
        updated.loc[:, "CREDIT_INCOME_RATIO"] = _safe_ratio(
            updated["AMT_CREDIT"], updated["AMT_INCOME_TOTAL"]
        )

    if {"AMT_ANNUITY", "AMT_INCOME_TOTAL", "ANNUITY_INCOME_RATIO"}.issubset(
        updated.columns
    ):
        updated.loc[:, "ANNUITY_INCOME_RATIO"] = _safe_ratio(
            updated["AMT_ANNUITY"], updated["AMT_INCOME_TOTAL"]
        )

    if {"AMT_CREDIT", "LOG_AMT_CREDIT"}.issubset(updated.columns):
        updated.loc[:, "LOG_AMT_CREDIT"] = np.log1p(
            np.maximum(updated["AMT_CREDIT"], 0)
        )

    return updated


def build_applied_overrides(
    original_df: pd.DataFrame,
    scored_df: pd.DataFrame,
    features_override: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    """Monta resumo dos overrides que alteraram features existentes."""
    if not features_override:
        return {}

    applied: dict[str, dict[str, Any]] = {}
    for feature in features_override:
        if feature not in original_df.columns or feature not in scored_df.columns:
            continue

        original_value = json.loads(pd.Series([original_df.iloc[0][feature]]).to_json()).get("0")
        scored_value = json.loads(pd.Series([scored_df.iloc[0][feature]]).to_json()).get("0")
        if original_value != scored_value:
            applied[feature] = {
                "original": original_value,
                "applied": scored_value,
            }
    return applied


def predict_by_client_id(
    client_id: int,
    model: Any = None,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Fluxo principal da API: Recebe o ID do cliente, aplica os overrides do gerente,
    prepara a matriz e retorna o parecer de crédito.
    """
    config = get_model_config()

    if model is None:
        model = load_model()

    original_df = fetch_client_data_by_id(client_id, config)
    input_df = apply_features_override(original_df, overrides)
    input_df = recalculate_derived_features(input_df)
    applied_overrides = build_applied_overrides(original_df, input_df, overrides)

    X_pred = build_prediction_matrix(input_df, config)
    normalized_df = normalize_prediction_input(model, X_pred)
    model_input = json.loads(normalized_df.iloc[0].to_json())

    proba = float(model.predict_proba(normalized_df)[:, 1][0])
    threshold = config.business_threshold
    prediction = 1 if proba >= threshold else 0

    top_risk_factors: list[tuple[str, float]] = []
    top_positive_factors: list[tuple[str, float]] = []

    try:
        contributions = model.predict(normalized_df, pred_contrib=True)[0]
        feature_contribs = contributions[:-1]
        columns = list(normalized_df.columns)

        if len(feature_contribs) != len(columns):
            raise ValueError(
                f"Incompatibilidade entre contribuições ({len(feature_contribs)}) "
                f"e colunas ({len(columns)})."
            )

        contrib_map: dict[str, float] = {
            col: float(val) for col, val in zip(columns, feature_contribs, strict=True)
        }

        total_abs_contrib = sum(abs(v) for v in contrib_map.values())

        positive_contribs = sorted(
            ((name, value) for name, value in contrib_map.items() if value > 0),
            key=lambda item: item[1],
            reverse=True,
        )
        negative_contribs = sorted(
            ((name, value) for name, value in contrib_map.items() if value < 0),
            key=lambda item: item[1],
        )

        def _to_impact_pct(name: str, value: float) -> tuple[str, float]:
            if total_abs_contrib > 0:
                impact_pct = (abs(value) / total_abs_contrib) * 100
            else:
                impact_pct = 0.0
            return (name, impact_pct)

        top_risk_factors = [
            _to_impact_pct(name, value) for name, value in positive_contribs[:5]
        ]
        top_positive_factors = [
            _to_impact_pct(name, value) for name, value in negative_contribs[:5]
        ]
    except Exception as exc:
        raise RuntimeError(
            f"Falha ao calcular contribuições locais (XAI) para o cliente {client_id}: {exc}"
        ) from exc

    return {
        "sk_id_curr": client_id,
        "probability": proba,
        "prediction": prediction,
        "threshold": threshold,
        "risk_band": risk_band(proba, threshold),
        "label": "Reprovado (Risco de Inadimplência)" if prediction == 1 else "Aprovado (Pagador Saudável)",
        "input": model_input,
        "applied_overrides": applied_overrides,
        "top_risk_factors": top_risk_factors,
        "top_positive_factors": top_positive_factors,
    }


if __name__ == "__main__":
    id_teste = int(sys.argv[1]) if len(sys.argv) > 1 else 100002

    try:
        print(f"Iniciando análise de crédito para o cliente ID: {id_teste}...")
        resultado = predict_by_client_id(id_teste)
        print(json.dumps(resultado, indent=4, ensure_ascii=False))
    except ValueError as e:
        print(e)
