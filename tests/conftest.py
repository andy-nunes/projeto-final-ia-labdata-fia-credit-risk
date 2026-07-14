"""Configuração compartilhada da suite pytest do projeto."""


def pytest_configure(config) -> None:
    """Registra markers customizados (disponível em Airflow e no container dev)."""
    config.addinivalue_line(
        "markers",
        "streamlit: testes que exigem o pacote streamlit (container dev)",
    )
    config.addinivalue_line(
        "markers",
        "airflow: testes que exigem o runtime Airflow (container airflow)",
    )
