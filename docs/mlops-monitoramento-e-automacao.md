# Próximos Passos de Desenvolvimento: Monitoramento e Automação

Documento de proposta teórica para a etapa individual do Projeto Final
(Labdata FIA), itens **iii** e **iv** do enunciado. Descreve *como seria*
operado o monitoramento em produção e *quais ações automatizadas / agentes*
poderiam ser acionados a partir das previsões — **sem alterar o código atual**.

A arquitetura já implementada (Airflow, MinIO, LightGBM, FastAPI e Streamlit)
é o ponto de partida. Os itens abaixo são evolução planejada, não entregáveis
de software nesta versão.

---

## iii) Monitoramento de dados e do modelo em produção

### Objetivo

Garantir que a solução continue alinhada ao problema de negócio depois do
deploy: reduzir calotes aprovados (falsos negativos), preservar taxa de
aprovação sustentável e detectar degradação antes que a régua operacional
deixe de ser confiável.

### O que monitorar

#### 1. Saúde operacional do serviço

| Sinal | Fonte atual / candidata | Falha típica |
|---|---|---|
| Disponibilidade da API | `GET /` (health check) | Container fora, timeout, erro 5xx |
| Latência de `/score` e `/client/{id}` | Logs da API / proxy | Carga, leitura lenta no MinIO |
| Presença dos artefatos | `artifacts/lightgbm_hcdr.pkl`, `model_metadata.json` | Treino incompleto, path S3 inválido |
| Falha de DAG | UI/logs do Airflow | QA Silver/Gold, falta de CSV no `raw` |

Ação sugerida: alerta imediato à operação de dados/MLOps; bloquear novas
escoragens se o artefato ou o health check falharem.

#### 2. Qualidade e estabilidade dos dados

O pipeline já valida Silver e Gold antes de publicar. Em produção, o mesmo
espírito se estende ao *fluxo contínuo* de novas propostas:

- **Volume e completude:** queda abrupta de linhas na ABT ou aumento de nulos em
  features críticas (`EXT_SOURCE_*`, agregados de bureau/cartão).
- **Drift de entrada (data drift):** comparação da distribuição das features de
  escoragem recente com a distribuição do conjunto de treino registrado em
  `model_metadata.json` (ex.: PSI ou KS em variáveis contínuas; proporção por
  categoria em `NAME_INCOME_TYPE`, `OCCUPATION_TYPE`, etc.).
- **Schema / contrato:** colunas esperadas pelo `feature_set` do
  `config/model_config.yaml` ausentes ou com tipo incompatível.

Mudança de comportamento dos dados sem mudança do modelo é um dos cenários
mais comuns de perda silenciosa de performance.

#### 3. Performance preditiva e impacto de negócio

Enquanto houver rótulo (`TARGET`) com atraso temporal típico de crédito, a
avaliação offline pode ser repetida periodicamente sobre uma janela recente,
reutilizando as métricas já adotadas no projeto:

- PR-AUC e F2-Score (priorização de recall da classe inadimplente);
- recall / precisão da classe 1;
- contagem de FN e FP na matriz de confusão;
- taxa de reprovação no `business_threshold` (hoje `0.08`);
- taxa de inadimplência entre aprovados (proxy de risco residual da carteira).

Essas métricas já nascem no treino e ficam versionadas em
`artifacts/model_metadata.json`. O monitoramento consistiria em **comparar a
janela viva com a linha de base do metadata**, e não apenas olhar um número
isolado.

Sem rótulo imediato (cenário real de concessão), usar *proxies*:

- estabilidade do score médio e da taxa de aprovação por segmento
  (já explorável no dashboard por variáveis do What-If);
- concordância entre score e faixas de `EXT_SOURCE_*`;
- taxa de reanálise manual / override da mesa.

#### 4. Governança do corte operacional

O threshold é decisão de negócio, não hiperparâmetro “mágico”. Monitorar:

- sensibilidade da taxa de FN/FP a pequenos deslocamentos do corte;
- divergência entre o threshold documentado no metadata e o efetivamente
  usado pela API;
- concentração de aprovações em segmentos de alto risco aparente.

### Gatilhos e respostas (runbook resumido)

| Sintoma | Hipótese | Resposta proposta |
|---|---|---|
| Health check ou artefato indisponível | Falha de infra / deploy | Rollback do serviço; não escorar |
| QA Silver/Gold falha na esteira | Quebra de contrato de dados | Corrigir origem; não publicar ABT |
| PSI alto em features-chave | Mudança de população / produto | Investigar; eventual retreino |
| Queda de PR-AUC / alta de FN vs. baseline | Modelo degradado | Congelar régua agressiva; retreino |
| Taxa de aprovação dispara sem mudança de política | Drift ou bug de feature | Auditoria de pipeline + amostra de casos |

### Encaixe na arquitetura atual

Sem novos componentes obrigatórios nesta entrega, o desenho natural seria:

