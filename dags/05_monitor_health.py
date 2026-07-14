"""DAG de monitoramento mínimo de MLOps (saúde, artefatos, coerência)."""

from datetime import datetime

from airflow.sdk import dag, task

from scripts.mlops_monitoring import run_monitoring


@dag(
    dag_id="05_monitor_health",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    tags=["credit-risk", "mlops", "monitoring"],
)
def monitor_health():
    """Dispara checagens pós-deploy e publica relatório no MinIO."""

    @task(task_id="run_monitoring_checks")
    def run_monitoring_task() -> dict[str, object]:
        """Executa o script de monitoramento e falha se overall=fail."""
        return run_monitoring(fail_on_error=True)

    run_monitoring_task()


monitor_health()
