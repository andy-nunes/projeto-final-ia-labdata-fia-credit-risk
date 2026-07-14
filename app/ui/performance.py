"""Aba Performance & ROI: métricas, matriz e segmentos."""

from __future__ import annotations

from html import escape
from typing import Any

import pandas as pd
import streamlit as st

from app.ui.components import _render_stat_card_html
from app.ui.constants import PROFILE_RISK_ATTRIBUTES, _CONFIG
from app.ui.formatting import (
    _format_brl,
    _format_decimal_br,
    _format_int_br,
    _format_pct_br,
    _format_risk_pct,
    _get_label,
)
from app.ui.session import _set_panel_flag
from scripts.model_config import (
    get_model_config,
    load_model_metadata,
    performance_from_metadata,
)

_SEGMENT_NUMERIC_ATTRIBUTES: dict[str, str] = {
    "AMT_CREDIT": "Valor solicitado",
    "AMT_ANNUITY": "Valor da parcela",
}

_SEGMENT_ATTRIBUTE_ORDER = [
    "NAME_INCOME_TYPE",
    "NAME_EDUCATION_TYPE",
    "AMT_CREDIT",
    "AMT_ANNUITY",
    "OCCUPATION_TYPE",
    "ORGANIZATION_TYPE",
]

def _get_model_test_performance(*, force: bool = False) -> dict[str, Any] | None:
    """Retorna métricas oficiais do metadata (memo só em sucesso)."""
    cached = st.session_state.get("model_test_performance")
    if cached is not None and not force:
        return cached
    if st.session_state.get("model_test_performance_error") and not force:
        return None
    try:
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

    profile_cols = [col for col in PROFILE_RISK_ATTRIBUTES if col in df_holdout.columns]
    amount_cols = [col for col in _SEGMENT_NUMERIC_ATTRIBUTES if col in df_holdout.columns]
    selected_cols = list(dict.fromkeys([*profile_cols, *amount_cols]))
    scored = df_holdout[selected_cols].copy()
    # Evita dtypes Arrow no fluxo de segmentação (podem quebrar atribuições/mutações).
    for col in selected_cols:
        if col in _SEGMENT_NUMERIC_ATTRIBUTES:
            scored[col] = pd.to_numeric(scored[col], errors="coerce")
        else:
            scored[col] = scored[col].astype("object")
    scored["prob_calote"] = prob_calote
    return scored

def _get_holdout_risk_scores() -> pd.DataFrame:
    """Resolve fingerprints de artefato e devolve o holdout escorado (cacheável)."""
    from scripts.predict import get_model_path

    config = get_model_config()
    demo_path = str(config.resolve_demo_holdout_path())
    # Fingerprint por URI: cache invalida quando o caminho oficial muda (retreino
    # no mesmo path exige restart do Streamlit ou versionamento futuro).
    demo_fingerprint = demo_path
    model_fingerprint = str(get_model_path())
    return _load_holdout_risk_scores(
        demo_path,
        demo_fingerprint,
        model_fingerprint,
    )

def _build_amount_band(value: Any) -> str:
    """Formata faixa monetária para exibição no ranking."""
    if not isinstance(value, pd.Interval):
        return str(value)
    left = max(float(value.left), 0.0)
    right = max(float(value.right), 0.0)
    return f"{_format_brl(left)} até {_format_brl(right)}"


def _with_numeric_bands(scored_df: pd.DataFrame, attribute: str) -> tuple[pd.DataFrame, str]:
    """Cria faixas para variáveis numéricas e devolve coluna de agrupamento."""
    if attribute not in _SEGMENT_NUMERIC_ATTRIBUTES:
        return scored_df, attribute

    working = scored_df.copy()
    numeric = pd.to_numeric(working[attribute], errors="coerce")
    valid = numeric.dropna()
    band_col = f"{attribute}__BAND"
    # Usa dtype object para evitar conflito com string[pyarrow] ao atribuir labels.
    band_labels = pd.Series("Não informado", index=working.index, dtype="object")
    if valid.empty:
        working[band_col] = band_labels
        return working, band_col

    bins = min(10, int(valid.nunique()))
    if bins < 2:
        band_labels.loc[valid.index] = f"{_format_brl(float(valid.iloc[0]))}"
        working[band_col] = band_labels
        return working, band_col

    bands = pd.qcut(valid, q=bins, duplicates="drop")
    band_labels.loc[valid.index] = bands.map(_build_amount_band).astype("object")
    working[band_col] = band_labels
    return working, band_col


