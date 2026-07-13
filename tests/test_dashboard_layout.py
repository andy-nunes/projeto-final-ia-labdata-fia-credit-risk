"""Testes dos helpers visuais do dashboard Streamlit."""

from pathlib import Path

import pytest


DASHBOARD_PATH = Path(__file__).resolve().parents[1] / "app" / "dashboard.py"
UI_DIR = Path(__file__).resolve().parents[1] / "app" / "ui"
PAGES_DIR = Path(__file__).resolve().parents[1] / "app" / "pages"
CATALOG_MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "app" / "abt_catalog.py"
)
if not DASHBOARD_PATH.exists():
    pytest.skip("O container atual nao monta app/dashboard.py.", allow_module_level=True)


def _dashboard_sources() -> str:
    """Concatena dashboard.py e app/ui/*.py para asserts estruturais."""
    parts = [DASHBOARD_PATH.read_text(encoding="utf-8")]
    if UI_DIR.is_dir():
        for path in sorted(UI_DIR.glob("*.py")):
            parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest

from app import dashboard


def test_render_stat_card_html_wraps_value_and_escapes_content() -> None:
    """Verifica que o card estatistico tem estrutura fixa e escapa HTML."""
    html = dashboard._render_stat_card_html(
        "Decisão",
        "<Aprovado & revisado>",
        tone="success",
    )

    assert 'class="stat-card stat-card-success"' in html
    assert 'class="stat-card-label">Decisão</div>' in html
    assert "&lt;Aprovado &amp; revisado&gt;" in html
    assert "<Aprovado & revisado>" not in html


def test_risk_band_tone_maps_risk_levels_to_semantic_colors() -> None:
    """Verifica o mapeamento visual das faixas de risco."""
    assert dashboard._risk_band_tone("Baixo risco") == "success"
    assert dashboard._risk_band_tone("Risco moderado") == "warning"
    assert dashboard._risk_band_tone("Alto risco") == "danger"
    assert dashboard._risk_band_tone("Sem classificação") == "neutral"


def test_probability_tone_follows_threshold_risk_levels() -> None:
    """Verifica a cor das probabilidades conforme threshold de negocio."""
    assert dashboard._probability_tone(0.02, 0.08) == "success"
    assert dashboard._probability_tone(0.05, 0.08) == "warning"
    assert dashboard._probability_tone(0.08, 0.08) == "danger"
    assert dashboard._probability_tone(None, 0.08) == "neutral"


def test_default_score_cards_use_portuguese_probability_labels() -> None:
    """Verifica que os cards de probabilidade seguem o mesmo padrao visual."""
    cards = dashboard._build_score_stat_cards(
        {
            "label": "Aprovado",
            "risk_band": "Baixo risco",
            "probability": 0.02,
            "prediction": 0,
            "threshold": 0.08,
            "sk_id_curr": 139767,
        }
    )
    html = "".join(cards)

    assert "Prob. inadimplência" in html
    assert "Prob. adimplência" in html
    assert "Probability" not in html
    assert 'class="stat-card-note">inadimplência</div>' not in html


def test_parse_money_override_accepts_numbers_within_feature_bounds() -> None:
    """Verifica que campos monetarios aceitam int, float e virgula decimal."""
    assert dashboard._parse_money_override("AMT_CREDIT", "1000") == 1000.0
    assert dashboard._parse_money_override("AMT_ANNUITY", "1615,50") == 1615.5
    assert dashboard._parse_money_override("AMT_CREDIT", 4050000.0) == 4050000.0


def test_parse_money_override_rejects_invalid_or_out_of_bounds_values() -> None:
    """Verifica que campos monetarios rejeitam negativos, texto e teto excedido."""
    for invalid_value in ("", "abc", "-1", "0", 4050000.01):
        with pytest.raises(ValueError):
            dashboard._parse_money_override("AMT_CREDIT", invalid_value)


def test_organization_type_is_editable_categorical_with_business_label() -> None:
    """Verifica que setor da organizacao aparece como simulacao categorica."""
    assert "ORGANIZATION_TYPE" in dashboard._CONFIG.editable_features
    assert "ORGANIZATION_TYPE" in dashboard.CATEGORICAL_OPTIONS
    assert "BUSINESS ENTITY TYPE 3" in dashboard.CATEGORICAL_OPTIONS["ORGANIZATION_TYPE"]
    assert (
        dashboard.FEATURE_TRANSLATIONS["ORGANIZATION_TYPE"]
        == "Tipo de Organização / Setor"
    )


