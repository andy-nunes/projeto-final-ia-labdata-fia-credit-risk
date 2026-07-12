# 📊 Home Credit Default Risk - Motor de Decisão de Crédito (MLOps)

Projeto Final MBA FIA para o desafio de Credit Risk com dados da competição
Home Credit Default Risk.

Este projeto implementa uma esteira completa de Machine Learning Operations (MLOps) para predição de risco de crédito, indo desde a ingestão de dados brutos até a disponibilização de um motor de inferência (FastAPI) e um painel de simulação para a mesa de crédito (Streamlit).

## 🏗️ Arquitetura da Solução

O ecossistema é totalmente containerizado e gerenciado via Docker, composto por:

* **Apache Airflow:** Orquestrador do pipeline de dados (ETL e treinamento do modelo).
* **MinIO (S3):** Data Lake local estruturado nos buckets `raw`, `clean`, `abt` e `artifacts`.
* **LightGBM:** Motor matemático escolhido via experimentação para maximizar o F2-Score (foco na penalização de Falsos Negativos).
* **FastAPI:** Microsserviço de backend responsável pela inferência e cálculo do SHAP (Explicabilidade Local).
* **Streamlit:** Frontend focado no usuário de negócios e na inspeção de dados.

Fluxo de dados entre camadas:

```
raw (CSVs Kaggle) → clean (Parquets padronizados) → abt (ABT de treino) → artifacts (modelo .pkl)
```

---

## ⚙️ Governança de Negócio (`model_config.yaml`)

Toda a lógica de infraestrutura, engenharia de atributos (features) e regras de negócios (como a régua de corte de aprovação) foi abstraída do código lógico e centralizada no arquivo estático `config/model_config.yaml`.

Qualquer alteração solicitada por auditoria ou pela diretoria de risco (ex: alterar o *threshold* de aprovação, ignorar colunas sensíveis ou ajustar hiperparâmetros) deve ser feita exclusivamente neste arquivo, garantindo controle de versão e rastreabilidade (GitOps).

---

## Pré-requisitos

1. Docker e Docker Compose instalados na máquina host.
2. Credenciais Kaggle em `~/.kaggle/kaggle.json` (necessário para a DAG de download).

---

## 🚀 Roteiro de Validação (Runbook)

Siga os passos abaixo para recriar e testar a esteira MLOps do zero.

### 1. Subir a Infraestrutura Base

Na raiz do projeto, inicie MinIO e Airflow em segundo plano:

```bash
docker compose build
docker compose up -d minio airflow
```

*(Aguarde aproximadamente 1 a 2 minutos para a inicialização completa do Airflow e do banco de dados interno.)*

Na inicialização, o container do Airflow executa `airflow db migrate` e
`airflow dags reserialize` antes do `airflow standalone`. Isso garante que, em
clones limpos, as DAGs montadas em `./dags` sejam serializadas no banco local e
apareçam na listagem/UI sem comando manual adicional.

O Airflow também usa hostname fixo `airflow` e define
`AIRFLOW__CORE__HOSTNAME_CALLABLE=scripts.airflow_config.get_airflow_hostname`
para evitar URLs internas de logs sem host, como `http://:8793/log/...`, em
ambientes Docker diferentes.

### 2. Executar o Pipeline de Dados e Treinamento (Airflow)

1. Acesse o orquestrador: **`http://localhost:8080`** (auth local via SimpleAuthManager: `admin` / `admin`).
2. Despause e execute as DAGs sequencialmente (aguarde uma finalizar com sucesso antes de iniciar a próxima):
   * `download_kaggle_to_minio` — ingestão dos CSVs brutos no bucket `raw`
   * `raw_to_clean_silver` — padronização e validação no bucket `clean`
   * `clean_to_abt_gold` — feature engineering e ABT no bucket `abt`
   * `train_lightgbm` — treinamento a partir de `s3://abt/abt_train.parquet` e exportação do modelo para `s3://artifacts/lightgbm_hcdr.pkl`

Equivalente via CLI:

```bash
docker compose exec -T airflow airflow dags unpause download_kaggle_to_minio
docker compose exec -T airflow airflow dags trigger download_kaggle_to_minio
docker compose exec -T airflow airflow dags trigger raw_to_clean_silver
docker compose exec -T airflow airflow dags trigger clean_to_abt_gold
docker compose exec -T airflow airflow dags trigger train_lightgbm
```

Todas as DAGs são manuais (`schedule=None`) e devem ser disparadas sob demanda.

### 3. Subir o Motor de Inferência (API Backend)

Na raiz do projeto, execute:

```bash
docker compose up -d api
```

