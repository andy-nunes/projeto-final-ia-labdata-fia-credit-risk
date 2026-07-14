#!/usr/bin/env bash
# Validação pré-banca: testes, DAGs Airflow e endpoints da API/Streamlit.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

echo "==> 1/4 Testes (Airflow — pipeline/DAGs; exclui marker streamlit)"
docker compose exec -T airflow python -m pytest /opt/airflow/tests \
  -m "not streamlit" -q

echo "==> 2/4 Testes (dev — marker streamlit: catálogo e dashboard)"
docker compose exec -T dev python -m pytest \
  tests -m streamlit -q

echo "==> 3/4 Airflow — importação das DAGs"
docker compose exec -T airflow airflow dags list-import-errors
docker compose exec -T airflow airflow dags list

echo "==> 4/4 Serviços — health check API e Streamlit"
curl -sf http://localhost:8000/ >/dev/null
curl -sf http://localhost:8501/ >/dev/null

echo ""
echo "Validação pré-banca concluída com sucesso."
