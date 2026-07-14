"""DAG Bronze que substitui arquivos Kaggle no bucket raw do MinIO."""

from datetime import datetime

from airflow.providers.standard.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.sdk import dag, task

from scripts.kaggle_to_minio import replace_kaggle_raw_files


@dag(
    dag_id="01_bronze_ingest_kaggle",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    tags=["credit-risk", "kaggle", "minio", "bronze"],
)
def download_kaggle_to_minio():
    """Define a DAG Bronze de carga dos dados brutos para o MinIO."""
    @task
    def download_and_upload() -> dict[str, object]:
        """Executa o script que substitui os CSVs no bucket raw."""
        return replace_kaggle_raw_files()

    trigger_silver_pipeline = TriggerDagRunOperator(
        task_id="trigger_silver_pipeline",
        trigger_dag_id="02_silver_clean_data",
        wait_for_completion=False,
        reset_dag_run=True,
    )

    download_and_upload() >> trigger_silver_pipeline


download_kaggle_to_minio()
