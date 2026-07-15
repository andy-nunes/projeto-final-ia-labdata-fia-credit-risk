"""Testes do helper de freshness do modelo treinado."""

from datetime import datetime, timedelta, timezone

from scripts.dag_freshness import (
    is_timestamp_fresh,
    parse_trained_at,
    trained_at_from_metadata,
)


def test_is_timestamp_fresh_true_within_window() -> None:
    now = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
    recent = now - timedelta(hours=6)
    assert is_timestamp_fresh(recent, within=timedelta(hours=24), now=now)


def test_is_timestamp_fresh_false_when_stale() -> None:
    now = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
    stale = now - timedelta(hours=25)
    assert not is_timestamp_fresh(stale, within=timedelta(hours=24), now=now)


def test_is_timestamp_fresh_false_when_missing() -> None:
    now = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
    assert not is_timestamp_fresh(None, within=timedelta(hours=24), now=now)


def test_is_timestamp_fresh_accepts_naive_datetimes() -> None:
    now = datetime(2026, 7, 15, 12, 0)
    recent = datetime(2026, 7, 15, 10, 0)
    assert is_timestamp_fresh(recent, within=timedelta(hours=24), now=now)


def test_parse_trained_at_iso_z() -> None:
    parsed = parse_trained_at("2026-07-15T12:00:00Z")
    assert parsed == datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)


def test_trained_at_from_metadata() -> None:
    metadata = {"trained_at": "2026-07-15T10:30:00+00:00"}
    assert trained_at_from_metadata(metadata) == datetime(
        2026, 7, 15, 10, 30, tzinfo=timezone.utc
    )


def test_trained_at_from_metadata_missing() -> None:
    assert trained_at_from_metadata({}) is None