A API expõe endpoints de escoragem e explicabilidade local (SHAP). Pelo
Compose, o dashboard da mesa de crédito consome essa API internamente via
`API_BASE_URL=http://api:8000`.

### 4. Subir o Painel da Mesa de Crédito (Dashboard Frontend)

Execute:

```bash
docker compose up -d streamlit
```

O serviço `streamlit` do `docker-compose.yml` sobe `app/dashboard.py` na porta
8501 e depende do serviço `api`. Se a porta já estiver em uso, pare o serviço
`streamlit` do compose ou rode manualmente em outra porta, por exemplo:

```bash
docker compose run --rm -p 8502:8501 dev streamlit run app/dashboard.py --server.address=0.0.0.0 --server.port=8501
```

### 5. Simulação na Mesa de Crédito

1. Acesse o painel: **`http://localhost:8501`**
2. Insira um **ID de Cliente** (`SK_ID_CURR`) válido da base de holdout de demonstração (`Dados/abt/abt_demo_holdout.parquet`, gerada pelo treinamento).
3. Analise o dossiê, faça edições cadastrais (What-If Analysis) se desejar, e clique em **"Rodar Escoragem"**.
4. O painel exibirá a probabilidade de calote, a recomendação final e os fatores determinantes para a decisão utilizando **SHAP Values**.

O dashboard usa `app/dashboard.py` como homepage. A tela exibe o motor de
decisão de crédito, consulta a API FastAPI pelo serviço `api` do Compose e
mantém um rodapé com os alunos responsáveis pelo desenvolvimento.

A homepage também possui acesso para `app/pages/catalogo_abt.py`, uma página
Streamlit com catálogo pesquisável das colunas da ABT. O catálogo é montado por
`app/abt_catalog.py` a partir do schema de `Dados/abt/abt_train.parquet`, das
marcações de `config/model_config.yaml` e das descrições oficiais do arquivo
`Dados/raw/HomeCredit_columns_description.csv`, distribuído junto aos dados da
competição Home Credit Default Risk no Kaggle. Features derivadas recebem
descrições inferidas pelas regras de engenharia ou pelo prefixo da fonte
agregada. A busca, os filtros de categoria/fonte, a tabela e o download rodam
client-side em um componente HTML/JavaScript, não como widgets Streamlit, para
evitar crashes nativos observados no runtime ao rerenderizar a página.
Detalhes de implementação e validação estão em `docs/catalogo-abt.md`.

Os campos editáveis de simulação são definidos em `config/model_config.yaml`.
Atualmente o painel permite alterar `AMT_CREDIT`, `AMT_ANNUITY`,
`NAME_EDUCATION_TYPE`, `NAME_INCOME_TYPE`, `OCCUPATION_TYPE` e
`ORGANIZATION_TYPE`. Os campos categóricos são renderizados como seleção quando
há lista controlada de categorias.

Os campos monetários `AMT_CREDIT` (Valor Solicitado) e `AMT_ANNUITY` (Valor da
Parcela Mensal) são campos de texto validados para remover os controles
incrementais `- / +` do Streamlit e evitar entradas inválidas. A regra é:

- aceitar somente números inteiros ou decimais, incluindo vírgula decimal;
- rejeitar texto, vazio, zero e valores negativos;
- limite inferior fixo: `1`;
- limite superior de `AMT_CREDIT`: `4.050.000,00`;
- limite superior de `AMT_ANNUITY`: `258.025,50`.

Os limites superiores foram extraídos de `abt_train.parquet`, usando o maior
valor observado em cada coluna na ABT de treino. A justificativa é manter a
simulação dentro do domínio conhecido pelo modelo LightGBM: valores acima do
máximo visto no treinamento seriam extrapolação operacional, poderiam gerar
scores menos confiáveis e não representam uma faixa aprendida pela esteira de
modelagem atual.

Na inferência online, a API aplica os overrides e recalcula as derivadas
financeiras diretamente impactadas antes de chamar o LightGBM:
`CREDIT_INCOME_RATIO`, `ANNUITY_INCOME_RATIO` e `LOG_AMT_CREDIT`. Isso evita
combinar valores simulados com ratios antigos congelados da ABT.

Os cards de resultado usam a mesma régua visual de risco:

- verde para baixo risco;
- amarelo para risco moderado;
- vermelho para alto risco;
- cinza para valor ausente ou desconhecido.

Essa régua é aplicada a `Risk Band`, `Prob. inadimplência` e
`Prob. adimplência`. Com `threshold=8%`, `Baixo risco` representa
probabilidade de inadimplência abaixo de `3,2%`, `Risco moderado` representa
probabilidade de `3,2%` até abaixo de `8%`, e `Alto risco` representa
probabilidade de `8%` ou mais.

---

