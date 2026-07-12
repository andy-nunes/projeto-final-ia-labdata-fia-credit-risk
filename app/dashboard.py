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

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from scripts.model_config import get_model_config

_CONFIG = get_model_config()
API_BASE_URL = _CONFIG.api_base_url
ID_COLUMN = _CONFIG.id_column
TARGET_COLUMN = _CONFIG.target_column

# ---------------------------------------------------------------------------
# Configuração da página + Dark Mode forçado
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Credit Risk Desk | Home Credit",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Força tema base dark antes do primeiro render
try:
    st._config.set_option("theme.base", "dark")
    st._config.set_option("theme.backgroundColor", "#0e1117")
    st._config.set_option("theme.secondaryBackgroundColor", "#1a1f2e")
    st._config.set_option("theme.textColor", "#fafafa")
    st._config.set_option("theme.primaryColor", "#3b82f6")
except Exception:
    pass

st.markdown(
    """
    <style>
    .stApp {
        background-color: #0e1117;
        color: #fafafa;
    }
    [data-testid="stHeader"] {
        background-color: rgba(14, 17, 23, 0.85);
    }
    .block-container {
        padding-top: 2.2rem;
        padding-bottom: 2.8rem;
        max-width: 1280px;
    }
    h1 {
        letter-spacing: 0;
        margin-bottom: 0.15rem;
    }
    h2, h3, h4, h5 {
        letter-spacing: 0;
    }
    div[data-testid="stVerticalBlock"] > div:has(.section-band) {
        margin-top: 0.6rem;
    }
    .section-band {
        border-top: 1px solid #273142;
        padding-top: 1.15rem;
        margin-top: 1.15rem;
    }
    .section-kicker {
        color: #93a4b8;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin: 0 0 0.25rem 0;
    }
    .section-title {
        color: #f8fafc;
        font-size: 1.08rem;
        font-weight: 700;
        line-height: 1.25;
        margin: 0 0 0.8rem 0;
    }
    div[data-testid="stTextInput"] label,
    div[data-testid="stNumberInput"] label,
    div[data-testid="stSelectbox"] label {
        color: #cbd5e1;
        font-weight: 600;
        line-height: 1.25;
    }
    div[data-testid="stTextInput"] input,
    div[data-testid="stNumberInput"] input,
    div[data-baseweb="select"] > div {
        border-radius: 8px;
        border-color: #334155;
        min-height: 2.75rem;
    }
    div[data-testid="stButton"] button {
        border-radius: 8px !important;
        min-height: 2.75rem;
        font-weight: 700 !important;
    }
    .score-btn button {
        background: #2563eb !important;
        color: white !important;
        border: 1px solid #3b82f6 !important;
        font-weight: 600 !important;
    }
    .score-action {
        margin-top: 1rem;
    }
    .approved-box {
        background: rgba(22, 163, 74, 0.13);
        border: 1px solid #22c55e;
        border-radius: 8px;
        padding: 1rem 1.15rem;
        margin: 0.35rem 0 1rem 0;
    }
    .rejected-box {
        background: rgba(220, 38, 38, 0.13);
        border: 1px solid #ef4444;
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
    .approved-box h3 { color: #86efac; }
    .rejected-box h3 { color: #fca5a5; }
    .feature-label {
        margin: 0 0 0.28rem 0;
        min-height: 2.35rem;
        line-height: 1.25;
    }
    .feature-label-business {
        color: #fafafa;
        font-size: 0.92rem;
        font-weight: 650;
    }
    .feature-label-tech {
        display: block;
        font-size: 0.76rem;
        color: #94a3b8;
        overflow-wrap: anywhere;
    }
    .stat-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.75rem;
        margin: 0.3rem 0 0.55rem 0;
    }
    .stat-card {
        background: #151b29;
        border: 1px solid #2d3548;
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
        border-left: 4px solid #facc15;
    }
    .stat-card-neutral {
        border-left: 4px solid #64748b;
    }
    .stat-card-label {
        color: #9ca3af;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        line-height: 1.2;
        text-transform: uppercase;
    }
    .stat-card-value {
        color: #f8fafc;
        font-size: 1.16rem;
        font-weight: 750;
        line-height: 1.25;
        white-space: normal;
        overflow-wrap: anywhere;
    }
    .stat-card-note {
        color: #94a3b8;
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
        background: #111827;
        border: 1px solid #273142;
        border-radius: 8px;
        padding: 0.72rem 0.85rem;
    }
    .factor-label {
        min-width: 0;
        line-height: 1.25;
    }
    .factor-label-business {
        color: #f8fafc;
        font-size: 0.92rem;
        font-weight: 650;
    }
    .factor-label-tech {
        display: block;
        color: #94a3b8;
        font-size: 0.75rem;
        margin-top: 0.12rem;
        overflow-wrap: anywhere;
    }
    .factor-value {
        color: #f8fafc;
        font-size: 0.92rem;
        font-weight: 750;
        text-align: right;
        white-space: nowrap;
    }
    .factor-track {
        height: 0.5rem;
        overflow: hidden;
        border-radius: 999px;
        background: #273142;
    }
    .factor-fill {
        height: 100%;
        border-radius: 999px;
        background: #38bdf8;
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
        border: 1px solid #273142;
        border-radius: 8px;
        padding: 0.72rem 0.85rem;
        background: #111827;
    }
    .override-title {
        color: #f8fafc;
        font-weight: 700;
        margin-bottom: 0.35rem;
    }
    .override-values {
        color: #cbd5e1;
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
    </style>
    """,
    unsafe_allow_html=True,
)

