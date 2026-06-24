# DAG: data_volume_check

## Objetivo

Validar se o volume local `Dados` esta montado e acessivel dentro do container
do Airflow.

## Configuracao

- DAG ID: `data_volume_check`
- Schedule: manual (`schedule=None`)
- Catchup: desabilitado (`catchup=False`)
- Tags: `credit-risk`, `infra`
- Arquivo: `dags/data_volume_check.py`

## Dependencias

Servicos:

- `airflow`

Variaveis:

- `DATA_DIR`, padrao `/opt/airflow/Dados`.

Volume esperado:

- `./Dados:/opt/airflow/Dados`

## Comportamento

Quando executada, a DAG:

1. Verifica se `DATA_DIR` existe.
2. Lista recursivamente os arquivos encontrados dentro do volume.
3. Retorna os caminhos relativos dos arquivos encontrados.
4. Falha com `FileNotFoundError` se o volume nao estiver montado.

## Como executar

```bash
docker compose exec -T airflow airflow dags trigger data_volume_check
```

## Como validar

Conferir estado da execucao:

```bash
docker compose exec -T airflow airflow tasks states-for-dag-run data_volume_check <run_id>
```

Resultado esperado:

- A task `list_data_files` fica em estado `success`.
- O retorno da task mostra os arquivos existentes em `Dados`.

## Casos de uso

- Confirmar que o volume `Dados` esta disponivel para futuras DAGs.
- Diagnosticar problemas de montagem do Docker Compose.
- Validar rapidamente se o Airflow consegue ler artefatos locais do projeto.
