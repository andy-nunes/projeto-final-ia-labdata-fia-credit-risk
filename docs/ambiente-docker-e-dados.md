# Ambiente Docker e Dados

Data da ultima atualizacao: 2026-06-29

## Contexto do Projeto

O PDF `docs/reference/ProjetoFinal_v2.pdf` descreve um projeto final de Machine Learning/IA
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
- `scikit-learn==1.7.2`
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

O `docker-compose.yml` define os servicos `dev`, `airflow`, `minio`,
`minio-client` e `streamlit`.

### Primeiros passos

1. Instale Docker e Docker Compose na maquina local.
2. Configure `~/.kaggle/kaggle.json` com as credenciais da Kaggle.
3. Rode `docker compose build`.
4. Suba os servicos com `docker compose up -d minio airflow api streamlit`.
5. Acesse Airflow, MinIO, API e Streamlit nos enderecos locais.
6. Para carregar os CSVs no bucket `raw` e encadear o restante da esteira,
   dispare a DAG `01_bronze_ingest_kaggle` (ela aciona automaticamente
   `02_silver_clean_data` → `03_gold_abt_features` → `04_model_train_lightgbm`).
7. Aguarde a conclusão das etapas Silver/Gold/Model na UI do Airflow.
8. Confirme a ABT final no bucket `abt` e os artefatos no bucket `artifacts`.

Comportamento do servico `dev`:

- Monta o repositorio local em `/app`.
- Monta `~/.kaggle` em `/root/.kaggle` como somente leitura.
- Define `KAGGLE_CONFIG_DIR=/root/.kaggle`.
- Define `PYTHONPATH=/app`.
- Abre `bash` por padrao.

Comportamento do servico `streamlit`:

- Sobe `app/dashboard.py` na porta `8501`.
- Executa `scripts/ensure_minio_buckets.py` antes da aplicacao para garantir
  os buckets `raw`, `clean`, `abt` e `artifacts`.
- Define `API_BASE_URL=http://api:8000` para consumir a API FastAPI pela rede
  interna do Compose.

Comportamento do servico `api`:

- Sobe `app/main.py` com `uvicorn` na porta `8000`.
- Carrega o modelo em `s3://artifacts/lightgbm_hcdr.pkl`.
- Usa o holdout local em `Dados/abt/abt_demo_holdout.parquet` para buscar
  dossies por `SK_ID_CURR`.

Comportamento do servico `airflow`:

- Monta `./dags` em `/opt/airflow/dags`.
- Monta `./scripts` em `/opt/airflow/scripts`.
- Define `PYTHONPATH=/opt/airflow` para permitir imports como
  `from scripts.kaggle_to_minio import ...`.
- Usa hostname fixo `airflow` e define
  `AIRFLOW__CORE__HOSTNAME_CALLABLE=scripts.airflow_config.get_airflow_hostname`
  para que os logs das tasks usem um host valido no servidor interno da porta
  `8793`.
- Define `ABT_PATH=s3://abt/abt_train.parquet`, `MODEL_PATH=s3://artifacts/lightgbm_hcdr.pkl`
  e `MODEL_METADATA_PATH=s3://artifacts/model_metadata.json` para que a DAG
  `04_model_train_lightgbm` leia a ABT e publique os artefatos de modelo no MinIO.
- Executa `airflow db migrate` e `airflow dags reserialize` antes do
  `airflow standalone`, garantindo que as DAGs sejam registradas no banco local
  em clones novos.

Comandos principais:

```bash
docker compose build
docker compose run --rm dev
docker compose up -d minio airflow streamlit
docker compose exec -T airflow airflow dags unpause 01_bronze_ingest_kaggle
docker compose exec -T airflow airflow dags trigger 01_bronze_ingest_kaggle
```

Para reiniciar o ambiente do zero:

```bash
docker compose down -v
```

## Download dos Dados Kaggle

A DAG manual `01_bronze_ingest_kaggle` baixa os arquivos da competicao
`home-credit-default-risk` e envia os CSVs para o bucket `raw` no MinIO.

A DAG sempre recarrega os dados brutos quando executada manualmente:

- Garante a existencia dos buckets `raw`, `clean`, `abt` e `artifacts`.
- Baixa os dados da Kaggle em diretorio temporario.
- Envia os 10 CSVs esperados para o bucket `raw`, substituindo objetos com o
  mesmo nome quando eles ja existem.
- Ao final, valida se os 10 CSVs esperados existem no bucket `raw`; se faltar
  algum arquivo, a task falha explicitamente.

Comando para disparar manualmente:

```bash
docker compose exec -T airflow airflow dags unpause 01_bronze_ingest_kaggle
docker compose exec -T airflow airflow dags trigger 01_bronze_ingest_kaggle
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
01_bronze_ingest_kaggle | /opt/airflow/dags/download_kaggle_to_minio.py | airflow | True
02_silver_clean_data      | /opt/airflow/dags/raw_to_clean_silver.py      | airflow | True
03_gold_abt_features      | /opt/airflow/dags/clean_to_abt_gold.py        | airflow | True
```

