# Handoff — próximo chat: performance e aparência do dashboard

Use este arquivo como contexto inicial no chat novo (`@docs/handoff-dashboard-performance.md`).

## Status Git (agora)

| Item | Valor |
|------|--------|
| Repo | `https://github.com/andy-nunes/projeto-final-ia-labdata-fia-credit-risk` |
| Branch atual | `docs/architecture-and-hmdr-cleanup` |
| Base | `main` (já contém a reorganização MLOps mergeada: `91222e4`) |
| Push desta branch | **Ainda não** — commits só locais |
| Working tree | Limpa (sem mudanças pendentes) |

### Commits nesta branch (ainda não no remoto)

1. `d8c0d9b` — Remove refs legadas `HMDR_*` nos docs  
2. `b5d9647` — Regenera PNG da arquitetura a partir do SVG (dag_ids `01`–`04`)  
3. `f300f2c` — Rótulos SVG/PNG: `data_sanitization.py` / `abt_transform.py`  
4. `bb5601b` — Split do dashboard em `app/ui/`  

## O que já foi feito (auditoria → polish)

### Concluído e na `main`

- Renomes: `data_sanitization`, `abt_transform`, `train`, `pipeline_orchestration`
- DAGs alinhadas a `01_bronze` … `04_model_train`
- `notebooks/`, `scripts/dev/`, docs por domínio
- Remote do colega (`mattnhb`) removido; só `origin` andy-nunes
- Feature `dashboard-catalog-tabs` mergeada e deletada
- Esteira Airflow + API + Streamlit validados pós-rebuild

### Concluído nesta branch (pendente push/PR)

- Docs sem `HMDR_*`
- Diagrama arquitetura atualizado (SVG + PNG)
- **Split do dashboard** (Fase 5):

```text
app/dashboard.py          (~141 linhas, entrypoint)
app/ui/
  styles.py, constants.py, formatting.py, components.py
  api.py, features.py, session.py, mesa.py, performance.py
```

### Validação recente do split

- Airflow: `80 passed`, 1 skipped  
- UI: `test_dashboard_layout` + `test_abt_catalog` → `29 passed`

## Assunto do próximo chat

**Performance e aparência do dashboard Streamlit.**

### Contexto de performance (já implementado antes)

Streamlit reexecuta as 3 abas a cada interação. Por isso há **lazy-load**:

| Bloco | Flag / botão | Efeito |
|-------|----------------|--------|
| Catálogo | `catalog_ready` / `btn_load_catalog` | Evita markdown gigante a cada rerun da mesa |
| Dossiê completo | `dossier_table_ready` | DataFrame ABT sob demanda |
| JSON do score | `score_json_ready` | JSON sob demanda |
| Mapeamento holdout | `holdout_segment_risk_ready` | Escora ~60k 1× + `@st.cache_data` |

**Trade-off conhecido:** depois de carregar tudo, catálogo/dataframes **voltam a ser remountados** em todo rerun (holdout ML fica em cache; render não). `Limpar` zera dossiê/JSON, mas **não** zera catálogo nem mapeamento.

### Plano antigo de referência

`~/.cursor/plans/dashboard_performance_review_ac1a09b9.plan.md` (lazy-load já marcado completed).

### Possíveis próximos passos (a decidir no chat novo)

1. Performance: carregar catálogo só na 1ª visita à aba / desmontar após uso / reduzir custo do HTML do catálogo  
2. Aparência: CSS, hierarquia visual, densidade da mesa, consistência das 3 abas  
3. Push/PR desta branch `docs/architecture-and-hmdr-cleanup` (docs + diagrama + split) antes ou junto com o polish de UI  

## Comandos úteis

```bash
cd /home/anderson/projeto-final-ia-labdata-fia-credit-risk
git checkout docs/architecture-and-hmdr-cleanup
git status -sb
git log --oneline main..HEAD

# Testes UI
docker compose run --rm --no-deps streamlit python -m pytest /app/tests/test_dashboard_layout.py -q

# Dashboard
# http://localhost:8501
```

## Prompt sugerido para o chat novo

> Continuar em `docs/architecture-and-hmdr-cleanup`. Ler `@docs/handoff-dashboard-performance.md`. Foco: performance e aparência do dashboard Streamlit (`app/dashboard.py` + `app/ui/`). Não reabrir a auditoria MLOps inteira. Propor melhorias concretas sem quebrar os asserts de `tests/test_dashboard_layout.py` (manter `st.tabs`, sem `st.fragment`/`st.radio` de navegação, um `@st.cache_data(show_spinner=False)`).
