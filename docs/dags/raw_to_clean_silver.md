# DAG: 02_silver_clean_data

## Objetivo

Processar e validar os oito CSVs descritos em `HMDR_Camada_Silver.ipynb`,
publicando no bucket `clean` somente Parquets aprovados.

## Configuração

- DAG ID: `02_silver_clean_data`
- Schedule: manual (`schedule=None`)
- Catchup: desabilitado
- Concorrência: `max_active_tasks=2`
- Pipeline: `scripts/data_sanitization.py`

## TaskGroups

A DAG possui oito grupos independentes, um por tabela. Cada grupo executa:

```text
coletar_e_processar -> validar -> escrever_clean
```

A primeira task lê `raw` e grava em
`Dados/.silver_staging/<run_id>/<table_id>/`. A segunda emite logs `[PASS]`,
`[WARNING]` e `[FAIL]` seguindo o notebook. A terceira só publica no `clean`
após QA aprovado e então remove o staging da tabela.

Ao concluir todas as escritas, a task `trigger_gold_pipeline` dispara
`03_gold_abt_features`.

Uma falha bloqueia somente o restante do grupo afetado. Os demais grupos
continuam; a execução da DAG termina em `failed` se algum grupo falhar.
Warnings por colunas ausentes não reprovam a task quando o notebook também
ignoraria a regra.

`bureau_balance` mantém processamento em chunks, deduplicação global compacta
e escrita incremental Parquet para evitar OOM.

## Execução

```bash
docker compose exec -T airflow airflow dags trigger 02_silver_clean_data
docker compose run --rm minio-client ls --recursive local/clean
```

Execução direta completa:

```bash
docker compose run --rm dev python scripts/data_sanitization.py
docker compose run --rm dev python scripts/data_sanitization.py bureau application_train
```

## Testes

```bash
docker compose run --rm dev pytest tests/test_silver_transformations.py tests/test_silver_validations.py tests/test_data_sanitization.py -q
docker compose run --rm airflow python -m pytest /opt/airflow/tests/test_silver_dags.py -q
```
