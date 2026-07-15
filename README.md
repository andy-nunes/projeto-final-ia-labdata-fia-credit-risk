# Home Credit Default Risk - Motor de Decisão de Crédito

Projeto final de MLOps para risco de crédito, baseado na competição Kaggle
Home Credit Default Risk. A solução implementa uma esteira completa para
baixar dados brutos, transformar bases transacionais em uma ABT de modelagem,
treinar um modelo LightGBM e disponibilizar um serviço de predição consumido por
um dashboard de simulação para a mesa de crédito.

**Entrega individual (MLOps):** arquitetura, Docker Compose, monitoramento (iii)
e automação com agentes (iv) estão documentados em
[`MLOps/Readme.md`](MLOps/Readme.md).

## Objetivo de negócio

O projeto apoia a decisão de concessão de crédito em um contexto no qual os
erros são assimétricos. Recusar um bom pagador reduz receita e oportunidade
comercial; aprovar um cliente que inadimplirá pode gerar perda direta de
crédito, custo de cobrança, provisão e deterioração da carteira.

Por isso, a modelagem prioriza a redução de falsos negativos: clientes
historicamente inadimplentes que seriam aprovados pelo motor. A solucao busca
combinar inclusão, critério de risco e explicabilidade para permitir aprovar
melhor, recusar com mais fundamento e proteger a margem da operação.

## Metodologia

A abordagem segue uma esteira MLOps local, containerizada e reprodutível:

- **Análise exploratória:** o notebook `notebooks/01_exp_analysis.ipynb` foi
  usado para conhecer as bases, distribuições, nulos e relações iniciais entre
  variáveis.
- **Ingestão:** a DAG `01_bronze_ingest_kaggle` baixa os CSVs do Kaggle e
  publica os dados brutos no bucket `raw` do MinIO.
- **Camada Silver:** `scripts/data_sanitization.py` (DAG `02_silver_clean_data`)
  transforma oito arquivos de negocio em Parquets tratados, com QA antes da
  escrita no bucket `clean`.
- **Camada Gold / ABT:** `scripts/abt_transform.py` (DAG `03_gold_abt_features`)
  agrega historicos de bureau, cartao, propostas anteriores, POS/CASH e
  pagamentos para gerar `abt_train.parquet` no bucket `abt`.
- **Modelagem:** a análise comparativa de modelos foi feita no notebook
  `notebooks/02_model_evaluation.ipynb`. A partir dessa comparação, o LightGBM foi
  escolhido como modelo campeão e seu treino foi consolidado em
  `Model/train.py` / `notebooks/03_train_exploration.ipynb`, usando `Model/model_config.yaml`
  para features, splits, métricas e threshold.
- **Orquestração:** as DAGs Airflow encadeiam a esteira; o equivalente CLI é
  `scripts/pipeline_orchestration.py`.
- **Serving:** `scripts/predict.py` alimenta a FastAPI e o Streamlit com
  consulta de cliente, escoragem e simulações What-If com explicabilidade local.

As métricas de negócio incluem PR-AUC, F2-Score, recall da classe inadimplente,
falsos negativos, falsos positivos e taxa de reprovação no threshold
operacional.

## Arquitetura da solução

<p align="center">
  <img
    src="docs/architecture/arquitetura-mlops-home-credit.png"
    alt="Arquitetura MLOps do motor de decisão de crédito"
    width="900"
  />
</p>

Arquivos da arquitetura: [`PNG`](docs/architecture/arquitetura-mlops-home-credit.png) e
[`SVG`](docs/architecture/arquitetura-mlops-home-credit.svg).

Componentes principais:

- **Airflow:** orquestra as DAGs manuais de ingestão, ETL, ABT e treinamento.
- **MinIO S3:** organiza o Data Lake local nos buckets `raw`, `clean`, `abt` e
  `artifacts`.
- **Scripts Python:** concentram transformações, validações, pipelines e
  inferência para manter DAGs finas.
- **LightGBM:** modelo supervisionado usado para predizer probabilidade de
  inadimplência.
- **FastAPI:** serviço de predição com endpoints de health check, consulta de
  cliente e escoragem.
- **Streamlit:** interface de negócio para consulta, simulação de variáveis e
  leitura dos fatores explicativos.

### Interface Streamlit (estado atual)

O dashboard principal (`app/dashboard.py`) foi organizado para leitura executiva
em quatro abas:

- `Mesa de Crédito`
- `Dicionário de Variáveis`
- `Performance e ROI`
- `Monitoramento MLOps`

No cabeçalho da aplicação:

- título institucional: `Motor de Decisão de Crédito — Home Credit`
- autoria: `Anderson Nunes`

## Pre-requisitos

