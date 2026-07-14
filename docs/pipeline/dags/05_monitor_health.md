# DAG 05 — Monitoramento de saúde (MLOps)

DAG manual (`schedule=None`) que executa o monitoramento mínimo de produção
descrito no item **iii** da entrega individual.

## Objetivo

Verificar se o serviço e os artefatos oficiais no MinIO estão coerentes antes
(ou depois) de uma demonstração / janela de escoragem.

## Script

`scripts/mlops_monitoring.py`

Checagens:

1. `GET` no health check da API (`API_HEALTH_URL`, padrão `http://api:8000/`)
2. Objetos no lake: ABT, holdout demo, modelo, metadata
3. Coerência do `business_threshold` entre `Model/model_config.yaml` e metadata

Saída:

- `s3://artifacts/monitoring/latest.json`
- `s3://artifacts/monitoring/runs/<timestamp>.json`

A task falha se `overall_status == fail` (ex.: artefato ausente ou API fora).

## Como disparar

```bash
docker compose exec -T airflow airflow dags unpause 05_monitor_health
docker compose exec -T airflow airflow dags trigger 05_monitor_health
```

Equivalente via API (sem Airflow):

```bash
curl -sS -X POST http://localhost:8000/monitoring/run
curl -sS http://localhost:8000/monitoring/latest
```
