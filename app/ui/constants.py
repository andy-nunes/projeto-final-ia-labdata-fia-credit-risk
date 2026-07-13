"""Constantes compartilhadas do dashboard Streamlit."""

from __future__ import annotations

from pathlib import Path

from app.abt_catalog import COLUMN_BUSINESS_NAMES
from scripts.model_config import get_model_config

ROOT_DIR = Path(__file__).resolve().parents[2]

_CONFIG = get_model_config()
API_BASE_URL = _CONFIG.api_base_url
ID_COLUMN = _CONFIG.id_column
TARGET_COLUMN = _CONFIG.target_column

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

PROFILE_RISK_ATTRIBUTES: dict[str, str] = {
    "ORGANIZATION_TYPE": "Setor / Organização",
    "OCCUPATION_TYPE": "Profissão",
    "NAME_INCOME_TYPE": "Tipo de Renda",
    "NAME_EDUCATION_TYPE": "Escolaridade",
}

