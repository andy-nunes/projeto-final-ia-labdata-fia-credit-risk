from __future__ import annotations

from datetime import datetime
from pathlib import Path
import os

from airflow.decorators import dag, task


DATA_DIR = Path(os.getenv("DATA_DIR", "/opt/airflow/Dados"))


@dag(
    dag_id="data_volume_check",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    tags=["credit-risk", "infra"],
)
def data_volume_check():
    @task
    def list_data_files() -> list[str]:
        if not DATA_DIR.exists():
            raise FileNotFoundError(f"Data directory not found: {DATA_DIR}")
        return sorted(str(path.relative_to(DATA_DIR)) for path in DATA_DIR.rglob("*") if path.is_file())

    list_data_files()


data_volume_check()
