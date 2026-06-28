"""Testes pytest estruturais da DAG Silver fundida."""

from pathlib import Path

import pytest
from airflow.models import DagBag

from scripts.silver_transformations import SILVER_TABLES


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DAGS_DIR = PROJECT_ROOT / "dags"


@pytest.fixture(scope="module")
def dag_bag() -> DagBag:
    """Carrega as DAGs do projeto uma vez para o módulo."""
    return DagBag(dag_folder=str(DAGS_DIR), include_examples=False)


def test_only_merged_silver_dag_loads(dag_bag: DagBag) -> None:
    """Mantém a DAG fundida e remove a DAG exclusiva de validação."""
    relevant_errors = {
        path: error
        for path, error in dag_bag.import_errors.items()
        if "silver" in path
    }
    assert relevant_errors == {}
    assert "raw_to_clean_silver" in dag_bag.dags
    assert "validate_clean_silver" not in dag_bag.dags


def test_merged_dag_has_eight_groups_and_twenty_four_tasks(dag_bag: DagBag) -> None:
    """Cria um grupo de três tasks para cada tabela."""
    dag = dag_bag.dags["raw_to_clean_silver"]
    expected_groups = {table_id.lower() for table_id in SILVER_TABLES}

    assert set(dag.task_group.children) == expected_groups
    assert len(dag.tasks) == 24
    for group_id in expected_groups:
        assert {task.task_id for task in dag.task_group.children[group_id].children.values()} == {
            f"{group_id}.coletar_e_processar",
            f"{group_id}.validar",
            f"{group_id}.escrever_clean",
        }


def test_each_group_has_an_isolated_three_task_chain(dag_bag: DagBag) -> None:
    """Encadeia somente tasks da mesma tabela e não conecta grupos."""
    dag = dag_bag.dags["raw_to_clean_silver"]
    for table_id in SILVER_TABLES:
        group_id = table_id.lower()
        collect = dag.get_task(f"{group_id}.coletar_e_processar")
        validate = dag.get_task(f"{group_id}.validar")
        write = dag.get_task(f"{group_id}.escrever_clean")

        assert collect.upstream_task_ids == set()
        assert collect.downstream_task_ids == {validate.task_id}
        assert validate.upstream_task_ids == {collect.task_id}
        assert validate.downstream_task_ids == {write.task_id}
        assert write.upstream_task_ids == {validate.task_id}
        assert write.downstream_task_ids == set()


def test_merged_dag_is_manual_and_memory_bounded(dag_bag: DagBag) -> None:
    """Mantém execução manual e no máximo duas tasks ativas."""
    dag = dag_bag.dags["raw_to_clean_silver"]
    assert dag.schedule is None
    assert dag.max_active_tasks == 2
