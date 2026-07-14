"""Treinamento do modelo LightGBM (train) a partir da ABT e model_config.yaml."""

from __future__ import annotations

import json
import os
import pickle
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Tuple

import lightgbm as lgb
import numpy as np
import pandas as pd
import s3fs
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    confusion_matrix,
    fbeta_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split

from scripts.model_config import ModelConfig, export_metadata, get_model_config

warnings.filterwarnings("ignore")

MINIO_KEY = os.getenv("MINIO_KEY", os.getenv("MINIO_ROOT_USER", "minioadmin"))
MINIO_SECRET = os.getenv("MINIO_SECRET", os.getenv("MINIO_ROOT_PASSWORD", "minioadmin"))
MINIO_ENDPOINT_URL = os.getenv("MINIO_ENDPOINT_URL", "http://minio:9000")


def get_s3_filesystem() -> s3fs.S3FileSystem:
    """Cria cliente S3 apontando para o MinIO local."""
    return s3fs.S3FileSystem(
        key=MINIO_KEY,
        secret=MINIO_SECRET,
        client_kwargs={"endpoint_url": MINIO_ENDPOINT_URL},
    )


def is_s3_path(path: str) -> bool:
    return isinstance(path, str) and path.startswith("s3://")


def read_parquet(path: str, fs: s3fs.S3FileSystem | None = None) -> pd.DataFrame:
    """Lê Parquet local ou remoto."""
    if is_s3_path(path):
        if fs is None:
            fs = get_s3_filesystem()
        with fs.open(path, "rb") as handle:
            return pd.read_parquet(handle, engine="pyarrow")
    return pd.read_parquet(path, engine="pyarrow")


def write_parquet(df: pd.DataFrame, path: str | Path, fs: s3fs.S3FileSystem | None = None) -> None:
    """Grava Parquet local ou remoto."""
    path_str = str(path)
    if is_s3_path(path_str):
        if fs is None:
            raise ValueError("Filesystem S3 obrigatório para escrita remota")
        with fs.open(path_str, "wb") as handle:
            df.to_parquet(handle, index=False, engine="pyarrow")
        return
    target = Path(path_str)
    target.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(target, index=False, engine="pyarrow")


def qa_abt_load(df: pd.DataFrame, config: ModelConfig) -> None:
    """Valida integridade básica da ABT."""
    print("[QA] Carga ABT")
    print(f" -> Linhas: {len(df):,}")
    print(f" -> SK_ID_CURR duplicados: {df.duplicated(subset=['SK_ID_CURR']).sum():,}")
    if "TARGET" not in df.columns:
        raise ValueError("TARGET ausente na ABT")
    rate = df["TARGET"].mean()
    print(f" -> Taxa TARGET: {rate:.2%}")
    print(f" -> Infinitos: {np.isinf(df.select_dtypes(include=[np.number])).sum().sum()}")
    expected = config.full_dataset_rows
    if len(df) != expected:
        print(f" -> [ATENÇÃO] Esperado {expected:,} linhas")
    print("---")