COMPLIANCE_404_MSG = (
    "Cliente não localizado na base do Bureau. Por questões de ética, compliance "
    "e prevenção a fraudes, não é permitido o preenchimento manual do dossiê de "
    "crédito para clientes sem rastro de dados."
)

FEATURE_TRANSLATIONS = {
    "AMT_CREDIT": "Valor Solicitado (R$)",
    "AMT_ANNUITY": "Valor da Parcela Mensal (R$)",
    "AMT_GOODS_PRICE": "Valor do Bem Financiado (R$)",
    "NAME_EDUCATION_TYPE": "Grau de Escolaridade",
    "NAME_INCOME_TYPE": "Tipo de Renda",
    "ORGANIZATION_TYPE": "Tipo de Organização / Setor",
    "OCCUPATION_TYPE": "Profissão / Ocupação",
    "EXT_SOURCE_1": "Score Externo 1 (Bureau)",
    "EXT_SOURCE_2": "Score Externo 2 (Bureau)",
    "EXT_SOURCE_3": "Score Externo 3 (Bureau)",
    "DAYS_BIRTH": "Dias de Vida (Idade)",
    "DAYS_EMPLOYED": "Tempo de Emprego (Dias)",
    "DAYS_ID_PUBLISH": "Dias desde Emissão do RG",
    "DAYS_REGISTRATION": "Dias desde Registro (Endereço)",
    "EXT_SOURCE_MEAN": "Média dos Scores Externos",
    "EXT_SOURCE_CNT": "Qtd. de Scores Externos Disponíveis",
    "FLAG_EMPLOYED": "Está Empregado? (1=Sim, 0=Não)",
    "DAYS_EMPLOYED_YEARS": "Tempo de Emprego (Anos)",
    "BUREAU_AMT_DEBT_SUM": "Dívida Total em Outros Bancos (R$)",
    "BUREAU_DAYS_CREDIT_MIN": "Dias desde o 1º Crédito",
    "PREV_DAYS_DECISION_MIN": "Dias desde a Últ. Proposta",
    "INST_DIAS_ATRASO_MEAN": "Média de Dias em Atraso (Histórico)",
    "INST_AMT_PAYMENT_SUM": "Total Pago em Empréstimos Ant. (R$)",
    "INST_PAYMENT_RATIO": "Taxa de Pagamento de Parcelas",
    "INST_RATE_ATRASO": "Taxa de Atraso em Parcelas",
    "CODE_GENDER": "Gênero",
    "FLAG_OWN_CAR": "Possui Carro?",
    "OWN_CAR_AGE": "Idade do Veículo Próprio (Anos)",
    "FLAG_OWN_REALTY": "Possui Imóvel?",
    "CNT_CHILDREN": "Qtd. de Filhos",
    "CNT_FAM_MEMBERS": "Tamanho da Família",
    "AMT_INCOME_TOTAL": "Renda Total Declarada (R$)",
    "NAME_FAMILY_STATUS": "Estado Civil",
    "NAME_HOUSING_TYPE": "Tipo de Moradia",
    "AGE_YEARS": "Idade (Anos)",
    "CREDIT_INCOME_RATIO": "Comprometimento de Renda",
    "ANNUITY_INCOME_RATIO": "Comprometimento da Renda (Parcela/Renda)",
    "HAS_BUREAU": "Possui Histórico no Bureau?",
    "HAS_PREVIOUS_APP": "Possui Proposta Anterior?",
    "REGION_RATING_CLIENT": "Risco Regional do Cliente",
    "REGION_RATING_CLIENT_W_CITY": "Risco Regional (com Cidade)",
    "DEF_30_CNT_SOCIAL_CIRCLE": "Inadimplência na Rede Social (30d)",
    "OBS_30_CNT_SOCIAL_CIRCLE": "Consultas na Rede Social (30d)",
    "DEF_60_CNT_SOCIAL_CIRCLE": "Inadimplência na Rede Social (60d)",
    "OBS_60_CNT_SOCIAL_CIRCLE": "Consultas na Rede Social (60d)",
    "HOUR_APPR_PROCESS_START": "Hora da Solicitação de Crédito",
    "WEEKDAY_APPR_PROCESS_START": "Dia da Semana da Solicitação",
    "FLAG_DOCUMENT_3": "Forneceu Documento Principal (RG/CPF)",
    "LIVE_CITY_NOT_WORK_CITY": "Mora e Trabalha em Cidades Diferentes",
    "REG_CITY_NOT_LIVE_CITY": "Endereço Registrado Difere da Moradia",
    "CC_UTILIZATION_MEAN": "Média de Uso do Cartão de Crédito",
    "CC_AMT_BALANCE_MEAN": "Média de Saldo no Cartão de Crédito",
    "POS_CNT_MONTHS": "Meses em Financiamentos (POS)",
    "PREV_CNT_APPS": "Qtd. de Solicitações Anteriores",
    "PREV_CNT_APPROVED": "Qtd. de Solicitações Aprovadas Anteriores",
    "PREV_CNT_REFUSED": "Qtd. de Solicitações Reprovadas Anteriores",
}