def _aggregate_profile_risk(scored_df: pd.DataFrame, attribute: str) -> tuple[pd.DataFrame, str]:
    """Agrega risco médio por categoria/faixa do atributo selecionado."""
    working, group_col = _with_numeric_bands(scored_df, attribute)
    grouped = (
        working.groupby(group_col, dropna=False, observed=False)["prob_calote"]
        .agg(risco_medio="mean", volume="count")
        .reset_index()
    )
    grouped[group_col] = grouped[group_col].astype(str).replace({"nan": "Não informado"})
    return grouped.sort_values("risco_medio", ascending=False).reset_index(drop=True), group_col

def _ranking_to_display(
    frame: pd.DataFrame,
    *,
    attr_col: str,
    display_cols: dict[str, str],
) -> pd.DataFrame:
    """Formata ranking agregado para exibição na aba de performance."""
    out = frame[[attr_col, "risco_medio", "volume"]].copy()
    out["risco_medio"] = out["risco_medio"].map(_format_risk_pct)
    out["volume"] = out["volume"].map(_format_int_br)
    return out.rename(columns=display_cols)

def _build_segment_rankings_cache(scored_holdout: pd.DataFrame) -> list[dict[str, Any]]:
    """Pré-calcula tabelas de risco por segmento para reutilizar entre reruns."""
    cache: list[dict[str, Any]] = []
    # Defesa extra contra string[pyarrow] em runtime do Streamlit.
    scored_holdout = scored_holdout.copy()
    all_attrs: dict[str, str] = {
        **PROFILE_RISK_ATTRIBUTES,
        **_SEGMENT_NUMERIC_ATTRIBUTES,
    }
    for col in all_attrs:
        if col not in scored_holdout.columns:
            continue
        if col in _SEGMENT_NUMERIC_ATTRIBUTES:
            scored_holdout[col] = pd.to_numeric(scored_holdout[col], errors="coerce")
        else:
            scored_holdout[col] = scored_holdout[col].astype("object")
    available_cols = [col for col in all_attrs if col in scored_holdout.columns]
    sorted_cols = sorted(
        available_cols,
        key=lambda col: (
            _SEGMENT_ATTRIBUTE_ORDER.index(col)
            if col in _SEGMENT_ATTRIBUTE_ORDER
            else 999
        ),
    )
    for attr_col in sorted_cols:
        attr_label = all_attrs[attr_col]
        ranking, group_col = _aggregate_profile_risk(scored_holdout, attr_col)
        display_cols = {
            group_col: attr_label,
            "risco_medio": "Risco médio",
            "volume": "Clientes",
        }

        if ranking.empty:
            cache.append(
                {
                    "attr_label": attr_label,
                    "mode": "empty",
                }
            )
            continue

        cache.append(
            {
                "attr_label": attr_label,
                "mode": "single",
                "table": _ranking_to_display(
                    ranking,
                    attr_col=group_col,
                    display_cols=display_cols,
                ),
            }
        )
    return cache

