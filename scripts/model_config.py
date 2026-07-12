"""Carrega e expõe a configuração central do modelo LightGBM."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "model_config.yaml"


@dataclass(frozen=True)
class ModelConfig:
    """Snapshot imutável da configuração do modelo."""

    raw: dict[str, Any]
    config_path: Path

    @property
    def target_column(self) -> str:
        return str(self.raw["project"]["target_column"])

    @property
    def id_column(self) -> str:
        return str(self.raw["project"]["id_column"])

    @property
    def random_state(self) -> int:
        return int(self.raw["reproducibility"]["random_state"])

    @property
    def full_dataset_rows(self) -> int:
        return int(self.raw["reproducibility"]["full_dataset_rows"])

    @property
    def split_train(self) -> float:
        return float(self.raw["splits"]["train"])

    @property
    def split_test(self) -> float:
        return float(self.raw["splits"]["test"])

    @property
    def split_demo(self) -> float:
        return float(self.raw["splits"]["demo_holdout"])

    @property
    def business_threshold(self) -> float:
        """Threshold de negócio para classificação binária (0 ou 1)."""
        business_rules = self.raw.get("business_rules", {})
        if "business_threshold" in business_rules:
            return float(business_rules["business_threshold"])
        return float(self.raw["business"]["threshold"])

    @property
    def f_beta(self) -> float:
        return float(self.raw["business"]["f_beta"])

    @property
    def drop_cols(self) -> list[str]:
        return list(self.raw["features"]["drop_cols"])

    @property
    def categorical_features(self) -> list[str]:
        return list(self.raw["features"]["categorical_features"])

    @property
    def editable_features(self) -> list[str]:
        return list(self.raw["features"]["editable_features"])

    @property
    def readonly_features(self) -> list[str]:
        return list(self.raw["features"]["readonly_features"])

    @property
    def feature_set(self) -> str:
        return str(self.raw["features"]["set"])

    @property
    def model_params(self) -> dict[str, Any]:
        return dict(self.raw["model"])

    @property
    def api_base_url(self) -> str:
        env_url = os.getenv("API_BASE_URL", "").strip()
        if env_url:
            return env_url
        return str(self.raw.get("api", {}).get("base_url", "http://localhost:8000"))

    def _resolve_path_key(self, primary: str, legacy: str) -> str:
        paths = self.raw["paths"]
        if primary in paths:
            return str(paths[primary])
        return str(paths[legacy])

    def resolve_abt_path(self) -> str:
        """Retorna caminho local da ABT se existir; caso contrário, S3."""
        env_path = os.getenv("ABT_PATH", "").strip()
        if env_path:
            return env_path
        local_rel = self._resolve_path_key("abt_path", "abt")
        local_path = REPO_ROOT / local_rel
        if local_path.exists():
            return str(local_path)
        return self._resolve_path_key("abt_path_s3", "abt_s3")

    def resolve_demo_holdout_path(self) -> Path:
        env_path = os.getenv("DEMO_HOLDOUT_PATH", "").strip()
        if env_path:
            return Path(env_path)
        return REPO_ROOT / self._resolve_path_key("demo_holdout_path", "demo_holdout")

    def resolve_model_artifact_path(self, prefer_s3: bool = False) -> str:
        env_path = os.getenv("MODEL_PATH", "").strip()
        if env_path:
            return env_path
        if prefer_s3:
            return self._resolve_path_key("model_artifact_path_s3", "model_artifact_s3")
        local_rel = self._resolve_path_key("model_artifact_path", "model_artifact")
        local_path = REPO_ROOT / local_rel
        if local_path.parent.exists():
            return str(local_path)
        return self._resolve_path_key("model_artifact_path_s3", "model_artifact_s3")

    def resolve_metadata_path(self, prefer_s3: bool = False) -> str:
        env_path = os.getenv("MODEL_METADATA_PATH", "").strip()
        if env_path:
            return env_path
        local_rel = self._resolve_path_key("metadata_path", "metadata")
        local_path = REPO_ROOT / local_rel
        if not prefer_s3:
            return str(local_path)
        return self._resolve_path_key("metadata_path_s3", "metadata_s3")

    def feature_columns(self, available_columns: list[str]) -> list[str]:
        """Resolve colunas de features conforme trilho configurado."""
        drop = set(self.drop_cols)
        available = [col for col in available_columns if col not in drop]
        feature_set = self.feature_set.lower()

        if feature_set == "full":
            return available

        core = list(self.raw["features"]["core"])
        extended_extra = list(self.raw["features"]["extended_extra"])

        if feature_set == "core":
            requested = core
        elif feature_set == "extended":
            requested = core + extended_extra
        else:
            raise ValueError(f"Trilho de features desconhecado: {self.feature_set}")

        missing = [col for col in requested if col not in available_columns]
        if missing:
            raise ValueError(f"Colunas ausentes na ABT para trilho {feature_set}: {missing}")
        return requested


def load_model_config(config_path: str | Path | None = None) -> ModelConfig:
    """Carrega YAML de configuração do modelo."""
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    with path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    _validate_splits(raw)
    return ModelConfig(raw=raw, config_path=path)


@lru_cache(maxsize=1)
def get_model_config() -> ModelConfig:
    """Retorna configuração cacheada (padrão do repositório)."""
    return load_model_config()


def _validate_splits(raw: dict[str, Any]) -> None:
    splits = raw["splits"]
    total = float(splits["train"]) + float(splits["test"]) + float(splits["demo_holdout"])
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"Splits devem somar 1.0; recebido {total:.6f}")


def write_metadata(path: str | Path, metadata: dict[str, Any]) -> None:
    """Persiste metadados do treino em JSON."""
    target = Path(path)
    if str(path).startswith("s3://"):
        raise ValueError("Use export_metadata para caminhos S3")
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = deepcopy(metadata)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def export_metadata(path: str, metadata: dict[str, Any], fs: Any | None = None) -> None:
    """Grava metadados localmente ou no MinIO."""
    payload = json.dumps(metadata, ensure_ascii=False, indent=2).encode("utf-8")
    if str(path).startswith("s3://"):
        if fs is None:
            raise ValueError("Filesystem S3 obrigatório para metadados remotos")
        with fs.open(path, "wb") as handle:
            handle.write(payload)
        return
    write_metadata(path, metadata)