1. **Airflow** — jobs periódicos de checagem de artefatos, cálculo de drift e
   reavaliação offline (quando houver target).
2. **MinIO** — guardar relatórios de monitoramento ao lado de `artifacts/`.
3. **Metadata do modelo** — linha de base oficial de métricas e threshold.
4. **Dashboard / API** — superfície humana para inspecionar segmentos e
   saúde, complementando alertas automáticos.

O que já existe (validações de camada, metadata, holdout de demo, painel de
performance) reduz o custo de implantar esse monitoramento; falta, no plano,
a *rotina contínua* e os *alertas*.

---

## iv) Ações automatizadas e agentes de IA a partir das previsões

### Objetivo

Conectar a saída do modelo (`probabilidade`, `decisão` no threshold,
contribuições locais de risco) a fluxos de negócio, reduzindo trabalho
manual repetitivo e acelerando a mesa de crédito — com humano no loop nas
decisões sensíveis.

As ideias abaixo são **propostas de produto/processo**, alinhadas ao que o
motor já expõe via `/score` e ao dashboard What-If.

### 1. Triagem automática da fila de crédito

- **Ação:** classificar propostas em faixas (ex.: autoaprovação candidata,
  análise padrão, análise reforçada, recusa candidata) com base no score e no
  threshold vigente.
- **Automação:** publicar o resultado em fila (mensagem/evento) consumida pelo
  sistema de origem das propostas.
- **Agente (futuro):** um agente de triagem lê o dossiê retornado pela API,
  resume os fatores de risco (já disponíveis via contribuições locais /
  XAI) e sugere a faixa, sempre registrando a justificativa para auditoria.

### 2. Dossiê assistido para o analista

- **Ação:** quando o score ficar em zona cinzenta (próximo ao corte), abrir
  automaticamente um card na mesa com cliente, decisão sugerida, top fatores
  de risco/proteção e campos editáveis do What-If.
- **Automação:** webhook da API de score → ferramenta de workflow (ou inbox
  interna).
- **Agente (futuro):** redigir um parecer em linguagem de negócio (“renda
  incompatível com annuity”, “histórico de atraso em installments”) a partir
  das features e das contribuições, sem substituir a decisão humana.

### 3. Alerta de carteira e concentração de risco

- **Ação:** se a taxa de aprovação em um segmento (ocupação, tipo de
  contrato, organização) ultrapassar limite de política, notificar risco /
  crédito.
- **Automação:** job diário sobre escoragens do período (reusa a lógica de
  ranking por segmento já pensada no dashboard).
- **Agente (futuro):** correlacionar o alerta com mudanças recentes de
  distribuição de features e sugerir se o problema parece drift de dados,
  mudança de campanha comercial ou instabilidade do modelo.

### 4. Ciclo de retreino e governança

- **Ação:** diante de drift persistente ou piora de FN vs. baseline do
  metadata, disparar a esteira já existente
  (`pipeline_orchestration` / DAGs Bronze→Silver→Gold→Train), gerar novo
  artefato e metadata, e exigir aprovação humana antes de publicar em
  produção.
- **Automação:** trigger condicional no Airflow; versionamento no MinIO.
- **Agente (futuro):** comparar metadata antigo vs. novo (métricas, threshold,
  top features) e produzir um relatório de “pode promover?” para o comitê de
  modelo.

### 5. Conformidade e explicabilidade sob demanda

- **Ação:** para toda recusa (ou amostra de aprovações), persistir o pacote
  de explicação local usado hoje na escoragem.
- **Automação:** armazenamento imutável no lake (`artifacts` ou bucket de
  auditoria).
- **Agente (futuro):** atender solicitações internas do tipo “por que este
  cliente foi recusado?” consultando o pacote auditável e respondendo em
  linguagem controlada, sem inventar atributos fora do modelo.

### Princípios de desenho (para a banca)

1. **Humano no loop** nas decisões de crédito e na promoção de modelo.
2. **Mesma fonte de verdade** — API de score + `model_metadata.json` +
   threshold de `model_config.yaml`.
3. **Rastreabilidade** — toda ação automática deve citar run de DAG, versão
   do artefato e fatores usados.
4. **Assimetria de erro** — automações de aprovação devem ser mais
   conservadoras que automações de encaminhamento para análise, coerente com
   a priorização de falsos negativos do projeto.

---

## Síntese

| Item do enunciado | Natureza nesta entrega | Conteúdo |
|---|---|---|
| iii Monitoramento | Proposta / próximos passos | Saúde do serviço, drift de dados, métricas de negócio vs. metadata, runbook |
| iv Automação e agentes | Proposta / próximos passos | Triagem, dossiê assistido, alerta de carteira, retreino governado, explicabilidade |

A infraestrutura atual já materializa a esteira de dados, o modelo, o serviço
de predição e a interface da mesa. Os itens iii e iv fecham o ciclo MLOps ao
definir **como a solução seria sustentada e acionada no negócio** após o
deploy demonstrado nesta versão do repositório.
