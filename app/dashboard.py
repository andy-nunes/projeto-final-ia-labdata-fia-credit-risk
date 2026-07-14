"""
Dashboard Streamlit — Front-End para gerentes de crédito.
Atua como cliente da API FastAPI (/client e /score) com regras de compliance.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

# Reexports para testes e compatibilidade com `from app import dashboard`.
from app.ui.api import api_get_client, api_post_score, _parse_http_error
from app.ui.components import (
    _build_audit_message,
    _build_score_stat_cards,
    _probability_tone,
    _render_factor_row_html,
    _render_override_item_html,
    _render_stat_card_html,
    _risk_band_tone,
)
from app.ui.constants import (
    API_BASE_URL,
    CATEGORICAL_OPTIONS,
    COMPLIANCE_404_MSG,
    DURATION_FEATURES,
    EDUCATION_OPTIONS,
    FEATURE_TRANSLATIONS,
    ID_COLUMN,
    INCOME_OPTIONS,
    MONEY_FEATURE_BOUNDS,
    MONEY_READONLY_FEATURES,
    OCCUPATION_OPTIONS,
    ORGANIZATION_OPTIONS,
    PROFILE_RISK_ATTRIBUTES,
    READONLY_FEATURES_DISPLAY_ORDER,
    READONLY_FEATURES_HIDDEN,
    SCORE_FEATURES,
    TARGET_COLUMN,
    _CONFIG,
)
from app.ui.features import (
    _coerce_override_value,
    _index_of,
    _options_with_current,
    _parse_money_override,
    _render_custom_label,
    _render_editable_feature,
    _render_readonly_feature,
)
from app.ui.formatting import (
    _format_brl,
    _format_decimal_br,
    _format_delay_mean,
    _format_duration_from_days,
    _format_int_br,
    _format_pct_br,
    _format_readonly_value,
    _format_risk_pct,
    _get_label,
    _is_approved,
    _is_binary_flag_column,
    _is_count_like_column,
    _is_days_column,
    _is_missing_value,
    _parse_money_input,
    _safe_float,
    _safe_str,
)
from app.ui.mesa import (
    _load_client_dossier,
    _render_catalog_tab,
    _render_client_workspace,
    _render_mesa_tab,
    _render_score_result,
    _run_credit_score,
)
from app.ui.monitoring import _render_monitoring_tab
from app.ui.performance import (
    _aggregate_profile_risk,
    _build_segment_rankings_cache,
    _get_holdout_risk_scores,
    _get_model_test_performance,
    _load_holdout_risk_scores,
    _ranking_to_display,
    _render_confusion_matrix,
    _render_performance_tab,
    _render_segment_rankings_cache,
)
from app.ui.session import (
    _clear_client_view_flags,
    _clear_dashboard_state,
    _clear_edit_widget_keys,
    _collect_overrides_from_session,
    _ensure_edit_widget_seeds,
    _init_session_state,
    _seed_edit_widgets_from_features,
)
from app.ui.styles import _PAGE_STYLE, _configure_page

def main() -> None:
    """Ponto de entrada do dashboard Streamlit."""
    _configure_page()
    _init_session_state()

    st.title("Motor de Decisão de Crédito — Home Credit")
    st.caption(
        "Aplicação de apoio à decisão para concessão de crédito, com modelo "
        "LightGBM e arquitetura MLOps (Airflow + MinIO + FastAPI + Streamlit)."
    )
    st.caption(
        "Autoria: Anderson Nunes"
    )
    st.caption(
        "Navegue pelas abas para consultar clientes, simular cenários, avaliar "
        "performance/ROI e acompanhar o monitoramento operacional."
    )

    # Navegacao por abas da mesa de credito, catalogo, performance e MLOps.
    tab_mesa, tab_catalogo, tab_performance, tab_monitoring = st.tabs(
        [
            "Mesa de Crédito",
            "Dicionário de Variáveis",
            "Performance e ROI",
            "Monitoramento MLOps",
        ]
    )

    with tab_mesa:
        _render_mesa_tab()

    with tab_catalogo:
        _render_catalog_tab()

    with tab_performance:
        _render_performance_tab()

    with tab_monitoring:
        _render_monitoring_tab()


if __name__ == "__main__":
    main()
