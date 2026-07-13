"""
Dashboard Streamlit — Front-End para gerentes de crédito.
Atua como cliente da API FastAPI (/client e /score) com regras de compliance.
"""

from __future__ import annotations

import json
import math
import sys
from html import escape
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from app.abt_catalog import COLUMN_BUSINESS_NAMES, render_catalog
from scripts.model_config import (
    get_model_config,
    load_model_metadata,
    test_performance_from_metadata,
)

_CONFIG = get_model_config()
API_BASE_URL = _CONFIG.api_base_url
ID_COLUMN = _CONFIG.id_column
TARGET_COLUMN = _CONFIG.target_column

# ---------------------------------------------------------------------------
# Configuração da página
# ---------------------------------------------------------------------------
_PAGE_STYLE = """
    <style>
    .stApp {
        background-color: #f8fafc;
        color: #0f172a;
    }
    [data-testid="stHeader"] {
        background-color: rgba(248, 250, 252, 0.92);
    }
    .block-container {
        padding-top: 2.2rem;
        padding-bottom: 2.8rem;
        max-width: 1280px;
    }
    h1 {
        letter-spacing: 0;
        margin-bottom: 0.15rem;
        color: #0f172a;
    }
    h2, h3, h4, h5 {
        letter-spacing: 0;
        color: #0f172a;
    }
    div[data-testid="stVerticalBlock"] > div:has(.section-band) {
        margin-top: 0.6rem;
    }
    .section-band {
        border-top: 1px solid #e2e8f0;
        padding-top: 1.15rem;
        margin-top: 1.15rem;
    }
    .section-kicker {
        color: #64748b;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin: 0 0 0.25rem 0;
    }
    .section-title {
        color: #0f172a;
        font-size: 1.08rem;
        font-weight: 700;
        line-height: 1.25;
        margin: 0 0 0.8rem 0;
    }
    div[data-testid="stTextInput"] label,
    div[data-testid="stNumberInput"] label,
    div[data-testid="stSelectbox"] label {
        color: #334155;
        font-weight: 600;
        line-height: 1.25;
    }
    div[data-testid="stTextInput"] input,
    div[data-testid="stNumberInput"] input,
    div[data-baseweb="select"] > div {
        border-radius: 8px;
        border-color: #cbd5e1;
        min-height: 2.75rem;
        background-color: #ffffff;
    }
    div[data-testid="stButton"] button {
        border-radius: 8px !important;
        min-height: 2.75rem;
        font-weight: 700 !important;
    }
    .score-btn button {
        background: #2563eb !important;
        color: white !important;
        border: 1px solid #2563eb !important;
        font-weight: 600 !important;
    }
    .score-action {
        margin-top: 1rem;
    }
    .approved-box {
        background: rgba(22, 163, 74, 0.08);
        border: 1px solid #86efac;
        border-radius: 8px;
        padding: 1rem 1.15rem;
        margin: 0.35rem 0 1rem 0;
    }
    .rejected-box {
        background: rgba(220, 38, 38, 0.08);
        border: 1px solid #fca5a5;
        border-radius: 8px;
        padding: 1rem 1.15rem;
        margin: 0.35rem 0 1rem 0;
    }
    .approved-box h3,
    .rejected-box h3 {
        font-size: 1.08rem;
        line-height: 1.25;
        margin: 0;
    }
    .approved-box h3 { color: #15803d; }
    .rejected-box h3 { color: #b91c1c; }
    .feature-label {
        margin: 0 0 0.28rem 0;
        min-height: 2.35rem;
        line-height: 1.25;
    }
    .feature-label-business {
        color: #0f172a;
        font-size: 0.92rem;
        font-weight: 650;
    }
    .feature-label-tech {
        display: none;
    }
    .stat-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.75rem;
        margin: 0.3rem 0 0.55rem 0;
    }
    .stat-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        min-height: 5.7rem;
        padding: 0.78rem 0.9rem;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        gap: 0.45rem;
    }
    .stat-card-success {
        border-left: 4px solid #22c55e;
    }
    .stat-card-danger {
        border-left: 4px solid #ef4444;
    }
    .stat-card-warning {
        border-left: 4px solid #eab308;
    }
    .stat-card-neutral {
        border-left: 4px solid #94a3b8;
    }
    .stat-card-label {
        color: #64748b;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        line-height: 1.2;
        text-transform: uppercase;
    }
    .stat-card-value {
        color: #0f172a;
        font-size: 1.16rem;
        font-weight: 750;
        line-height: 1.25;
        white-space: normal;
        overflow-wrap: anywhere;
    }
    .stat-card-note {
        color: #64748b;
        font-size: 0.78rem;
        line-height: 1.25;
    }
    .factor-list {
        display: grid;
        gap: 0.55rem;
        margin-top: 0.55rem;
    }
    .factor-row {
        display: grid;
        grid-template-columns: minmax(0, 1fr) 5.5rem minmax(8rem, 28%);
        align-items: center;
        gap: 0.75rem;
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 0.72rem 0.85rem;
    }
    .factor-label {
        min-width: 0;
        line-height: 1.25;
    }
    .factor-label-business {
        color: #0f172a;
        font-size: 0.92rem;
        font-weight: 650;
    }
    .factor-label-tech {
        display: none;
    }
    .factor-value {
        color: #0f172a;
        font-size: 0.92rem;
        font-weight: 750;
        text-align: right;
        white-space: nowrap;
    }
    .factor-track {
        height: 0.5rem;
        overflow: hidden;
        border-radius: 999px;
        background: #e2e8f0;
    }
    .factor-fill {
        height: 100%;
        border-radius: 999px;
        background: #2563eb;
    }
    .factor-row-success .factor-fill {
        background: #22c55e;
    }
    .factor-row-danger .factor-fill {
        background: #ef4444;
    }
    .override-list {
        display: grid;
        gap: 0.6rem;
    }
    .override-item {
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 0.72rem 0.85rem;
        background: #ffffff;
    }
    .override-title {
        color: #0f172a;
        font-weight: 700;
        margin-bottom: 0.35rem;
    }
    .override-values {
        color: #475569;
        font-size: 0.9rem;
        line-height: 1.45;
    }
    @media (max-width: 760px) {
        .stat-grid {
            grid-template-columns: 1fr;
        }
        .factor-row {
            grid-template-columns: 1fr;
            gap: 0.45rem;
        }
        .factor-value {
            text-align: left;
        }
    }
    .cm-wrap {
        margin: 0.75rem 0 1.1rem 0;
    }
    .cm-title {
        display: flex;
        align-items: center;
        gap: 0.65rem;
        color: #0f766e;
        font-size: 1.05rem;
        font-weight: 700;
        margin: 0 0 0.9rem 0;
    }
    .cm-title::before {
        content: "";
        display: inline-block;
        width: 5px;
        height: 1.35rem;
        border-radius: 3px;
        background: #0f766e;
        flex-shrink: 0;
    }
    .cm-grid {
        display: grid;
        grid-template-columns: 8.5rem 1fr 1fr;
        grid-template-rows: auto 1fr 1fr;
        gap: 0.65rem;
        align-items: stretch;
    }
    .cm-corner { min-height: 1px; }
    .cm-col-header {
        background: #1e293b;
        color: #f8fafc;
        border-radius: 10px;
        padding: 0.65rem 0.75rem;
        text-align: center;
        font-size: 0.82rem;
        font-weight: 650;
        letter-spacing: 0.02em;
    }
    .cm-col-header .ok { color: #4ade80; font-weight: 800; }
    .cm-col-header .bad { color: #f87171; font-weight: 800; }
    .cm-row-label {
        display: flex;
        align-items: center;
        justify-content: flex-end;
        padding-right: 0.35rem;
        color: #334155;
        font-size: 0.88rem;
        font-weight: 650;
        text-align: right;
    }
    .cm-cell {
        border-radius: 12px;
        min-height: 7.2rem;
        padding: 1rem 0.85rem;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 0.35rem;
        text-align: center;
    }
    .cm-cell-ok {
        background: #ecfdf5;
        border: 1.5px solid #86efac;
    }
    .cm-cell-bad {
        background: #fef2f2;
        border: 1.5px solid #fca5a5;
    }
    .cm-value {
        font-size: 1.85rem;
        font-weight: 800;
        line-height: 1.1;
    }
    .cm-cell-ok .cm-value { color: #0f766e; }
    .cm-cell-bad .cm-value { color: #b91c1c; }
    .cm-label {
        font-size: 0.9rem;
        font-weight: 650;
    }
    .cm-cell-ok .cm-label { color: #15803d; }
    .cm-cell-bad .cm-label { color: #dc2626; }
    .cm-footer {
        margin-top: 0.75rem;
        background: #ecfdf5;
        border: 1px solid #bbf7d0;
        border-radius: 12px;
        padding: 0.85rem 1rem;
        color: #14532d;
        font-size: 0.92rem;
        line-height: 1.35;
        display: flex;
        align-items: center;
        gap: 0.55rem;
    }
    .cm-footer strong { color: #15803d; }
    @media (max-width: 900px) {
        .cm-grid {
            grid-template-columns: 1fr 1fr;
            grid-template-rows: auto auto auto auto;
        }
        .cm-corner { display: none; }
        .cm-row-label {
            grid-column: 1 / -1;
            justify-content: flex-start;
            text-align: left;
            padding: 0.2rem 0 0 0;
        }
    }
    </style>
    """


