# Dados do Projeto

Este diretório existe para atender a estrutura de entrega do projeto e para
suportar staging local em execução Docker.

## Onde estão os dados oficiais

Neste projeto, os dados oficiais de runtime **não são versionados no Git**.
Eles são armazenados no MinIO (S3 compatível), nos buckets:

- `raw` (dados brutos)
- `clean` (camada Silver tratada)
- `abt` (base analítica para modelagem)
- `artifacts` (modelo treinado e metadados)

## Arquivos esperados pelo enunciado

O enunciado cita exemplos como `raw_data.csv`, `clean_data.csv` e `abt.csv`.
Na implementação desta solução, os equivalentes são produzidos e mantidos no
Data Lake (MinIO), com rastreabilidade via DAGs e scripts.

## Como reproduzir a carga de dados

1. Subir a infraestrutura:

```bash
docker compose up -d minio airflow
```

2. Executar a esteira via Airflow (disparar a DAG Bronze):

```bash
docker compose exec -T airflow airflow dags trigger 01_bronze_ingest_kaggle
```

3. Inspecionar os objetos gerados no MinIO:

```bash
docker compose run --rm minio-client ls --recursive local/raw
docker compose run --rm minio-client ls --recursive local/clean
docker compose run --rm minio-client ls --recursive local/abt
```

## Observação

A pasta `Dados/` local pode conter apenas arquivos temporários de staging e
debug. A fonte de verdade operacional para ingestão, transformação e serving é
o MinIO.