def _get_label(tech_name: str) -> str:
    translation = FEATURE_TRANSLATIONS.get(tech_name)
    if translation:
        return f"{translation} ({tech_name})"
    return tech_name


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
    """Renderiza label com nome de negócio + identificador técnico em HTML."""
    business = FEATURE_TRANSLATIONS.get(tech_name)
    if business:
        st.markdown(
            f'<p class="feature-label">'
            f'<span class="feature-label-business">{business}</span> '
            f'<span class="feature-label-tech">({tech_name})</span>'
            f"</p>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<p class="feature-label feature-label-business">{tech_name}</p>',
            unsafe_allow_html=True,
        )


def _format_readonly_value(col_name: str, value: Any) -> str:
    """Formata valor somente leitura com placeholder e conversão dias → anos."""
    if value is None or value == "":
        return "Sem Info"
    if isinstance(value, float) and math.isnan(value):
        return "Sem Info"
    try:
        import pandas as pd

        if pd.isna(value):
            return "Sem Info"
    except (ImportError, TypeError, ValueError):
        pass

    val_str = str(value).strip()
    if not val_str:
        return "Sem Info"

    if "DAYS_" in col_name and col_name != "DAYS_EMPLOYED_YEARS":
        try:
            num_val = float(value)
            if math.isnan(num_val):
                return "Sem Info"
            anos = abs(num_val) / 365.25
            return f"{val_str} (~ {anos:.1f} anos)"
        except (TypeError, ValueError):
            pass

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