1. Docker e Docker Compose instalados.
2. Token da API Kaggle em `~/.config/fia-credit-risk/kaggle/kaggle.env` (gerado em
   [kaggle.com/settings/api](https://www.kaggle.com/settings/api) → *Generate New Token*),
   no formato `KAGGLE_API_TOKEN=<seu-token>`.
3. Copiar `.env.example` para `.env` na raiz e preencher somente segredos locais
   (ex.: `GEMINI_API_KEY`). Esse é o caminho canônico para o Compose base.
4. Para segredos locais fora do repositório, o `docker-compose.override.yml`
   carrega opcionalmente (`required: false`) arquivos em:
   - `~/.config/fia-credit-risk/gemini/gemini.env`
   - `~/.config/fia-credit-risk/kaggle/kaggle.env`
   - `~/.config/fia-credit-risk/minio/minio.env`
   - `~/.config/fia-credit-risk/airflow/airflow.env`
5. Porta local livre para os servicos principais: `8080`, `9000`, `9001`,
   `8000` e `8501`.

### Contrato de configuracao das integracoes externas

- Configuracao nao sensivel de Kaggle, MinIO e Gemini fica versionada em
  `config/integrations.yaml`.
- Segredos continuam fora do repositório (`GEMINI_API_KEY`,
  `KAGGLE_API_TOKEN`, credenciais MinIO por env).
- Precedencia de resolucao: **env > YAML > default interno minimo**.
- Overwrites MinIO suportados por env:
  - endpoint/buckets do loader central: `MINIO_ENDPOINT_URL`, `RAW_BUCKET`,
    `PROJECT_BUCKETS`
  - credenciais MinIO (segredos): `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`,
    `MINIO_KEY`, `MINIO_SECRET`
  - paths de modelagem/serving: `ABT_PATH`, `DEMO_HOLDOUT_PATH`,
    `MODEL_PATH`, `MODEL_METADATA_PATH`

### Nota sobre dependências (app x orquestrador)

- `requirements.txt` concentra dependências do runtime de app/pipeline Python
  (API, Streamlit e scripts de dados/modelo).
- O Apache Airflow é provido pela imagem base do serviço `airflow`
  (`apache/airflow:3.1.2-python3.13`) definida em `Dockerfile.airflow`.
- Pacotes extras específicos do orquestrador são instalados via
  `requirements-airflow.txt`.

## Como treinar o modelo

Suba a infraestrutura:

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

> Limitação conhecida de ambiente local: este projeto usa `LocalExecutor` com
> banco SQLite para desenvolvimento e demonstração de TCC. Não é uma topologia
> de alta disponibilidade para produção.

### 2. Executar o Pipeline de Dados e Treinamento (Airflow)

1. Acesse o orquestrador: **`http://localhost:8080`** (auth local via `AIRFLOW_SIMPLE_AUTH_MANAGER_USERS`; default: `admin:admin`).
2. Despause as DAGs da esteira Medalhão + monitoramento e dispare apenas a primeira; as demais da esteira são acionadas automaticamente via `TriggerDagRunOperator`:
   * `01_bronze_ingest_kaggle` — ingestão dos CSVs brutos no bucket `raw` → dispara Silver
   * `02_silver_clean_data` — padronização e validação no bucket `clean` → dispara Gold
   * `03_gold_abt_features` — feature engineering e ABT no bucket `abt` → dispara treino
   * `04_model_train_lightgbm` — treinamento a partir de `s3://abt/abt_train.parquet` e exportação do modelo para `s3://artifacts/lightgbm_hcdr.pkl` → dispara monitoramento
   * `05_monitor_health` — checagens de saúde a cada 5 min (freshness 24h sobre o treino)

Equivalente via CLI:

```bash
docker compose exec -T airflow airflow dags unpause 01_bronze_ingest_kaggle
docker compose exec -T airflow airflow dags unpause 02_silver_clean_data
docker compose exec -T airflow airflow dags unpause 03_gold_abt_features
docker compose exec -T airflow airflow dags unpause 04_model_train_lightgbm
docker compose exec -T airflow airflow dags unpause 05_monitor_health
docker compose exec -T airflow airflow dags trigger 01_bronze_ingest_kaggle
```

O encadeamento Bronze → Silver → Gold → Model → Monitor é automático após o trigger inicial.
A DAG `05_monitor_health` também roda a cada 5 minutos enquanto o `trained_at` do modelo estiver nas últimas 24h.

Saidas esperadas:

- `raw`: 10 CSVs da competicao Kaggle.
- `clean`: Parquets Silver tratados e validados.
- `abt`: `abt_train.parquet` e `abt_demo_holdout.parquet`.
- `artifacts`: `lightgbm_hcdr.pkl` e `model_metadata.json`.

Dados oficiais de runtime ficam no MinIO (S3). Arquivos sob `Dados/` sao
apenas staging/debug e nao competem com o lake.

Para inspecionar objetos no MinIO:

```bash
docker compose run --rm minio-client ls --recursive local/artifacts
docker compose run --rm minio-client stat local/abt/abt_train.parquet
```

## Execução do serviço de predição

Depois de treinar o modelo e publicar os artefatos no MinIO, suba a API:

```bash
docker compose up -d api
```

Valide o health check:

```bash
curl -sS http://localhost:8000/
```

Consulte o dossiê de um cliente do holdout de demonstração:

```bash
curl -sS http://localhost:8000/client/139767
```

Execute uma escoragem sem alterações:

```bash
curl -sS -X POST http://localhost:8000/score \
  -H 'Content-Type: application/json' \
  -d '{"client_id":139767,"features_override":{}}'
```

Gerar parecer **CredIA** sob demanda (sem rerodar a escoragem):

```bash
curl -sS -X POST http://localhost:8000/score/ai-commentary \
  -H 'Content-Type: application/json' \
  -d '{"score_payload":{"sk_id_curr":139767,"probability":0.0453,"prediction":0,"threshold":0.08,"risk_band":"Risco moderado","label":"Aprovado (Pagador Saudável)","top_risk_factors":[["CC_UTILIZATION_MAX",18.0]],"top_positive_factors":[["NAME_EDUCATION_TYPE",7.0]],"applied_overrides":{},"input":{"EXT_SOURCE_MEAN":0.55}}}'
```

Execute uma simulação What-If com override de features:

```bash
curl -sS -X POST http://localhost:8000/score \
  -H 'Content-Type: application/json' \
  -d '{"client_id":139767,"features_override":{"AMT_CREDIT":500000,"AMT_ANNUITY":25000}}'
```

Para usar a interface de negócio:

```bash
docker compose up -d streamlit
```

Acesse `http://localhost:8501`. O dashboard consome a API internamente via
`API_BASE_URL=http://api:8000`.

### Configuração do CredIA (Gemini)

Caminho canônico (Compose base): `.env` na raiz do projeto.

```bash
GEMINI_API_KEY=<sua-chave>
GEMINI_MODEL=gemini-flash-lite-latest
GEMINI_MODEL_FALLBACKS=gemini-2.0-flash-lite,gemini-2.5-flash-lite
```

Alternativa opcional (segredo fora do repo): criar
`~/.config/fia-credit-risk/gemini/gemini.env`; o `docker-compose.override.yml` já
faz o carregamento com `required: false`.

```bash
mkdir -p ~/.config/fia-credit-risk/gemini
cat > ~/.config/fia-credit-risk/gemini/gemini.env <<'EOF'
GEMINI_API_KEY=<sua-chave>
GEMINI_MODEL=gemini-flash-lite-latest
GEMINI_MODEL_FALLBACKS=gemini-2.0-flash-lite,gemini-2.5-flash-lite
EOF
chmod 700 ~/.config/fia-credit-risk/gemini
chmod 600 ~/.config/fia-credit-risk/gemini/gemini.env
```

### Configuração do Kaggle

Caminho canônico do token no host:

```bash
mkdir -p ~/.config/fia-credit-risk/kaggle
cat > ~/.config/fia-credit-risk/kaggle/kaggle.env <<'EOF'
KAGGLE_API_TOKEN=<seu-token>
EOF
chmod 700 ~/.config/fia-credit-risk/kaggle
chmod 600 ~/.config/fia-credit-risk/kaggle/kaggle.env
```

O `docker-compose.override.yml` carrega esse arquivo como `env_file` para os
serviços `dev` e `airflow` (`required: false`).

### Configuração do MinIO e Airflow (local)

Para centralizar credenciais locais fora do repositório:

```bash
mkdir -p ~/.config/fia-credit-risk/minio ~/.config/fia-credit-risk/airflow
cat > ~/.config/fia-credit-risk/minio/minio.env <<'EOF'
MINIO_ENDPOINT_URL=http://minio:9000
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
MINIO_KEY=minioadmin
MINIO_SECRET=minioadmin
AIRFLOW_CONN_MINIO_DEFAULT=aws://minioadmin:minioadmin@?host=http%3A%2F%2Fminio%3A9000
EOF
cat > ~/.config/fia-credit-risk/airflow/airflow.env <<'EOF'
AIRFLOW_SIMPLE_AUTH_MANAGER_USERS=admin:admin
EOF
chmod 700 ~/.config/fia-credit-risk/minio ~/.config/fia-credit-risk/airflow
chmod 600 ~/.config/fia-credit-risk/minio/minio.env ~/.config/fia-credit-risk/airflow/airflow.env
```

Observações operacionais:

- Defaults oficiais ficam em `config/integrations.yaml`; as variaveis acima
  sao overrides opcionais.

- A escoragem (`/score`) roda com baixa latência e **não bloqueia** na IA.
- O parecer é gerado sob demanda via botão `Gerar parecer CredIA` na Mesa.
- O CredIA usa contexto da run (`/score`), benchmarks da carteira (holdout) e
  highlights do notebook `notebooks/01_exp_analysis.ipynb`.
- Se o Gemini estiver indisponível (ex.: pico de demanda), o card exibe
  indisponibilidade com detalhe técnico e mantém humano no loop.

### Decisões de modelagem e operação (contexto TCC)

- `scale_pos_weight=1.0` no treino (`scripts/train.py`) foi uma decisão de
  negócio deliberada para evitar aumento excessivo de falsos positivos; o
  equilíbrio operacional da carteira é controlado via `business_threshold=0.08`.
- A orquestração oficial de execução é via Airflow (DAGs 01→05). O script
  `scripts/pipeline_orchestration.py` permanece como alternativa CLI fora do
  orquestrador.
- O monitoramento recorrente (`05_monitor_health`) roda em janela de 24h após
  treino recente; para o escopo do TCC essa política é intencional e pode ser
  expandida no roadmap.
- `notebooks/03_train_exploration.ipynb` é artefato exploratório congelado com
  outputs preservados para banca; não faz parte do runtime de produção.
- Staging temporário Gold/Silver é removido em execuções bem-sucedidas; sobras
  podem ocorrer apenas em falhas/interrupções.

## Próximos passos de desenvolvimento

Os itens **iii** (monitoramento) e **iv** (automação + agente de apoio) possuem
implementação operacional:

- Monitoramento: DAG `05_monitor_health` / `POST /monitoring/run` →
  `s3://artifacts/monitoring/latest.json` (saúde, artefatos, PSI/drift, schema, baseline)
- Automação: triagem pós-`/score` e `POST /webhooks/credit-decision` →
  `s3://artifacts/automation/`
- CredIA: `POST /score/ai-commentary` + bloco visual na Mesa de Crédito para
  insights e checklist ao gerente

Detalhes em [`MLOps/Readme.md`](MLOps/Readme.md) e na documentação
[`docs/architecture/mlops-monitoramento-e-automacao.md`](docs/architecture/mlops-monitoramento-e-automacao.md).

Evoluções futuras (alertas contínuos de drift em janela viva, experimentos com
modelos multimodais) permanecem no roadmap, sempre com humano no loop.


## Documentação

Detalhes operacionais e técnicos ficam em [`docs/README.md`](docs/README.md):

- `docs/architecture/ambiente-docker-e-dados.md`: ambiente Docker, servicos e volumes.
- `docs/pipeline/camada-silver.md`: transformações, staging e QA de `raw` para `clean`.
- `docs/pipeline/camada-gold-abt-design.md`: transformações, staging e QA de `clean`
  para `abt`.
- `docs/operations/catalogo-abt.md`: dicionario de variaveis da ABT no Streamlit.
- `docs/pipeline/dags/README.md`: índice e comandos das DAGs manuais.
- `docs/modeling/exemplos-confusion-matrix.md`: exemplos de TN, TP, FN e FP.
- `docs/operations/minio-client.md`: inspeção e cópia de objetos no MinIO.
- `docs/modeling/model-config.md`: guia do `Model/model_config.yaml`.
- `docs/architecture/mlops-monitoramento-e-automacao.md`: proposta de monitoramento (iii) e
  de automação / agentes de IA (iv).

## Validação básica

Depois de alterar DAGs, scripts ou testes, rode validações proporcionais:

```bash
bash scripts/dev/validate_pre_defesa.sh
```

Ou, manualmente:

```bash
docker compose exec -T airflow python -m pytest /opt/airflow/tests -q
docker compose exec -T airflow airflow dags list-import-errors
docker compose exec -T airflow airflow dags list
```

Todo módulo, classe, helper, fixture e função de teste Python novo deve possuir
docstring em português. A suíte usa `pytest` e `pytest-mock`.

Markers oficiais (`pytest.ini` / `tests/conftest.py`):

- `streamlit` — testes da UI/catalogo (container `dev`)
- `airflow` — testes de DAGs (container `airflow`)

Exemplo:

```bash
docker compose exec -T airflow python -m pytest /opt/airflow/tests -m "not streamlit" -q
docker compose exec -T dev python -m pytest tests -m streamlit -q
```