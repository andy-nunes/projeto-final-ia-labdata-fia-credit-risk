# DAG 05 — Monitoramento de saúde (MLOps)

DAG agendada a cada **5 minutos** que executa o monitoramento mínimo de
produção. As checagens só rodam se o modelo oficial (`trained_at` em
`model_metadata.json`) estiver nas **últimas 24h** — artefato gerado pela
DAG `04_model_train_lightgbm`. Também é disparada automaticamente ao final
do treino via `TriggerDagRunOperator`.

## Objetivo

Verificar se o serviço e os artefatos oficiais no MinIO estão coerentes enquanto
o modelo treinado permanece na janela operacional de 24h.

## Configuração

- DAG ID: `05_monitor_health`
- Schedule: a cada 5 minutos (`timedelta(minutes=5)`)
- Freshness: exige `trained_at` do modelo no MinIO dentro de 24h
- Catchup: desabilitado (`catchup=False`)
- `max_active_runs`: `1`
- Tags: `credit-risk`, `mlops`, `monitoring`
- Arquivo: `dags/05_monitor_health.py`
- Script: `scripts/mlops_monitoring.py`
- Helper de freshness: `scripts/dag_freshness.py`

## Tasks

1. `ensure_training_freshness` (`@task.short_circuit`): segue apenas se
   `trained_at` do metadata estiver nas últimas 24h (sem ORM — compatível com
   Airflow 3); caso contrário, pula `run_monitoring_checks`.
2. `run_monitoring_checks`: executa as checagens e falha se `overall_status=fail`.

## Checagens

1. `GET` no health check da API (`API_HEALTH_URL`, padrão `http://api:8000/`)
2. Objetos no lake: ABT, holdout demo, modelo, metadata
3. Coerência do `business_threshold` entre `Model/model_config.yaml` e metadata

Saída:

- `s3://artifacts/monitoring/latest.json`
- `s3://artifacts/monitoring/runs/<timestamp>.json`

## Como operar

Despause a DAG (necessário para schedule e para o trigger pós-treino):

```bash
docker compose exec -T airflow airflow dags unpause 05_monitor_health
```

Após um treino bem-sucedido, o monitoramento dispara sozinho. Dentro da janela
de 24h, novas execuções ocorrem a cada 5 minutos. Fora da janela, a DAG ainda
é agendada, mas a task de checagem é pulada até um novo treino.

Equivalente via API (sem Airflow / sem gate de freshness):

```bash
curl -sS -X POST http://localhost:8000/monitoring/run
curl -sS http://localhost:8000/monitoring/latest
```
