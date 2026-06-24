# Ambiente Docker e Dados

Data do registro: 2026-06-23

## Contexto do Projeto

O PDF `ProjetoFinal_v2.pdf` descreve um projeto final de Machine Learning/IA
baseado no ciclo CRISP-DM. O desafio escolhido neste repositorio e Credit Risk,
usando a competicao Kaggle Home Credit Default Risk.

Pontos relevantes do PDF para esta etapa:

- O projeto deve ter codigo versionado no Git.
- A estrutura deve incluir uma pasta `Dados` para arquivos brutos, limpos e ABT.
- A etapa individual exige proposta de arquitetura funcional e uso de
  `docker-compose`.
- Tambem serao exigidos pipeline de dados, treinamento, predicao, app/API e
  componentes de MLOps em etapas futuras.

## Estrutura Criada

Foram adicionados arquivos para um ambiente inicial de desenvolvimento:

- `Dockerfile`: imagem base do projeto.
- `Dockerfile.airflow`: imagem customizada do Airflow com dependencias para
  Kaggle e MinIO.
- `docker-compose.yml`: servico `dev` para executar scripts no container.
- `.dockerignore`: evita copiar dados, ambiente virtual e arquivos desnecessarios
  para o build.
- `requirements.txt`: dependencias Python iniciais.
- `requirements-airflow.txt`: dependencias adicionais da imagem Airflow.
- `scripts/`: codigos executaveis reutilizados pelo projeto e importados pelas
  DAGs.
- `Dados/.gitkeep`: preserva a pasta de volumes locais no Git.
- Atualizacao do `README.md` com comandos principais.
- Atualizacao do `.gitignore` com `*.csv`.

## Imagem Docker

A imagem usa:

- Base: `python:3.13-slim`.
- Python validado no container: `3.13.14`.
- Diretorio de trabalho: `/app`.
- Dependencias de sistema: `bash` e `libgomp1`.
- Dependencias Python instaladas via `requirements.txt`.

Principais bibliotecas instaladas:

- `kagglehub`
- `numpy`
- `pandas`
- `scikit-learn`
- `matplotlib`
- `seaborn`
- `jupyterlab`
- `python-dotenv`
- `pyarrow`
- `streamlit`
- `boto3`

## Imagem Airflow

A imagem customizada do Airflow usa:

- Base: `apache/airflow:3.1.2-python3.13`.
- Python validado no container: `3.13.9`.
- Airflow validado no container: `3.1.2`.
- Executor local: `LocalExecutor`.
- Auth local de desenvolvimento: `SimpleAuthManager` com
  `simple_auth_manager_all_admins=true`.
- Dependencias adicionais instaladas via `requirements-airflow.txt`.

## Docker Compose

O `docker-compose.yml` define os servicos `dev`, `airflow`, `minio` e
`streamlit`.

### Primeiros passos

1. Instale Docker e Docker Compose na maquina local.
2. Configure `~/.kaggle/kaggle.json` com as credenciais da Kaggle.
3. Rode `docker compose build`.
4. Suba os servicos com `docker compose up -d minio airflow streamlit`.
5. Acesse Airflow, MinIO e Streamlit nos enderecos locais.
6. Para carregar os CSVs no bucket `raw`, dispare a DAG `download_kaggle_to_minio`.

Comportamento do servico `dev`:

- Monta o repositorio local em `/app`.
- Monta `~/.kaggle` em `/root/.kaggle` como somente leitura.
- Define `KAGGLE_CONFIG_DIR=/root/.kaggle`.
- Define `PYTHONPATH=/app`.
- Abre `bash` por padrao.

Comportamento do servico `airflow`:

- Monta `./dags` em `/opt/airflow/dags`.
- Monta `./scripts` em `/opt/airflow/scripts`.
- Define `PYTHONPATH=/opt/airflow` para permitir imports como
  `from scripts.kaggle_to_minio import ...`.

Comandos principais:

```bash
docker compose build
docker compose run --rm dev
docker compose up -d minio airflow streamlit
docker compose exec -T airflow airflow dags unpause download_kaggle_to_minio
docker compose exec -T airflow airflow dags trigger download_kaggle_to_minio
```

Para reiniciar o ambiente do zero:

```bash
docker compose down -v
```

## Download dos Dados Kaggle

A DAG manual `download_kaggle_to_minio` baixa os arquivos da competicao
`home-credit-default-risk` e envia os CSVs para o bucket `raw` no MinIO.

A DAG sempre recarrega os dados brutos quando executada manualmente:

- Garante a existencia dos buckets `raw`, `clean` e `abt`.
- Baixa os dados da Kaggle em diretorio temporario.
- Envia os 10 CSVs esperados para o bucket `raw`, substituindo objetos com o
  mesmo nome quando eles ja existem.
- Ao final, valida se os 10 CSVs esperados existem no bucket `raw`; se faltar
  algum arquivo, a task falha explicitamente.

Comando para disparar manualmente:

```bash
docker compose exec -T airflow airflow dags unpause download_kaggle_to_minio
docker compose exec -T airflow airflow dags trigger download_kaggle_to_minio
```

Resultado esperado:

- Download do arquivo Kaggle de aproximadamente 688 MB.
- Replace dos CSVs extraidos no bucket `raw`.

Arquivos baixados:

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

## Controle de Versao dos Dados

