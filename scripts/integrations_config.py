"""Carrega e expoe configuracao central de integracoes externas."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "integrations.yaml"

_DEFAULT_KAGGLE_COMPETITION = "home-credit-default-risk"
_DEFAULT_EXPECTED_RAW_FILES: tuple[str, ...] = (
    "HomeCredit_columns_description.csv",
    "POS_CASH_balance.csv",
    "application_test.csv",
    "application_train.csv",
    "bureau.csv",
    "bureau_balance.csv",
    "credit_card_balance.csv",
    "installments_payments.csv",
    "previous_application.csv",
    "sample_submission.csv",
)
_DEFAULT_MINIO_ENDPOINT_URL = "http://minio:9000"
_DEFAULT_RAW_BUCKET = "raw"
_DEFAULT_PROJECT_BUCKETS: tuple[str, ...] = ("raw", "clean", "abt", "artifacts")
_DEFAULT_CREDIA_HOLDOUT_PATH_S3 = "s3://abt/abt_demo_holdout.parquet"
_DEFAULT_GEMINI_MODEL = "gemini-flash-lite-latest"
_DEFAULT_GEMINI_FALLBACKS: tuple[str, ...] = (
    "gemini-2.0-flash-lite",
    "gemini-2.5-flash-lite",
)
_DEFAULT_GEMINI_TIMEOUT_SECONDS = 20
_DEFAULT_GEMINI_TEMPERATURE = 0.2
_DEFAULT_GEMINI_TOP_P = 0.9
_DEFAULT_GEMINI_MAX_OUTPUT_TOKENS = 900


@dataclass(frozen=True)
class KaggleConfig:
    """Configuracao de ingestao Kaggle versionada no repositorio."""

    competition_name: str
    expected_raw_files: tuple[str, ...]


@dataclass(frozen=True)
class MinioPathsConfig:
    """Caminhos S3 usados pelas integracoes externas."""

    demo_holdout_path_s3: str

    @property
    def credia_demo_holdout_path_s3(self) -> str:
        """Compatibilidade retroativa para chave antiga."""
        return self.demo_holdout_path_s3


@dataclass(frozen=True)
class MinioConfig:
    """Configuracao nao sensivel de endpoint e buckets do MinIO."""

    endpoint_url: str
    raw_bucket: str
    project_buckets: tuple[str, ...]
    paths: MinioPathsConfig


@dataclass(frozen=True)
class GeminiGenerationConfig:
    """Hiperparametros de geracao do Gemini."""

    temperature: float
    top_p: float
    max_output_tokens: int


@dataclass(frozen=True)
class GeminiConfig:
    """Configuracao operacional do provedor Gemini."""

    model: str
    model_fallbacks: tuple[str, ...]
    timeout_seconds: int
    generation: GeminiGenerationConfig


@dataclass(frozen=True)
class IntegrationsConfig:
    """Snapshot imutavel da configuracao das integracoes externas."""

    raw: dict[str, Any]
    config_path: Path
    kaggle: KaggleConfig
    minio: MinioConfig
    gemini: GeminiConfig


def resolve_default_integrations_path() -> Path:
    """Resolve o YAML padrao de integracoes externas."""
    return DEFAULT_CONFIG_PATH


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    if not isinstance(raw, dict):
        raise ValueError("integrations.yaml deve conter um objeto no topo")
    return raw


def _coerce_csv_env(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _coerce_sequence(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return _coerce_csv_env(value)
    return []


def _env_or_yaml_string(env_key: str, yaml_value: Any, default: str) -> str:
    env_value = os.getenv(env_key, "").strip()
    if env_value:
        return env_value
    yaml_text = str(yaml_value).strip() if yaml_value is not None else ""
    return yaml_text or default


def _env_or_yaml_list(env_key: str, yaml_value: Any, default: tuple[str, ...]) -> tuple[str, ...]:
    env_items = _coerce_csv_env(os.getenv(env_key))
    if env_items:
        return tuple(env_items)
    yaml_items = _coerce_sequence(yaml_value)
    if yaml_items:
        return tuple(yaml_items)
    return default


def _env_or_yaml_int(env_key: str, yaml_value: Any, default: int) -> int:
    env_value = os.getenv(env_key, "").strip()
    if env_value:
        return int(env_value)
    if yaml_value is not None:
        return int(yaml_value)
    return default


def _env_or_yaml_float(env_key: str, yaml_value: Any, default: float) -> float:
    env_value = os.getenv(env_key, "").strip()
    if env_value:
        return float(env_value)
    if yaml_value is not None:
        return float(yaml_value)
    return default


def load_integrations_config(config_path: str | Path | None = None) -> IntegrationsConfig:
    """Carrega configuracao de integracoes com precedencia env > YAML > default."""
    path = Path(config_path) if config_path else resolve_default_integrations_path()
    raw = _read_yaml(path)

    kaggle_raw = raw.get("kaggle", {}) if isinstance(raw.get("kaggle"), dict) else {}
    minio_raw = raw.get("minio", {}) if isinstance(raw.get("minio"), dict) else {}
    minio_paths_raw = (
        minio_raw.get("paths", {}) if isinstance(minio_raw.get("paths"), dict) else {}
    )
    gemini_raw = raw.get("gemini", {}) if isinstance(raw.get("gemini"), dict) else {}
    generation_raw = (
        gemini_raw.get("generation", {})
        if isinstance(gemini_raw.get("generation"), dict)
        else {}
    )

    kaggle = KaggleConfig(
        competition_name=_env_or_yaml_string(
            "KAGGLE_COMPETITION_NAME",
            kaggle_raw.get("competition_name"),
            _DEFAULT_KAGGLE_COMPETITION,
        ),
        expected_raw_files=_env_or_yaml_list(
            "KAGGLE_EXPECTED_RAW_FILES",
            kaggle_raw.get("expected_raw_files"),
            _DEFAULT_EXPECTED_RAW_FILES,
        ),
    )

    minio = MinioConfig(
        endpoint_url=_env_or_yaml_string(
            "MINIO_ENDPOINT_URL",
            minio_raw.get("endpoint_url"),
            _DEFAULT_MINIO_ENDPOINT_URL,
        ),
        raw_bucket=_env_or_yaml_string("RAW_BUCKET", minio_raw.get("raw_bucket"), _DEFAULT_RAW_BUCKET),
        project_buckets=_env_or_yaml_list(
            "PROJECT_BUCKETS",
            minio_raw.get("project_buckets"),
            _DEFAULT_PROJECT_BUCKETS,
        ),
        paths=MinioPathsConfig(
            demo_holdout_path_s3=_env_or_yaml_string(
                "DEMO_HOLDOUT_PATH",
                minio_paths_raw.get("credia_demo_holdout_path_s3")
                or minio_paths_raw.get("demo_holdout_path_s3"),
                _DEFAULT_CREDIA_HOLDOUT_PATH_S3,
            )
        ),
    )

    gemini = GeminiConfig(
        model=_env_or_yaml_string("GEMINI_MODEL", gemini_raw.get("model"), _DEFAULT_GEMINI_MODEL),
        model_fallbacks=_env_or_yaml_list(
            "GEMINI_MODEL_FALLBACKS",
            gemini_raw.get("model_fallbacks"),
            _DEFAULT_GEMINI_FALLBACKS,
        ),
        timeout_seconds=_env_or_yaml_int(
            "GEMINI_TIMEOUT_SECONDS",
            gemini_raw.get("timeout_seconds"),
            _DEFAULT_GEMINI_TIMEOUT_SECONDS,
        ),
        generation=GeminiGenerationConfig(
            temperature=_env_or_yaml_float(
                "GEMINI_TEMPERATURE",
                generation_raw.get("temperature"),
                _DEFAULT_GEMINI_TEMPERATURE,
            ),
            top_p=_env_or_yaml_float(
                "GEMINI_TOP_P",
                generation_raw.get("top_p"),
                _DEFAULT_GEMINI_TOP_P,
            ),
            max_output_tokens=_env_or_yaml_int(
                "GEMINI_MAX_OUTPUT_TOKENS",
                generation_raw.get("max_output_tokens"),
                _DEFAULT_GEMINI_MAX_OUTPUT_TOKENS,
            ),
        ),
    )

    return IntegrationsConfig(
        raw=raw,
        config_path=path,
        kaggle=kaggle,
        minio=minio,
        gemini=gemini,
    )


@lru_cache(maxsize=1)
def get_integrations_config() -> IntegrationsConfig:
    """Retorna configuracao cacheada de integracoes."""
    return load_integrations_config()
