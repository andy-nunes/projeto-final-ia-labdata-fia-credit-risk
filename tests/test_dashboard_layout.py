"""Testes dos helpers visuais do dashboard Streamlit."""

from pathlib import Path

import pytest


DASHBOARD_PATH = Path(__file__).resolve().parents[1] / "app" / "dashboard.py"
CATEGORY_PAGE_PATH = (
    Path(__file__).resolve().parents[1] / "app" / "pages" / "catalogo_abt.py"
)
if not DASHBOARD_PATH.exists():
    pytest.skip("O container atual nao monta app/dashboard.py.", allow_module_level=True)

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

    app.button[1].click()
    app.run()

    assert len(app.exception) == 0
    assert app.text_input[0].value == "139767"


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
    assert "Consulte o catálogo de campos da ABT" in page_text
    assert "Desenvolvido por" not in page_text
    assert "Anderson Nunes" not in page_text
    assert "Mateus Nicolas" not in page_text
    assert "Rafael Waideman" not in page_text


def test_dashboard_catalog_navigation_does_not_use_page_link_registry() -> None:
    """Verifica que a navegacao do catalogo nao depende do registry multipagina."""
    source = DASHBOARD_PATH.read_text(encoding="utf-8")

    assert "st.page_link" not in source
    assert "/catalogo_abt" in source


def test_catalog_filters_use_links_to_avoid_native_select_crash() -> None:
    """Verifica que catalogo usa componente client-side sem widgets instaveis."""
    source = CATEGORY_PAGE_PATH.read_text(encoding="utf-8")

    assert "st.multiselect" not in source
    assert "st.selectbox" not in source
    assert "st.text_input" not in source
    assert "st.download_button" not in source
    assert "components.html" in source
    assert "render_catalog_explorer_html" in source
