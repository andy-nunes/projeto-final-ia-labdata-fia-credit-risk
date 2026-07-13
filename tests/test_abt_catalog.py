"""Testes do catalogo de colunas da ABT exibido no Streamlit."""

from pathlib import Path

import pandas as pd
import pytest

CATALOG_MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "app" / "abt_catalog.py"
)
if not CATALOG_MODULE_PATH.exists():
    pytest.skip(
        "O container atual nao monta app/abt_catalog.py.",
        allow_module_level=True,
    )

from app.abt_catalog import (
    BUSINESS_DESCRIPTIONS,
    ColumnDescription,
    GENERIC_FORBIDDEN,
    build_catalog_frame,
    filter_catalog,
    format_variable_entry,
    infer_description,
    render_catalog_explorer_html,
    render_catalog_table_html,
    translate_description,
)


def test_build_catalog_frame_combines_schema_official_and_derived_descriptions(
) -> None:
    """Verifica catalogo com descricao Kaggle, derivada e flags de uso."""
    schema = [
        {"name": "SK_ID_CURR", "type": "int64"},
        {"name": "AMT_CREDIT", "type": "double"},
        {"name": "CREDIT_INCOME_RATIO", "type": "double"},
        {"name": "BUREAU_CNT_CREDITS", "type": "double"},
    ]
    descriptions = {
        "AMT_CREDIT": ColumnDescription(
            table="application_{train|test}.csv",
            description="Credit amount of the loan",
            special="",
        )
    }

    catalog = build_catalog_frame(schema, descriptions)

    credit = catalog[catalog["nome"] == "AMT_CREDIT"].iloc[0]
    ratio = catalog[catalog["nome"] == "CREDIT_INCOME_RATIO"].iloc[0]
    bureau = catalog[catalog["nome"] == "BUREAU_CNT_CREDITS"].iloc[0]

    assert "crédito solicitado" in credit["descricao"].lower()
    assert credit["fonte"] == "application_{train|test}.csv"
    assert credit["editavel_ui"] == "Sim"
    assert ratio["categoria"] == "Derivada"
    assert "renda" in ratio["descricao"].lower()
    assert bureau["categoria"] == "Agregado"
    assert bureau["fonte"] == "bureau.csv"
    assert GENERIC_FORBIDDEN not in catalog["descricao"].tolist()


def test_business_descriptions_cover_expected_abt_columns() -> None:
    """Garante dicionario interno com as 198 variaveis da ABT full."""
    assert len(BUSINESS_DESCRIPTIONS) == 198
    assert "SK_ID_CURR" in BUSINESS_DESCRIPTIONS
    assert "TARGET" in BUSINESS_DESCRIPTIONS
    assert "BUREAU_AMT_DEBT_SUM" in BUSINESS_DESCRIPTIONS
    assert GENERIC_FORBIDDEN not in BUSINESS_DESCRIPTIONS.values()


def test_infer_description_never_returns_generic_gold_fallback() -> None:
    """Verifica ausencia do texto generico proibido."""
    assert (
        infer_description("UNKNOWN_GOLD_FEATURE_XYZ", None)
        != GENERIC_FORBIDDEN
    )
    assert GENERIC_FORBIDDEN not in infer_description(
        "BUREAU_AMT_DEBT_SUM",
        None,
    )


def test_filter_catalog_searches_text_and_filters_category_source() -> None:
    """Verifica busca textual combinada com filtros estruturados."""
    frame = pd.DataFrame(
        [
            {
                "nome": "AMT_CREDIT",
                "tipo": "double",
                "categoria": "Raw Kaggle",
                "fonte": "application_{train|test}.csv",
                "descricao": "Credit amount of the loan",
                "especial": "",
            },
            {
                "nome": "BUREAU_CNT_CREDITS",
                "tipo": "double",
                "categoria": "Agregado",
                "fonte": "bureau.csv",
                "descricao": "Agregado por cliente",
                "especial": "",
            },
        ]
    )

    filtered = filter_catalog(
        frame,
        query="bureau",
        categories=["Agregado"],
        sources=["bureau.csv"],
    )

    assert filtered["nome"].tolist() == ["BUREAU_CNT_CREDITS"]


def test_translate_description_handles_known_texts_and_document_flags() -> None:
    """Verifica traducao das descricoes oficiais usadas no catalogo."""
    assert translate_description("Gender of the client") == "Gênero do cliente."
    assert (
        "documento 7" in translate_description("Did client provide document 7")
    )


def test_render_catalog_table_html_escapes_values_and_preserves_table() -> None:
    """Verifica render HTML estavel sem depender do componente dataframe."""
    frame = pd.DataFrame(
        [
            {
                "posicao": 1,
                "nome": "AMT_<CREDIT>",
                "tipo": "double",
                "categoria": "Raw Kaggle",
                "fonte": "application_{train|test}.csv",
                "descricao": "Credit <amount>",
                "especial": "",
                "entra_no_modelo": "Sim",
                "editavel_ui": "Sim",
                "categorica_modelo": "Nao",
            }
        ]
    )

    html = render_catalog_table_html(frame)

    assert 'class="catalog-table"' in html
    assert "AMT_&lt;CREDIT&gt;" in html
    assert "Credit &lt;amount&gt;" in html
    assert "AMT_<CREDIT>" not in html


def test_render_catalog_explorer_html_embeds_client_side_filtering() -> None:
    """Verifica explorador HTML legado (rota FastAPI) com busca e filtros."""
    frame = pd.DataFrame(
        [
            {
                "posicao": 1,
                "nome": "AMT_CREDIT",
                "tipo": "double",
                "categoria": "Raw Kaggle",
                "fonte": "application_{train|test}.csv",
                "descricao": "Credit amount",
                "especial": "",
                "entra_no_modelo": "Sim",
                "editavel_ui": "Sim",
                "categorica_modelo": "Nao",
            }
        ]
    )

    html = render_catalog_explorer_html(frame)

    assert 'id="catalog-search"' in html
    assert '"categories": ["Raw Kaggle"]' in html
    assert "function applyFilters()" in html
    assert "downloadCsv" in html
    assert "AMT_CREDIT" in html


def test_format_variable_entry_uses_technical_name_and_italic_type() -> None:
    """Verifica formato textual limpo exigido pela mesa de crédito."""
    entry = format_variable_entry(
        column_name="AMT_CREDIT",
        data_type="double",
        description="Valor do crédito solicitado.",
    )

    assert entry.startswith("**AMT_CREDIT** *(double)*")
    assert "* Valor do crédito solicitado." in entry


def test_format_variable_entry_supports_highlight_role() -> None:
    """Verifica destaque de identificador/alvo com papel de negócio."""
    entry = format_variable_entry(
        column_name="SK_ID_CURR",
        data_type="int64",
        description="Código único de identificação do CPF/dossiê na base do Bureau.",
        role="Identificador",
    )

    assert "**SK_ID_CURR** *(Identificador - int64)*" in entry
    assert "Código único de identificação" in entry
