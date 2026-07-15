"""Testes estruturais das DAGs de treino e monitoramento."""

from datetime import timedelta
from pathlib import Path

import pytest

pytest.importorskip("airflow")

from airflow.models import DagBag

pytestmark = pytest.mark.airflow

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DAGS_DIR = PROJECT_ROOT / "dags"


@pytest.fixture(scope="module")
def monitor_bag():
    """Carrega as DAGs de treino/monitoramento sem exemplos do Airflow."""
    bag = DagBag(dag_folder=str(DAGS_DIR), include_examples=False)
    relevant_errors = {
        path: error
        for path, error in bag.import_errors.items()
        if "04_model_train" in path or "05_monitor_health" in path
    }
    assert relevant_errors == {}, relevant_errors
    return bag


def test_model_train_triggers_monitor_health(monitor_bag) -> None:
    """Após o treino, dispara a DAG de monitoramento."""
    train_dag = monitor_bag.dags["04_model_train_lightgbm"]
    assert train_dag.schedule is None
    assert "trigger_monitor_health" in train_dag.task_ids
    train_task = train_dag.get_task("run_training_script")
    trigger = train_dag.get_task("trigger_monitor_health")
    assert train_task.downstream_task_ids == {"trigger_monitor_health"}
    assert trigger.trigger_dag_id == "05_monitor_health"


def test_monitor_health_schedule_and_freshness_gate(monitor_bag) -> None:
    """Monitoramento a cada 5 min, condicionado à freshness de 24h do treino."""
    monitor_dag = monitor_bag.dags["05_monitor_health"]
    schedule = monitor_dag.schedule
    assert schedule == timedelta(minutes=5) or getattr(schedule, "delta", None) == timedelta(
        minutes=5
    ) or getattr(getattr(monitor_dag, "timetable", None), "_delta", None) == timedelta(
        minutes=5
    )
    assert monitor_dag.catchup is False
    assert monitor_dag.max_active_runs == 1
    assert set(monitor_dag.task_ids) == {
        "ensure_training_freshness",
        "run_monitoring_checks",
    }
    gate = monitor_dag.get_task("ensure_training_freshness")
    checks = monitor_dag.get_task("run_monitoring_checks")
    assert gate.downstream_task_ids == {"run_monitoring_checks"}
    assert checks.upstream_task_ids == {"ensure_training_freshness"}
