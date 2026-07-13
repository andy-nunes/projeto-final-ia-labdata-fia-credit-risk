"""Widgets de features editáveis e somente leitura."""

from __future__ import annotations

import math
from html import escape
from typing import Any

import streamlit as st

from app.ui.constants import (
    CATEGORICAL_OPTIONS,
    MONEY_FEATURE_BOUNDS,
    _CONFIG,
)
from app.ui.formatting import (
    _format_readonly_value,
    _get_label,
    _safe_float,
    _safe_str,
)

def _render_custom_label(tech_name: str) -> None:
    """Renderiza apenas o nome comercial da feature (sem sigla técnica)."""
    label = _get_label(tech_name)
    st.markdown(
        f'<p class="feature-label">'
        f'<span class="feature-label-business">{escape(str(label))}</span>'
        f"</p>",
        unsafe_allow_html=True,
    )

def _render_readonly_feature(col_name: str, value: Any) -> None:
    """Exibe campo somente leitura sem widget state (evita conflito no rerun)."""
    _render_custom_label(col_name)
    formatted = _format_readonly_value(col_name, value)
    st.markdown(
        (
            '<div style="padding: 0.45rem 0.75rem; border: 1px solid #e2e8f0; '
            'border-radius: 0.5rem; background: #f8fafc; color: #334155; '
            'min-height: 2.4rem; display: flex; align-items: center;">'
            f"{escape(str(formatted))}"
            "</div>"
        ),
        unsafe_allow_html=True,
    )

def _render_editable_feature(features: dict[str, Any], feature_name: str, client_id: int) -> Any:
    """Renderiza campo editável do What-If (valores iniciais vêm do seed fora do form)."""
    _render_custom_label(feature_name)
    widget_key = f"edit_{client_id}_{feature_name}"

    if feature_name in MONEY_FEATURE_BOUNDS:
        min_value, max_value = MONEY_FEATURE_BOUNDS[feature_name]
        orig_value = _safe_float(features.get(feature_name), default=min_value)
        valor_formatado = (
            f"{orig_value:,.2f}"
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )
        entered = st.text_input(
            feature_name,
            help=(
                f"Informe um número entre {min_value:.2f} e {max_value:.2f}. "
                "Use ponto ou vírgula como separador decimal."
            ),
            label_visibility="collapsed",
            key=widget_key,
        )
        st.caption(f"Valor legível (dossiê): R$ {valor_formatado}")
        return entered

    if feature_name in CATEGORICAL_OPTIONS:
        options = _options_with_current(CATEGORICAL_OPTIONS[feature_name], features.get(feature_name))
        return st.selectbox(
            feature_name,
            options,
            label_visibility="collapsed",
            key=widget_key,
        )

    return st.text_input(
        feature_name,
        label_visibility="collapsed",
        key=widget_key,
    )

def _options_with_current(options: list[str], current: Any) -> list[str]:
    current_str = _safe_str(current).strip()
    if current_str == "Sem Info":
        return ["Sem Info", *list(options)]
    opts = list(options)
    if current_str and current_str not in opts:
        opts = [current_str] + opts
    if not opts:
        opts = [current_str or "N/A"]
    return opts

def _index_of(options: list[str], current: Any) -> int:
    current_str = _safe_str(current).strip()
    if current_str == "Sem Info":
        current_str = ""
    if current_str in options:
        return options.index(current_str)
    return 0

def _coerce_override_value(
    feature_name: str, widget_value: Any, original_features: dict[str, Any]
) -> Any:
    """Evita enviar placeholder de UI como override na API."""
    if isinstance(widget_value, str) and widget_value.strip() == "Sem Info":
        return original_features.get(feature_name)
    if feature_name in MONEY_FEATURE_BOUNDS:
        return _parse_money_override(feature_name, widget_value)
    return widget_value

def _parse_money_override(feature_name: str, value: Any) -> float:
    """Converte e valida campos monetarios editaveis dentro dos limites da ABT."""
    min_value, max_value = MONEY_FEATURE_BOUNDS[feature_name]
    if isinstance(value, str):
        normalized = value.strip().replace(",", ".")
        if not normalized:
            raise ValueError(
                f"{_get_label(feature_name)} deve ser um número entre "
                f"{min_value:.2f} e {max_value:.2f}."
            )
    else:
        normalized = value

    try:
        parsed = float(normalized)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{_get_label(feature_name)} deve ser um número entre "
            f"{min_value:.2f} e {max_value:.2f}."
        ) from exc

    if math.isnan(parsed) or parsed < min_value or parsed > max_value:
        raise ValueError(
            f"{_get_label(feature_name)} deve ser um número entre "
            f"{min_value:.2f} e {max_value:.2f}."
        )
    return parsed

