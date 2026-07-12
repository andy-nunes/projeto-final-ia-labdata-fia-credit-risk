"""Pagina Streamlit com catalogo pesquisavel das colunas da ABT."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from app.abt_catalog import build_catalog_frame, render_catalog_explorer_html

st.set_page_config(
    page_title="Catálogo ABT | Home Credit",
    layout="wide",
    initial_sidebar_state="collapsed",
)

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
        max-width: 1320px;
    }
    h1, h2, h3, h4 {
        letter-spacing: 0;
    }
    .catalog-note {
        border-top: 1px solid #273142;
        color: #94a3b8;
        font-size: 0.84rem;
        line-height: 1.45;
        margin-top: 1rem;
        padding-top: 0.85rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Catálogo de Campos da ABT")
st.caption(
    "Dicionário pesquisável da tabela analítica final usada no modelo LightGBM."
)

st.markdown("[Voltar para a homepage](/)")

catalog = build_catalog_frame()

metric_cols = st.columns(4)
metric_cols[0].metric("Colunas na ABT", len(catalog))
metric_cols[1].metric("Entram no modelo", int((catalog["entra_no_modelo"] == "Sim").sum()))
metric_cols[2].metric("Editáveis na UI", int((catalog["editavel_ui"] == "Sim").sum()))
metric_cols[3].metric(
    "Com descrição Kaggle",
    int((catalog["categoria"] == "Raw Kaggle").sum()),
)

components.html(
    render_catalog_explorer_html(catalog),
    height=850,
    scrolling=True,
)

st.markdown(
    """
    <div class="catalog-note">
        As descrições das colunas raw vêm do arquivo
        <code>HomeCredit_columns_description.csv</code>, distribuído junto aos
        dados da competição Home Credit Default Risk no Kaggle. Features criadas
        nas camadas Silver/Gold recebem descrição inferida pela regra de
        transformação ou pelo prefixo da fonte agregada.
    </div>
    """,
    unsafe_allow_html=True,
)
