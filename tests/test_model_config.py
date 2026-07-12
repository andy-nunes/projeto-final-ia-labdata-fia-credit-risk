import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from scripts.model_config import ModelConfig, load_model_config, write_metadata
from scripts.abt_to_model_lightgbm import split_abt_three_way, split_features_target


@pytest.fixture
def sample_config(tmp_path: Path) -> ModelConfig:
    config_data = {
        "project": {"name": "test", "target_column": "TARGET", "id_column": "SK_ID_CURR"},
        "reproducibility": {"random_state": 42, "full_dataset_rows": 1000},
        "splits": {"train": 0.80, "test": 0.199, "demo_holdout": 0.001},
        "business": {"f_beta": 2, "primary_metric": "pr_auc"},
        "business_rules": {"business_threshold": 0.25},
        "features": {
            "set": "full",
            "drop_cols": ["SK_ID_CURR", "TARGET"],
            "categorical_features": ["feat_cat"],
            "editable_features": ["feat_a"],
            "readonly_features": ["feat_b"],
            "core": ["feat_a"],
            "extended_extra": ["feat_b"],
        },
        "model": {
            "algorithm": "lightgbm",
            "n_estimators": 10,
            "num_leaves": 8,
            "learning_rate": 0.1,
            "max_depth": -1,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
        },
        "paths": {
            "abt_path": "Dados/abt/abt_train.parquet",
            "abt_path_s3": "s3://abt/abt_train.parquet",
            "demo_holdout_path": "Dados/abt/abt_demo_holdout.parquet",
            "model_artifact_path": "artifacts/lightgbm_hcdr.pkl",
            "model_artifact_path_s3": "s3://artifacts/lightgbm_hcdr.pkl",
            "metadata_path": "artifacts/model_metadata.json",
            "metadata_path_s3": "s3://artifacts/model_metadata.json",
        },
        "api": {"base_url": "http://localhost:8000"},
        "minio": {"endpoint_url": "http://minio:9000", "key": "a", "secret": "b"},
        "metadata": {"version": "test", "description": "test"},
    }
    config_path = tmp_path / "model_config.yaml"
    config_path.write_text(yaml.safe_dump(config_data), encoding="utf-8")
    return load_model_config(config_path)


def test_split_abt_three_way_respects_fractions(sample_config: ModelConfig) -> None:
    rng = pd.Series([0, 1] * 5000)
    df = pd.DataFrame({"SK_ID_CURR": range(10000), "TARGET": rng, "feat_a": 1.0})
    train, test, demo = split_abt_three_way(df, sample_config)
    total = len(df)
    assert len(train) + len(test) + len(demo) == total
    assert abs(len(train) / total - 0.80) < 0.01
    assert abs(len(test) / total - 0.199) < 0.01
    assert abs(len(demo) / total - 0.001) < 0.002


def test_feature_columns_full_excludes_drop_cols(sample_config: ModelConfig) -> None:
    cols = ["SK_ID_CURR", "TARGET", "feat_a", "feat_b"]
    selected = sample_config.feature_columns(cols)
    assert selected == ["feat_a", "feat_b"]


def test_governance_properties_exposed(sample_config: ModelConfig) -> None:
    assert sample_config.business_threshold == 0.25
    assert sample_config.editable_features == ["feat_a"]
    assert sample_config.readonly_features == ["feat_b"]
    assert sample_config.categorical_features == ["feat_cat"]
    assert sample_config.api_base_url == "http://localhost:8000"


def test_write_metadata_creates_json(tmp_path: Path) -> None:
    target = tmp_path / "meta.json"
    write_metadata(target, {"trained_at": "2026-01-01", "threshold": 0.25})
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["threshold"] == 0.25