def split_abt_three_way(
    df: pd.DataFrame,
    config: ModelConfig,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Separa ABT em treino, teste e holdout de demo (estratificado)."""
    demo_frac = config.split_demo
    test_frac = config.split_test
    train_frac = config.split_train
    random_state = config.random_state

    # Isola o conjunto de demonstração (holdout) e mantém o restante para modelagem
    df_work, df_demo = train_test_split(
        df,
        test_size=demo_frac,
        random_state=random_state,
        stratify=df["TARGET"],
    )
    
    # Particiona o conjunto de trabalho entre treino e teste respeitando a proporção global
    test_size_remain = test_frac / (train_frac + test_frac)
    
    df_train, df_test = train_test_split(
        df_work,
        test_size=test_size_remain,
        random_state=random_state,
        stratify=df_work["TARGET"],
    )
    
    return df_train.reset_index(drop=True), df_test.reset_index(drop=True), df_demo.reset_index(drop=True)


def select_feature_frame(df: pd.DataFrame, config: ModelConfig) -> pd.DataFrame:
    """Filtra colunas conforme trilho de features da configuração."""
    feature_cols = config.feature_columns(list(df.columns))
    keep_cols = list(dict.fromkeys([*config.drop_cols, *feature_cols]))
    keep_cols = [col for col in keep_cols if col in df.columns]
    return df[keep_cols].copy()


def split_features_target(df: pd.DataFrame, config: ModelConfig) -> Tuple[pd.DataFrame, pd.Series]:
    """Separa matriz de features e vetor alvo."""
    feature_df = select_feature_frame(df, config)
    y = df["TARGET"].astype(int)
    X = feature_df.drop(columns=[col for col in config.drop_cols if col in feature_df.columns])
    return X, y


def prepare_boosters_data(
    X_train: pd.DataFrame,
    X_other: pd.DataFrame,
    categorical_columns: list[str],
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Tipa categorias nativas para LightGBM."""
    X_train_boost = X_train.copy()
    X_other_boost = X_other.copy()
    for col in categorical_columns:
        X_train_boost[col] = X_train_boost[col].astype("category")
        X_other_boost[col] = pd.Categorical(
            X_other_boost[col],
            categories=X_train_boost[col].cat.categories,
        )
    return X_train_boost, X_other_boost


def build_lgbm_classifier(
    config: ModelConfig,
    scale_pos_weight: float,
    categorical_columns: list[str],
) -> lgb.LGBMClassifier:
    """Instancia LightGBM com hiperparâmetros da configuração."""
    params = config.model_params
    return lgb.LGBMClassifier(
        n_estimators=int(params["n_estimators"]),
        learning_rate=float(params["learning_rate"]),
        num_leaves=int(params["num_leaves"]),
        max_depth=int(params["max_depth"]),
        subsample=float(params["subsample"]),
        colsample_bytree=float(params["colsample_bytree"]),
        scale_pos_weight=scale_pos_weight,
        random_state=config.random_state,
        n_jobs=-1,
        verbose=-1,
        categorical_feature=categorical_columns,
    )


def compute_metrics(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    config: ModelConfig,
) -> dict[str, float]:
    """Calcula métricas de negócio e discriminação no threshold configurado."""
    threshold = config.business_threshold
    y_pred = (y_proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    n_pos = int((y_true == 1).sum())
    return {
        "roc_auc": float(roc_auc_score(y_true, y_proba)),
        "pr_auc": float(average_precision_score(y_true, y_proba)),
        "f2": float(fbeta_score(y_true, y_pred, beta=config.f_beta, zero_division=0)),
        "recall_inadimplente": float(recall_score(y_true, y_pred, zero_division=0)),
        "precision_inadimplente": float(precision_score(y_true, y_pred, zero_division=0)),
        "fn": float(fn),
        "fp": float(fp),
        "tp": float(tp),
        "tn": float(tn),
        "taxa_reprovacao": float(y_pred.mean()),
        "recall_meta_pct": float(tp / n_pos) if n_pos else 0.0,
        "threshold": threshold,
    }


def print_metrics(label: str, metrics: dict[str, float], config: ModelConfig) -> None:
    """Imprime métricas formatadas para stdout."""
    threshold = config.business_threshold
    print(f"  {label}")
    print(
        f"    PR-AUC={metrics['pr_auc']:.4f} | ROC-AUC={metrics['roc_auc']:.4f} | F2={metrics['f2']:.4f}"
    )
    print(
        f"    Recall={metrics['recall_inadimplente']:.1%} | FN={int(metrics['fn']):,} | "
        f"FP={int(metrics['fp']):,} | reprovação={metrics['taxa_reprovacao']:.1%} (t={threshold})"
    )


def train_lgbm(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    config: ModelConfig,
    categorical_columns: list[str],
) -> Tuple[lgb.LGBMClassifier, float, float]:
    """Treina LightGBM e retorna modelo, scale_pos_weight e tempo de treino."""
    # scale_pos_weight = (y_train == 0).sum() / max((y_train == 1).sum(), 1)
    scale_pos_weight = 1.0
    model = build_lgbm_classifier(config, scale_pos_weight, categorical_columns)
    start = time.perf_counter()
    model.fit(X_train, y_train)
    return model, float(scale_pos_weight), time.perf_counter() - start


def evaluate_model(
    model: lgb.LGBMClassifier,
    X_eval: pd.DataFrame,
    y_eval: pd.Series,
    config: ModelConfig,
) -> dict[str, Any]:
    """Avalia modelo no conjunto informado."""
    proba = model.predict_proba(X_eval)[:, 1]
    metrics = compute_metrics(y_eval.values, proba, config)
    y_pred = (proba >= config.business_threshold).astype(int)
    return {
        **metrics,
        "classification_report": classification_report(
            y_eval,
            y_pred,
            target_names=["Pagou (0)", "Inadimplente (1)"],
        ),
        "confusion_matrix": confusion_matrix(y_eval, y_pred).tolist(),
    }


def export_model(model: lgb.LGBMClassifier, target_path: str, fs: s3fs.S3FileSystem | None = None) -> None:
    """Serializa modelo treinado."""
    model_bytes = pickle.dumps(model)
    if is_s3_path(target_path):
        if fs is None:
            raise ValueError("Filesystem S3 obrigatório para artefato remoto")
        with fs.open(target_path, "wb") as handle:
            handle.write(model_bytes)
        return
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as handle:
        handle.write(model_bytes)


def build_metadata(
    config: ModelConfig,
    metrics: dict[str, Any],
    scale_pos_weight: float,
    feature_columns: list[str],
    split_sizes: dict[str, int],
    model_path: str,
    metadata_path: str,
    elapsed_seconds: float,
) -> dict[str, Any]:
    """Monta metadados persistidos após o treino."""
    return {
        "project": config.raw["project"]["name"],
        "config_version": config.raw["metadata"]["version"],
        "config_path": str(config.config_path),
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "algorithm": config.model_params["algorithm"],
        "feature_set": config.feature_set,
        "feature_count": len(feature_columns),
        "feature_columns": feature_columns,
        "random_state": config.random_state,
        "splits": {
            "train": config.split_train,
            "test": config.split_test,
            "demo_holdout": config.split_demo,
            "rows": split_sizes,
        },
        "business": {
            "threshold": config.business_threshold,
            "f_beta": config.f_beta,
            "primary_metric": config.raw["business"]["primary_metric"],
        },
        "hyperparameters": config.model_params,
        "scale_pos_weight": scale_pos_weight,
        "metrics_test": {
            key: metrics[key]
            for key in (
                "pr_auc",
                "roc_auc",
                "f2",
                "tn",
                "fp",
                "fn",
                "tp",
                "recall_inadimplente",
                "precision_inadimplente",
                "taxa_reprovacao",
                "threshold",
            )
        },
        "confusion_matrix_test": metrics.get("confusion_matrix"),
        "training_seconds": elapsed_seconds,
        "artifacts": {
            "model_path": model_path,
            "metadata_path": metadata_path,
            "demo_holdout_path": str(config.resolve_demo_holdout_path()),
        },
    }


def run_training(
    artifacts_path: str | None = None,
    config: ModelConfig | None = None,
) -> str:
    """Executa pipeline completo de treino, avaliação e exportação."""
    config = config or get_model_config()
    fs = get_s3_filesystem()
    abt_path = config.resolve_abt_path()

    print("Setup treino LightGBM")
    print(f"Config: {config.config_path}")
    print(f"ABT: {abt_path}")
    print(
        f"Splits: treino={config.split_train:.1%} | teste={config.split_test:.1%} | "
        f"demo={config.split_demo:.1%} | threshold={config.business_threshold}"
    )

    abt = read_parquet(abt_path, fs)
    print(f"Carregado: {abt.shape[0]:,} linhas x {abt.shape[1]} colunas")
    qa_abt_load(abt, config)

    df_train, df_test, df_demo = split_abt_three_way(abt, config)
    demo_path = config.resolve_demo_holdout_path()
    write_parquet(df_demo, demo_path, fs=fs if is_s3_path(demo_path) else None)
    print(f"Holdout demo salvo: {demo_path} ({len(df_demo):,} linhas)")

    X_train, y_train = split_features_target(df_train, config)
    X_test, y_test = split_features_target(df_test, config)
    categorical_columns = X_train.select_dtypes(include=["object", "string", "category"]).columns.tolist()

    print(f"Features ({config.feature_set}): {X_train.shape[1]}")
    print(f"Treino: {len(X_train):,} | Teste: {len(X_test):,} | Demo: {len(df_demo):,}")
    print(f"Taxa TARGET treino: {y_train.mean():.2%} | teste: {y_test.mean():.2%}")

    X_train_boost, X_test_boost = prepare_boosters_data(X_train, X_test, categorical_columns)
    model, scale_pos_weight, elapsed = train_lgbm(X_train_boost, y_train, config, categorical_columns)
    metrics = evaluate_model(model, X_test_boost, y_test, config)

    print("\n[MÉTRICAS] Conjunto de teste (19,9%)")
    print_metrics("LightGBM", metrics, config)
    print("\nClassification report:")
    print(metrics["classification_report"])

    if artifacts_path is None:
        artifacts_path = config.resolve_model_artifact_path()
    metadata_path = config.resolve_metadata_path()
    metadata = build_metadata(
        config=config,
        metrics=metrics,
        scale_pos_weight=scale_pos_weight,
        feature_columns=X_train_boost.columns.tolist(),
        split_sizes={"train": len(df_train), "test": len(df_test), "demo": len(df_demo)},
        model_path=artifacts_path,
        metadata_path=metadata_path,
        elapsed_seconds=elapsed,
    )

    print("\n[EXPORTAÇÃO] Salvando modelo e metadados")
    print(f"  Modelo: {artifacts_path}")
    export_model(model, artifacts_path, fs if is_s3_path(artifacts_path) else None)
    export_metadata(
        metadata_path,
        metadata,
        fs if is_s3_path(metadata_path) else None,
    )
    print(f"  Metadados: {metadata_path}")
    print(f"  Tempo de treino: {elapsed:.1f}s")
    return artifacts_path


if __name__ == "__main__":
    run_training()
