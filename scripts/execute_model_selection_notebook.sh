#!/usr/bin/env bash
# Executa o notebook de seleção de modelo e grava outputs no .ipynb.
# Requer Docker Desktop em execução.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

NOTEBOOK="scripts/abt_to_model_home_credit_test.ipynb"

if ! command -v docker >/dev/null 2>&1; then
  DOCKER="/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe"
else
  DOCKER="docker"
fi

COMPOSE="$DOCKER compose"

echo "==> Garantindo imagem dev..."
$COMPOSE build dev

echo "==> Executando notebook (dataset integral, ~15-25 min)..."
$COMPOSE run --rm dev bash -lc "
  pip install -q jupyter nbconvert ipykernel lightgbm xgboost &&
  jupyter nbconvert --to notebook --execute \
    --ExecutePreprocessor.timeout=7200 \
    --output /tmp/abt_to_model_home_credit_test.executed.ipynb \
    /app/$NOTEBOOK &&
  cp /app/$NOTEBOOK /app/${NOTEBOOK}.bak &&
  mv /tmp/abt_to_model_home_credit_test.executed.ipynb /app/$NOTEBOOK
"

echo "==> Notebook atualizado com outputs em $NOTEBOOK"
