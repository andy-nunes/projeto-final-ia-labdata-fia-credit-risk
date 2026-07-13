# Camada Silver: raw para clean

## Visao geral

A camada Silver foi consolidada na DAG manual `02_silver_clean_data`. Ela le os
oito CSVs de negocio no bucket `raw`, aplica as transformacoes derivadas do
notebook `HMDR_Camada_Silver.ipynb`, valida o resultado intermediario e publica
no bucket `clean` somente os Parquets aprovados.

A implementacao foi separada por responsabilidade:

- `dags/02_silver_clean_data.py`: apenas orquestracao Airflow.
- `scripts/silver_transformations.py`: regras de transformacao e configuracao
  das oito tabelas.
- `scripts/silver_validations.py`: regras de QA e logs no formato do notebook.
- `scripts/data_sanitization.py`: staging, validacao, upload, limpeza e execucao
  direta pela CLI.

## Fluxo da DAG

A DAG nao possui schedule e usa `max_active_tasks=2`. Cada tabela possui um
TaskGroup independente com a cadeia:

```text
coletar_e_processar -> validar -> escrever_clean
```

Os oito grupos sao:

- `application_train`
- `application_test`
- `bureau`
- `bureau_balance`
- `POS_CASH_balance`
- `credit_card_balance`
- `previous_application`
- `installments_payments`

Uma falha interrompe apenas o grupo afetado. Os demais grupos continuam a
execucao, mas o DagRun termina como `failed` se qualquer task falhar.

## Staging e publicacao

A primeira task baixa o CSV do `raw`, transforma os dados e grava um Parquet em:

```text
Dados/.silver_staging/<run_id>/<table_id>/<arquivo_silver>.parquet
```

A task de validacao le esse arquivo. A task de escrita exige `qa_status=passed`
antes de enviar o objeto para o bucket `clean`. Depois de um upload bem-sucedido,
somente o staging daquela tabela e removido. Se o QA ou o upload falhar, o
arquivo intermediario permanece disponivel para diagnostico.

Arquivos `*.parquet` e o diretorio `Dados/.silver_staging` sao ignorados pelo
Git porque sao artefatos locais de dados.

`bureau_balance` e processada em chunks, com deduplicacao global e escrita
incremental, para evitar carregar aproximadamente 27 milhoes de linhas na
memoria do container.

## Semantica das validacoes

Os logs seguem o formato visual do notebook:

```text
[QA] application_train_silver.parquet
 -> [PASS] regra aprovada
 -> [WARNING] regra ignorada conforme o notebook
 -> [FAIL] regra reprovada
--- Fim QA application_train ---
```

- `[PASS]`: regra aprovada.
- `[WARNING]`: condicao que o notebook nao reprovaria, como uma coluna opcional
  ausente; a task continua.
- `[FAIL]`: regra obrigatoria reprovada; a task `validar` falha e
  `escrever_clean` nao executa naquele grupo.

Todas as regras sao avaliadas antes de uma eventual `SilverValidationError`,
permitindo que os logs mostrem todas as reprovações encontradas na tabela.

## Execucao manual

Pelo Airflow:

```bash
docker compose exec -T airflow airflow dags trigger 02_silver_clean_data
```

Pela CLI, para todas as tabelas ou para uma selecao:

```bash
docker compose run --rm dev python scripts/data_sanitization.py
docker compose run --rm dev python scripts/data_sanitization.py bureau application_train
```

O bloco `if __name__ == "__main__"` executa o pipeline diretamente. A CLI
continua para as demais tabelas quando uma falha, imprime cada tabela reprovada
com `[FAIL]` e retorna codigo `1` se houver qualquer falha; sem falhas, retorna
codigo `0`.

## Testes e verificacao

Os testes usam `pytest` e `pytest-mock`; o framework `unittest` nao faz parte da
suite Silver.

```bash
docker compose exec -T airflow python -m pytest /opt/airflow/tests -q
docker compose exec -T airflow airflow dags list-import-errors
docker compose exec -T airflow airflow dags list
```

Os testes cobrem transformacoes, warnings e failures, formato dos logs, staging,
bloqueio de upload sem QA, limpeza apos sucesso, continuidade da CLI e estrutura
dos oito TaskGroups.
