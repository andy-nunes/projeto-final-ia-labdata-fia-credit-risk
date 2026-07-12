"""Configuracoes auxiliares usadas pelo Airflow no ambiente local."""

import os


def get_airflow_hostname() -> str:
    """Retorna um hostname estavel para registro e leitura de logs das tasks."""
    return os.getenv("AIRFLOW_HOSTNAME", "airflow")
