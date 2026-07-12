"""DAG manual com um pipeline Silver isolado por tabela."""

from datetime import datetime

from airflow.sdk import dag, get_current_context, task, task_group

from scripts.silver_pipeline import (
    collect_and_process,
    validate_staged,
    write_clean,
)
from scripts.silver_transformations import SILVER_TABLES


@dag(
    dag_id="raw_to_clean_silver",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    max_active_tasks=2,
    tags=["credit-risk", "minio", "silver", "clean", "quality"],
)
def raw_to_clean_silver():
    """Define oito grupos independentes de processamento, QA e publicação."""

    @task_group
    def silver_table_group(table_id: str):
        """Cria a cadeia isolada de uma tabela Silver."""

        @task(task_id="coletar_e_processar")
        def collect_task(selected_table: str) -> dict[str, object]:
            """Coleta o CSV raw e produz o Parquet no staging compartilhado."""
            context = get_current_context()
            return collect_and_process(selected_table, context["run_id"])

        @task(task_id="validar")
        def validate_task(metadata: dict[str, object]) -> dict[str, object]:
            """Executa todas as regras de QA sobre o staging da tabela."""
            return validate_staged(metadata)

        @task(task_id="escrever_clean")
        def write_task(metadata: dict[str, object]) -> dict[str, object]:
            """Publica somente o Parquet aprovado e remove seu staging."""
            return write_clean(metadata)

        collected = collect_task(table_id)
        validated = validate_task(collected)
        write_task(validated)

    for table_id in SILVER_TABLES:
        silver_table_group.override(group_id=table_id.lower())(table_id)


raw_to_clean_silver()
