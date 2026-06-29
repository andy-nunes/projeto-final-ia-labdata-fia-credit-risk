"""DAG manual e sequencial para construir a ABT da camada Gold."""

from datetime import datetime

from airflow.sdk import dag, get_current_context, task, task_group

from scripts.gold_pipeline import (
    build_abt_stage,
    process_application,
    process_bureau,
    process_bureau_balance,
    process_credit_card,
    process_installments,
    process_pos_cash,
    process_previous_application,
    validate_abt_stage,
    validate_application_stage,
    validate_bureau_balance_stage,
    validate_bureau_stage,
    validate_credit_card_stage,
    validate_installments_stage,
    validate_pos_cash_stage,
    validate_previous_application_stage,
    write_abt,
)


@dag(
    dag_id="clean_to_abt_gold",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    tags=["credit-risk", "minio", "gold", "abt", "quality"],
)
def clean_to_abt_gold():
    """Define sete grupos sequenciais de processamento, QA e publicação."""

    @task_group(group_id="application_train")
    def application_group():
        """Cria e valida as features da base principal."""

        @task(task_id="processar_application")
        def process_task() -> dict[str, object]:
            """Processa application a partir do bucket clean."""
            return process_application(get_current_context()["run_id"])

        @task(task_id="validar_application")
        def validate_task(metadata: dict[str, object]) -> dict[str, object]:
            """Valida application enriquecida no staging."""
            return validate_application_stage(metadata)

        return validate_task(process_task())

    @task_group(group_id="bureau")
    def bureau_group(gate: dict[str, object]):
        """Processa bureau e bureau balance com sua ponte de contratos."""

        @task(task_id="processar_bureau")
        def process_bureau_task(_: dict[str, object]) -> dict[str, object]:
            """Agrega contratos bureau."""
            return process_bureau(get_current_context()["run_id"])

        @task(task_id="validar_bureau")
        def validate_bureau_task(metadata: dict[str, object]) -> dict[str, object]:
            """Valida o agregado bureau."""
            return validate_bureau_stage(metadata)

        @task(task_id="processar_bureau_balance")
        def process_balance_task(_: dict[str, object]) -> dict[str, object]:
            """Agrega o histórico mensal bureau balance."""
            return process_bureau_balance(get_current_context()["run_id"])

        @task(task_id="validar_bureau_balance")
        def validate_balance_task(metadata: dict[str, object]) -> dict[str, object]:
            """Valida o agregado bureau balance."""
            return validate_bureau_balance_stage(metadata)

        bureau_metadata = validate_bureau_task(process_bureau_task(gate))
        return validate_balance_task(process_balance_task(bureau_metadata))

    @task_group(group_id="pos_cash")
    def pos_group(gate: dict[str, object]):
        """Processa e valida o histórico POS/CASH."""

        @task(task_id="processar_pos_cash")
        def process_task(_: dict[str, object]) -> dict[str, object]:
            """Agrega a origem POS/CASH."""
            return process_pos_cash(get_current_context()["run_id"])

        @task(task_id="validar_pos_cash")
        def validate_task(metadata: dict[str, object]) -> dict[str, object]:
            """Valida o agregado POS/CASH."""
            return validate_pos_cash_stage(metadata)

        return validate_task(process_task(gate))

    @task_group(group_id="credit_card")
    def credit_card_group(gate: dict[str, object]):
        """Processa e valida o histórico de cartão."""

        @task(task_id="processar_credit_card")
        def process_task(_: dict[str, object]) -> dict[str, object]:
            """Agrega a origem credit card."""
            return process_credit_card(get_current_context()["run_id"])

        @task(task_id="validar_credit_card")
        def validate_task(metadata: dict[str, object]) -> dict[str, object]:
            """Valida o agregado de cartão."""
            return validate_credit_card_stage(metadata)

        return validate_task(process_task(gate))

    @task_group(group_id="previous_application")
    def previous_group(gate: dict[str, object]):
        """Processa e valida propostas anteriores."""

        @task(task_id="processar_previous_application")
        def process_task(_: dict[str, object]) -> dict[str, object]:
            """Agrega a origem previous application."""
            return process_previous_application(get_current_context()["run_id"])

        @task(task_id="validar_previous_application")
        def validate_task(metadata: dict[str, object]) -> dict[str, object]:
            """Valida o agregado de propostas anteriores."""
            return validate_previous_application_stage(metadata)

        return validate_task(process_task(gate))

    @task_group(group_id="installments")
    def installments_group(gate: dict[str, object]):
        """Processa e valida pagamentos de parcelas."""

        @task(task_id="processar_installments")
        def process_task(_: dict[str, object]) -> dict[str, object]:
            """Agrega a origem installments."""
            return process_installments(get_current_context()["run_id"])

        @task(task_id="validar_installments")
        def validate_task(metadata: dict[str, object]) -> dict[str, object]:
            """Valida o agregado de parcelas."""
            return validate_installments_stage(metadata)

        return validate_task(process_task(gate))

    @task_group(group_id="abt_final")
    def final_group(gate: dict[str, object]):
        """Monta, valida e publica a ABT final."""

        @task(task_id="montar_abt")
        def build_task(_: dict[str, object]) -> dict[str, object]:
            """Monta a ABT a partir dos stagings aprovados."""
            return build_abt_stage(get_current_context()["run_id"])

        @task(task_id="validar_abt")
        def validate_task(metadata: dict[str, object]) -> dict[str, object]:
            """Executa o QA final bloqueante."""
            return validate_abt_stage(metadata)

        @task(task_id="escrever_abt")
        def write_task(metadata: dict[str, object]) -> dict[str, object]:
            """Publica exclusivamente o Parquet final aprovado."""
            return write_abt(metadata)

        return write_task(validate_task(build_task(gate)))

    application = application_group()
    bureau = bureau_group(application)
    pos = pos_group(bureau)
    card = credit_card_group(pos)
    previous = previous_group(card)
    installments = installments_group(previous)
    final_group(installments)


clean_to_abt_gold()
