"""Estilos e configuração visual da página Streamlit."""

from __future__ import annotations

import streamlit as st

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
    div[data-testid="stTextInput"],
    div[data-testid="stNumberInput"],
    div[data-testid="stSelectbox"] {
        margin-bottom: 0.65rem;
    }
    div[data-testid="stButton"] button {
        border-radius: 8px !important;
        min-height: 2.75rem;
        font-weight: 700 !important;
    }
    div[data-testid="stButton"] button[kind="primary"] {
        background: linear-gradient(135deg, #3b82f6, #8b5cf6) !important;
        color: #ffffff !important;
        border: 1px solid #6366f1 !important;
        box-shadow: 0 4px 14px rgba(79, 70, 229, 0.22) !important;
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
    .credia-action {
        margin-top: 0.4rem;
        margin-bottom: 0.35rem;
    }
    .credia-btn button {
        background: linear-gradient(135deg, #3b82f6, #8b5cf6) !important;
        color: #ffffff !important;
        border: 1px solid #6366f1 !important;
        font-weight: 700 !important;
        box-shadow: 0 4px 14px rgba(79, 70, 229, 0.22) !important;
    }
    .credia-btn button:hover {
        filter: brightness(1.03);
        border-color: #4f46e5 !important;
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
    .triage-box {
        border-radius: 8px;
        padding: 1rem 1.15rem;
        margin: 0.85rem 0 1rem 0;
        border: 1px solid #cbd5e1;
        background: #f8fafc;
    }
    .triage-box-auto {
        background: rgba(22, 163, 74, 0.08);
        border-color: #86efac;
    }
    .triage-box-mesa {
        background: rgba(217, 119, 6, 0.10);
        border-color: #fcd34d;
    }
    .triage-box-recusa {
        background: rgba(220, 38, 38, 0.08);
        border-color: #fca5a5;
    }
    .triage-kicker {
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #64748b;
        margin: 0 0 0.35rem 0;
    }
    .triage-title {
        font-size: 1.05rem;
        font-weight: 700;
        margin: 0 0 0.35rem 0;
        color: #0f172a;
        line-height: 1.3;
    }
    .triage-box-auto .triage-title { color: #15803d; }
    .triage-box-mesa .triage-title { color: #b45309; }
    .triage-box-recusa .triage-title { color: #b91c1c; }
    .triage-body {
        margin: 0;
        color: #334155;
        font-size: 0.92rem;
        line-height: 1.45;
    }
    .triage-path {
        margin: 0.55rem 0 0 0;
        font-size: 0.78rem;
        color: #64748b;
        word-break: break-all;
    }
    .ai-card {
        border-radius: 8px;
        padding: 1rem 1.15rem;
        margin: 0.85rem 0 0.9rem 0;
        border: 1px solid #bfdbfe;
        background: linear-gradient(135deg, rgba(59, 130, 246, 0.10), rgba(139, 92, 246, 0.10));
    }
    .ai-kicker {
        font-size: 0.95rem;
        font-weight: 800;
        letter-spacing: 0.02em;
        text-transform: none;
        color: #1d4ed8;
        margin: 0 0 0.3rem 0;
    }
    .ai-title {
        font-size: 1.12rem;
        font-weight: 700;
        margin: 0 0 0.48rem 0;
        color: #312e81;
    }
    .ai-line {
        margin: 0.28rem 0;
        color: #0f172a;
        font-size: 0.91rem;
        line-height: 1.45;
    }
    .ai-guardrail {
        margin: 0.52rem 0 0.35rem 0;
        color: #0f766e;
        font-size: 0.82rem;
        font-weight: 600;
    }
    .ai-alerts {
        margin: 0.2rem 0 0 1.1rem;
        color: #334155;
        font-size: 0.88rem;
        line-height: 1.35;
    }
    .ai-subtitle {
        margin: 0.55rem 0 0.25rem 0;
        color: #312e81;
        font-size: 0.88rem;
        font-weight: 700;
    }
    .ai-brief {
        margin-top: 0.5rem;
        border: 1px solid #c7d2fe;
        border-radius: 8px;
        background: rgba(255, 255, 255, 0.65);
        padding: 0.6rem 0.75rem;
    }
    .ai-md-heading {
        margin: 0.2rem 0 0.4rem 0;
        color: #1e1b4b;
        font-size: 1.05rem;
        font-weight: 700;
    }
    .ai-md-paragraph {
        margin: 0.22rem 0;
        color: #0f172a;
        font-size: 0.9rem;
        line-height: 1.45;
    }
    .ai-md-list {
        margin: 0.25rem 0 0.4rem 1rem;
        color: #1e293b;
        font-size: 0.88rem;
        line-height: 1.4;
    }
    .feature-label {
        margin: 0 0 0.4rem 0;
        min-height: 1.55rem;
        line-height: 1.25;
    }
    .readonly-value-box {
        padding: 0.45rem 0.75rem;
        border: 1px solid #e2e8f0;
        border-radius: 0.5rem;
        background: #f8fafc;
        color: #334155;
        min-height: 2.4rem;
        display: flex;
        align-items: center;
        margin-bottom: 0.68rem;
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
    .stat-grid-5 {
        grid-template-columns: repeat(5, minmax(0, 1fr));
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
        overflow-wrap: normal;
        word-break: keep-all;
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
    .dossier-actions {
        margin-top: 0.75rem;
    }
    @media (max-width: 760px) {
        .stat-grid {
            grid-template-columns: 1fr;
        }
        .stat-grid-5 {
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
    @media (min-width: 761px) and (max-width: 1100px) {
        .stat-grid-5 {
            grid-template-columns: repeat(3, minmax(0, 1fr));
        }
    }
    button[data-baseweb="tab"] {
        font-weight: 650;
        letter-spacing: 0.01em;
        background: transparent !important;
        border: none !important;
        border-radius: 0 !important;
        padding: 0.45rem 1.15rem !important;
        margin: 0 !important;
        min-height: auto !important;
        color: #334155 !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #1d4ed8 !important;
        background: #eff6ff !important;
        border-radius: 6px !important;
        font-weight: 700;
    }
    div[data-testid="stTabs"] [role="tablist"] {
        gap: 0.9rem;
        border-bottom: 1px solid #e2e8f0;
        margin-bottom: 0.45rem;
        padding-bottom: 0.15rem;
    }
    div[data-testid="stForm"] {
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 0.85rem 1rem 1rem 1rem;
        background: #ffffff;
    }
    div[data-testid="stForm"] [data-testid="stVerticalBlock"] {
        gap: 0.55rem;
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

