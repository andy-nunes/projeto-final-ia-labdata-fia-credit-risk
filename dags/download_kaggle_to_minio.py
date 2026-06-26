"""DAG manual que substitui arquivos Kaggle no bucket raw do MinIO."""

from datetime import datetime

from airflow.sdk import dag, task

from scripts.kaggle_to_minio import replace_kaggle_raw_files


@dag(
    dag_id="download_kaggle_to_minio",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    tags=["credit-risk", "kaggle", "minio"],
)
def download_kaggle_to_minio():
    """Define a DAG manual de carga dos dados brutos para o MinIO."""
    @task
    def download_and_upload() -> dict[str, object]:
        """Executa o script que substitui os CSVs no bucket raw."""
        return replace_kaggle_raw_files()

    download_and_upload()


download_kaggle_to_minio()