def _render_editable_feature(
    features: dict[str, Any],
    feature_name: str,
    client_id: int,
) -> Any:
    """Renderiza widget de simulação para uma feature editável configurada."""
    _render_custom_label(feature_name)
    widget_key = f"edit_{client_id}_{feature_name}"

    if feature_name in MONEY_FEATURE_BOUNDS:
        min_value, max_value = MONEY_FEATURE_BOUNDS[feature_name]
        value = _safe_float(features.get(feature_name), default=min_value)
        return st.text_input(
            feature_name,
            value=f"{value:.2f}",
            help=f"Informe um número entre {min_value:.2f} e {max_value:.2f}.",
            label_visibility="collapsed",
            key=widget_key,
        )

    if feature_name in CATEGORICAL_OPTIONS:
        options = _options_with_current(
            CATEGORICAL_OPTIONS[feature_name],
            features.get(feature_name),
        )
        return st.selectbox(
            feature_name,
            options,
            index=_index_of(options, features.get(feature_name)),
            label_visibility="collapsed",
            key=widget_key,
        )

    return st.text_input(
        feature_name,
        value=_safe_str(features.get(feature_name)),
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


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "client_features" not in st.session_state:
    st.session_state.client_features = None
if "client_id" not in st.session_state:
    st.session_state.client_id = None
if "score_result" not in st.session_state:
    st.session_state.score_result = None
if "sk_id_input" not in st.session_state:
    st.session_state.sk_id_input = str(st.session_state.client_id or 139767)


def _clear_dashboard_state() -> None:
    """Limpa dossie, score e restaura o identificador padrao da tela."""
    st.session_state.client_features = None
    st.session_state.client_id = None
    st.session_state.score_result = None
    st.session_state.sk_id_input = "139767"


# ---------------------------------------------------------------------------
# Layout superior
# ---------------------------------------------------------------------------
st.title("Credit Risk Desk — Home Credit")
st.caption(
    "Motor de decisão de crédito com dados Home Credit, modelo LightGBM "
    "e API de escoragem"
)
st.caption("Consulte o catálogo de campos da ABT para ver tipos, fontes e descrições.")
st.markdown("[Abrir catálogo de campos da ABT](/catalogo_abt)")

top_col1, top_col2, top_col3 = st.columns([2.4, 1, 1], vertical_alignment="bottom")
with top_col1:
    sk_id_input = st.text_input(
        ID_COLUMN,
        key="sk_id_input",
        help="Identificador do cliente na base do Bureau / holdout de demonstração.",
    )
with top_col2:
    consultar = st.button("Consultar Cliente", type="primary", use_container_width=True)
with top_col3:
    st.button("Limpar", use_container_width=True, on_click=_clear_dashboard_state)

if consultar:
    st.session_state.score_result = None
    sk_id_text = str(sk_id_input).strip()
    if not sk_id_text.isdigit() or int(sk_id_text) < 1:
        st.session_state.client_features = None
        st.session_state.client_id = None
        st.error(f"Informe um {ID_COLUMN} inteiro positivo.")
    else:
        client_id_query = int(sk_id_text)
        try:
            response = api_get_client(client_id_query)
            st.session_state.client_features = response.get("features", {})
            st.session_state.client_id = client_id_query
            st.success(f"Cliente {client_id_query} localizado na base do Bureau.")
        except ConnectionError as exc:
            st.session_state.client_features = None
            st.session_state.client_id = None
            st.error(str(exc))
        except RuntimeError as exc:
            status, _ = _parse_http_error(exc)
            st.session_state.client_features = None
            st.session_state.client_id = None
            if status == 404:
                st.error(COMPLIANCE_404_MSG)
            else:
                st.error(f"Falha ao consultar cliente (HTTP {status}): {exc}")

# ---------------------------------------------------------------------------
# Simulação (somente se cliente existir)
# ---------------------------------------------------------------------------
features = st.session_state.client_features
if features:
    st.markdown(
        f"""
        <div class="section-band">
            <div class="section-kicker">Dossiê do cliente</div>
            <div class="section-title">{ID_COLUMN} = {st.session_state.client_id}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns(2)

    with left:
        st.markdown("##### Simulação")
        editable_values: dict[str, Any] = {}
        for feature_name in _CONFIG.editable_features:
            editable_values[feature_name] = _render_editable_feature(
                features,
                feature_name,
                int(st.session_state.client_id),
            )

    with right:
        st.markdown("##### Informações do cliente")
        ro_left, ro_right = st.columns(2)
        mid = (len(_CONFIG.readonly_features) + 1) // 2
        for idx, col_name in enumerate(_CONFIG.readonly_features):
            target = ro_left if idx < mid else ro_right
            with target:
                _render_custom_label(col_name)
                st.text_input(
                    label=col_name,
                    value=_format_readonly_value(col_name, features.get(col_name)),
                    disabled=True,
                    label_visibility="collapsed",
                    key=f"ro_{st.session_state.client_id}_{col_name}",
                )

    with st.expander("Ver dossiê completo"):
        full_dossier = {
            _get_label(key): _format_readonly_value(key, value)
            for key, value in features.items()
        }
        st.json(full_dossier)

    st.markdown('<div class="score-action">', unsafe_allow_html=True)
    st.markdown('<div class="score-btn">', unsafe_allow_html=True)
    run_score = st.button(
        "Rodar Escoragem de Crédito",
        type="primary",
        use_container_width=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    if run_score:
        try:
            overrides = {
                name: _coerce_override_value(name, editable_values[name], features)
                for name in _CONFIG.editable_features
            }
            result = api_post_score(int(st.session_state.client_id), overrides)
            st.session_state.score_result = result
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

    # -----------------------------------------------------------------------
    # Resultados
    # -----------------------------------------------------------------------
    result = st.session_state.score_result
    if result:
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
        card_tone = "success" if approved else "danger"

        st.markdown(
            f'<div class="{box_class}"><h3>{"✓ Parecer favorável" if approved else "✗ Parecer desfavorável"}</h3></div>',
            unsafe_allow_html=True,
        )

        stat_cards = _build_score_stat_cards(
            result,
            int(st.session_state.client_id),
        )
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
                st.write("Nenhuma alteração aplicada; escoragem feita com o dossiê original.")

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

        target_raw = st.session_state.client_features.get(TARGET_COLUMN)
        if target_raw is not None:
            try:
                import math

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
            st.json(result)
else:
    st.info(
        f"Informe um **{ID_COLUMN}** válido e clique em **Consultar Cliente** "
        "para carregar o dossiê a partir da API."
    )