def _configure_page() -> None:
    """Define título, layout e CSS do app (apenas quando o script é executado)."""
    st.set_page_config(
        page_title="Credit Risk Desk | Home Credit",
        page_icon="🏦",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.markdown(_PAGE_STYLE, unsafe_allow_html=True)


COMPLIANCE_404_MSG = (
    "Cliente não localizado na base do Bureau. Por questões de ética, compliance "
    "e prevenção a fraudes, não é permitido o preenchimento manual do dossiê de "
    "crédito para clientes sem rastro de dados."
)

FEATURE_TRANSLATIONS = {
    **COLUMN_BUSINESS_NAMES,
    "DAYS_BIRTH": "Idade",
    "FLAG_EMPLOYED": "Está Empregado?",
    "EXT_SOURCE_1": "Score Serasa",
    "EXT_SOURCE_2": "Score Boa Vista",
    "EXT_SOURCE_3": "Score SPC Brasil",
    "EXT_SOURCE_MEAN": "Média dos Scores Externos",
    "BUREAU_AMT_DEBT_SUM": "Dívida Total em Outros Bancos",
    "DAYS_ID_PUBLISH": "Tempo desde Emissão do RG",
    "DAYS_EMPLOYED": "Tempo de Emprego",
    "BUREAU_DAYS_CREDIT_MIN": "Tempo desde o 1º Crédito",
    "PREV_DAYS_DECISION_MIN": "Tempo desde a Última Proposta",
    "INST_DIAS_ATRASO_MEAN": "Média de Dias em Atraso",
}

READONLY_FEATURES_HIDDEN = frozenset(
    {
        "EXT_SOURCE_CNT",
        "DAYS_EMPLOYED_YEARS",
        "INST_AMT_PAYMENT_SUM",
    }
)

# Ordem comercial fixa do grid 3x4 (proximidade de contexto).
READONLY_FEATURES_DISPLAY_ORDER = [
    "EXT_SOURCE_1",
    "EXT_SOURCE_2",
    "EXT_SOURCE_3",
    "EXT_SOURCE_MEAN",
    "DAYS_BIRTH",
    "DAYS_ID_PUBLISH",
    "FLAG_EMPLOYED",
    "DAYS_EMPLOYED",
    "BUREAU_AMT_DEBT_SUM",
    "BUREAU_DAYS_CREDIT_MIN",
    "PREV_DAYS_DECISION_MIN",
    "INST_DIAS_ATRASO_MEAN",
]

SCORE_FEATURES = frozenset(
    {
        "EXT_SOURCE_1",
        "EXT_SOURCE_2",
        "EXT_SOURCE_3",
        "EXT_SOURCE_MEAN",
    }
)

DURATION_FEATURES = frozenset(
    {
        "DAYS_EMPLOYED",
        "DAYS_ID_PUBLISH",
        "BUREAU_DAYS_CREDIT_MIN",
        "PREV_DAYS_DECISION_MIN",
    }
)

MONEY_READONLY_FEATURES = frozenset({"BUREAU_AMT_DEBT_SUM"})


def _get_label(tech_name: str) -> str:
    """Retorna apenas o nome comercial; fallback para o nome técnico limpo."""
    return FEATURE_TRANSLATIONS.get(tech_name, tech_name)


def _render_stat_card_html(
    label: str,
    value: Any,
    *,
    tone: str = "neutral",
    note: str | None = None,
) -> str:
    """Retorna HTML escapado para um card estatistico do resultado."""
    safe_tone = tone if tone in {"success", "warning", "danger", "neutral"} else "neutral"
    note_html = ""
    if note:
        note_html = f'<div class="stat-card-note">{escape(str(note))}</div>'
    return (
        f'<div class="stat-card stat-card-{safe_tone}">'
        f'<div class="stat-card-label">{escape(str(label))}</div>'
        f'<div class="stat-card-value">{escape(str(value))}</div>'
        f"{note_html}"
        f"</div>"
    )


def _risk_band_tone(risk_band_value: Any) -> str:
    """Mapeia a faixa de risco para a cor semantica do card."""
    normalized = str(risk_band_value or "").strip().lower()
    if normalized == "baixo risco":
        return "success"
    if normalized == "risco moderado":
        return "warning"
    if normalized == "alto risco":
        return "danger"
    return "neutral"


def _probability_tone(probability: Any, threshold: Any) -> str:
    """Mapeia probabilidade de inadimplencia para a cor de risco."""
    if probability is None or threshold is None:
        return "neutral"
    try:
        probability_value = float(probability)
        threshold_value = float(threshold)
    except (TypeError, ValueError):
        return "neutral"
    if threshold_value <= 0:
        return "neutral"
    if probability_value < threshold_value * 0.4:
        return "success"
    if probability_value < threshold_value:
        return "warning"
    return "danger"


def _build_score_stat_cards(
    result: dict[str, Any],
    client_id: int | None = None,
) -> list[str]:
    """Monta os cards de resumo da escoragem com labels padronizados."""
    approved = _is_approved(result)
    card_tone = "success" if approved else "danger"

    proba = result.get("probability")
    proba_txt = f"{float(proba):.2%}" if proba is not None else "—"
    approval_proba_txt = "—"
    if proba is not None:
        approval_proba_txt = f"{1.0 - float(proba):.2%}"

    prediction_value = result.get("prediction")
    prediction_label = "—"
    if prediction_value is not None:
        prediction_label = (
            f"{int(prediction_value)} "
            f"({'inadimplente' if int(prediction_value) == 1 else 'adimplente'})"
        )

    threshold_value = result.get("threshold")
    threshold_txt = (
        f"{float(threshold_value):.2%}" if threshold_value is not None else "—"
    )
    scored_client = result.get("sk_id_curr", client_id)
    probability_tone = _probability_tone(proba, threshold_value)

    return [
        _render_stat_card_html("Decisão", result.get("label", "—"), tone=card_tone),
        _render_stat_card_html(
            "Risk Band",
            result.get("risk_band", "—"),
            tone=_risk_band_tone(result.get("risk_band")),
        ),
        _render_stat_card_html(
            "Prob. inadimplência",
            proba_txt,
            tone=probability_tone,
        ),
        _render_stat_card_html(
            "Prob. adimplência",
            approval_proba_txt,
            tone=probability_tone,
        ),
        _render_stat_card_html("Classe prevista", prediction_label),
        _render_stat_card_html("Threshold", threshold_txt, note="reprovação"),
        _render_stat_card_html("Cliente", scored_client),
    ]


def _build_audit_message(
    prediction: int,
    target: int,
    *,
    has_overrides: bool,
) -> tuple[str, str]:
    """Monta mensagem de auditoria do holdout considerando simulacoes."""
    simulation_note = ""
    if has_overrides:
        simulation_note = (
            " Atenção: esta auditoria compara a decisão simulada após "
            "alterações nos campos com o histórico real do cliente no holdout."
        )

    if prediction == 0 and target == 0:
        return (
            "success",
            "**Acerto — Verdadeiro Negativo:** O modelo aprovou este cliente e, "
            "de fato, ele manteve os pagamentos em dia no histórico do banco. "
            "A decisão de crédito foi correta."
            f"{simulation_note}",
        )

    if prediction == 1 and target == 1:
        return (
            "success",
            "**Acerto — Verdadeiro Positivo:** O modelo reprovou este cliente e, "
            "de fato, ele apresentou inadimplência no histórico do banco. "
            "A decisão de crédito foi correta."
            f"{simulation_note}",
        )

    if prediction == 0 and target == 1:
        return (
            "error",
            "**Erro grave — Falso Negativo:** O modelo aprovou este cliente, "
            "mas ele deu calote no histórico do banco. Esta é a falha mais "
            "crítica: o banco teria concedido crédito a um mau pagador."
            f"{simulation_note}",
        )

    return (
        "warning",
        "**Falso Alarme — Falso Positivo:** O modelo reprovou este cliente, "
        "mas ele teria pago em dia no histórico do banco. O banco perdeu uma "
        "oportunidade de negócio com um bom pagador."
        f"{simulation_note}",
    )


def _render_factor_row_html(
    business_label: str,
    tech_name: str,
    impact_pct: float,
    *,
    tone: str = "neutral",
) -> str:
    """Retorna HTML escapado para uma linha de fator determinante."""
    safe_tone = tone if tone in {"success", "danger", "neutral"} else "neutral"
    pct_value = float(impact_pct)
    pct_width = max(0.0, min(pct_value, 100.0))
    return (
        f'<div class="factor-row factor-row-{safe_tone}">'
        f'<div class="factor-label">'
        f'<span class="factor-label-business">{escape(str(business_label))}</span>'
        f'<span class="factor-label-tech">({escape(str(tech_name))})</span>'
        f"</div>"
        f'<div class="factor-value">{pct_value:.1f}%</div>'
        f'<div class="factor-track">'
        f'<div class="factor-fill" style="width: {pct_width:.1f}%;"></div>'
        f"</div>"
        f"</div>"
    )


def _render_override_item_html(feature_name: str, values: dict[str, Any]) -> str:
    """Retorna HTML escapado para uma alteracao aplicada na simulacao."""
    return (
        '<div class="override-item">'
        f'<div class="override-title">{escape(_get_label(feature_name))}</div>'
        '<div class="override-values">'
        f"Valor original: <code>{escape(str(values.get('original')))}</code><br>"
        f"Valor aplicado: <code>{escape(str(values.get('applied')))}</code>"
        "</div>"
        "</div>"
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


def _is_missing_value(value: Any) -> bool:
    """Indica se o valor deve ser tratado como ausência de informação."""
    if value is None or value == "":
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    try:
        import pandas as pd

        if pd.isna(value):
            return True
    except (ImportError, TypeError, ValueError):
        pass
    return False


def _format_duration_from_days(abs_days: float) -> str:
    """Converte dias absolutos em meses (<12) ou anos inteiros (>=12 meses)."""
    months = abs_days / (365.25 / 12.0)
    if months < 12:
        return f"{int(round(months))} meses"
    return f"{int(abs_days / 365.25)} anos"


def _format_delay_mean(abs_days: float) -> str:
    """Formata média de atraso em dias, meses ou anos conforme a magnitude."""
    if abs_days < 30:
        return f"{int(round(abs_days))} dias"
    if abs_days < 365:
        months = abs_days / (365.25 / 12.0)
        return f"{int(round(months))} meses"
    return f"{int(abs_days / 365.25)} anos"


def _format_brl(value: float) -> str:
    """Formata número no padrão monetário brasileiro (R$ 1.250.600,00)."""
    formatted = f"{value:,.2f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


def _parse_money_input(raw_value: Any) -> float | None:
    """Tenta converter texto de input monetário em float; None se inválido."""
    if raw_value is None:
        return None
    text = str(raw_value).strip()
    if not text or text == "Sem Info":
        return None
    normalized = text.replace("R$", "").replace(" ", "")
    if "," in normalized and "." in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")
    elif "," in normalized:
        normalized = normalized.replace(",", ".")
    try:
        parsed = float(normalized)
    except ValueError:
        return None
    if math.isnan(parsed):
        return None
    return parsed


def _is_binary_flag_column(col_name: str) -> bool:
    """Indica se a coluna segue o padrão de flag binária da ABT."""
    return (
        col_name.startswith(("FLAG_", "REG_", "LIVE_", "HAS_"))
        or col_name.endswith("_FLAG")
    )


def _is_days_column(col_name: str) -> bool:
    """Indica se a coluna representa duração/tempo em dias."""
    return "DAYS_" in col_name or "_DAYS_" in col_name


def _is_count_like_column(col_name: str) -> bool:
    """Indica se a coluna representa contagem, hora ou dia (inteiro limpo)."""
    if _is_days_column(col_name):
        return False
    return (
        col_name in {"CNT_CHILDREN", "CNT_FAM_MEMBERS"}
        or col_name.startswith(("CNT_", "HOUR_"))
        or "_CNT_" in col_name
        or col_name.endswith(("_CNT", "_HOUR", "_DAY"))
        or "_HOUR" in col_name
    )

def _format_readonly_value(col_name: str, value: Any) -> str:
    """Formata valor somente leitura com unidades comerciais de negócio."""
    if _is_missing_value(value):
        return "Sem Info"

    val_str = str(value).strip()
    if not val_str:
        return "Sem Info"

    # Flags binárias: cobre 0/1 e Y/N antes da conversão numérica estrita.
    if _is_binary_flag_column(col_name):
        upper = val_str.upper()
        if upper in {"1", "1.0", "Y", "YES"}:
            return "Sim"
        if upper in {"0", "0.0", "N", "NO"}:
            return "Não"

    try:
        num_val = float(value)
        if math.isnan(num_val):
            return "Sem Info"
    except (TypeError, ValueError):
        return val_str

    if _is_binary_flag_column(col_name):
        if num_val == 1.0:
            return "Sim"
        if num_val == 0.0:
            return "Não"

    if col_name in SCORE_FEATURES:
        return str(int(round(num_val * 1000)))

    if col_name == "DAYS_BIRTH":
        return f"{int(abs(num_val) / 365.25)} anos"

    if col_name in DURATION_FEATURES:
        return _format_duration_from_days(abs(num_val))

    if col_name == "INST_DIAS_ATRASO_MEAN":
        return _format_delay_mean(abs(num_val))

    if col_name in MONEY_READONLY_FEATURES:
        return _format_brl(num_val)

    if _is_days_column(col_name):
        return _format_delay_mean(abs(num_val))

    if _is_count_like_column(col_name) and num_val == int(num_val):
        return str(int(num_val))

    return val_str


# Opções categóricas típicas da ABT (Silver: UPPER/TRIM)
EDUCATION_OPTIONS = [
    "HIGHER EDUCATION",
    "SECONDARY / SECONDARY SPECIAL",
    "INCOMPLETE HIGHER",
    "LOWER SECONDARY",
    "ACADEMIC DEGREE",
]
INCOME_OPTIONS = [
    "WORKING",
    "COMMERCIAL ASSOCIATE",
    "PENSIONER",
    "STATE SERVANT",
    "UNEMPLOYED",
    "STUDENT",
    "BUSINESSMAN",
    "MATERNITY LEAVE",
]
OCCUPATION_OPTIONS = [
    "LABORERS",
    "SALES STAFF",
    "CORE STAFF",
    "MANAGERS",
    "DRIVERS",
    "HIGH SKILL TECH STAFF",
    "ACCOUNTANTS",
    "MEDICINE STAFF",
    "SECURITY STAFF",
    "COOKING STAFF",
    "CLEANING STAFF",
    "PRIVATE SERVICE STAFF",
    "LOW-SKILL LABORERS",
    "WAITERS/BARMEN STAFF",
    "SECRETARIES",
    "REALTY AGENTS",
    "HR STAFF",
    "IT STAFF",
]
ORGANIZATION_OPTIONS = [
    "BUSINESS ENTITY TYPE 3",
    "XNA",
    "SELF-EMPLOYED",
    "OTHER",
    "MEDICINE",
    "BUSINESS ENTITY TYPE 2",
    "GOVERNMENT",
    "SCHOOL",
    "TRADE: TYPE 7",
    "KINDERGARTEN",
    "CONSTRUCTION",
    "BUSINESS ENTITY TYPE 1",
    "TRANSPORT: TYPE 4",
    "TRADE: TYPE 3",
    "INDUSTRY: TYPE 9",
    "INDUSTRY: TYPE 3",
    "SECURITY",
    "HOUSING",
    "MILITARY",
    "BANK",
    "AGRICULTURE",
    "POLICE",
    "POSTAL",
    "SECURITY MINISTRIES",
    "RESTAURANT",
    "SERVICES",
    "UNIVERSITY",
    "INDUSTRY: TYPE 7",
    "TRANSPORT: TYPE 3",
    "INDUSTRY: TYPE 1",
    "HOTEL",
    "ELECTRICITY",
    "TELECOM",
    "EMERGENCY",
    "ADVERTISING",
    "TRADE: TYPE 2",
    "CULTURE",
    "INSURANCE",
    "INDUSTRY: TYPE 11",
    "LEGAL SERVICES",
    "MOBILE",
    "CLEANING",
    "TRANSPORT: TYPE 2",
    "INDUSTRY: TYPE 4",
    "TRADE: TYPE 1",
    "INDUSTRY: TYPE 5",
    "INDUSTRY: TYPE 2",
    "TRADE: TYPE 6",
    "INDUSTRY: TYPE 12",
    "TRADE: TYPE 4",
    "INDUSTRY: TYPE 13",
    "RELIGION",
    "TRADE: TYPE 5",
    "INDUSTRY: TYPE 10",
    "INDUSTRY: TYPE 6",
    "TRANSPORT: TYPE 1",
    "INDUSTRY: TYPE 8",
]

CATEGORICAL_OPTIONS: dict[str, list[str]] = {
    "NAME_EDUCATION_TYPE": EDUCATION_OPTIONS,
    "NAME_INCOME_TYPE": INCOME_OPTIONS,
    "OCCUPATION_TYPE": OCCUPATION_OPTIONS,
    "ORGANIZATION_TYPE": ORGANIZATION_OPTIONS,
}

MONEY_FEATURE_BOUNDS: dict[str, tuple[float, float]] = {
    "AMT_CREDIT": (1.0, 4050000.0),
    "AMT_ANNUITY": (1.0, 258025.5),
}


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


def _safe_str(value: Any) -> str:
    if value is None:
        return "Sem Info"
    try:
        import math

        if isinstance(value, float) and math.isnan(value):
            return "Sem Info"
    except Exception:
        pass
    text = str(value).strip()
    if not text:
        return "Sem Info"
    return text


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


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


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


def api_get_client(client_id: int) -> dict[str, Any]:
    """GET /client/{id} — retorna features ou levanta com status HTTP."""
    url = f"{API_BASE_URL}/client/{client_id}"
    req = Request(url, method="GET", headers={"Accept": "application/json"})
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(json.dumps({"status": exc.code, "body": body})) from exc
    except URLError as exc:
        raise ConnectionError(
            f"API indisponível em {API_BASE_URL}. Verifique se o uvicorn está rodando."
        ) from exc


def api_post_score(client_id: int, features_override: dict[str, Any]) -> dict[str, Any]:
    """POST /score com client_id + features_override."""
    payload = json.dumps(
        {"client_id": client_id, "features_override": features_override}
    ).encode("utf-8")
    req = Request(
        f"{API_BASE_URL}/score",
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(json.dumps({"status": exc.code, "body": body})) from exc
    except URLError as exc:
        raise ConnectionError(
            f"API indisponível em {API_BASE_URL}. Verifique se o uvicorn está rodando."
        ) from exc


def _parse_http_error(exc: RuntimeError) -> tuple[int | None, str]:
    try:
        payload = json.loads(str(exc))
        return payload.get("status"), payload.get("body", str(exc))
    except Exception:
        return None, str(exc)


def _is_approved(result: dict[str, Any]) -> bool:
    label = str(result.get("label", "")).lower()
    band = str(result.get("risk_band", "")).lower()
    prediction = result.get("prediction")
    if prediction == 0 or "aprovado" in label or "baixo" in band:
        return True
    return False


def _format_int_br(value: int) -> str:
    return f"{int(value):,}".replace(",", ".")


def _format_pct_br(value: float, *, digits: int = 1) -> str:
    return f"{value * 100:.{digits}f}%".replace(".", ",")


def _format_decimal_br(value: float, *, digits: int = 4) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def _get_model_test_performance(*, force: bool = False) -> dict[str, Any] | None:
    """Retorna métricas oficiais do metadata (memo só em sucesso)."""
    cached = st.session_state.get("model_test_performance")
    if cached is not None and not force:
        return cached
    if st.session_state.get("model_test_performance_error") and not force:
        return None
    try:
        # Preferir arquivo local do container; evita fallback S3 no caminho da UI.
        perf = test_performance_from_metadata(load_model_metadata())
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


# Variáveis categóricas do What-If usadas no mapeamento de risco por segmento.
PROFILE_RISK_ATTRIBUTES: dict[str, str] = {
    "ORGANIZATION_TYPE": "Setor / Organização",
    "OCCUPATION_TYPE": "Profissão",
    "NAME_INCOME_TYPE": "Tipo de Renda",
    "NAME_EDUCATION_TYPE": "Escolaridade",
}


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


def _format_risk_pct(value: float) -> str:
    return f"{float(value) * 100:.2f}%"


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
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


def _load_client_dossier(client_id_query: int) -> None:
    """Consulta API e persiste dossiê + seeds dos widgets What-If."""
    response = api_get_client(client_id_query)
    features_dict = response.get("features") or {}
    if not features_dict:
        st.error(f"Cliente {client_id_query} retornou dossiê vazio na API.")
        return

    previous_id = st.session_state.get("client_id")
    if previous_id != client_id_query:
        _clear_edit_widget_keys(previous_id)
    _clear_edit_widget_keys(client_id_query)

    st.session_state.client_features = features_dict
    st.session_state.client_id = client_id_query
    st.session_state.score_result = None
    _clear_client_view_flags()
    _seed_edit_widgets_from_features(features_dict, client_id_query)
    st.success(f"Cliente {client_id_query} localizado na base do Bureau.")


def _run_credit_score(features: dict[str, Any]) -> None:
    """Executa escoragem usando valores commitados pelo form de simulação."""
    client_id = int(st.session_state.client_id)
    overrides = _collect_overrides_from_session(client_id, features)
    st.session_state.score_result = api_post_score(client_id, overrides)
    st.session_state.score_json_ready = False


# ---------------------------------------------------------------------------
# Layout superior (montado em main)
# ---------------------------------------------------------------------------
def _render_score_result(
    features: dict[str, Any],
    client_id: int,
    result: dict[str, Any],
) -> None:
    """Renderiza o parecer, cards, fatores e auditoria da última escoragem."""
    st.markdown(
        """
        <div class="section-band">
            <div class="section-kicker">Resultado</div>
            <div class="section-title">Escoragem de crédito</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    approved = _is_approved(result)
    box_class = "approved-box" if approved else "rejected-box"

    st.markdown(
        f'<div class="{box_class}"><h3>'
        f'{"✓ Parecer favorável" if approved else "✗ Parecer desfavorável"}'
        f"</h3></div>",
        unsafe_allow_html=True,
    )

    stat_cards = _build_score_stat_cards(result, client_id)
    st.markdown(
        f'<div class="stat-grid">{"".join(stat_cards)}</div>',
        unsafe_allow_html=True,
    )

    applied_overrides = result.get("applied_overrides") or {}
    with st.expander("Simulação aplicada"):
        if applied_overrides:
            override_items = [
                _render_override_item_html(feature_name, values)
                for feature_name, values in applied_overrides.items()
            ]
            st.markdown(
                f'<div class="override-list">{"".join(override_items)}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.write(
                "Nenhuma alteração aplicada; escoragem feita com o dossiê original."
            )

    if approved:
        st.markdown("#### Fatores Determinantes para Aprovação")
        factors = result.get("top_positive_factors") or []
        empty_msg = "Nenhum fator positivo identificado."
        factor_tone = "success"
    else:
        st.markdown("#### Motivos da Reprovação (Fatores de Risco)")
        factors = result.get("top_risk_factors") or []
        empty_msg = "Nenhum fator de risco identificado."
        factor_tone = "danger"

    if factors:
        factor_rows = []
        for feature_name, impact_pct in factors:
            tech_name = str(feature_name)
            business_label = FEATURE_TRANSLATIONS.get(tech_name, tech_name)
            factor_rows.append(
                _render_factor_row_html(
                    business_label,
                    tech_name,
                    float(impact_pct),
                    tone=factor_tone,
                )
            )
        st.markdown(
            f'<div class="factor-list">{"".join(factor_rows)}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.caption(empty_msg)

    target_raw = features.get(TARGET_COLUMN)
    if target_raw is not None:
        try:
            if isinstance(target_raw, float) and math.isnan(target_raw):
                target_raw = None
        except Exception:
            pass

    if target_raw is not None:
        target = int(target_raw)
        prediction = result.get("prediction")

        st.markdown("#### Auditoria do Modelo (Holdout)")

        audit_tone, audit_message = _build_audit_message(
            int(prediction),
            target,
            has_overrides=bool(applied_overrides),
        )
        if audit_tone == "success":
            st.success(audit_message)
        elif audit_tone == "error":
            st.error(audit_message)
        else:
            st.warning(audit_message)

    with st.expander("Output - JSON"):
        if st.session_state.get("score_json_ready"):
            st.json(result)
        elif st.button(
            "Mostrar JSON da escoragem",
            key="btn_show_score_json",
            use_container_width=True,
        ):
            st.session_state.score_json_ready = True
            st.json(result)
        else:
            st.caption(
                "O JSON completo só é montado sob demanda para não pesar o rerun."
            )


def _render_client_workspace(features: dict[str, Any], client_id: int) -> None:
    """Dossiê interativo: What-If em form evita rerun a cada tecla/select."""
    _ensure_edit_widget_seeds(features, client_id)

    st.markdown(
        '<div style="border-left: 4px solid #2563eb; padding-left: 10px; '
        'margin-bottom: 15px;"><h5 style="margin: 0;">Dados atualizados '
        "para simulação</h5></div>",
        unsafe_allow_html=True,
    )
    with st.form("form_whatif_score", clear_on_submit=False):
        editable_features = list(_CONFIG.editable_features)
        for row_start in range(0, len(editable_features), 3):
            row_features = editable_features[row_start : row_start + 3]
            cols = st.columns(3)
            for col, feature_name in zip(cols, row_features):
                with col:
                    _render_editable_feature(features, feature_name, client_id)

        st.markdown('<div class="score-action">', unsafe_allow_html=True)
        st.markdown('<div class="score-btn">', unsafe_allow_html=True)
        run_score = st.form_submit_button(
            "Rodar Escoragem de Crédito",
            type="primary",
            use_container_width=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    if run_score:
        try:
            _run_credit_score(features)
        except ValueError as exc:
            st.error(str(exc))
        except ConnectionError as exc:
            st.error(str(exc))
        except RuntimeError as exc:
            status, _ = _parse_http_error(exc)
            if status == 404:
                st.error(COMPLIANCE_404_MSG)
            else:
                st.error(f"Falha na escoragem (HTTP {status}): {exc}")

    st.markdown(
        '<div style="border-left: 4px solid #64748b; padding-left: 10px; '
        'margin-bottom: 15px;"><h5 style="margin: 0;">Dados fixos do '
        "cliente</h5></div>",
        unsafe_allow_html=True,
    )
    readonly_features = [
        col_name
        for col_name in READONLY_FEATURES_DISPLAY_ORDER
        if col_name not in READONLY_FEATURES_HIDDEN
        and col_name in _CONFIG.readonly_features
    ]
    for row_start in range(0, len(readonly_features), 3):
        row_features = readonly_features[row_start : row_start + 3]
        cols = st.columns(3)
        for col, col_name in zip(cols, row_features):
            with col:
                _render_readonly_feature(col_name, features.get(col_name))

    if st.button(
        "Carregar dossiê completo (todas as variáveis da ABT)",
        key="btn_load_dossier_table",
        use_container_width=True,
        disabled=bool(st.session_state.get("dossier_table_ready")),
    ):
        st.session_state.dossier_table_ready = True

    if st.session_state.get("dossier_table_ready"):
        with st.expander(
            "Ver dossiê completo (todas as variáveis da ABT)",
            expanded=True,
        ):
            dossier_rows = [
                {
                    "Variável": FEATURE_TRANSLATIONS.get(col_name, col_name),
                    "Campo": col_name,
                    "Valor": _format_readonly_value(col_name, value),
                }
                for col_name, value in features.items()
            ]
            st.dataframe(
                pd.DataFrame(dossier_rows),
                use_container_width=True,
                hide_index=True,
            )
    else:
        st.caption(
            "O dossiê completo da ABT só é montado sob demanda para não "
            "pesar cada interação da mesa."
        )

    result = st.session_state.score_result
    if result:
        _render_score_result(features, client_id, result)


def _render_mesa_tab() -> None:
    busca_col, limpar_col = st.columns([5, 1], vertical_alignment="bottom")
    with busca_col:
        with st.form("form_busca_cliente", clear_on_submit=False):
            busca_inner1, busca_inner2 = st.columns([3, 1], vertical_alignment="bottom")
            with busca_inner1:
                sk_id_input = st.text_input(
                    ID_COLUMN,
                    key="sk_id_input",
                    help=(
                        "Identificador do cliente na base do Bureau / "
                        "holdout de demonstração."
                    ),
                )
            with busca_inner2:
                consultar = st.form_submit_button(
                    "Consultar Cliente",
                    type="primary",
                    use_container_width=True,
                )
    with limpar_col:
        st.button(
            "Limpar",
            use_container_width=True,
            on_click=_clear_dashboard_state,
            key="btn_limpar",
        )

    if consultar:
        sk_id_text = str(sk_id_input or "").strip()
        if not sk_id_text.isdigit() or int(sk_id_text) < 1:
            # Não apaga dossiê já carregado quando a consulta é inválida.
            st.error(f"Informe um {ID_COLUMN} inteiro positivo.")
        else:
            try:
                _load_client_dossier(int(sk_id_text))
            except ConnectionError as exc:
                st.error(str(exc))
            except RuntimeError as exc:
                status, _ = _parse_http_error(exc)
                if status == 404:
                    st.error(COMPLIANCE_404_MSG)
                else:
                    st.error(f"Falha ao consultar cliente (HTTP {status}): {exc}")

    features = st.session_state.client_features
    if features:
        client_id = int(st.session_state.client_id)
        st.markdown(f"### Cliente *{client_id}*")
        _render_client_workspace(features, client_id)
    else:
        st.info(
            f"Informe um **{ID_COLUMN}** válido e clique em **Consultar Cliente** "
            "para carregar o dossiê a partir da API."
        )


def _render_catalog_tab() -> None:
    """Catálogo sob demanda: markdown grande não roda a cada rerun da mesa."""
    if not st.session_state.get("catalog_ready"):
        st.title("Variáveis da Análise de Risco")
        st.caption(
            "Dicionário de fatores do motor de decisão. Carregue sob demanda "
            "para não pesar a Mesa de Crédito."
        )
        if st.button(
            "Carregar dicionário de variáveis",
            type="secondary",
            key="btn_load_catalog",
        ):
            st.session_state.catalog_ready = True
        else:
            st.info(
                "O dicionário monta o markdown de todas as variáveis da ABT. "
                "Carregue quando for consultar as descrições de negócio."
            )
            return

    render_catalog(show_back_link=True)


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


def main() -> None:
    """Ponto de entrada do dashboard Streamlit."""
    _configure_page()
    _init_session_state()

    st.title("Credit Risk Desk — Home Credit")
    st.caption(
        "Motor de decisão de crédito com dados Home Credit, modelo LightGBM "
        "e API de escoragem"
    )
    st.caption(
        "Consulte as variáveis da análise de risco para entender os fatores "
        "do motor de decisão."
    )

    # Navegacao por abas da mesa de credito, catalogo e performance do modelo.
    tab_mesa, tab_catalogo, tab_performance = st.tabs(
        [
            "🏦 Mesa de Crédito",
            "📖 Variáveis da Análise de Risco",
            "📈 Performance & ROI do Modelo",
        ]
    )

    with tab_mesa:
        _render_mesa_tab()

    with tab_catalogo:
        _render_catalog_tab()

    with tab_performance:
        _render_performance_tab()


if __name__ == "__main__":
    main()
