# Monitoramento e Automação MLOps (itens iii e iv)

Documento de referência para a etapa individual do Projeto Final (Labdata FIA).
Descreve o **monitoramento em produção** e as **ações automatizadas / agentes de IA**
conectados às previsões do motor de crédito.

A arquitetura base (Airflow, MinIO, LightGBM, FastAPI e Streamlit) já está
implementada. Este documento alinha **proposta teórica** e **implementação mínima
operacional** presente no repositório.

---

## Mapa implementação × evolução

| Capacidade | Status no código | Artefato |
|---|---|---|
| Health check da API | ✅ Implementado | `scripts/mlops_monitoring.py`, `GET /` |
| Presença de artefatos no MinIO | ✅ Implementado | DAG `05_monitor_health` |
| Coerência de threshold (config × metadata) | ✅ Implementado | `check_threshold_coherence` |
| Contrato de features (schema) | ✅ Implementado | `check_feature_schema` |
| Data drift (PSI) | ✅ Implementado | `check_data_drift` + `DataPipeline/pipeline_config.yaml` |
| Performance baseline (decay proxy) | ✅ Implementado | `check_performance_baseline` |
| Triagem pós-escoragem (filas MinIO) | ✅ Implementado | `scripts/credit_automation.py` |
| Webhook de decisão | ✅ Implementado | `POST /webhooks/credit-decision` |
| Agentes LLM (parecer em linguagem natural) | 🔜 Evolução futura | Proposta abaixo (item iv) |
| Alertas contínuos / PSI em janela viva | 🔜 Evolução futura | Runbook + Airflow agendado |

---

## iii) Monitoramento de dados e do modelo em produção

### Objetivo

Garantir que a solução continue alinhada ao problema de negócio depois do
deploy: reduzir calotes aprovados (falsos negativos), preservar taxa de
aprovação sustentável e detectar degradação antes que a régua operacional
deixe de ser confiável.

### O que monitorar

#### 1. Saúde operacional do serviço

| Sinal | Fonte atual | Falha típica |
|---|---|---|
| Disponibilidade da API | `GET /` (health check) | Container fora, timeout, erro 5xx |
| Latência de `/score` e `/client/{id}` | Relatório `api_health` | Carga, leitura lenta no MinIO |
| Presença dos artefatos | `artifacts/lightgbm_hcdr.pkl`, `model_metadata.json` | Treino incompleto, path S3 inválido |
| Falha de DAG | UI/logs do Airflow | QA Silver/Gold, falta de CSV no `raw` |

Ação: alerta imediato à operação de dados/MLOps; bloquear novas escoragens se
o artefato ou o health check falharem.

#### 2. Qualidade e estabilidade dos dados

O pipeline já valida Silver e Gold antes de publicar. Em produção contínua:

- **Volume e completude:** queda abrupta de linhas na ABT ou aumento de nulos em
  features críticas (`EXT_SOURCE_*`, agregados de bureau/cartão).
- **Drift de entrada (data drift):** PSI entre amostra da ABT (referência) e
  holdout de demo (proxy da população escorada). Features monitoradas em
  `DataPipeline/pipeline_config.yaml`.
- **Schema / contrato:** colunas esperadas pelo `feature_set` do
  `Model/model_config.yaml` alinhadas ao `model_metadata.json`.

**Implementação:** `check_data_drift` e `check_feature_schema` em
`scripts/mlops_monitoring.py`, acionados pela DAG `05_monitor_health` e por
`POST /monitoring/run`.

#### 3. Performance preditiva e impacto de negócio

Métricas de treino versionadas em `artifacts/model_metadata.json`:

- PR-AUC e F2-Score;
- recall / precisão da classe inadimplente;
- FN e FP na matriz de confusão;
- taxa de reprovação no `business_threshold` (0,08).

**Implementação atual:** `check_performance_baseline` confirma que a linha de
base está registrada e dentro de faixas sanáveis. A reavaliação periódica com
rótulo atrasado (concept drift / decay real) é evolução planejada via job
Airflow agendado.

Sem rótulo imediato, usar *proxies*:

