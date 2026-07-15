# Handoff — Dashboard (performance + aparência)

Use este arquivo como contexto inicial em um chat novo (`@docs/handoff-dashboard-performance.md`).

## Objetivo

Evoluir **performance e aparência** do dashboard Streamlit sem reabrir escopo de arquitetura/pipeline.

## Estado técnico de referência (perene)

- Entry point: `app/dashboard.py`
- Módulos de UI: `app/ui/`
  - `styles.py`, `constants.py`, `formatting.py`, `components.py`
  - `api.py`, `features.py`, `session.py`, `mesa.py`, `performance.py`, `monitoring.py`
- Catálogo: `app/abt_catalog.py`

## Contratos que não devem quebrar

- Navegação por abas com `st.tabs` (sem multipage legado).
- Sem `st.fragment` para navegação.
- Sem `st.radio` de navegação global.
- Regras de lazy-load e flags de sessão mantidas.
- Compatibilidade com `tests/test_dashboard_layout.py`.

## Contexto de performance atual

O dashboard usa carregamento sob demanda para reduzir custo de rerun:

| Bloco | Flag / botão | Efeito |
|---|---|---|
| Catálogo | `catalog_ready` / `btn_load_catalog` | Evita markdown pesado em reruns da mesa |
| Dossiê completo | `dossier_table_ready` | Monta dataframe ABT sob demanda |
| JSON da escoragem | `score_json_ready` | Exibe payload técnico sob demanda |
| Segmentação Holdout | `holdout_segment_risk_ready` | Cálculo e cache sob demanda |
| Métricas oficiais | `performance_metrics_ready` | Carrega metadata/model KPIs sob demanda |

## Próximos passos sugeridos

1. **Performance**
   - reduzir recomputação e remount de blocos pesados;
   - revisar pontos de cache no catálogo/performance.
2. **Aparência**
   - ajustar hierarquia visual, densidade e consistência de copy entre abas.
3. **Confiabilidade**
   - manter asserts de UI sincronizados com copy/estrutura real.

## Comandos úteis

```bash
cd /home/anderson/projeto-final-ia-labdata-fia-credit-risk
git status -sb
git log --oneline --decorate -n 20

# UI (Streamlit-marked)
docker compose exec -T dev python -m pytest tests -m streamlit -q

# Core integrações/CredIA
docker compose exec -T api python -m pytest /app/tests/test_integrations_config.py /app/tests/test_ai_commentary.py -q

# Airflow
docker compose exec -T airflow python -m pytest /opt/airflow/tests -q
```

## Segurança operacional

- Não incluir tokens/chaves em commits ou snippets.
- Evitar compartilhar saída bruta de `docker compose config` quando houver segredos resolvidos.
- Preferir redaction em logs/prints de ambiente.
