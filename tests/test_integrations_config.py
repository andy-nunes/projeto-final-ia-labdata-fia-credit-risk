from pathlib import Path

import yaml

from scripts.integrations_config import get_integrations_config, load_integrations_config


def _clear_integrations_env(monkeypatch) -> None:
    for env_key in (
        "KAGGLE_COMPETITION_NAME",
        "KAGGLE_EXPECTED_RAW_FILES",
        "MINIO_ENDPOINT_URL",
        "RAW_BUCKET",
        "PROJECT_BUCKETS",
        "DEMO_HOLDOUT_PATH",
        "GEMINI_MODEL",
        "GEMINI_MODEL_FALLBACKS",
        "GEMINI_TIMEOUT_SECONDS",
        "GEMINI_TEMPERATURE",
        "GEMINI_TOP_P",
        "GEMINI_MAX_OUTPUT_TOKENS",
    ):
        monkeypatch.delenv(env_key, raising=False)


def _write_yaml(path: Path, payload: dict) -> None:
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")


def test_load_integrations_config_from_yaml(tmp_path: Path, monkeypatch) -> None:
    _clear_integrations_env(monkeypatch)
    config_path = tmp_path / "integrations.yaml"
    _write_yaml(
        config_path,
        {
            "kaggle": {
                "competition_name": "custom-competition",
                "expected_raw_files": ["a.csv", "b.csv"],
            },
            "minio": {
                "endpoint_url": "http://localhost:9000",
                "raw_bucket": "bronze",
                "project_buckets": ["bronze", "silver", "gold", "artifacts"],
                "paths": {"demo_holdout_path_s3": "s3://gold/demo.parquet"},
            },
            "gemini": {
                "model": "gemini-x",
                "model_fallbacks": ["gemini-y", "gemini-z"],
                "timeout_seconds": 33,
                "generation": {
                    "temperature": 0.4,
                    "top_p": 0.8,
                    "max_output_tokens": 777,
                },
            },
        },
    )

    cfg = load_integrations_config(config_path)

    assert cfg.kaggle.competition_name == "custom-competition"
    assert cfg.kaggle.expected_raw_files == ("a.csv", "b.csv")
    assert cfg.minio.endpoint_url == "http://localhost:9000"
    assert cfg.minio.raw_bucket == "bronze"
    assert cfg.minio.project_buckets == ("bronze", "silver", "gold", "artifacts")
    assert cfg.minio.paths.demo_holdout_path_s3 == "s3://gold/demo.parquet"
    assert cfg.gemini.model == "gemini-x"
    assert cfg.gemini.model_fallbacks == ("gemini-y", "gemini-z")
    assert cfg.gemini.timeout_seconds == 33
    assert cfg.gemini.generation.temperature == 0.4
    assert cfg.gemini.generation.top_p == 0.8
    assert cfg.gemini.generation.max_output_tokens == 777


def test_env_precedence_over_yaml(tmp_path: Path, monkeypatch) -> None:
    _clear_integrations_env(monkeypatch)
    config_path = tmp_path / "integrations.yaml"
    _write_yaml(
        config_path,
        {
            "kaggle": {"competition_name": "yaml-competition"},
            "minio": {
                "raw_bucket": "yaml-raw",
                "paths": {"demo_holdout_path_s3": "s3://yaml/demo.parquet"},
            },
            "gemini": {
                "model": "yaml-model",
                "model_fallbacks": ["yaml-fallback"],
                "timeout_seconds": 11,
            },
        },
    )

    monkeypatch.setenv("KAGGLE_COMPETITION_NAME", "env-competition")
    monkeypatch.setenv("RAW_BUCKET", "env-raw")
    monkeypatch.setenv("DEMO_HOLDOUT_PATH", "s3://env/demo.parquet")
    monkeypatch.setenv("GEMINI_MODEL", "env-model")
    monkeypatch.setenv("GEMINI_MODEL_FALLBACKS", "env-fallback-1,env-fallback-2")
    monkeypatch.setenv("GEMINI_TIMEOUT_SECONDS", "44")

    cfg = load_integrations_config(config_path)

    assert cfg.kaggle.competition_name == "env-competition"
    assert cfg.minio.raw_bucket == "env-raw"
    assert cfg.minio.paths.demo_holdout_path_s3 == "s3://env/demo.parquet"
    assert cfg.gemini.model == "env-model"
    assert cfg.gemini.model_fallbacks == ("env-fallback-1", "env-fallback-2")
    assert cfg.gemini.timeout_seconds == 44


def test_minimum_defaults_without_yaml(monkeypatch) -> None:
    _clear_integrations_env(monkeypatch)

    cfg = load_integrations_config(Path("/tmp/does-not-exist-integrations.yaml"))

    assert cfg.kaggle.competition_name == "home-credit-default-risk"
    assert "application_train.csv" in cfg.kaggle.expected_raw_files
    assert cfg.minio.endpoint_url == "http://minio:9000"
    assert cfg.minio.raw_bucket == "raw"
    assert cfg.minio.project_buckets == ("raw", "clean", "abt", "artifacts")
    assert cfg.minio.paths.demo_holdout_path_s3 == "s3://abt/abt_demo_holdout.parquet"
    assert cfg.gemini.model == "gemini-flash-lite-latest"
    assert cfg.gemini.model_fallbacks == ("gemini-2.0-flash-lite", "gemini-2.5-flash-lite")
    assert cfg.gemini.timeout_seconds == 20


def test_get_integrations_config_returns_cached(tmp_path: Path, monkeypatch) -> None:
    _clear_integrations_env(monkeypatch)
    config_path = tmp_path / "integrations.yaml"
    _write_yaml(config_path, {"gemini": {"model": "cached-model"}})

    monkeypatch.setattr(
        "scripts.integrations_config.resolve_default_integrations_path",
        lambda: config_path,
    )
    get_integrations_config.cache_clear()

    first = get_integrations_config()
    second = get_integrations_config()

    assert first is second
    assert first.gemini.model == "cached-model"
