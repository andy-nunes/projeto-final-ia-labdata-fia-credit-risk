# DAG: clean_to_abt_gold

## Objetivo

Reproduzir o fluxo de `HMDR_Camada_Gold_ABT.html`, agregando sete Parquets da
camada Silver em uma tabela analítica com uma linha por cliente e `TARGET`
preservado.

## Configuração

- DAG ID: `clean_to_abt_gold`
- Schedule: manual (`schedule=None`)
- Catchup: desabilitado
- Execuções simultâneas: `max_active_runs=1`
- Pipeline importado: `scripts/gold_pipeline.py`
- Saída exclusiva no MinIO: `abt/abt_train.parquet`

## Sequência

```text
application_train: processar -> validar
  -> bureau: processar bureau -> validar bureau
             -> processar bureau_balance -> validar bureau_balance
  -> pos_cash: processar -> validar
  -> credit_card: processar -> validar
  -> previous_application: processar -> validar
  -> installments: processar -> validar
  -> abt_final: montar -> validar -> escrever
```

São sete TaskGroups e 17 tasks. A cadeia é estritamente sequencial: qualquer
falha bloqueia todas as etapas posteriores e impede a escrita no bucket `abt`.

## Entradas

O pipeline lê do bucket `clean`:

- `application_train_silver.parquet`
- `bureau_silver.parquet`
- `bureau_balance_silver.parquet`
- `POS_CASH_balance_silver.parquet`
- `credit_card_balance_silver.parquet`
- `previous_application_silver.parquet`
- `installments_payments_silver.parquet`

## Staging e XCom

Cada processamento grava um Parquet em
`Dados/.gold_staging/<run_id>/<etapa>/`. As tasks trocam somente metadados e
caminhos pelo XCom. Downloads temporários das origens são removidos ao fim da
task.

Se uma transformação, validação ou upload falhar, o staging permanece para
diagnóstico. Após upload bem-sucedido, todo o diretório do `run_id` é removido.

## QA

Os logs seguem o notebook:

```text
[QA] bureau_gold
 -> [PASS] regra aprovada
 -> [INFO] métrica diagnóstica
 -> [FAIL] regra reprovada
--- Fim QA bureau_gold ---
```

`[INFO]` não reprova. Todos os resultados aplicáveis são registrados antes de
uma `GoldValidationError`. O QA final exige 307.511 linhas, chave única,
`TARGET` preservado, ausência de infinitos e flags `HAS_*` coerentes.

## Execução

```bash
docker compose exec -T airflow airflow dags trigger clean_to_abt_gold
docker compose run --rm dev python scripts/gold_pipeline.py
docker compose run --rm minio-client stat local/abt/abt_train.parquet
```

Uma execução aprovada substitui o objeto final existente. Uma falha mantém a
última ABT aprovada intacta.