@pytest.mark.parametrize(
    ("prediction", "target", "expected_tone", "expected_title"),
    [
        (0, 0, "success", "Acerto — Verdadeiro Negativo"),
        (1, 1, "success", "Acerto — Verdadeiro Positivo"),
        (0, 1, "error", "Erro grave — Falso Negativo"),
        (1, 0, "warning", "Falso Alarme — Falso Positivo"),
    ],
)
def test_audit_message_mentions_simulation_when_overrides_exist(
    prediction: int,
    target: int,
    expected_tone: str,
    expected_title: str,
) -> None:
    """Verifica que auditoria alerta quando a decisao usou campos alterados."""
    tone, message = dashboard._build_audit_message(
        prediction,
        target,
        has_overrides=True,
    )

    assert tone == expected_tone
    assert expected_title in message
    assert "decisão simulada após alterações nos campos" in message
    assert "histórico real do cliente no holdout" in message


def test_audit_message_without_overrides_keeps_direct_historical_interpretation() -> None:
    """Verifica que auditoria sem simulacao nao adiciona ressalva de alteracao."""
    tone, message = dashboard._build_audit_message(
        prediction=0,
        target=0,
        has_overrides=False,
    )

    assert tone == "success"
    assert "Acerto — Verdadeiro Negativo" in message
    assert "decisão simulada após alterações nos campos" not in message


def test_render_factor_row_html_preserves_alignment_and_limits_progress() -> None:
    """Verifica que fatores determinantes usam grade fixa e progresso limitado."""
    html = dashboard._render_factor_row_html(
        "Taxa <risco>",
        "INST_RATE_ATRASO",
        142.5,
        tone="danger",
    )

    assert 'class="factor-row factor-row-danger"' in html
    assert 'class="factor-label-business">Taxa &lt;risco&gt;</span>' in html
    assert 'class="factor-label-tech">(INST_RATE_ATRASO)</span>' in html
    assert 'class="factor-value">142.5%</div>' in html
    assert 'style="width: 100.0%;"' in html


def test_clear_button_does_not_mutate_widget_state_after_render() -> None:
    """Verifica que limpar a tela nao dispara exception de estado do Streamlit."""
    app = AppTest.from_file(str(DASHBOARD_PATH), default_timeout=30)
    app.run()

    app.button(key="btn_limpar").click()
    app.run()

    assert len(app.exception) == 0
    assert app.session_state["sk_id_input"] == "139767"


def test_score_flow_preserves_client_state_after_second_rerun() -> None:
    """Verifica que escoragem nao reseta o dossie carregado em reruns seguintes."""
    sample = {
        "features": {
            "SK_ID_CURR": 139767,
            "TARGET": 0,
            "AMT_CREDIT": 2013840.0,
            "AMT_ANNUITY": 53253.0,
            "NAME_EDUCATION_TYPE": "HIGHER EDUCATION",
            "NAME_INCOME_TYPE": "COMMERCIAL ASSOCIATE",
            "OCCUPATION_TYPE": "MANAGERS",
            "ORGANIZATION_TYPE": "BUSINESS ENTITY TYPE 3",
            "EXT_SOURCE_1": 500.0,
            "EXT_SOURCE_2": 300.0,
            "EXT_SOURCE_3": 200.0,
            "DAYS_BIRTH": -12000,
            "DAYS_EMPLOYED": -2000,
            "DAYS_ID_PUBLISH": -5000,
            "EXT_SOURCE_MEAN": 0.33,
            "EXT_SOURCE_CNT": 3,
            "FLAG_EMPLOYED": 1,
            "DAYS_EMPLOYED_YEARS": 5.5,
            "BUREAU_AMT_DEBT_SUM": 10000,
            "BUREAU_DAYS_CREDIT_MIN": -1000,
            "PREV_DAYS_DECISION_MIN": -500,
            "INST_DIAS_ATRASO_MEAN": 0,
            "INST_AMT_PAYMENT_SUM": 5000,
        }
    }
    score = {
        "label": "Aprovado",
        "risk_band": "Baixo risco",
        "probability": 0.02,
        "prediction": 0,
        "threshold": 0.08,
        "sk_id_curr": 139767,
        "applied_overrides": {},
        "top_positive_factors": [["EXT_SOURCE_MEAN", 12.5]],
        "top_risk_factors": [],
    }

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(dashboard, "api_get_client", lambda _client_id: sample)
        monkeypatch.setattr(dashboard, "api_post_score", lambda _client_id, _overrides: score)

        app = AppTest.from_file(str(DASHBOARD_PATH), default_timeout=30)
        app.run()
        app.text_input(key="sk_id_input").set_value("139767")
        next(b for b in app.button if b.label == "Consultar Cliente").click().run()
        assert len(app.exception) == 0

        page_text = "\n".join(str(element.value) for element in app.markdown)
        assert "Cliente" in page_text

        next(
            b for b in app.button if b.label == "Rodar Escoragem de Crédito"
        ).click().run()
        assert len(app.exception) == 0

        page_text = "\n".join(str(element.value) for element in app.markdown)
        assert "Parecer" in page_text
        assert "Informe um SK_ID_CURR válido" not in "\n".join(
            str(element.value) for element in app.info
        )
        assert app.session_state["client_features"] is not None
        assert app.session_state["score_result"] is not None

        app.run()
        assert len(app.exception) == 0
        assert app.session_state["client_features"] is not None
        assert "Informe um SK_ID_CURR válido" not in "\n".join(
            str(element.value) for element in app.info
        )


