# DAG: 04_model_train_lightgbm

## Objetivo

Treinar o modelo LightGBM final a partir da ABT Gold e publicar os artefatos de
modelo no MinIO.

## Configuracao

- DAG ID: `04_model_train_lightgbm`
- Schedule: manual (`schedule=None`)
- Catchup: desabilitado (`catchup=False`)
- `max_active_runs`: `1`
- Tags: `credit-risk`, `model`, `lightgbm`, `training`
- Arquivo: `dags/04_model_train_lightgbm.py`
- Script importado: `scripts/train.py`

## Dependencias

Servicos:

- `airflow`
- `minio`

Entradas:

- `s3://abt/abt_train.parquet`
- `Model/model_config.yaml`

Saidas:

- `s3://artifacts/lightgbm_hcdr.pkl`
- `s3://artifacts/model_metadata.json`
- `Dados/abt/abt_demo_holdout.parquet`

Variaveis no servico `airflow`:

- `ABT_PATH=s3://abt/abt_train.parquet`
- `MODEL_PATH=s3://artifacts/lightgbm_hcdr.pkl`
- `MODEL_METADATA_PATH=s3://artifacts/model_metadata.json`
- `MINIO_ENDPOINT_URL=http://minio:9000`
- `MINIO_ROOT_USER=minioadmin`
- `MINIO_ROOT_PASSWORD=minioadmin`

Bibliotecas:

- `lightgbm`
- `pandas`
- `pyarrow`
- `s3fs`
- `scikit-learn==1.7.2`

A versao do `scikit-learn` fica pinada para manter compatibilidade entre o
ambiente que serializa componentes do artefato e os servicos que fazem
deserializacao em runtime.
- `pyyaml`

## Comportamento

Quando executada, a DAG:

1. Chama `run_training()` em `scripts/train.py`.
2. Le a ABT final do bucket `abt`.
3. Separa a base em treino, teste e holdout de demonstracao, mantendo
   estratificacao por `TARGET`.
4. Salva o holdout de demonstracao em `Dados/abt/abt_demo_holdout.parquet`.
5. Treina o `LightGBMClassifier` com os parametros de `Model/model_config.yaml`.
6. Avalia o modelo no conjunto de teste.
7. Publica o modelo serializado no bucket `artifacts`.
8. Publica os metadados de treinamento no bucket `artifacts`.

Os conjuntos de treino e teste ficam apenas em memoria durante a execucao. O
holdout de demonstracao e persistido localmente para consumo da aplicacao.

## Como executar

Pela CLI:

```bash
docker compose exec -T airflow airflow dags trigger 04_model_train_lightgbm
```

Pela interface:

1. Acesse `http://localhost:8080`.
2. Abra a DAG `04_model_train_lightgbm`.
3. Use a acao de trigger manual.

## Como validar

Conferir a ultima execucao:

```bash
docker compose exec -T airflow airflow dags list-runs 04_model_train_lightgbm
```

Conferir artefatos no MinIO:

```bash
docker compose run --rm minio-client ls --recursive local/artifacts
```

Conferir o holdout local:

```bash
ls -lh Dados/abt/abt_demo_holdout.parquet
```

Resultado esperado:

- A task `run_training_script` fica em estado `success`.
- O bucket `artifacts` contem `lightgbm_hcdr.pkl` e `model_metadata.json`.
- O arquivo `Dados/abt/abt_demo_holdout.parquet` e atualizado.

## Observacoes

- A DAG nao executa automaticamente; deve ser disparada sob demanda.
- A ABT precisa existir em `s3://abt/abt_train.parquet` antes do treino.
- A publicacao do modelo no MinIO substitui objetos existentes com os mesmos
  nomes.
