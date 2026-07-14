# MLOps — Entrega Individual (FIA Labdata)

Documento de referência da **etapa individual** do Projeto Final: arquitetura
funcional, infraestrutura Docker, orquestração do pipeline, monitoramento (iii)
e automação com agentes de IA (iv).

> **Nota de estrutura:** os scripts executáveis vivem em `scripts/` (fonte única
> de verdade). As pastas `MLOps/`, `Model/` e `DataPipeline/` espelham os caminhos
> exigidos pelo enunciado via symlinks, sem duplicar código.

---

## i) Proposta de Arquitetura Funcional

### Fluxo de dados (origem → deploy)

```
Kaggle (CSVs)
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  DAG 01_bronze_ingest_kaggle                                    │
│  scripts/kaggle_to_minio.py                                     │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
                    MinIO bucket: raw
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  DAG 02_silver_clean_data                                       │
│  DataPipeline/data_sanitization.py                              │
│  (QA + Parquet Silver)                                          │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
                    MinIO bucket: clean
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  DAG 03_gold_abt_features                                       │
│  DataPipeline/abt_transform.py                                │
│  (feature engineering + ABT)                                    │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
                    MinIO bucket: abt  →  abt_train.parquet
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  DAG 04_model_train_lightgbm                                    │
│  Model/train.py + Model/model_config.yaml                       │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
                    MinIO bucket: artifacts
                    (lightgbm_hcdr.pkl + model_metadata.json)
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
     FastAPI (app/main.py)          Streamlit (app/dashboard.py)
     Model/predict.py               consome API via /client e /score
```

### Diagrama visual

<p align="center">
  <img
    src="../docs/architecture/arquitetura-mlops-home-credit.png"
    alt="Arquitetura MLOps do motor de decisão de crédito"
    width="900"
  />
</p>

Arquivos: [`PNG`](../docs/architecture/arquitetura-mlops-home-credit.png) ·
[`SVG`](../docs/architecture/arquitetura-mlops-home-credit.svg)

### Componentes

| Componente | Papel | Artefato principal |
|---|---|---|
| **MinIO** | Object Storage (Data Lake S3-compatível) | Buckets `raw`, `clean`, `abt`, `artifacts` |
| **Airflow** | Orquestração das DAGs manuais encadeadas | `dags/01_…` a `dags/04_…` |
| **DataPipeline** | ETL Silver e Gold com QA bloqueante | `data_sanitization.py`, `abt_transform.py`, `pipeline_config.yaml` |
| **Model** | Treino LightGBM e inferência | `train.py`, `predict.py`, `model_config.yaml` |
| **FastAPI** | Serviço REST de escoragem | `app/main.py` — `/`, `/client/{id}`, `/score` |
| **Streamlit** | Interface da mesa de crédito (What-If + XAI) | `app/dashboard.py` |

Os CSVs **não** ficam versionados em `/Dados`; a ingestão publica diretamente
no MinIO. A pasta `Dados/` guarda apenas volumes de staging temporário; ABT,
holdout de demo, modelo e metadata oficiais residem nos buckets do lake.

---

## ii) Infraestrutura Docker Compose

Arquivo: [`MLOps/docker-compose.yml`](docker-compose.yml) (symlink para a raiz).

### Serviços

| Serviço | Porta | Função |
|---|---|---|
| `minio` | 9000 / 9001 | Data Lake |
| `airflow` | 8080 | Orquestrador (UI: admin / admin) |
| `api` | 8000 | FastAPI de predição |
| `streamlit` | 8501 | Dashboard de negócio |
| `dev` | — | Shell interativo para scripts |
| `minio-client` | — | CLI `mc` para inspeção de buckets |

### Dependências: `requirements.txt` x Airflow

- O `requirements.txt` da raiz cobre o runtime de aplicação e pipeline Python
  (ex.: FastAPI, Streamlit, boto3, s3fs, LightGBM, scikit-learn).