def test_invalid_consult_does_not_clear_loaded_dossier() -> None:
    """Consulta inválida não pode apagar o dossiê já carregado."""
    sample = {
        "features": {
            "SK_ID_CURR": 139767,
            "TARGET": 0,
            "AMT_CREDIT": 1000.0,
            "AMT_ANNUITY": 100.0,
            "NAME_EDUCATION_TYPE": "HIGHER EDUCATION",
            "NAME_INCOME_TYPE": "WORKING",
            "OCCUPATION_TYPE": "MANAGERS",
            "ORGANIZATION_TYPE": "OTHER",
        }
    }

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(dashboard, "api_get_client", lambda _client_id: sample)
        app = AppTest.from_file(str(DASHBOARD_PATH), default_timeout=30)
        app.run()
        app.text_input(key="sk_id_input").set_value("139767")
        next(b for b in app.button if b.label == "Consultar Cliente").click().run()
        assert app.session_state["client_features"] is not None

        app.text_input(key="sk_id_input").set_value("abc")
        next(b for b in app.button if b.label == "Consultar Cliente").click().run()
        assert app.session_state["client_features"] is not None
        assert app.session_state["client_id"] == 139767
        assert any("inteiro positivo" in str(e.value) for e in app.error)


def test_dashboard_renders_project_copy_without_student_footer() -> None:
    """Verifica que a home exibe descricao do projeto sem rodape de autores."""
    app = AppTest.from_file(str(DASHBOARD_PATH), default_timeout=30)
    app.run()

    page_text = "\n".join(
        str(element.value)
        for collection in (app.markdown, app.caption)
        for element in collection
    )

    assert (
        "Motor de decisão de crédito com dados Home Credit, modelo LightGBM "
        "e API de escoragem"
    ) in page_text
    assert "Consulte as variáveis da análise de risco" in page_text
    assert "Desenvolvido por" not in page_text
    assert "Anderson Nunes" not in page_text
    assert "Mateus Nicolas" not in page_text
    assert "Rafael Waideman" not in page_text


