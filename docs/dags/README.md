# DAGs

Esta pasta documenta as DAGs Airflow do projeto. Todas as DAGs atuais sao
manuais (`schedule=None`) e devem ser disparadas sob demanda pela interface do
Airflow ou pela CLI.

As DAGs devem conter apenas a orquestracao. O codigo executavel usado pelo
projeto fica em `scripts/` e deve ser importado pelas DAGs quando necessario.

## DAGs disponiveis

- [`download_kaggle_to_minio`](download_kaggle_to_minio.md): baixa os dados
  brutos da competicao Home Credit Default Risk e substitui os CSVs no bucket
  `raw` do MinIO.

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
