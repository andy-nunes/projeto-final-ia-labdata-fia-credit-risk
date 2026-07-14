"""Testes unitários do monitoramento MLOps e da automação de triagem."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.credit_automation import (
    build_automation_event,
    classify_triage_action,
    publish_automation_event,
    triage_label,
)
from scripts.mlops_monitoring import (
    compute_categorical_psi,
    compute_psi,
    merge_status,
    _psi_status,
)


def test_merge_status_picks_worst() -> None:
    """Garante que fail vence warn e ok."""
    assert merge_status("ok", "warn") == "warn"
    assert merge_status("warn", "fail", "ok") == "fail"
    assert merge_status("ok", "ok") == "ok"


def test_compute_psi_is_low_for_identical_distributions() -> None:
    """Distribuições iguais devem produzir PSI próximo de zero."""
    series = pd.Series(np.linspace(0.0, 1.0, 200))
    psi_value = compute_psi(series, series.sample(frac=1.0, random_state=42))
    assert psi_value < 0.05


def test_compute_psi_rises_with_shifted_distribution() -> None:
    """Distribuição deslocada deve elevar o PSI."""
    baseline = pd.Series(np.random.default_rng(42).normal(0.0, 1.0, 1000))
    shifted = pd.Series(np.random.default_rng(42).normal(2.0, 1.0, 1000))
    assert compute_psi(baseline, shifted) > compute_psi(baseline, baseline.sample(500))


def test_compute_categorical_psi_detects_category_shift() -> None:
    """Mudança de proporção categórica deve elevar o PSI."""
    expected = pd.Series(["A"] * 90 + ["B"] * 10)
    actual = pd.Series(["A"] * 50 + ["B"] * 50)
    assert compute_categorical_psi(expected, actual) > 0.1


@pytest.mark.parametrize(
    ("psi_value", "expected"),
    [
        (0.05, "ok"),
        (0.15, "warn"),
        (0.30, "fail"),
    ],
)
def test_psi_status_thresholds(psi_value: float, expected: str) -> None:
    """Limiares warn/fail do PSI seguem o pipeline_config."""
    assert _psi_status(psi_value, psi_warn=0.10, psi_fail=0.25) == expected


@pytest.mark.parametrize(
    ("probability", "threshold", "expected"),
    [
        (0.02, 0.08, "autoaprovacao_candidata"),
        (0.05, 0.08, "mesa_analise"),
        (0.08, 0.08, "recusa_candidata"),
        (0.20, 0.08, "recusa_candidata"),
    ],
)
def test_classify_triage_action(probability: float, threshold: float, expected: str) -> None:
    """Faixas de triagem alinhadas ao threshold de negócio."""
    assert classify_triage_action(probability, threshold) == expected
    assert triage_label(expected)


def test_build_automation_event_marks_human_in_the_loop() -> None:
    """Evento de automação sempre exige humano no loop."""
    score = {
        "sk_id_curr": 139767,
        "probability": 0.045,
        "prediction": 0,
        "threshold": 0.08,
        "risk_band": "Risco moderado",
        "label": "Aprovado (Pagador Saudável)",
        "top_risk_factors": [("AMT_CREDIT", 12.0)],
        "top_positive_factors": [("EXT_SOURCE_2", 20.0)],
        "applied_overrides": {},
    }
    event = build_automation_event(score)
    assert event["action"] == "mesa_analise"
    assert event["human_in_the_loop"] is True
    assert event["client_id"] == 139767
    assert event["event_type"] == "credit_decision_triage"


def test_publish_automation_event_writes_json(tmp_path: Path, monkeypatch) -> None:
    """Publicação grava JSON local via filesystem fake compatível com s3fs API."""

    class FakeFS:
        def __init__(self) -> None:
            self.files: dict[str, bytes] = {}

        def makedirs(self, path: str, exist_ok: bool = False) -> None:
            return None

        def open(self, path: str, mode: str = "rb"):
            if "w" in mode:
                parent = tmp_path / path.replace("s3://", "")
                parent.parent.mkdir(parents=True, exist_ok=True)

                class Writer:
                    def __init__(self, target: Path) -> None:
                        self.target = target
                        self.buffer = bytearray()

                    def write(self, data: bytes) -> int:
                        self.buffer.extend(data)
                        return len(data)

                    def __enter__(self):
                        return self

                    def __exit__(self, *args):
                        self.target.write_bytes(bytes(self.buffer))

                return Writer(parent)
            raise FileNotFoundError(path)

    event = {
        "event_type": "credit_decision_triage",
        "client_id": 1,
        "action": "mesa_analise",
        "human_in_the_loop": True,
    }
    monkeypatch.setenv(
        "AUTOMATION_EVENTS_PREFIX",
        f"s3://artifacts/automation/events",
    )
    published = publish_automation_event(event, fs=FakeFS())
    assert "storage" in published
    path = published["storage"]["event_path"]
    assert "/mesa_analise/" in path
    assert path.endswith("_1.json")
    assert published["storage"]["queue_prefix"].endswith("/mesa_analise")
