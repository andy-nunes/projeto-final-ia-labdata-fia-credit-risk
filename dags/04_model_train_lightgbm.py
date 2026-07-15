"""Airflow DAG para treinar o modelo LightGBM a partir da ABT."""

from datetime import datetime

from airflow.providers.standard.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.sdk import dag, task

from scripts.train import run_training


@dag(
    dag_id="04_model_train_lightgbm",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    tags=["credit-risk", "model", "lightgbm", "training"],
)
def train_lightgbm():
    @task(task_id="run_training_script")
    def run_training_task() -> str:
        """Executa o script de treinamento e exporta o modelo."""
        return run_training()

    trigger_monitor_health = TriggerDagRunOperator(
        task_id="trigger_monitor_health",
        trigger_dag_id="05_monitor_health",
        wait_for_completion=False,
        reset_dag_run=True,
    )

    run_training_task() >> trigger_monitor_health


train_lightgbm()
