from __future__ import annotations

from app import ai_commentary


def test_build_ai_commentary_reports_unavailable_without_api_key(monkeypatch) -> None:
    monkeypatch.setattr(ai_commentary, "_GEMINI_API_KEY", "")
    payload = {
        "sk_id_curr": 123,
        "probability": 0.22,
        "threshold": 0.08,
        "risk_band": "Alto risco",
        "top_risk_factors": [("AMT_CREDIT", 40.0)],
        "top_positive_factors": [("EXT_SOURCE_1", 5.0)],
        "applied_overrides": {"AMT_CREDIT": {"original": 1000, "applied": 1500}},
    }

    result = ai_commentary.build_ai_commentary(payload)

    assert result["human_in_the_loop"] is True
    assert result["available"] is False
    assert result["audit"]["provider"] == "gemini"
    assert result["audit"]["status"] == "unavailable_no_api_key"
    assert "indisponível" in result["message"].lower()


def test_build_ai_commentary_uses_llm_with_expected_shape(monkeypatch) -> None:
    monkeypatch.setattr(ai_commentary, "_GEMINI_API_KEY", "fake-key")

    def _fake_call(
        _: dict[str, object],
        *,
        model_name: str,
    ) -> dict[str, object]:
        assert model_name
        return {
            "summary": "S" * 460,
            "insights": ["Insight 1", "Insight 2"],
            "recommended_checks": ["Check 1"],
            "manager_brief_md": "### Parecer\n- Insight em markdown.",
        }

    monkeypatch.setattr(ai_commentary, "_call_gemini_with_guardrails", _fake_call)

    result = ai_commentary.build_ai_commentary(
        {
            "sk_id_curr": 222,
            "probability": 0.05,
            "threshold": 0.08,
            "risk_band": "Risco moderado",
            "top_risk_factors": [],
            "top_positive_factors": [],
            "applied_overrides": {},
        }
    )

    assert result["audit"]["provider"] == "gemini"
    assert result["audit"]["status"] == "ok"
    assert result["available"] is True
    assert len(result["summary"]) <= 420
    assert result["insights"] == ["Insight 1", "Insight 2"]
    assert result["recommended_checks"] == ["Check 1"]


def test_coerce_structured_response_from_markdown() -> None:
    raw = """### Parecer do gerente
- Risco concentrado em utilização de crédito.
- Comparar estabilidade de renda com histórico.
Validar documento de renda recente.
"""
    result = ai_commentary._coerce_structured_response(raw)
    assert result["summary"].startswith("### Parecer")
    assert len(result["insights"]) >= 1
    assert "manager_brief_md" in result and result["manager_brief_md"]


def test_coerce_structured_response_from_truncated_jsonish() -> None:
    raw = (
        '{"summary":"Cliente com risco moderado.",'
        '"insights":["Uso de limite elevado.","Tempo de emprego curto."],'
        '"recommended_checks":["Validar renda atual."],'
        '"manager_brief_md":"### Analise\\n- Priorizar checagem documental"'
    )
    result = ai_commentary._coerce_structured_response(raw)
    assert result["summary"].startswith("Cliente com risco moderado")
    assert result["insights"][0].startswith("Uso de limite")
    assert result["recommended_checks"][0].startswith("Validar renda")


def test_normalize_markdown_text_unescapes_newlines() -> None:
    raw = "### Analise\\n\\n- Item 1\\n- Item 2"
    result = ai_commentary._normalize_markdown_text(raw)
    assert "\n\n- Item 1" in result