def _render_segment_rankings_cache(cache: list[dict[str, Any]]) -> None:
    """Renderiza rankings memoizados sem reagregar o holdout."""
    if not cache:
        st.warning(
            "Nenhuma das variáveis de segmento do What-If está disponível "
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

def _render_performance_tab() -> None:
    st.markdown(
        """
        <div class="section-band">
            <div class="section-kicker">Diretoria de Risco</div>
            <div class="section-title">Performance do modelo e impacto na carteira</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.session_state.get("performance_metrics_ready"):
        unload_col, _ = st.columns([1, 3])
        with unload_col:
            if st.button(
                "Ocultar métricas oficiais",
                key="btn_unload_model_metrics",
                use_container_width=True,
            ):
                _set_panel_flag("performance_metrics_ready", False)

        perf = _get_model_test_performance()

        if perf is None and st.session_state.get("model_test_performance_error"):
            st.error(
                "Não foi possível carregar os indicadores oficiais do modelo "
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
                if perf is None and st.session_state.get(
                    "model_test_performance_error"
                ):
                    st.error(
                        "Não foi possível carregar os indicadores oficiais do modelo "
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
                "Visão executiva da qualidade do modelo no split de teste "
                f"({test_rows_label} propostas, threshold de {threshold_label}) e risco médio "
                "dos perfis editáveis no simulador What-If."
            )

            st.markdown("### KPIs executivos da carteira")
            kpi_cards = [
                _render_stat_card_html(
                    "Taxa de Calote Base",
                    base_rate_label,
                    note="Risco médio histórico sem apoio do modelo.",
                ),
                _render_stat_card_html(
                    "Taxa Pós-Modelo",
                    post_rate_label,
                    tone="success",
                    note=(
                        f"Risco observado entre os {approved_label} aprovados — "
                        f"queda de {reduction_label}."
                    ),
                ),
                _render_stat_card_html(
                    "Captura de inadimplência (Recall)",
                    recall_label,
                    tone="success",
                    note=(
                        f"{tp_label} de {defaults_label} inadimplentes barrados "
                        "antes da concessão de crédito."
                    ),
                ),
            ]
            st.markdown(
                f'<div class="stat-grid">{"".join(kpi_cards)}</div>',
                unsafe_allow_html=True,
            )

            st.markdown("### Qualidade estatística do modelo")
            disc_cards = [
                _render_stat_card_html(
                    "ROC-AUC",
                    roc_auc_label,
                    note="Capacidade geral de separação entre bons e maus pagadores.",
                ),
                _render_stat_card_html(
                    "PR-AUC",
                    pr_auc_label,
                    note="Métrica principal para classe de inadimplência.",
                ),
                _render_stat_card_html(
                    "Precision",
                    precision_label,
                    note="Entre os reprovados, quantos eram inadimplentes reais.",
                ),
                _render_stat_card_html(
                    "F2-Score",
                    f2_label,
                    note=f"β={f_beta:g} — prioriza captura de risco sobre seletividade.",
                ),
                _render_stat_card_html(
                    "Taxa de reprovação",
                    reprovacao_label,
                    note=f"Percentual reprovado com threshold de {threshold_label}.",
                ),
            ]
            st.markdown(
                f'<div class="stat-grid stat-grid-5">{"".join(disc_cards)}</div>',
                unsafe_allow_html=True,
            )

            _render_confusion_matrix(
                tn=int(perf["tn"]),
                fp=int(perf["fp"]),
                fn=int(perf["fn"]),
                tp=int(perf["tp"]),
                threshold_label=threshold_cm,
                recall_pct=recall_label,
            )
    else:
        if st.button(
            "Carregar indicadores oficiais",
            type="secondary",
            key="btn_load_model_metrics",
        ):
            _set_panel_flag("performance_metrics_ready", True)
        st.info(
            "Indicadores, qualidade estatística e matriz de confusão ficam sob demanda "
            "para manter a navegação da Mesa de Crédito leve."
        )

    # ------------------------------------------------------------------
    # Bloco 3 — Mapeamento de risco por segmento (todas as variáveis)
    # Carregamento sob demanda: evita escorar o holdout a cada rerun da mesa.
    # ------------------------------------------------------------------
    st.markdown("### Mapeamento de risco por segmento (variáveis editáveis)")
    st.caption(
        "Probabilidade média de inadimplência estimada na base Holdout, "
        "agregada por perfis cadastrais e por faixas de valor solicitado/parcela."
    )

    if st.session_state.get("holdout_segment_risk_ready"):
        unload_col, _ = st.columns([1, 3])
        with unload_col:
            if st.button(
                "Ocultar mapeamento",
                key="btn_unload_segment_risk",
                use_container_width=True,
            ):
                _set_panel_flag("holdout_segment_risk_ready", False)

        cached_rankings = st.session_state.get("segment_rankings_cache")
        if cached_rankings is not None:
            _render_segment_rankings_cache(cached_rankings)
            return

        try:
            scored_holdout = _get_holdout_risk_scores()
        except Exception as exc:
            st.error(
                "Não foi possível calcular o risco por segmento no Holdout. "
                f"Verifique modelo e base de demonstração. Detalhe: {exc}"
            )
            return

        rankings_cache = _build_segment_rankings_cache(scored_holdout)
        st.session_state.segment_rankings_cache = rankings_cache
        _render_segment_rankings_cache(rankings_cache)
        return

    if st.button(
        "Carregar análise por segmento",
        type="secondary",
        key="btn_load_segment_risk",
    ):
        _set_panel_flag("holdout_segment_risk_ready", True)
    st.info(
        "A análise por segmento escora o Holdout uma vez e reutiliza cache. "
        "Carregue quando quiser avaliar perfis específicos."
    )

