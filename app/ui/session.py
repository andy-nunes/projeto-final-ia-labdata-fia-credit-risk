"""Estado de sessão do dashboard Streamlit."""

from __future__ import annotations

from typing import Any

import streamlit as st

from app.ui.constants import CATEGORICAL_OPTIONS, MONEY_FEATURE_BOUNDS, _CONFIG
from app.ui.features import (
    _coerce_override_value,
    _index_of,
    _options_with_current,
)
from app.ui.formatting import _safe_float, _safe_str

def _init_session_state() -> None:
    """Inicializa chaves persistentes da mesa (só em execução Streamlit)."""
    if "client_features" not in st.session_state:
        st.session_state.client_features = None
    if "client_id" not in st.session_state:
        st.session_state.client_id = None
    if "score_result" not in st.session_state:
        st.session_state.score_result = None
    if "sk_id_input" not in st.session_state:
        st.session_state.sk_id_input = str(st.session_state.client_id or 139767)
    if "holdout_segment_risk_ready" not in st.session_state:
        st.session_state.holdout_segment_risk_ready = False
    if "catalog_ready" not in st.session_state:
        st.session_state.catalog_ready = False
    if "dossier_table_ready" not in st.session_state:
        st.session_state.dossier_table_ready = False
    if "score_json_ready" not in st.session_state:
        st.session_state.score_json_ready = False
    if "segment_rankings_cache" not in st.session_state:
        st.session_state.segment_rankings_cache = None

def _clear_edit_widget_keys(client_id: int | None = None) -> None:
    """Remove valores de widgets What-If para evitar reaproveitar estado antigo."""
    prefix = f"edit_{client_id}_" if client_id is not None else "edit_"
    for key in list(st.session_state.keys()):
        if str(key).startswith(prefix):
            del st.session_state[key]

def _clear_client_view_flags() -> None:
    """Reseta painéis pesados do dossiê/JSON ao trocar ou limpar cliente."""
    st.session_state.dossier_table_ready = False
    st.session_state.score_json_ready = False

def _clear_dashboard_state() -> None:
    """Limpa dossie, score e restaura o identificador padrao da tela."""
    _clear_edit_widget_keys(st.session_state.get("client_id"))
    st.session_state.client_features = None
    st.session_state.client_id = None
    st.session_state.score_result = None
    st.session_state.sk_id_input = "139767"
    _clear_client_view_flags()

def _seed_edit_widgets_from_features(features: dict[str, Any], client_id: int) -> None:
    """Inicializa chaves dos widgets What-If fora do form (obrigatório no Streamlit)."""
    for feature_name in _CONFIG.editable_features:
        widget_key = f"edit_{client_id}_{feature_name}"
        if feature_name in MONEY_FEATURE_BOUNDS:
            min_value, _ = MONEY_FEATURE_BOUNDS[feature_name]
            orig_value = _safe_float(features.get(feature_name), default=min_value)
            st.session_state[widget_key] = f"{orig_value:.2f}"
            continue

        if feature_name in CATEGORICAL_OPTIONS:
            options = _options_with_current(
                CATEGORICAL_OPTIONS[feature_name],
                features.get(feature_name),
            )
            st.session_state[widget_key] = options[
                _index_of(options, features.get(feature_name))
            ]
            continue

        st.session_state[widget_key] = _safe_str(features.get(feature_name))

def _ensure_edit_widget_seeds(features: dict[str, Any], client_id: int) -> None:
    """Garante seeds ausentes sem sobrescrever edições em andamento."""
    missing = any(
        f"edit_{client_id}_{feature_name}" not in st.session_state
        for feature_name in _CONFIG.editable_features
    )
    if missing:
        _seed_edit_widgets_from_features(features, client_id)

def _collect_overrides_from_session(
    client_id: int,
    features: dict[str, Any],
) -> dict[str, Any]:
    """Lê overrides dos widgets What-If via session_state após submit do form."""
    return {
        name: _coerce_override_value(
            name,
            st.session_state.get(f"edit_{client_id}_{name}"),
            features,
        )
        for name in _CONFIG.editable_features
    }

