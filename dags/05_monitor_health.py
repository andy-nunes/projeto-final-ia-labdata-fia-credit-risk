"""DAG de monitoramento mínimo de MLOps (saúde, artefatos, coerência)."""

from datetime import datetime, timedelta

from airflow.sdk import dag, task

from scripts.dag_freshness import has_fresh_model_training
from scripts.mlops_monitoring import run_monitoring

TRAIN_FRESHNESS = timedelta(hours=24)
MONITOR_INTERVAL = timedelta(minutes=5)


@dag(
    dag_id="05_monitor_health",
    start_date=datetime(2026, 1, 1),
    schedule=MONITOR_INTERVAL,
    catchup=False,
    max_active_runs=1,
    tags=["credit-risk", "mlops", "monitoring"],
)
def monitor_health():
    """Checagens pós-treino e periódicas enquanto o treino estiver fresco (24h)."""

    @task.short_circuit(task_id="ensure_training_freshness")
    def ensure_training_freshness() -> bool:
        """Segue apenas se ``trained_at`` do modelo estiver nas últimas 24h."""
        return has_fresh_model_training(within=TRAIN_FRESHNESS)

    @task(task_id="run_monitoring_checks")
    def run_monitoring_task() -> dict[str, object]:
        """Executa o script de monitoramento e falha se overall=fail."""
        return run_monitoring(fail_on_error=True)

    ensure_training_freshness() >> run_monitoring_task()


monitor_health()
