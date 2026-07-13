import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

fake_lightgbm = types.ModuleType('lightgbm')


class DummyLGBMClassifier:
    pass


fake_lightgbm.LGBMClassifier = DummyLGBMClassifier
sys.modules.setdefault('lightgbm', fake_lightgbm)

from scripts.predict import build_prediction_matrix, get_business_threshold
from scripts.model_config import get_model_config


def test_resolve_model_artifact_path_uses_full_s3_path_from_config(monkeypatch) -> None:
    monkeypatch.setenv('ARTIFACTS_PATH', 's3://artifacts')

    config = get_model_config()
    resolved = config.resolve_model_artifact_path(prefer_s3=True)

    assert resolved == 's3://artifacts/lightgbm_hcdr.pkl'


def test_resolve_metadata_path_uses_full_s3_path_from_config() -> None:
    resolved = get_model_config().resolve_metadata_path(prefer_s3=True)

    assert resolved == 's3://artifacts/model_metadata.json'


def test_get_business_threshold_from_central_config() -> None:
    assert get_business_threshold() == get_model_config().business_threshold
    assert get_business_threshold() == 0.08


def test_build_prediction_matrix_uses_drop_cols_from_config() -> None:
    import pandas as pd

    config = get_model_config()
    input_df = pd.DataFrame(
        {
            config.id_column: [100002],
            config.target_column: [0],
            "AMT_CREDIT": [250000.0],
            "AMT_ANNUITY": [12000.0],
        }
    )

    matrix = build_prediction_matrix(input_df, config)

    assert config.id_column not in matrix.columns
    assert config.target_column not in matrix.columns
    assert "AMT_CREDIT" in matrix.columns