- estabilidade do score médio e da taxa de aprovação por segmento (dashboard);
- concordância entre score e faixas de `EXT_SOURCE_*`;
- taxa de reanálise manual / override da mesa.

#### 4. Governança do corte operacional

- sensibilidade da taxa de FN/FP a pequenos deslocamentos do corte;
- divergência entre threshold no metadata e na API;
- concentração de aprovações em segmentos de alto risco.

**Implementação:** `check_threshold_coherence`.

### Gatilhos e respostas (runbook resumido)

| Sintoma | Hipótese | Resposta proposta |
|---|---|---|
| Health check ou artefato indisponível | Falha de infra / deploy | Rollback do serviço; não escorar |
| QA Silver/Gold falha na esteira | Quebra de contrato de dados | Corrigir origem; não publicar ABT |
| PSI alto em features-chave | Mudança de população / produto | Investigar; eventual retreino |
| Queda de PR-AUC / alta de FN vs. baseline | Modelo degradado | Congelar régua agressiva; retreino |
| Taxa de aprovação dispara sem mudança de política | Drift ou bug de feature | Auditoria de pipeline + amostra de casos |

### Encaixe na arquitetura atual

1. **Airflow** — DAG `05_monitor_health` (manual; evolução: schedule periódico).
2. **MinIO** — relatórios em `s3://artifacts/monitoring/`.
3. **Metadata do modelo** — linha de base oficial de métricas e threshold.
4. **Dashboard / API** — aba Monitoramento MLOps + endpoints `/monitoring/*`.

---

## iv) Ações automatizadas e agentes de IA a partir das previsões

### Objetivo

Conectar a saída do modelo (`probabilidade`, `decisão` no threshold,
contribuições locais de risco) a fluxos de negócio, reduzindo trabalho
manual repetitivo e acelerando a mesa de crédito — com humano no loop nas
decisões sensíveis.

### Implementado hoje (triagem sem LLM)

| Ação | Implementação |
|---|---|
| Classificação em faixas pós-`/score` | `scripts/credit_automation.py` |
| Filas auditáveis no MinIO | `s3://artifacts/automation/queues/{fila}/` |
| Webhook externo | `POST /webhooks/credit-decision` |
| Humano no loop | `human_in_the_loop: true` em todo evento |

Faixas (threshold `t` = 0,08):

- `proba < 0.4·t` → `autoaprovacao_candidata`
- `0.4·t ≤ proba < t` → `mesa_analise`
- `proba ≥ t` → `recusa_candidata`

### Evolução com agentes de IA (proposta)

1. **Agente de triagem** — resume fatores XAI e sugere faixa com justificativa auditável.
2. **Dossiê assistido** — parecer em linguagem de negócio para zona cinzenta (What-If).
3. **Alerta de carteira** — correlaciona drift com mudanças de campanha ou modelo.
4. **Comitê de promoção de modelo** — compara metadata antigo vs. novo antes do deploy.
5. **Conformidade sob demanda** — responde “por que recusado?” a partir do pacote XAI persistido.

### Princípios de desenho (para a banca)

1. **Humano no loop** nas decisões de crédito e na promoção de modelo.
2. **Mesma fonte de verdade** — API de score + `model_metadata.json` +
   threshold de `model_config.yaml`.
3. **Rastreabilidade** — toda ação automática cita run de DAG, versão do artefato
   e fatores usados.
4. **Assimetria de erro** — automações de aprovação mais conservadoras que
   encaminhamento para análise.

---

## Síntese

| Item do enunciado | Natureza nesta entrega | Conteúdo |
|---|---|---|
| iii Monitoramento | Implementação mínima + runbook | Saúde, artefatos, PSI/drift, schema, baseline de métricas |
| iv Automação e agentes | Triagem implementada + proposta LLM | Filas MinIO, webhook, humano no loop; agentes como evolução |

A infraestrutura materializa a esteira de dados, o modelo, o serviço de predição
e a interface da mesa. Os itens iii e iv fecham o ciclo MLOps com monitoramento
operacional e automação de triagem auditável, deixando agentes conversacionais
como evolução natural sobre os eventos já publicados no lake.
