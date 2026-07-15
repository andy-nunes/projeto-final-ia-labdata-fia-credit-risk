"""Helpers de freshness do modelo treinado (sem acesso ORM ao metadata DB)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


def is_timestamp_fresh(
    latest_end: datetime | None,
    *,
    within: timedelta,
    now: datetime | None = None,
) -> bool:
    """Retorna True se ``latest_end`` está dentro da janela ``within`` a partir de ``now``."""
    if latest_end is None:
        return False

    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    if latest_end.tzinfo is None:
        latest_end = latest_end.replace(tzinfo=timezone.utc)
    return latest_end >= reference - within


def parse_trained_at(value: Any) -> datetime | None:
    """Converte ``trained_at`` ISO-8601 do metadata em ``datetime`` UTC."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def trained_at_from_metadata(metadata: dict[str, Any]) -> datetime | None:
    """Extrai ``trained_at`` de um dicionário de metadata de modelo."""
    return parse_trained_at(metadata.get("trained_at"))


def has_fresh_model_training(
    *,
    within: timedelta,
    now: datetime | None = None,
) -> bool:
    """True se o modelo oficial no MinIO foi treinado dentro da janela ``within``.

    Usa ``trained_at`` de ``model_metadata.json`` (artefato da DAG
    ``04_model_train_lightgbm``), evitando acesso ORM ao metadata DB do Airflow 3.
    """
    from scripts.model_config import load_model_metadata

    try:
        metadata = load_model_metadata()
    except FileNotFoundError:
        return False

    return is_timestamp_fresh(
        trained_at_from_metadata(metadata),
        within=within,
        now=now,
    )