- O **Apache Airflow não é instalado por esse arquivo**: ele já vem da imagem
  base do orquestrador em `Dockerfile.airflow` (`apache/airflow:3.1.2-python3.13`).
- Dependências adicionais usadas dentro do container Airflow ficam em
  `requirements-airflow.txt`.
- Decisão arquitetural: separar as dependências do app e do orquestrador para
  reduzir acoplamento e manter build reproduzível por serviço.

### Pré-requisito (ingestão Bronze)

Token Kaggle em `~/.kaggle/access_token` ([settings/api](https://www.kaggle.com/settings/api)
→ *Generate New Token*). A pasta `~/.kaggle` é montada no container do Airflow;
o script `kagglehub` usa esse token para baixar a competição.

### Subir o ambiente

```bash
docker compose build
docker compose up -d minio airflow
```

Aguarde 1–2 minutos para o Airflow concluir `db migrate` e `dags reserialize`.

### Executar o pipeline (Airflow)

1. Acesse `http://localhost:8080`.
2. Despause as quatro DAGs e dispare **apenas** `01_bronze_ingest_kaggle`; as
   demais são acionadas automaticamente.

Equivalente CLI:

```bash
docker compose exec -T airflow airflow dags unpause 01_bronze_ingest_kaggle
docker compose exec -T airflow airflow dags unpause 02_silver_clean_data
docker compose exec -T airflow airflow dags unpause 03_gold_abt_features
docker compose exec -T airflow airflow dags unpause 04_model_train_lightgbm
docker compose exec -T airflow airflow dags trigger 01_bronze_ingest_kaggle
```

### Orquestração fora do Airflow

[`MLOps/pipeline_orchestration.py`](pipeline_orchestration.py) executa a mesma
cadeia via CLI:

```bash
docker compose exec -T dev python -m scripts.pipeline_orchestration
docker compose exec -T dev python -m scripts.pipeline_orchestration --skip-ingest
```

### Subir e testar o serviço de predição

```bash
docker compose up -d api streamlit

curl -sS http://localhost:8000/
curl -sS http://localhost:8000/client/139767
curl -sS -X POST http://localhost:8000/score \
  -H 'Content-Type: application/json' \
  -d '{"client_id":139767,"features_override":{}}'
```

Dashboard: `http://localhost:8501`

Abas da interface (estado atual)

- `Mesa de Crédito`
- `Dicionário de Variáveis`
- `Performance e ROI`
- `Monitoramento MLOps`

Inspecionar MinIO:

```bash
docker compose run --rm minio-client ls --recursive local/artifacts
docker compose run --rm minio-client stat local/abt/abt_train.parquet
```

---

## iii) Monitoramento em Produção

Documento teórico:
[`docs/architecture/mlops-monitoramento-e-automacao.md`](../docs/architecture/mlops-monitoramento-e-automacao.md)

### Implementação operacional

| Peça | Caminho |
|---|---|
| Script | `scripts/mlops_monitoring.py` |
| Config drift (PSI) | `DataPipeline/pipeline_config.yaml` → seção `monitoring` |
| DAG | `05_monitor_health` |
| Relatório | `s3://artifacts/monitoring/latest.json` |
| API | `GET /monitoring/latest`, `POST /monitoring/run` |

Checagens automatizadas:

- Saúde da API e latência do health check
- Presença de ABT, holdout, modelo e metadata no MinIO
- Coerência do `business_threshold` (config × metadata)
- Contrato de features (schema metadata × ABT)
- **Data drift (PSI)** em features-chave: `EXT_SOURCE_*`, `AMT_CREDIT`, `AMT_ANNUITY`, `NAME_INCOME_TYPE`
- **Linha de base de performance** (PR-AUC, recall, FN/FP do `model_metadata.json`)

```bash
docker compose exec -T airflow airflow dags unpause 05_monitor_health
docker compose exec -T airflow airflow dags trigger 05_monitor_health
curl -sS -X POST http://localhost:8000/monitoring/run | python3 -m json.tool
curl -sS http://localhost:8000/monitoring/latest | python3 -m json.tool
```

### Runbook resumido

| Sintoma | Resposta proposta |
|---|---|
| Health check ou artefato indisponível | Rollback; não escorar novas propostas |
| QA Silver/Gold falha | Corrigir origem; não publicar ABT |
| Drift alto em features-chave | Investigar; eventual retreino |
| Queda de PR-AUC / alta de FN | Congelar régua agressiva; retreino governado |

---

## iv) Ações Automatizadas e Agentes de IA

Documento teórico (inclui agentes futuros):
[`docs/architecture/mlops-monitoramento-e-automacao.md`](../docs/architecture/mlops-monitoramento-e-automacao.md)

### Em produção hoje (implementado)

| Peça | Caminho |
|---|---|
| Script | `scripts/credit_automation.py` |
| Integração | `POST /score` (campo `automation` + `emit_automation`) |
| Webhook | `POST /webhooks/credit-decision` |
| Eventos | `s3://artifacts/automation/queues/{fila}/` + `latest.json` |

Faixas (threshold `t`, padrão 0,08) — cada uma vira **pasta** no MinIO:

- `proba < 0.4·t` → `queues/autoaprovacao_candidata/`
- `0.4·t ≤ proba < t` → `queues/mesa_analise/`
- `proba ≥ t` → `queues/recusa_candidata/`

**Humano no loop:** a automação não concede crédito; apenas classifica e audita.

```bash
curl -sS -X POST http://localhost:8000/score \
  -H 'Content-Type: application/json' \
  -d '{"client_id":139767,"features_override":{},"emit_automation":true}' \
  | python3 -m json.tool

docker compose run --rm minio-client cat local/artifacts/automation/latest.json
```

### Proposta técnica (roadmap)

- Agentes de IA/LLM para gerar parecer em linguagem natural, explicações
  contextualizadas e apoio ao analista de crédito.
- Consumo dos eventos já publicados em `s3://artifacts/automation/` como trilha
  de auditoria e gatilho de contexto.
- Continuidade do princípio de governança: **humano no loop** para decisão final.

---

## Mapa de arquivos (conformidade com enunciado)

| Caminho exigido | Implementação |
|---|---|
| `MLOps/docker-compose.yml` | Symlink → `../docker-compose.yml` |
| `MLOps/pipeline_orchestration.py` | Symlink → `../scripts/pipeline_orchestration.py` |
| `MLOps/Readme.md` | Este arquivo |
| `Model/predict.py` | Symlink → `../scripts/predict.py` |
| `Model/train.py` | Symlink → `../scripts/train.py` |
| `Model/model_config.yaml` | Configuração central do LightGBM |
| `DataPipeline/data_sanitization.py` | Symlink → `../scripts/data_sanitization.py` |
| `DataPipeline/abt_transform.py` | Symlink → `../scripts/abt_transform.py` |
| `DataPipeline/pipeline_config.yaml` | Buckets, chaves e parâmetros de drift (PSI) |
| `app/` | FastAPI + Streamlit (serviço de predição) |

Configuração central do modelo: `Model/model_config.yaml`.

### Validação pré-banca

```bash
bash scripts/dev/validate_pre_defesa.sh
```

Executa testes (Airflow + dev), verifica importação das DAGs e health checks da API
e do Streamlit.

---

## Documentação complementar

- [`docs/README.md`](../docs/README.md) — índice técnico completo
- [`docs/architecture/ambiente-docker-e-dados.md`](../docs/architecture/ambiente-docker-e-dados.md)
- [`docs/pipeline/dags/README.md`](../docs/pipeline/dags/README.md)
- [`README.md`](../README.md) — visão geral do projeto e instruções de treino
