# DAGs

Esta pasta documenta as DAGs Airflow do projeto. Todas as DAGs atuais sao
manuais (`schedule=None`) e devem ser disparadas sob demanda pela interface do
Airflow ou pela CLI.

A arquitetura, a semantica de QA, o staging e a execucao direta da camada
Silver estao detalhados em [`docs/camada-silver.md`](../camada-silver.md).
O desenho e o contrato operacional da camada Gold estao em
[`docs/camada-gold-abt-design.md`](../camada-gold-abt-design.md).

As DAGs devem conter apenas a orquestracao. O codigo executavel usado pelo
projeto fica em `scripts/` e deve ser importado pelas DAGs quando necessario.

## DAGs disponiveis

- [`download_kaggle_to_minio`](download_kaggle_to_minio.md): baixa os dados
  brutos da competicao Home Credit Default Risk e substitui os CSVs no bucket
  `raw` do MinIO.
- [`raw_to_clean_silver`](raw_to_clean_silver.md): transforma oito CSVs do
  bucket `raw` em Parquets validados no bucket `clean`, com oito TaskGroups
  independentes de três tasks.
- [`clean_to_abt_gold`](clean_to_abt_gold.md): agrega sete Parquets do bucket
  `clean` em uma ABT validada no bucket `abt`, com sete TaskGroups e 17 tasks
  sequenciais.

## Comandos uteis

Listar DAGs:

```bash
docker compose exec -T airflow airflow dags list
```

Em clones limpos, o container do Airflow ja executa `airflow dags reserialize`
na inicializacao. Se o ambiente foi iniciado antes dessa configuracao ou se a
listagem ficar desatualizada, rode:

```bash
docker compose exec -T airflow airflow dags reserialize
docker compose exec -T airflow airflow dags list
```

Disparar uma DAG:

```bash
docker compose exec -T airflow airflow dags trigger <dag_id>
```

Consultar o estado das tasks de uma execucao:

```bash
docker compose exec -T airflow airflow tasks states-for-dag-run <dag_id> <run_id>
```

Ver arquivos no bucket `raw` depois de uma execucao:

```bash
docker compose run --rm minio-client ls --recursive local/raw
```

Ver os Parquets gerados no bucket `clean`:

```bash
docker compose run --rm minio-client ls --recursive local/clean
```

Ver a ABT final:

```bash
docker compose run --rm minio-client stat local/abt/abt_train.parquet
```

Executar os pipelines fora do Airflow, mantendo a mesma logica importada pelas
DAGs:

```bash
docker compose run --rm dev python scripts/silver_pipeline.py
docker compose run --rm dev python scripts/gold_pipeline.py
```

Validar a suite e o carregamento das DAGs:

```bash
docker compose exec -T airflow python -m pytest /opt/airflow/tests -q
docker compose exec -T airflow airflow dags list-import-errors
```

## Logs das tasks

O servico `airflow` usa hostname fixo `airflow` e define
`AIRFLOW__CORE__HOSTNAME_CALLABLE=scripts.airflow_config.get_airflow_hostname`.
Essa configuracao evita que o Airflow registre tasks com hostname vazio e tente
buscar logs em URLs invalidas como `http://:8793/log/...`.
