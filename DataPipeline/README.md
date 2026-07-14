# DataPipeline

Scripts de ETL Silver e Gold exigidos pelo enunciado da entrega individual.
Os executáveis são symlinks para `scripts/` (fonte única de verdade).

## Arquivos

| Caminho | Função |
|---|---|
| `data_sanitization.py` | Bronze → Silver: leitura do bucket `raw`, QA bloqueante, escrita no `clean` |
| `abt_transform.py` | Silver → Gold: agregações, feature engineering, publicação de `abt_train.parquet` |
| `pipeline_config.yaml` | Configuração central de buckets, chaves e parâmetros de monitoramento |

## Configuração

A configuração oficial do lake está em **`pipeline_config.yaml`** (esta pasta) e é
complementada por:

- **`Model/model_config.yaml`** — paths S3 de ABT, modelo, holdout e features de modelagem
- **Variáveis de ambiente** no `docker-compose.yml` (`MINIO_ENDPOINT_URL`, `RAW_BUCKET`, etc.)

Em runtime, os scripts leem primeiro variáveis de ambiente; o YAML documenta os
valores padrão e o contrato entre camadas.

## Fluxo MinIO

```
raw/*.csv  →  data_sanitization.py  →  clean/*_silver.parquet
clean/*    →  abt_transform.py       →  abt/abt_train.parquet
```

Staging temporário (Parquets intermediários por execução) fica em `Dados/.silver_staging`
e `Dados/.gold_staging` — não compete com o Data Lake.