## Ambiente com Docker

### Comandos úteis

Abra um shell interativo dentro do ambiente de desenvolvimento:

```bash
docker compose run --rm dev
```

Suba todos os serviços locais (MinIO, Airflow, API e Streamlit):

```bash
docker compose up -d --build
```

Reinicie tudo do zero (inclui volumes):

```bash
docker compose down -v
```

### Acessos locais

- Airflow: http://localhost:8080 (SimpleAuthManager)
- MinIO Console: http://localhost:9001 (`minioadmin` / `minioadmin`)
- MinIO API: http://localhost:9000
- Streamlit (dashboard da mesa de crédito): http://localhost:8501
- API FastAPI: http://localhost:8000

Todos esses serviços montam a pasta `Dados/` dentro dos containers.

Na inicialização do serviço `streamlit` do compose, `scripts/ensure_minio_buckets.py` cria os buckets `raw`, `clean`, `abt` e `artifacts`.

### Pipelines fora do Airflow

Os mesmos fluxos podem ser executados diretamente, mantendo a lógica importada pelas DAGs:

```bash
docker compose run --rm dev python scripts/silver_pipeline.py bureau application_train
docker compose run --rm dev python scripts/gold_pipeline.py
```

### QA, staging e publicação

**Camada clean (Silver):** cada tabela possui um TaskGroup isolado com
`coletar_e_processar -> validar -> escrever_clean`; o bucket `clean` só recebe
Parquets aprovados. O QA registra `[PASS]`, `[WARNING]` e `[FAIL]`. Somente
`[FAIL]` bloqueia a publicação. Staging aprovado é removido após o upload;
staging reprovado permanece em `Dados/.silver_staging` para diagnóstico.

**Camada abt (Gold):** sete TaskGroups e 17 tasks estritamente sequenciais.
As entradas são sete Parquets do bucket `clean`. Os agregados temporários ficam
em `Dados/.gold_staging/<run_id>` e não trafegam pelo XCom. Somente após todas
as validações `[PASS]` o pipeline substitui `abt/abt_train.parquet`; `[INFO]`
não reprova, `[FAIL]` bloqueia a cadeia e preserva o staging para diagnóstico.

### MinIO Client

Para inspecionar ou copiar arquivos entre MinIO e `Dados/`, use o serviço
`minio-client`. Consulte `docs/minio-client.md`.

Exemplos:

```bash
docker compose run --rm minio-client ls --recursive local/raw
docker compose run --rm minio-client ls --recursive local/clean
docker compose run --rm minio-client stat local/abt/abt_train.parquet
```

Para detalhes das DAGs Airflow disponíveis, consulte `docs/dags/README.md`.

---

## Dados

Arquivos CSV não devem ser versionados. A pasta `Dados/` existe para volumes
locais e artefatos intermediários, mas os dados brutos baixados pelo Kaggle
devem ser armazenados no bucket `raw` do MinIO.

O holdout de demonstração (`Dados/abt/abt_demo_holdout.parquet`) é gerado
localmente pelo pipeline de treinamento. O modelo treinado e seus metadados são
publicados no MinIO em `s3://artifacts/lightgbm_hcdr.pkl` e
`s3://artifacts/model_metadata.json`, para consumo posterior pela API e pelo
dashboard da mesa de crédito.

---

## Documentação

- `docs/ambiente-docker-e-dados.md`: arquitetura local, serviços e fluxo de
  dados entre os buckets.
- `docs/camada-silver.md`: transformações, staging e QA de `raw` para `clean`.
- `docs/camada-gold-abt-design.md`: transformações, staging e QA de `clean`
  para `abt`.
- `docs/catalogo-abt.md`: catálogo pesquisável da ABT no Streamlit, origem dos
  metadados, descrições em português e validações.
- `docs/dags/README.md`: índice e comandos das DAGs manuais.
- `docs/exemplos-confusion-matrix.md`: storytelling dos quatro cenários da
  matriz de confusão com exemplos reais de `SK_ID_CURR`.
- `docs/minio-client.md`: inspeção e cópia de objetos no MinIO.
- `docs/model-config.md`: guia do `config/model_config.yaml`, incluindo
  threshold, features, paths, overrides por variavel de ambiente e quando
  retreinar o modelo.

---

## Validação do projeto

Depois de alterar DAGs, scripts ou testes, execute no ambiente Airflow:

```bash
docker compose exec -T airflow python -m pytest /opt/airflow/tests -q
docker compose exec -T airflow airflow dags list-import-errors
docker compose exec -T airflow airflow dags list
```

Todo módulo, classe, helper, fixture e função de teste Python novo deve possuir
docstring em português. A suite usa `pytest` e `pytest-mock`.
