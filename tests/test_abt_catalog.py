"""Testes do catalogo de colunas da ABT exibido no Streamlit."""

import pandas as pd

from app.abt_catalog import (
    ColumnDescription,
    build_catalog_frame,
    filter_catalog,
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

    assert credit["descricao"] == "Valor do crédito solicitado."
    assert credit["fonte"] == "application_{train|test}.csv"
    assert credit["editavel_ui"] == "Sim"
    assert ratio["categoria"] == "Derivada"
    assert "renda total" in ratio["descricao"]
    assert bureau["categoria"] == "Agregado"
    assert bureau["fonte"] == "bureau.csv"


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
        translate_description("Did client provide document 7")
        == "Indica se o cliente apresentou o documento 7."
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
    """Verifica explorador client-side com busca, filtros e download."""
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