Se uma DAG existir em `dags/` mas nao aparecer na listagem depois de uma subida
antiga do ambiente, force a serializacao manualmente:

```bash
docker compose exec -T airflow airflow dags reserialize
docker compose exec -T airflow airflow dags list
```

```bash
docker compose exec -T airflow airflow tasks states-for-dag-run 01_bronze_ingest_kaggle manual__2026-06-24T00:11:24+00:00
```

Resultado relevante:

```text
download_and_upload | success
```

## Estado Atual

O projeto possui um ambiente Docker funcional e um fluxo reproduzivel de dados
em tres camadas: carga bruta no bucket `raw`, promocao validada para `clean` e
construcao da ABT de treino em `abt/abt_train.parquet`.

## Servicos Locais

Foram adicionados servicos locais para a etapa de arquitetura/MLOps:

- `airflow`: orquestracao de pipelines.
- `minio`: storage S3-compativel local.
- `minio-client`: cliente auxiliar para inspecionar e copiar objetos.
- `api`: backend FastAPI de escoragem de credito.
- `streamlit`: dashboard web da mesa de crédito, implementado em
  `app/dashboard.py`.

Comando para subir os servicos:

```bash
docker compose up -d minio airflow api streamlit
```

Acessos:

- Airflow: `http://localhost:8080`
- MinIO API: `http://localhost:9000`
- MinIO Console: `http://localhost:9001`
- API FastAPI: `http://localhost:8000`
- Streamlit: `http://localhost:8501`

Credenciais locais de desenvolvimento:

- Airflow: auth local simplificada via `SimpleAuthManager`
- MinIO: `minioadmin` / `minioadmin`

Montagem da pasta `Dados`:

- Airflow: `/opt/airflow/Dados`
- MinIO: `/Dados`
- MinIO Client: `/Dados`
- Streamlit: `/app/Dados`

O app do Streamlit esta em `app/dashboard.py`. Ele atua como cliente da API
FastAPI configurada em `config/model_config.yaml` (`api.base_url`) e e a
homepage oficial do painel da mesa de credito.

### Dashboard Streamlit

O painel apresenta o motor de decisao de credito com dados Home Credit, modelo
LightGBM e API de escoragem.

A aba **Catalogo** em `app/dashboard.py` exibe um catalogo pesquisavel das colunas da ABT com nome, tipo, categoria,
fonte, descricao, marcacao de entrada no modelo, marcacao de campo editavel e
marcacao de categorica do modelo. A montagem fica em `app/abt_catalog.py`,
usando o schema de `Dados/abt/abt_train.parquet`, o arquivo
`config/model_config.yaml` e o dicionario oficial
`Dados/raw/HomeCredit_columns_description.csv`, que vem do pacote de dados da
competicao Home Credit Default Risk no Kaggle. Colunas derivadas da camada Gold
recebem descricao inferida pela regra de criacao ou pelo prefixo da fonte
agregada. A busca, os filtros de categoria/fonte, a tabela e o download rodam
client-side em um componente HTML/JavaScript, nao como widgets Streamlit como
`text_input`, `selectbox`, `multiselect`, `download_button` ou `dataframe`,
porque widgets interativos causaram crashes nativos `Exited (139)` no runtime
do Streamlit ao rerenderizar a pagina. A documentacao especifica fica em
`docs/catalogo-abt.md`.

Os campos editaveis sao definidos em `config/model_config.yaml`. Atualmente o
dashboard permite simular `AMT_CREDIT`, `AMT_ANNUITY`, `NAME_EDUCATION_TYPE`,
`NAME_INCOME_TYPE`, `OCCUPATION_TYPE` e `ORGANIZATION_TYPE`. Os campos
categoricos aparecem como selecao quando existe uma lista controlada de
categorias; `ORGANIZATION_TYPE` usa o rotulo de negocio "Tipo de Organização /
Setor".

Os campos monetarios `AMT_CREDIT` (Valor Solicitado) e `AMT_ANNUITY` (Valor da
Parcela Mensal) sao renderizados como campos de texto, nao como `number_input`.
Essa escolha remove os controles incrementais `- / +` do Streamlit e deixa a
validacao sob controle da aplicacao.

Validacao aplicada aos dois campos:

- aceita valores inteiros ou decimais, incluindo virgula decimal;
- rejeita vazio, texto, zero, negativos e valores fora do intervalo;
- limite inferior: `1`;
- limite superior de `AMT_CREDIT`: `4.050.000,00`;
- limite superior de `AMT_ANNUITY`: `258.025,50`.

Os limites superiores foram calculados a partir do arquivo `abt_train.parquet`,
tomando o maior valor observado em cada coluna da ABT de treino:

```text
AMT_CREDIT  max = 4050000.0
AMT_ANNUITY max = 258025.5
```