def test_dashboard_catalog_navigation_does_not_use_page_link_registry() -> None:
    """Verifica navegacao in-app do catalogo via abas sem registry multipage."""
    source = _dashboard_sources()

    assert "st.page_link" not in source
    assert "st.switch_page" not in source
    assert "/catalogo_abt" not in source
    assert "tab_mesa, tab_catalogo, tab_performance = st.tabs(" in source
    assert '"🏦 Mesa de Crédito"' in source
    assert '"📖 Variáveis da Análise de Risco"' in source
    assert '"📈 Performance & ROI do Modelo"' in source
    assert 'st.form("form_busca_cliente"' in source
    assert "def main() -> None:" in source
    assert 'if __name__ == "__main__":' in source
    assert "_configure_page" in source
    assert "_init_session_state" in source
    assert "_render_mesa_tab" in source
    assert "_render_client_workspace" in source
    assert 'st.form("form_whatif_score"' in source
    assert "@st.fragment" not in source
    assert "_render_score_result" in source
    assert "_seed_edit_widgets_from_features" in source
    assert "_collect_overrides_from_session" in source
    assert "_render_readonly_feature" in source
    assert 'key="btn_consultar"' not in source
    assert 'key="btn_rodar_escoragem"' not in source
    assert "Rodar Escoragem de Crédito" in source
    assert "render_catalog(show_back_link=True)" in source
    assert "catalog_ready" in source
    assert 'key="btn_load_catalog"' in source
    assert "dossier_table_ready" in source
    assert 'key="btn_load_dossier_table"' in source
    assert "score_json_ready" in source
    assert 'key="btn_show_score_json"' in source
    assert "segment_rankings_cache" in source
    assert "_get_holdout_risk_scores" in source
    assert "_local_file_fingerprint" in source
    assert 'key="btn_retry_model_metrics"' in source
    assert "st.rerun()" not in source
    assert "Catálogo em manutenção para otimização de performance." not in source
    assert '@st.cache_data(show_spinner=False)' in source
    assert source.count("@st.cache_data(show_spinner=False)") == 1
    assert "holdout_segment_risk_ready" in source
    assert 'key="btn_load_segment_risk"' in source
    assert "_get_model_test_performance" in source
    assert '@st.cache_data(show_spinner="Carregando métricas oficiais do modelo...")' not in source
    assert '@st.cache_data(show_spinner="Calculando risco da carteira Holdout...")' not in source
    assert "### KPIs Executivos de Saneamento da Carteira" in source
    assert "### Métricas de Discriminação e Captura" in source
    assert "ROC-AUC:" in source
    assert "PR-AUC:" in source
    assert "_format_decimal_br" in source
    assert "_render_confusion_matrix" in source
    assert "performance_from_metadata" in source
    assert "load_model_metadata" in source
    assert "### Storytelling de Risco e Defesa do Modelo" not in source
    assert "### Mapeamento de Risco por Segmento (Variáveis Editáveis)" in source
    assert "performance_profile_attr" not in source
    assert "st.bar_chart" not in source
    assert "Mais seguras" in source
    assert "Mais arriscadas" in source
    assert "len(ranking) <= 5" in source
    assert "Taxa de Calote Base: 8,07%" not in source
    assert "tn=34455" not in source
    assert "fp=21801" not in source
    assert "fn=1241" not in source
    assert "tp=3698" not in source
    assert "tn=int(perf[\"tn\"])" in source
    assert "cm-cell-ok" in source
    assert "import seaborn as sns" not in source
    assert "st.pyplot(" not in source
    assert "st.radio(" not in source
    assert 'key="dashboard_view"' not in source
    assert "st.dataframe(" in source
    assert "Não apaga dossiê já carregado" in source
    assert "from scripts.predict import (" not in source.split("def _load_holdout_risk_scores")[0]


def test_catalog_page_is_disabled_to_avoid_duplicate_sidebar_entry() -> None:
    """Garante que nao existe pagina multipage antiga no menu lateral."""
    assert not (PAGES_DIR / "catalogo_abt.py").exists()
    page_files = list(PAGES_DIR.glob("*.py")) if PAGES_DIR.exists() else []
    assert page_files == []


def test_catalog_uses_native_business_dictionary_layout() -> None:
    """Verifica dicionario nativo sem widgets instaveis nem iframe/tabela."""
    catalog_source = CATALOG_MODULE_PATH.read_text(encoding="utf-8")

    assert "st.multiselect" not in catalog_source
    assert "st.selectbox" not in catalog_source
    assert "st.download_button" not in catalog_source
    assert "st.dataframe" not in catalog_source
    assert "components.html" not in catalog_source
    assert "st.iframe" not in catalog_source
    assert "st.metric" not in catalog_source
    assert "st.expander" not in catalog_source
    assert 'st.title("Variáveis da Análise de Risco")' in catalog_source
    assert "HIGHLIGHT_COLUMNS" in catalog_source
    assert "BUSINESS_DESCRIPTIONS" in catalog_source
    assert "format_variable_entry" in catalog_source
    assert "def render_catalog" in catalog_source
    # Texto generico so pode existir como constante de bloqueio.
    assert 'GENERIC_FORBIDDEN = "Feature criada na camada Gold' in catalog_source
    assert catalog_source.count(
        "Feature criada na camada Gold a partir das tabelas limpas do projeto."
    ) == 1
