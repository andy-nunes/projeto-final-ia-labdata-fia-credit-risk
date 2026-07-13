"""Aba Performance & ROI: métricas, matriz e segmentos."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from app.ui.components import _render_stat_card_html
from app.ui.constants import PROFILE_RISK_ATTRIBUTES, ROOT_DIR, _CONFIG
from app.ui.formatting import (
    _format_decimal_br,
    _format_int_br,
    _format_pct_br,
    _format_risk_pct,
    _get_label,
)
from scripts.model_config import (
    get_model_config,
    load_model_metadata,
    performance_from_metadata,
)

def _get_model_test_performance(*, force: bool = False) -> dict[str, Any] | None:
    """Retorna métricas oficiais do metadata (memo só em sucesso)."""
    cached = st.session_state.get("model_test_performance")
    if cached is not None and not force:
        return cached
    if st.session_state.get("model_test_performance_error") and not force:
        return None
    try:
        # Preferir arquivo local do container; evita fallback S3 no caminho da UI.
        perf = performance_from_metadata(load_model_metadata())
    except Exception as exc:  # noqa: BLE001 — UI mostra o erro
        st.session_state.pop("model_test_performance", None)
        st.session_state.model_test_performance_error = str(exc)
        return None
    st.session_state.model_test_performance = perf
    st.session_state.model_test_performance_error = None
    return perf

def _render_confusion_matrix(
    *,
    tn: int,
    fp: int,
    fn: int,
    tp: int,
    threshold_label: str,
    recall_pct: str,
) -> None:
    """Matriz de confusão em cards (Streamlit nativo — evita quebra do HTML no markdown)."""

    def _cell(kind: str, value: int, label: str) -> str:
        return (
            f'<div class="cm-cell cm-cell-{kind}">'
            f'<div class="cm-value">{_format_int_br(value)}</div>'
            f'<div class="cm-label">{escape(label)}</div>'
            f"</div>"
        )

    st.markdown(
        f'<div class="cm-title">Matriz de Confusão: LightGBM '
        f"(t={escape(threshold_label)})</div>",
        unsafe_allow_html=True,
    )

    header_spacer, header_paid, header_default = st.columns([1.15, 1, 1])
    with header_spacer:
        st.write("")
    with header_paid:
        st.markdown(
            '<div class="cm-col-header">PREVISTO: <span class="ok">PAGOU</span></div>',
            unsafe_allow_html=True,
        )
    with header_default:
        st.markdown(
            '<div class="cm-col-header">PREVISTO: '
            '<span class="bad">INADIMPLENTE</span></div>',
            unsafe_allow_html=True,
        )

    row1_label, row1_tn, row1_fp = st.columns([1.15, 1, 1])
    with row1_label:
        st.markdown(
            '<div class="cm-row-label">Real: Pagou</div>',
            unsafe_allow_html=True,
        )
    with row1_tn:
        st.markdown(_cell("ok", tn, "Verdadeiros Negativos"), unsafe_allow_html=True)
    with row1_fp:
        st.markdown(_cell("bad", fp, "Falsos Positivos"), unsafe_allow_html=True)

    row2_label, row2_fn, row2_tp = st.columns([1.15, 1, 1])
    with row2_label:
        st.markdown(
            '<div class="cm-row-label">Real: Inadimplente</div>',
            unsafe_allow_html=True,
        )
    with row2_fn:
        st.markdown(_cell("bad", fn, "Falsos Negativos"), unsafe_allow_html=True)
    with row2_tp:
        st.markdown(_cell("ok", tp, "Verdadeiros Positivos"), unsafe_allow_html=True)

    st.markdown(
        '<div class="cm-footer"><span aria-hidden="true">🛡️</span>'
        f"<span><strong>RECALL DE {escape(recall_pct)}:</strong> "
        "O motor prioriza barrar o prejuízo (FN) sacrificando volume (FP)."
        "</span></div>",
        unsafe_allow_html=True,
    )

def _local_file_fingerprint(path: Path | str | None) -> str:
    """Fingerprint local para invalidar cache quando o artefato muda."""
    if path is None:
        return "missing"
    candidate = Path(path)
    if not candidate.exists() or not candidate.is_file():
        return str(path)
    stat = candidate.stat()
    return f"{candidate}:{stat.st_mtime_ns}:{stat.st_size}"

@st.cache_data(show_spinner=False)
def _load_holdout_risk_scores(
    demo_path: str,
    demo_fingerprint: str,
    model_fingerprint: str,
) -> pd.DataFrame:
    """Lê o holdout, escora a carteira e devolve categorias + prob. de calote."""
    # Lazy-import: a mesa só fala com a API; predict/S3 entram só no mapeamento.
    from scripts.predict import (
        build_prediction_matrix,
        get_s3_filesystem,
        is_s3_path,
        load_model,
        normalize_prediction_input,
    )

    _ = demo_fingerprint, model_fingerprint  # entram no hash do cache_data
    config = get_model_config()

    if is_s3_path(demo_path):
        fs = get_s3_filesystem()
        with fs.open(demo_path, "rb") as handle:
            df_holdout = pd.read_parquet(handle, engine="pyarrow")
    else:
        df_holdout = pd.read_parquet(demo_path)

    model = load_model()
    X_pred = build_prediction_matrix(df_holdout, config)
    X_pred_norm = normalize_prediction_input(model, X_pred)
    prob_calote = model.predict_proba(X_pred_norm)[:, 1]

    profile_cols = [
        col for col in PROFILE_RISK_ATTRIBUTES if col in df_holdout.columns
    ]
    scored = df_holdout[profile_cols].copy()
    scored["prob_calote"] = prob_calote
    return scored

def _get_holdout_risk_scores() -> pd.DataFrame:
    """Resolve fingerprints de artefato e devolve o holdout escorado (cacheável)."""
    from scripts.predict import get_model_path, resolve_local_model_path

    config = get_model_config()
    demo_path = config.resolve_demo_holdout_path()
    demo_path_str = str(demo_path)
    demo_fingerprint = _local_file_fingerprint(demo_path)

    local_model = resolve_local_model_path(config)
    model_fingerprint = (
        _local_file_fingerprint(local_model)
        if local_model is not None
        else str(get_model_path())
    )
    return _load_holdout_risk_scores(
        demo_path_str,
        demo_fingerprint,
        model_fingerprint,
    )

def _aggregate_profile_risk(scored_df: pd.DataFrame, attribute: str) -> pd.DataFrame:
    """Agrega risco médio por categoria do atributo cadastral selecionado."""
    grouped = (
        scored_df.groupby(attribute, dropna=False, observed=False)["prob_calote"]
        .agg(risco_medio="mean", volume="count")
        .reset_index()
    )
    grouped[attribute] = grouped[attribute].astype(str).replace({"nan": "Não informado"})
    return grouped.sort_values("risco_medio", ascending=False).reset_index(drop=True)

def _ranking_to_display(
    frame: pd.DataFrame,
    *,
    attr_col: str,
    display_cols: dict[str, str],
) -> pd.DataFrame:
    """Formata ranking agregado para exibição na aba de performance."""
    out = frame[[attr_col, "risco_medio"]].copy()
    out["risco_medio"] = out["risco_medio"].map(_format_risk_pct)
    return out.rename(columns=display_cols)

def _build_segment_rankings_cache(scored_holdout: pd.DataFrame) -> list[dict[str, Any]]:
    """Pré-calcula tabelas de risco por segmento para reutilizar entre reruns."""
    cache: list[dict[str, Any]] = []
    available_attrs = [
        (label, col)
        for col, label in PROFILE_RISK_ATTRIBUTES.items()
        if col in scored_holdout.columns
    ]
    for attr_label, attr_col in available_attrs:
        ranking = _aggregate_profile_risk(scored_holdout, attr_col)
        display_cols = {
            attr_col: attr_label,
            "risco_medio": "Risco médio",
        }

        if ranking.empty:
            cache.append(
                {
                    "attr_label": attr_label,
                    "mode": "empty",
                }
            )
            continue

        if len(ranking) <= 5:
            cache.append(
                {
                    "attr_label": attr_label,
                    "mode": "single",
                    "table": _ranking_to_display(
                        ranking,
                        attr_col=attr_col,
                        display_cols=display_cols,
                    ),
                }
            )
        else:
            top_risky = ranking.head(5)
            bottom_safe = ranking.sort_values(
                "risco_medio", ascending=True
            ).head(5)
            cache.append(
                {
                    "attr_label": attr_label,
                    "mode": "split",
                    "safe_table": _ranking_to_display(
                        bottom_safe,
                        attr_col=attr_col,
                        display_cols=display_cols,
                    ),
                    "risky_table": _ranking_to_display(
                        top_risky,
                        attr_col=attr_col,
                        display_cols=display_cols,
                    ),
                }
            )
    return cache

def _render_segment_rankings_cache(cache: list[dict[str, Any]]) -> None:
    """Renderiza rankings memoizados sem reagregar o holdout."""
    if not cache:
        st.warning(
            "Nenhuma das variáveis categóricas do What-If está disponível "
            "na base Holdout carregada."
        )
        return

    for item in cache:
        st.markdown(f"#### {item['attr_label']}")
        mode = item["mode"]
        if mode == "empty":
            st.info("Sem categorias suficientes para ranquear.")
            continue
        if mode == "single":
            st.dataframe(
                item["table"],
                hide_index=True,
                width="stretch",
            )
            continue

        table_col1, table_col2 = st.columns(2)
        with table_col1:
            st.markdown("**Mais seguras**")
            st.dataframe(
                item["safe_table"],
                hide_index=True,
                width="stretch",
            )
        with table_col2:
            st.markdown("**Mais arriscadas**")
            st.dataframe(
                item["risky_table"],
                hide_index=True,
                width="stretch",
            )

def _render_performance_tab() -> None:
    st.markdown(
        """
        <div class="section-band">
            <div class="section-kicker">Diretoria de Risco</div>
            <div class="section-title">Confiabilidade do LightGBM e impacto na carteira</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    perf = _get_model_test_performance()

    if perf is None and st.session_state.get("model_test_performance_error"):
        st.error(
            "Não foi possível carregar as métricas oficiais do modelo "
            f"(`artifacts/model_metadata.json`): "
            f"{st.session_state.model_test_performance_error}"
        )
        if st.button(
            "Tentar novamente",
            key="btn_retry_model_metrics",
            type="secondary",
        ):
            st.session_state.pop("model_test_performance", None)
            st.session_state.pop("model_test_performance_error", None)
            perf = _get_model_test_performance(force=True)
            if perf is None and st.session_state.get("model_test_performance_error"):
                st.error(
                    "Não foi possível carregar as métricas oficiais do modelo "
                    f"(`artifacts/model_metadata.json`): "
                    f"{st.session_state.model_test_performance_error}"
                )

    if perf is not None:
        test_rows_label = _format_int_br(perf["test_rows"])
        threshold_label = _format_pct_br(perf["threshold"], digits=0)
        threshold_cm = f"{perf['threshold']:.2f}".replace(".", ",")
        recall_label = _format_pct_br(perf["recall"])
        precision_label = _format_pct_br(perf["precision"])
        roc_auc_label = _format_decimal_br(perf["roc_auc"])
        pr_auc_label = _format_decimal_br(perf["pr_auc"])
        f2_label = _format_decimal_br(perf["f2"])
        reprovacao_label = _format_pct_br(perf["taxa_reprovacao"])
        f_beta = perf.get("f_beta", 2.0)
        base_rate_label = _format_pct_br(perf["base_default_rate"])
        post_rate_label = _format_pct_br(perf["post_model_default_rate"])
        reduction_label = _format_pct_br(perf["default_reduction"], digits=0)
        approved_label = _format_int_br(perf["approved"])
        tp_label = _format_int_br(perf["tp"])
        defaults_label = _format_int_br(perf["defaults_total"])

        st.caption(
            "Apresentação executiva com a matriz de confusão oficial no split de teste "
            f"({test_rows_label} propostas, threshold de {threshold_label}) e risco médio "
            "dos perfis cadastrais editáveis no What-If."
        )

        # ------------------------------------------------------------------
        # Bloco 1 — KPIs executivos de saneamento da carteira
        # ------------------------------------------------------------------
        st.markdown("### KPIs Executivos de Saneamento da Carteira")
        kpi_col1, kpi_col2, kpi_col3 = st.columns(3)
        with kpi_col1:
            st.markdown(
                f"""
                **Taxa de Calote Base: {base_rate_label}**

                Média natural da carteira sem modelo.
                """
            )
        with kpi_col2:
            st.markdown(
                f"""
                **Taxa Pós-Modelo: {post_rate_label}**

                Risco real entre os {approved_label} clientes aprovados — queda de
                {reduction_label} na inadimplência.
                """
            )
        with kpi_col3:
            st.markdown(
                f"""
                **Captura de Calotes (Recall): {recall_label}**

                {tp_label} de {defaults_label} inadimplentes barrados antes da concessão.
                """
            )

        # ------------------------------------------------------------------
        # Bloco 1b — Discriminação e área sob as curvas
        # ------------------------------------------------------------------
        st.markdown("### Métricas de Discriminação e Captura")
        disc_col1, disc_col2, disc_col3, disc_col4, disc_col5 = st.columns(5)
        with disc_col1:
            st.markdown(
                f"""
                **ROC-AUC: {roc_auc_label}**

                Área sob a curva ROC — separação geral do modelo.
                """
            )
        with disc_col2:
            st.markdown(
                f"""
                **PR-AUC: {pr_auc_label}**

                Área sob Precision-Recall — métrica primária do treino.
                """
            )
        with disc_col3:
            st.markdown(
                f"""
                **Precision: {precision_label}**

                Dos reprovados, quantos eram calotes reais.
                """
            )
        with disc_col4:
            st.markdown(
                f"""
                **F2-Score: {f2_label}**

                β={f_beta:g} — prioriza recall sobre precision.
                """
            )
        with disc_col5:
            st.markdown(
                f"""
                **Reprovação: {reprovacao_label}**

                Taxa de reprovação no threshold de {threshold_label}.
                """
            )

        # ------------------------------------------------------------------
        # Bloco 2 — Matriz de confusão visual (estilo executivo)
        # ------------------------------------------------------------------
        _render_confusion_matrix(
            tn=int(perf["tn"]),
            fp=int(perf["fp"]),
            fn=int(perf["fn"]),
            tp=int(perf["tp"]),
            threshold_label=threshold_cm,
            recall_pct=recall_label,
        )

    # ------------------------------------------------------------------
    # Bloco 3 — Mapeamento de risco por segmento (todas as variáveis)
    # Carregamento sob demanda: evita escorar o holdout a cada rerun da mesa.
    # ------------------------------------------------------------------
    st.markdown("### Mapeamento de Risco por Segmento (Variáveis Editáveis)")
    st.caption(
        "Probabilidade média de calote estimada pelo LightGBM na base Holdout, "
        "agregada pelas variáveis categóricas do simulador What-If."
    )

    if not st.session_state.get("holdout_segment_risk_ready"):
        if st.button(
            "Carregar mapeamento de risco",
            type="secondary",
            key="btn_load_segment_risk",
        ):
            st.session_state.holdout_segment_risk_ready = True
            st.session_state.segment_rankings_cache = None
        else:
            st.info(
                "O mapeamento escora a carteira Holdout uma vez e fica em cache. "
                "Carregue quando for analisar os segmentos."
            )
            return

    cached_rankings = st.session_state.get("segment_rankings_cache")
    if cached_rankings is not None:
        _render_segment_rankings_cache(cached_rankings)
        return

    try:
        scored_holdout = _get_holdout_risk_scores()
    except Exception as exc:
        st.error(
            "Não foi possível calcular o risco da carteira Holdout. "
            f"Verifique o artefato do modelo e o parquet de demonstração. Detalhe: {exc}"
        )
        return

    rankings_cache = _build_segment_rankings_cache(scored_holdout)
    st.session_state.segment_rankings_cache = rankings_cache
    _render_segment_rankings_cache(rankings_cache)