A justificativa para usar esses tetos e evitar extrapolacao fora do dominio de
treinamento do modelo. O LightGBM foi ajustado com exemplos ate esses valores;
permitir simulacoes acima desse intervalo levaria a uma regiao sem evidencia
historica na ABT atual, reduzindo a confiabilidade operacional do score e da
explicabilidade local. O limite inferior `1` impede simulacoes sem valor
economico valido, como zero ou negativo, que tambem nao representam uma
proposta de credito realista.

Depois de aplicar overrides, a API recalcula no caminho de inferencia online as
derivadas financeiras que dependem diretamente dos valores simulados:
`CREDIT_INCOME_RATIO`, `ANNUITY_INCOME_RATIO` e `LOG_AMT_CREDIT`. Esse
comportamento fica em `scripts/predict.py` e evita que o modelo receba um valor
monetario novo junto com ratios antigos congelados da ABT. O recálculo nao altera
os pipelines offline Silver/Gold.

Os cards de resultado sao padronizados por risco. `Risk Band`,
`Prob. inadimplencia` e `Prob. adimplencia` usam lateral verde para baixo
risco, amarela para risco moderado, vermelha para alto risco e cinza para valor
ausente ou desconhecido. A faixa vem de `scripts/predict.py`: com o threshold
de negocio atual de `8%`, `Baixo risco` fica abaixo de `3,2%`, `Risco
moderado` fica de `3,2%` ate abaixo de `8%`, e `Alto risco` fica em `8%` ou
mais.

### Buckets do MinIO

Na inicializacao do servico `streamlit`, o comando executa
`scripts/ensure_minio_buckets.py` antes de subir a aplicacao web.

Buckets criados:

- `raw`
- `clean`
- `abt`
- `artifacts`

O sincronismo automatico da pasta local `Dados` para buckets foi removido. A
carga de dados brutos agora acontece pela DAG `01_bronze_ingest_kaggle`, que
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

- Buckets incluem `raw`, `clean`, `abt` e `artifacts`.
- Bucket `raw` contem os 10 CSVs esperados.

```bash
docker compose exec -T airflow airflow dags list
```

Resultado relevante:

```text
01_bronze_ingest_kaggle | /opt/airflow/dags/download_kaggle_to_minio.py | airflow | True
02_silver_clean_data      | /opt/airflow/dags/raw_to_clean_silver.py      | airflow | True
03_gold_abt_features      | /opt/airflow/dags/clean_to_abt_gold.py        | airflow | True
```

## Camada Clean (Silver)

A DAG manual `02_silver_clean_data` lê oito CSVs do bucket `raw` e cria oito
TaskGroups independentes. Cada grupo coleta e processa no staging, valida com as
regras de `HMDR_Camada_Silver.ipynb` e só então publica no bucket `clean`.
O fluxo operacional fica em `scripts/data_sanitization.py`; regras puras ficam em
`scripts/silver_transformations.py` e `scripts/silver_validations.py`.
O processamento de `bureau_balance` usa chunks e escrita incremental Parquet
para não carregar seus 27,3 milhões de linhas simultaneamente na memória.

Os logs de QA usam `[PASS]`, `[WARNING]` e `[FAIL]`. Warnings seguem a lógica do
notebook e não reprovam tasks. Falhas preservam o Parquet intermediário; uploads
bem-sucedidos removem o staging da tabela.

Consulte [`docs/camada-silver.md`](camada-silver.md) para a arquitetura completa,
semantica de falhas, execucao pela CLI e testes pytest.

```bash
docker compose exec -T airflow airflow dags trigger 02_silver_clean_data
docker compose run --rm minio-client ls --recursive local/clean
docker compose run --rm dev python scripts/data_sanitization.py bureau
```

## Camada Gold (ABT)

A DAG manual `03_gold_abt_features` consome sete Parquets do bucket `clean` e
executa 17 tasks sequenciais em sete TaskGroups. Cada origem é processada e
validada antes da próxima; o grupo final monta, valida e publica
`abt/abt_train.parquet`.

DataFrames intermediários são Parquets locais em
`Dados/.gold_staging/<run_id>`. O XCom recebe somente caminhos e metadados. Uma
falha preserva o staging e impede o upload; sucesso remove todo o staging da
execução. A validação final exige exatamente 307.511 clientes e preservação do
`TARGET`.

```bash
docker compose exec -T airflow airflow dags trigger 03_gold_abt_features
docker compose run --rm dev python scripts/abt_transform.py
docker compose run --rm minio-client stat local/abt/abt_train.parquet
```

Consulte [`docs/dags/clean_to_abt_gold.md`](dags/clean_to_abt_gold.md) para o
grafo, entradas, QA e comportamento operacional.

Ainda nao foram implementados:

- Treinamento em `Model/train.py`.
- Predicao em `Model/predict.py`.
- App Streamlit final de predicao.
- Componentes adicionais de MLOps.