Foi adicionado ao `.gitignore`:

```gitignore
*.csv
```

Isso impede o versionamento de arquivos CSV locais. A fonte de verdade dos dados
brutos passa a ser o bucket `raw` do MinIO.

Exemplo de verificacao para arquivos CSV locais:

```bash
git check-ignore -v Dados/raw/application_train.csv
```

Resultado esperado:

```text
.gitignore:221:*.csv Dados/raw/application_train.csv
```

## Verificacoes Realizadas

Comandos executados e resultados:

```bash
python3 -m py_compile dags/download_kaggle_to_minio.py
```

Resultado: passou.

```bash
docker compose config
```

Resultado: configuracao valida.

```bash
docker compose build
```

Resultado: imagem construida com sucesso.

```bash
docker compose build airflow
```

Resultado: imagem `fia-credit-risk-airflow` construida com `kagglehub` e
`boto3`.

```bash
docker compose run --rm airflow python --version
```

Resultado:

```text
Python 3.13.9
```

```bash
docker compose run --rm airflow airflow version
```

Resultado:

```text
3.1.2
```

```bash
docker compose run --rm dev python -c "import sys, kagglehub, pandas, sklearn; print(sys.version.split()[0]); print('imports ok')"
```

Resultado:

```text
3.13.14
imports ok
```

```bash
docker compose exec -T airflow airflow dags list
```

Resultado relevante:

```text
download_kaggle_to_minio | /opt/airflow/dags/download_kaggle_to_minio.py | airflow | True
```

```bash
docker compose exec -T airflow airflow tasks states-for-dag-run download_kaggle_to_minio manual__2026-06-24T00:11:24+00:00
```

Resultado relevante:

```text
download_and_upload | success
```

## Estado Atual

O projeto possui um ambiente Docker funcional para desenvolvimento Python e um
fluxo reproduzivel para baixar os dados brutos do Kaggle e armazena-los no
bucket `raw` do MinIO.

## Servicos Locais

Foram adicionados servicos locais para a etapa de arquitetura/MLOps:

- `airflow`: orquestracao de pipelines.
- `minio`: storage S3-compativel local.
- `streamlit`: app web inicial para visualizar o volume de dados e testar
  conectividade com MinIO.

Comando para subir os servicos:

```bash
docker compose up -d minio airflow streamlit
```

Acessos:

- Airflow: `http://localhost:8080`
- MinIO API: `http://localhost:9000`
- MinIO Console: `http://localhost:9001`
- Streamlit: `http://localhost:8501`

Credenciais locais de desenvolvimento:

- Airflow: auth local simplificada via `SimpleAuthManager`
- MinIO: `minioadmin` / `minioadmin`

Montagem da pasta `Dados`:

- Airflow: `/opt/airflow/Dados`
- MinIO: `/Dados`
- Streamlit: `/app/Dados`

O app inicial do Streamlit esta em `app/streamlit_app.py` e lista os arquivos do
volume `Dados`, alem de testar uma conexao S3 com o MinIO via `boto3`.

### Buckets do MinIO

Na inicializacao do servico `streamlit`, o comando executa
`scripts/ensure_minio_buckets.py` antes de subir a aplicacao web.

Buckets criados:

- `raw`
- `clean`
- `abt`

O sincronismo automatico da pasta local `Dados` para buckets foi removido. A
carga de dados brutos agora acontece pela DAG `download_kaggle_to_minio`, que
envia os CSVs ao bucket `raw`.

Objetos verificados em `raw`:

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

Verificacoes realizadas:

```bash
docker compose ps
```

Resultado: `airflow`, `minio` e `streamlit` em estado `Up`.

```bash
curl -sS -o /dev/null -w '%{http_code}\n' http://localhost:8501
curl -sS -o /dev/null -w '%{http_code}\n' http://localhost:9001
curl -sS -o /dev/null -w '%{http_code}\n' http://localhost:9000/minio/health/live
curl -sS -o /dev/null -w '%{http_code}\n' http://localhost:8080
```

Resultados:

- Streamlit: `200`
- MinIO Console: `200`
- MinIO health: `200`
- Airflow: `200`

```bash
docker compose run --rm dev python -c "import boto3, os; from botocore.client import Config; c=boto3.client('s3', endpoint_url=os.getenv('MINIO_ENDPOINT_URL'), aws_access_key_id=os.getenv('MINIO_ROOT_USER'), aws_secret_access_key=os.getenv('MINIO_ROOT_PASSWORD'), config=Config(signature_version='s3v4'), region_name='us-east-1'); print([b['Name'] for b in c.list_buckets()['Buckets']]); print(len(c.list_objects_v2(Bucket='raw').get('Contents', [])))"
```

Resultados:

- Buckets incluem `raw`, `clean` e `abt`.
- Bucket `raw` contem os 10 CSVs esperados.

```bash
docker compose exec -T airflow airflow dags list
```

Resultado relevante:

```text
download_kaggle_to_minio | /opt/airflow/dags/download_kaggle_to_minio.py | airflow | True
```

Ainda nao foram implementados:

- Pipeline de limpeza em `DataPipeline`.
- Geracao da ABT.
- Treinamento em `Model/train.py`.
- Predicao em `Model/predict.py`.
- App Streamlit final de predicao.
- Componentes adicionais de MLOps.
