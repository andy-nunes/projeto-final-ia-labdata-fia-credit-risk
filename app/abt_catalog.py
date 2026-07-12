"""Utilidades para montar o catalogo descritivo das colunas da ABT."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
import json
from pathlib import Path
import re
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from scripts.model_config import get_model_config

ROOT_DIR = Path(__file__).resolve().parents[1]
ABT_PATH = ROOT_DIR / "Dados" / "abt" / "abt_train.parquet"
RAW_DESCRIPTION_PATH = ROOT_DIR / "Dados" / "raw" / "HomeCredit_columns_description.csv"


@dataclass(frozen=True)
class ColumnDescription:
    """Descricao oficial de uma coluna disponibilizada no pacote Kaggle."""

    table: str
    description: str
    special: str


DERIVED_DESCRIPTIONS: dict[str, str] = {
    "AGE_YEARS": "Idade do cliente em anos, derivada de DAYS_BIRTH.",
    "FLAG_EMPLOYED": "Indicador de vinculo empregaticio derivado de DAYS_EMPLOYED.",
    "EXT_SOURCE_MEAN": "Media dos scores externos EXT_SOURCE_1, EXT_SOURCE_2 e EXT_SOURCE_3.",
    "EXT_SOURCE_CNT": "Quantidade de scores externos disponiveis para o cliente.",
    "CREDIT_INCOME_RATIO": "Razao entre valor solicitado do credito e renda total declarada.",
    "ANNUITY_INCOME_RATIO": "Razao entre parcela mensal e renda total declarada.",
    "LOG_AMT_CREDIT": "Transformacao log1p do valor solicitado do credito.",
    "DAYS_EMPLOYED_YEARS": "Tempo de emprego em anos, derivado do modulo de DAYS_EMPLOYED.",
    "INST_PAYMENT_RATIO": "Razao entre total pago e total previsto em parcelas anteriores.",
    "INST_RATE_ATRASO": "Proporcao de parcelas anteriores pagas com atraso.",
    "INST_RATE_CALOTE": "Proporcao de parcelas anteriores classificadas como calote.",
    "INST_RATE_UNDERPAY": "Proporcao de parcelas anteriores pagas abaixo do valor previsto.",
}

PREFIX_DESCRIPTIONS: tuple[tuple[str, str, str], ...] = (
    ("BUREAU_", "bureau.csv", "Agregado por cliente a partir do historico de creditos reportado ao bureau."),
    ("BB_", "bureau_balance.csv", "Agregado mensal do status de contratos do bureau, consolidado por cliente."),
    ("POS_", "POS_CASH_balance.csv", "Agregado por cliente do historico POS/CASH de financiamentos anteriores."),
    ("CC_", "credit_card_balance.csv", "Agregado por cliente do historico de cartao de credito."),
    ("PREV_", "previous_application.csv", "Agregado por cliente de propostas anteriores."),
    ("INST_", "installments_payments.csv", "Agregado por cliente do historico de pagamentos de parcelas."),
    ("HAS_", "features Gold", "Indicador binario de presenca de historico em uma fonte agregada."),
)

CATALOG_DISPLAY_LABELS: dict[str, str] = {
    "posicao": "Posição",
    "nome": "Nome",
    "tipo": "Tipo",
    "categoria": "Categoria",
    "fonte": "Fonte",
    "descricao": "Descrição",
    "especial": "Especial",
    "entra_no_modelo": "Modelo",
    "editavel_ui": "Editável",
    "categorica_modelo": "Categórica",
}

DESCRIPTION_TRANSLATIONS: dict[str, str] = {
    "Age of client's car": "Idade do carro do cliente.",
    "Approximately at what hour did the client apply for the loan": "Hora aproximada em que o cliente solicitou o empréstimo.",
    "Client's age in days at the time of application": "Idade do cliente em dias no momento da solicitação.",
    "Clients income type (businessman, working, maternity leave,\x85)": "Tipo de renda do cliente, como empresário, empregado ou licença maternidade.",
    "Credit amount of the loan": "Valor do crédito solicitado.",
    "Did client provide email (1=YES, 0=NO)": "Indica se o cliente informou e-mail (1=sim, 0=não).",
    "Did client provide home phone (1=YES, 0=NO)": "Indica se o cliente informou telefone residencial (1=sim, 0=não).",
    "Did client provide mobile phone (1=YES, 0=NO)": "Indica se o cliente informou telefone celular (1=sim, 0=não).",
    "Did client provide work phone (1=YES, 0=NO)": "Indica se o cliente informou telefone comercial/de trabalho (1=sim, 0=não).",
    "Family status of the client": "Estado civil ou situação familiar do cliente.",
    "Flag if client owns a house or flat": "Indica se o cliente possui casa ou apartamento.",
    "Flag if client's contact address does not match work address (1=different, 0=same, at city level)": "Indica se o endereço de contato difere do endereço de trabalho, no nível de cidade (1=diferente, 0=igual).",
    "Flag if client's contact address does not match work address (1=different, 0=same, at region level)": "Indica se o endereço de contato difere do endereço de trabalho, no nível de região (1=diferente, 0=igual).",
    "Flag if client's permanent address does not match contact address (1=different, 0=same, at city level)": "Indica se o endereço permanente difere do endereço de contato, no nível de cidade (1=diferente, 0=igual).",
    "Flag if client's permanent address does not match contact address (1=different, 0=same, at region level)": "Indica se o endereço permanente difere do endereço de contato, no nível de região (1=diferente, 0=igual).",
    "Flag if client's permanent address does not match work address (1=different, 0=same, at city level)": "Indica se o endereço permanente difere do endereço de trabalho, no nível de cidade (1=diferente, 0=igual).",
    "Flag if client's permanent address does not match work address (1=different, 0=same, at region level)": "Indica se o endereço permanente difere do endereço de trabalho, no nível de região (1=diferente, 0=igual).",
    "Flag if the client owns a car": "Indica se o cliente possui carro.",
    "For consumer loans it is the price of the goods for which the loan is given": "Para crédito ao consumidor, representa o preço do bem financiado.",
    "Gender of the client": "Gênero do cliente.",
    "How many days before application did client change phone": "Quantidade de dias antes da solicitação em que o cliente alterou o telefone.",
    "How many days before the application did client change his registration": "Quantidade de dias antes da solicitação em que o cliente alterou seu cadastro.",
    "How many days before the application did client change the identity document with which he applied for the loan": "Quantidade de dias antes da solicitação em que o cliente alterou o documento de identidade usado no pedido.",
    "How many days before the application the person started current employment": "Quantidade de dias antes da solicitação em que o cliente iniciou o emprego atual.",
    "How many family members does client have": "Quantidade de membros na família do cliente.",
    "How many observation of client's social surroundings defaulted on 30 DPD (days past due)": "Quantidade de observações do círculo social do cliente com inadimplência acima de 30 dias.",
    "How many observation of client's social surroundings defaulted on 60 (days past due) DPD": "Quantidade de observações do círculo social do cliente com inadimplência acima de 60 dias.",
    "How many observation of client's social surroundings with observable 30 DPD (days past due) default": "Quantidade de observações do círculo social do cliente avaliáveis para inadimplência acima de 30 dias.",
    "How many observation of client's social surroundings with observable 60 DPD (days past due) default": "Quantidade de observações do círculo social do cliente avaliáveis para inadimplência acima de 60 dias.",
    "ID of loan in our sample": "Identificador do empréstimo/cliente na amostra.",
    "Identification if loan is cash or revolving": "Identifica se o empréstimo é em dinheiro ou crédito rotativo.",
    "Income of the client": "Renda total declarada pelo cliente.",
    "Level of highest education the client achieved": "Maior nível de escolaridade alcançado pelo cliente.",
    "Loan annuity": "Valor da parcela/anuidade do empréstimo.",
    "Normalized information about building where the client lives, What is average (_AVG suffix), modus (_MODE suffix), median (_MEDI suffix) apartment size, common area, living area, age of building, number of elevators, number of entrances, state of the building, number of floor": "Informação normalizada sobre o imóvel onde o cliente mora, como tamanho do apartamento, área comum, área habitável, idade do prédio, elevadores, entradas, estado do imóvel e número de andares; os sufixos indicam média, moda ou mediana.",
    "Normalized population of region where client lives (higher number means the client lives in more populated region)": "População normalizada da região onde o cliente mora; valores maiores indicam regiões mais populosas.",
    "Normalized score from external data source": "Score normalizado de uma fonte externa de dados.",
    "Number of children the client has": "Quantidade de filhos do cliente.",
    "Number of enquiries to Credit Bureau about the client 3 month before application (excluding one month before application)": "Quantidade de consultas ao bureau de crédito sobre o cliente nos 3 meses antes da solicitação, excluindo o último mês.",
    "Number of enquiries to Credit Bureau about the client one day before application (excluding one hour before application)": "Quantidade de consultas ao bureau de crédito sobre o cliente no dia anterior à solicitação, excluindo a última hora.",
    "Number of enquiries to Credit Bureau about the client one day year (excluding last 3 months before application)": "Quantidade de consultas ao bureau de crédito sobre o cliente no último ano, excluindo os últimos 3 meses antes da solicitação.",
    "Number of enquiries to Credit Bureau about the client one hour before application": "Quantidade de consultas ao bureau de crédito sobre o cliente na hora anterior à solicitação.",
    "Number of enquiries to Credit Bureau about the client one month before application (excluding one week before application)": "Quantidade de consultas ao bureau de crédito sobre o cliente no mês anterior à solicitação, excluindo a última semana.",
    "Number of enquiries to Credit Bureau about the client one week before application (excluding one day before application)": "Quantidade de consultas ao bureau de crédito sobre o cliente na semana anterior à solicitação, excluindo o último dia.",
    "On which day of the week did the client apply for the loan": "Dia da semana em que o cliente solicitou o empréstimo.",
    "Our rating of the region where client lives (1,2,3)": "Classificação interna da região onde o cliente mora (1, 2 ou 3).",
    "Our rating of the region where client lives with taking city into account (1,2,3)": "Classificação interna da região onde o cliente mora considerando também a cidade (1, 2 ou 3).",
    "Target variable (1 - client with payment difficulties: he/she had late payment more than X days on at least one of the first Y installments of the loan in our sample, 0 - all other cases)": "Variável alvo histórica: 1 indica cliente com dificuldade de pagamento, com atraso superior a X dias em ao menos uma das primeiras Y parcelas; 0 indica os demais casos.",
    "Type of organization where client works": "Tipo de organização ou setor onde o cliente trabalha.",
    "Was mobile phone reachable (1=YES, 0=NO)": "Indica se o telefone celular estava alcançável (1=sim, 0=não).",
    "What is the housing situation of the client (renting, living with parents, ...)": "Situação de moradia do cliente, como aluguel, casa própria ou morando com os pais.",
    "What kind of occupation does the client have": "Tipo de ocupação ou profissão do cliente.",
    "Who was accompanying client when he was applying for the loan": "Quem acompanhava o cliente no momento da solicitação do empréstimo.",
}


def load_abt_schema(path: Path = ABT_PATH) -> list[dict[str, str]]:
    """Le o schema da ABT sem carregar o parquet completo em memoria."""
    schema = pq.read_schema(path)
    return [
        {"name": field.name, "type": str(field.type)}
        for field in schema
    ]


def load_kaggle_descriptions(
    path: Path = RAW_DESCRIPTION_PATH,
) -> dict[str, ColumnDescription]:
    """Carrega descricoes oficiais do arquivo HomeCredit_columns_description."""
    if not path.exists():
        return {}

    frame = pd.read_csv(path, encoding="latin1")
    descriptions: dict[str, ColumnDescription] = {}

    for row in frame.itertuples(index=False):
        column_name = str(getattr(row, "Row")).strip()
        table = str(getattr(row, "Table")).strip()
        description = str(getattr(row, "Description")).strip()
        special = getattr(row, "Special")
        special_text = "" if pd.isna(special) else str(special).strip()

        current = descriptions.get(column_name)
        if current is None or "application_" in table:
            descriptions[column_name] = ColumnDescription(
                table=table,
                description=description,
                special=special_text,
            )

    return descriptions


def infer_source(column_name: str, official: ColumnDescription | None) -> str:
    """Infere a fonte operacional da coluna no catalogo."""
    if official is not None:
        return official.table
    for prefix, source, _ in PREFIX_DESCRIPTIONS:
        if column_name.startswith(prefix):
            return source
    return "feature engineering Gold"


def infer_category(column_name: str, official: ColumnDescription | None) -> str:
    """Classifica a coluna em um grupo operacional para filtragem."""
    if column_name == "SK_ID_CURR":
        return "Identificador"
    if column_name == "TARGET":
        return "Alvo"
    if column_name in DERIVED_DESCRIPTIONS:
        return "Derivada"
    if column_name.startswith(("FLAG_", "HAS_")):
        return "Indicador"
    if official is not None:
        return "Raw Kaggle"
    if any(column_name.startswith(prefix) for prefix, _, _ in PREFIX_DESCRIPTIONS):
        return "Agregado"
    return "Derivada"


def infer_description(column_name: str, official: ColumnDescription | None) -> str:
    """Retorna descricao oficial ou descricao inferida para features criadas."""
    if column_name in DERIVED_DESCRIPTIONS:
        return DERIVED_DESCRIPTIONS[column_name]

    if column_name.startswith("FLAG_EXT_SOURCE_") and column_name.endswith("_MISSING"):
        source_name = column_name.removeprefix("FLAG_").removesuffix("_MISSING")
        return f"Indicador de ausencia do score externo {source_name}."

    if official is not None:
        return official.description

    for prefix, _, description in PREFIX_DESCRIPTIONS:
        if column_name.startswith(prefix):
            return description

    return "Feature criada na camada Gold a partir das tabelas limpas do projeto."


def translate_description(description: str) -> str:
    """Traduz descricoes oficiais recorrentes para portugues."""
    document_match = re.fullmatch(r"Did client provide document (\d+)", description)
    if document_match:
        return (
            "Indica se o cliente apresentou o documento "
            f"{document_match.group(1)}."
        )
    return DESCRIPTION_TRANSLATIONS.get(description, description)


def build_catalog_frame(
    schema_rows: list[dict[str, str]] | None = None,
    descriptions: dict[str, ColumnDescription] | None = None,
) -> pd.DataFrame:
    """Monta dataframe pesquisavel com metadados de todas as colunas da ABT."""
    config = get_model_config()
    schema = schema_rows if schema_rows is not None else load_abt_schema()
    official_descriptions = (
        descriptions if descriptions is not None else load_kaggle_descriptions()
    )
    drop_cols = set(config.drop_cols)
    editable = set(config.editable_features)
    categorical = set(config.categorical_features)

    records: list[dict[str, Any]] = []
    for position, field in enumerate(schema, start=1):
        column_name = field["name"]
        official = official_descriptions.get(column_name)
        records.append(
            {
                "posicao": position,
                "nome": column_name,
                "tipo": field["type"],
                "categoria": infer_category(column_name, official),
                "fonte": infer_source(column_name, official),
                "descricao": translate_description(
                    infer_description(column_name, official)
                ),
                "especial": official.special if official else "",
                "entra_no_modelo": "Nao" if column_name in drop_cols else "Sim",
                "editavel_ui": "Sim" if column_name in editable else "Nao",
                "categorica_modelo": "Sim" if column_name in categorical else "Nao",
            }
        )

    return pd.DataFrame.from_records(records)


def filter_catalog(
    frame: pd.DataFrame,
    query: str = "",
    categories: list[str] | None = None,
    sources: list[str] | None = None,
) -> pd.DataFrame:
    """Filtra catalogo por texto livre, categoria e fonte."""
    filtered = frame.copy()

    if categories:
        filtered = filtered[filtered["categoria"].isin(categories)]

    if sources:
        filtered = filtered[filtered["fonte"].isin(sources)]

    normalized_query = query.strip().lower()
    if normalized_query:
        searchable = filtered[
            ["nome", "tipo", "categoria", "fonte", "descricao", "especial"]
        ].astype(str)
        mask = searchable.apply(
            lambda row: normalized_query in " ".join(row).lower(),
            axis=1,
        )
        filtered = filtered[mask]

    return filtered.reset_index(drop=True)


def render_catalog_table_html(frame: pd.DataFrame) -> str:
    """Renderiza catalogo em HTML simples para evitar crash do dataframe nativo."""
    if frame.empty:
        return (
            '<div class="catalog-empty">'
            "Nenhum campo encontrado para os filtros selecionados."
            "</div>"
        )

    display_columns = [
        column for column in CATALOG_DISPLAY_LABELS
        if column in frame.columns
    ]
    header_cells = "".join(
        f"<th>{escape(CATALOG_DISPLAY_LABELS[column])}</th>"
        for column in display_columns
    )

    body_rows: list[str] = []
    for row in frame[display_columns].itertuples(index=False, name=None):
        cells = "".join(
            f"<td>{escape('' if pd.isna(value) else str(value))}</td>"
            for value in row
        )
        body_rows.append(f"<tr>{cells}</tr>")

    return (
        '<div class="catalog-table-wrap">'
        '<table class="catalog-table">'
        f"<thead><tr>{header_cells}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table>"
        "</div>"
    )


def render_catalog_explorer_html(frame: pd.DataFrame) -> str:
    """Renderiza explorador client-side para evitar rerender do Streamlit."""
    display_columns = [
        column for column in CATALOG_DISPLAY_LABELS
        if column in frame.columns
    ]
    labels = {column: CATALOG_DISPLAY_LABELS[column] for column in display_columns}
    records = (
        frame[display_columns]
        .fillna("")
        .astype(str)
        .to_dict(orient="records")
    )
    categories = sorted(frame["categoria"].dropna().astype(str).unique())
    sources = sorted(frame["fonte"].dropna().astype(str).unique())
    payload = json.dumps(
        {
            "columns": display_columns,
            "labels": labels,
            "records": records,
            "categories": categories,
            "sources": sources,
        },
        ensure_ascii=False,
    ).replace("</", "<\\/")

    return f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    :root {{
      color-scheme: dark;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    html, body {{
      background: #0e1117;
      color: #fafafa;
      margin: 0;
      padding: 0;
    }}
    .catalog-shell {{
      display: grid;
      gap: 0.9rem;
    }}
    .catalog-search-form,
    .filter-group {{
      border: 1px solid #273142;
      border-radius: 8px;
      padding: 0.75rem;
    }}
    .filter-label {{
      color: #cbd5e1;
      display: block;
      font-size: 0.82rem;
      font-weight: 700;
      margin-bottom: 0.55rem;
    }}
    .catalog-search-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
    }}
    #catalog-search {{
      background: #0f172a;
      border: 1px solid #334155;
      border-radius: 8px;
      color: #f8fafc;
      flex: 1 1 280px;
      min-height: 2.45rem;
      padding: 0 0.75rem;
    }}
    #catalog-search:focus {{
      border-color: #60a5fa;
      outline: none;
    }}
    .catalog-button,
    .filter-chip {{
      border: 1px solid #334155;
      border-radius: 999px;
      color: #cbd5e1;
      cursor: pointer;
      display: inline-block;
      font-size: 0.78rem;
      font-weight: 700;
      line-height: 1;
      padding: 0.5rem 0.68rem;
      text-decoration: none;
    }}
    .catalog-button {{
      background: #2563eb;
      border-color: #3b82f6;
      border-radius: 8px;
      color: #fff;
      font-size: 0.84rem;
      min-height: 2.45rem;
      padding: 0.62rem 0.85rem;
    }}
    .filter-chip:hover,
    .catalog-button:hover {{
      background: rgba(59, 130, 246, 0.18);
      border-color: #60a5fa;
      color: #f8fafc;
    }}
    .filter-chip-active {{
      background: #2563eb;
      border-color: #3b82f6;
      color: #ffffff;
    }}
    .filter-chip-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.42rem;
    }}
    .catalog-summary {{
      color: #cbd5e1;
      font-size: 0.84rem;
    }}
    .catalog-table-wrap {{
      border: 1px solid #273142;
      border-radius: 8px;
      max-height: 56vh;
      overflow: auto;
      width: 100%;
    }}
    .catalog-table {{
      border-collapse: collapse;
      color: #e5e7eb;
      font-size: 0.82rem;
      min-width: 1180px;
      width: 100%;
    }}
    .catalog-table thead th {{
      background: #111827;
      border-bottom: 1px solid #334155;
      color: #f8fafc;
      font-weight: 700;
      position: sticky;
      text-align: left;
      top: 0;
      z-index: 1;
    }}
    .catalog-table th,
    .catalog-table td {{
      border-bottom: 1px solid #1f2937;
      line-height: 1.35;
      padding: 0.64rem 0.72rem;
      vertical-align: top;
    }}
    .catalog-table tbody tr:nth-child(even) {{
      background: rgba(30, 41, 59, 0.35);
    }}
    .catalog-table tbody tr:hover {{
      background: rgba(59, 130, 246, 0.14);
    }}
    .catalog-table td:nth-child(1),
    .catalog-table td:nth-child(3),
    .catalog-table td:nth-child(4),
    .catalog-table td:nth-child(8),
    .catalog-table td:nth-child(9),
    .catalog-table td:nth-child(10) {{
      white-space: nowrap;
    }}
    .catalog-empty {{
      border: 1px solid #273142;
      border-radius: 8px;
      color: #cbd5e1;
      padding: 1rem;
    }}
  </style>
</head>
<body>
  <div class="catalog-shell">
    <form class="catalog-search-form" id="search-form">
      <label class="filter-label" for="catalog-search">Pesquisar</label>
      <div class="catalog-search-row">
        <input id="catalog-search" type="search"
          placeholder="Ex.: AMT_CREDIT, bureau, parcela, score externo">
        <button class="catalog-button" type="submit">Pesquisar</button>
        <button class="catalog-button" id="clear-button" type="button">Limpar</button>
        <button class="catalog-button" id="download-button" type="button">
          Baixar catálogo em CSV
        </button>
      </div>
    </form>
    <div class="filter-group">
      <div class="filter-label">Categoria</div>
      <div class="filter-chip-row" id="category-filters"></div>
    </div>
    <div class="filter-group">
      <div class="filter-label">Fonte</div>
      <div class="filter-chip-row" id="source-filters"></div>
    </div>
    <div class="catalog-summary" id="catalog-summary"></div>
    <div id="catalog-table"></div>
  </div>
  <script>
    const catalogData = {payload};
    let selectedCategory = "";
    let selectedSource = "";
    let query = "";

    function escapeHtml(value) {{
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }}

    function matchesQuery(row) {{
      if (!query) {{
        return true;
      }}
      const text = catalogData.columns.map((column) => row[column]).join(" ").toLowerCase();
      return text.includes(query);
    }}

    function filteredRows() {{
      return catalogData.records.filter((row) => {{
        const categoryOk = !selectedCategory || row.categoria === selectedCategory;
        const sourceOk = !selectedSource || row.fonte === selectedSource;
        return categoryOk && sourceOk && matchesQuery(row);
      }});
    }}

    function renderChips(containerId, options, selectedValue, onClick) {{
      const container = document.getElementById(containerId);
      const allActive = selectedValue === "";
      const chips = [
        `<button type="button" class="filter-chip ${{allActive ? "filter-chip-active" : ""}}" data-value="">Todas</button>`
      ];
      for (const option of options) {{
        const active = selectedValue === option;
        const label = active ? `${{option}} ×` : option;
        chips.push(
          `<button type="button" class="filter-chip ${{active ? "filter-chip-active" : ""}}" data-value="${{escapeHtml(option)}}">${{escapeHtml(label)}}</button>`
        );
      }}
      container.innerHTML = chips.join("");
      container.querySelectorAll("button").forEach((button) => {{
        button.addEventListener("click", () => onClick(button.dataset.value || ""));
      }});
    }}

    function renderTable(rows) {{
      const target = document.getElementById("catalog-table");
      if (rows.length === 0) {{
        target.innerHTML = '<div class="catalog-empty">Nenhum campo encontrado para os filtros selecionados.</div>';
        return;
      }}
      const header = catalogData.columns
        .map((column) => `<th>${{escapeHtml(catalogData.labels[column])}}</th>`)
        .join("");
      const body = rows.map((row) => {{
        const cells = catalogData.columns
          .map((column) => `<td>${{escapeHtml(row[column])}}</td>`)
          .join("");
        return `<tr>${{cells}}</tr>`;
      }}).join("");
      target.innerHTML = `
        <div class="catalog-table-wrap">
          <table class="catalog-table">
            <thead><tr>${{header}}</tr></thead>
            <tbody>${{body}}</tbody>
          </table>
        </div>
      `;
    }}

    function applyFilters() {{
      query = document.getElementById("catalog-search").value.trim().toLowerCase();
      const rows = filteredRows();
      renderChips("category-filters", catalogData.categories, selectedCategory, (value) => {{
        selectedCategory = value === selectedCategory ? "" : value;
        applyFilters();
      }});
      renderChips("source-filters", catalogData.sources, selectedSource, (value) => {{
        selectedSource = value === selectedSource ? "" : value;
        applyFilters();
      }});
      document.getElementById("catalog-summary").textContent =
        `${{rows.length}} de ${{catalogData.records.length}} campos exibidos`;
      renderTable(rows);
    }}

    function downloadCsv() {{
      const rows = filteredRows();
      const header = catalogData.columns.map((column) => catalogData.labels[column]);
      const csvRows = [header, ...rows.map((row) => catalogData.columns.map((column) => row[column]))];
      const csv = csvRows.map((row) => row.map((value) => {{
        const text = String(value ?? "");
        return `"${{text.replaceAll('"', '""')}}"`;
      }}).join(",")).join("\\n");
      const blob = new Blob([csv], {{ type: "text/csv;charset=utf-8" }});
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "catalogo_abt.csv";
      link.click();
      URL.revokeObjectURL(url);
    }}

    document.getElementById("search-form").addEventListener("submit", (event) => {{
      event.preventDefault();
      applyFilters();
    }});
    document.getElementById("catalog-search").addEventListener("input", applyFilters);
    document.getElementById("clear-button").addEventListener("click", () => {{
      selectedCategory = "";
      selectedSource = "";
      document.getElementById("catalog-search").value = "";
      applyFilters();
    }});
    document.getElementById("download-button").addEventListener("click", downloadCsv);
    applyFilters();
  </script>
</body>
</html>
"""
