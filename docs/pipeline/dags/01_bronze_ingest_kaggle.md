# DAG: 01_bronze_ingest_kaggle

## Objetivo

Baixar os arquivos brutos da competicao Kaggle `home-credit-default-risk` e
armazenar os CSVs esperados no bucket `raw` do MinIO.

## Configuracao

- DAG ID: `01_bronze_ingest_kaggle`
- Schedule: manual (`schedule=None`)
- Catchup: desabilitado (`catchup=False`)
- Tags: `credit-risk`, `kaggle`, `minio`, `bronze`
- Arquivo: `dags/01_bronze_ingest_kaggle.py`
- Script importado: `scripts/kaggle_to_minio.py`

## Dependencias

Servicos:

- `airflow`
- `minio`

Credenciais e variaveis:

- O container do Airflow recebe `KAGGLE_API_TOKEN` por variável de ambiente.
- Recomenda-se manter o token em
  `~/.config/fia-credit-risk/kaggle/kaggle.env` e carregar via
  `docker-compose.override.yml` (`env_file`).
- Token: gere em [kaggle.com/settings/api](https://www.kaggle.com/settings/api)
  (*Generate New Token*) e salve como
  `KAGGLE_API_TOKEN=<seu-token>` no arquivo
  `~/.config/fia-credit-risk/kaggle/kaggle.env`.
- `MINIO_ENDPOINT_URL`, padrao `http://minio:9000`.
- `MINIO_ROOT_USER`, padrao `minioadmin`.
- `MINIO_ROOT_PASSWORD`, padrao `minioadmin`.
- `RAW_BUCKET`, padrao `raw`.

Bibliotecas:

- `kagglehub`
- `boto3`

## Comportamento

Quando executada, a DAG:

1. Chama `replace_kaggle_raw_files()` em `scripts/kaggle_to_minio.py`.
2. Cria os buckets `raw`, `clean`, `abt` e `artifacts` caso eles ainda nao
   existam.
3. Baixa a competicao `home-credit-default-risk` para um diretorio temporario.
4. Localiza os 10 CSVs esperados no conteudo baixado.
5. Envia os 10 CSVs para o bucket `raw`.
6. Substitui objetos existentes no bucket quando o nome do arquivo ja existe.
7. Valida se todos os arquivos esperados existem no bucket depois do upload.
8. Falha explicitamente se algum arquivo esperado estiver ausente.
9. Dispara a DAG `02_silver_clean_data` via `trigger_silver_pipeline`.

## Arquivos esperados

- `HomeCredit_columns_description.csv`
- `POS_CASH_balance.csv`
- `application_test.csv`
- `application_train.csv`
- `bureau.csv`
- `bureau_balance.csv`
- `credit_card_balance.csv`
- `installments_payments.csv`
- `previous_application.csv`
- `sample_submission.csv`

## Como executar

Pela CLI:

```bash
docker compose exec -T airflow airflow dags trigger 01_bronze_ingest_kaggle
```

Pela interface:

1. Acesse `http://localhost:8080`.
2. Abra a DAG `01_bronze_ingest_kaggle`.
3. Use a acao de trigger manual.

## Como validar

Conferir estado da execucao:

```bash
docker compose exec -T airflow airflow tasks states-for-dag-run 01_bronze_ingest_kaggle <run_id>
```

Conferir objetos no MinIO:

```bash
docker compose run --rm minio-client ls --recursive local/raw
```

Resultado esperado:

- A task `download_and_upload` fica em estado `success`.
- O bucket `raw` contem os 10 CSVs esperados.
- Os timestamps dos objetos sao atualizados a cada execucao, confirmando replace.

## Observacoes

- A DAG nao usa `Dados/raw` como cache local.
- A DAG mantem apenas a orquestracao; a logica de download, validacao e upload
  fica em `scripts/kaggle_to_minio.py`.
- A fonte de verdade dos dados brutos e o bucket `raw` no MinIO.
- A execucao baixa cerca de 688 MB da Kaggle e pode levar alguns minutos,
  dependendo da rede.
