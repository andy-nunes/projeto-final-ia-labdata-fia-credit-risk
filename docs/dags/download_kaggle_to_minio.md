# DAG: download_kaggle_to_minio

## Objetivo

Baixar os arquivos brutos da competicao Kaggle `home-credit-default-risk` e
armazenar os CSVs esperados no bucket `raw` do MinIO.

## Configuracao

- DAG ID: `download_kaggle_to_minio`
- Schedule: manual (`schedule=None`)
- Catchup: desabilitado (`catchup=False`)
- Tags: `credit-risk`, `kaggle`, `minio`
- Arquivo: `dags/download_kaggle_to_minio.py`
- Script importado: `scripts/kaggle_to_minio.py`

## Dependencias

Servicos:

- `airflow`
- `minio`

Credenciais e variaveis:

- O container do Airflow precisa acessar as credenciais Kaggle montadas em
  `/home/airflow/.kaggle`.
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
2. Cria os buckets `raw`, `clean` e `abt` caso eles ainda nao existam.
3. Baixa a competicao `home-credit-default-risk` para um diretorio temporario.
4. Localiza os 10 CSVs esperados no conteudo baixado.
5. Envia os 10 CSVs para o bucket `raw`.
6. Substitui objetos existentes no bucket quando o nome do arquivo ja existe.
7. Valida se todos os arquivos esperados existem no bucket depois do upload.
8. Falha explicitamente se algum arquivo esperado estiver ausente.

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
docker compose exec -T airflow airflow dags trigger download_kaggle_to_minio
```

Pela interface:

1. Acesse `http://localhost:8080`.
2. Abra a DAG `download_kaggle_to_minio`.
3. Use a acao de trigger manual.

## Como validar

Conferir estado da execucao:

```bash
docker compose exec -T airflow airflow tasks states-for-dag-run download_kaggle_to_minio <run_id>
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
