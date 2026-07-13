"""Testes estruturais da DAG Gold sequencial."""

from pathlib import Path

import pytest
from airflow.models import DagBag


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DAGS_DIR = PROJECT_ROOT / "dags"


@pytest.fixture(scope="module")
def gold_dag():
    """Carrega e devolve a DAG Gold sem exemplos do Airflow."""
    bag = DagBag(dag_folder=str(DAGS_DIR), include_examples=False)
    relevant_errors = {
        path: error for path, error in bag.import_errors.items() if "gold" in path
    }
    assert relevant_errors == {}
    return bag.dags["03_gold_abt_features"]


def test_gold_dag_is_manual_sequential_and_grouped(gold_dag) -> None:
    """Mantém configuração manual, sete grupos e dezoito tasks."""
    assert gold_dag.schedule is None
    assert gold_dag.catchup is False
    assert gold_dag.max_active_runs == 1
    assert set(gold_dag.task_group.children) == {
        "application_train",
        "bureau",
        "pos_cash",
        "credit_card",
        "previous_application",
        "installments",
        "abt_final",
        "trigger_model_training",
    }
    assert len(gold_dag.tasks) == 18
    assert "trigger_model_training" in gold_dag.task_ids


def test_gold_dag_has_the_confirmed_task_sequence(gold_dag) -> None:
    """Encadeia todas as fronteiras de processamento, QA, escrita e trigger."""
    sequence = [
        "application_train.processar_application",
        "application_train.validar_application",
        "bureau.processar_bureau",
        "bureau.validar_bureau",
        "bureau.processar_bureau_balance",
        "bureau.validar_bureau_balance",
        "pos_cash.processar_pos_cash",
        "pos_cash.validar_pos_cash",
        "credit_card.processar_credit_card",
        "credit_card.validar_credit_card",
        "previous_application.processar_previous_application",
        "previous_application.validar_previous_application",
        "installments.processar_installments",
        "installments.validar_installments",
        "abt_final.montar_abt",
        "abt_final.validar_abt",
        "abt_final.escrever_abt",
        "trigger_model_training",
    ]

    for current_id, next_id in zip(sequence, sequence[1:]):
        current = gold_dag.get_task(current_id)
        following = gold_dag.get_task(next_id)
        assert current.downstream_task_ids == {next_id}
        assert following.upstream_task_ids == {current_id}
