"""Componentes HTML reutilizáveis do dashboard."""

from __future__ import annotations

from html import escape
from typing import Any

from app.ui.formatting import _get_label, _is_approved

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


def _triage_box_class(action: str) -> str:
    """Classe CSS da caixa de fila sugerida."""
    if action == "autoaprovacao_candidata":
        return "triage-box triage-box-auto"
    if action == "recusa_candidata":
        return "triage-box triage-box-recusa"
    return "triage-box triage-box-mesa"


def _render_triage_queue_html(
    *,
    action: str,
    action_label: str,
    event_path: str | None = None,
) -> str:
    """Card visível da fila sugerida (automação / webhook) para a banca."""
    titles = {
        "autoaprovacao_candidata": "Fila sugerida: autoaprovação candidata",
        "mesa_analise": "Fila sugerida: mesa de crédito",
        "recusa_candidata": "Fila sugerida: recusa candidata",
    }
    title = titles.get(action, f"Fila sugerida: {action}")
    path_html = ""
    if event_path:
        path_html = (
            f'<p class="triage-path">Evento auditável no MinIO: '
            f"<code>{escape(event_path)}</code></p>"
        )
    return (
        f'<div class="{_triage_box_class(action)}">'
        f'<div class="triage-kicker">Automação pós-escoragem · humano no loop</div>'
        f'<div class="triage-title">{escape(title)}</div>'
        f'<p class="triage-body">{escape(action_label)}. '
        f"A automação encaminha a proposta para esta fila; "
        f"o analista confirma a decisão de crédito.</p>"
        f"{path_html}"
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
    probability_tone = _probability_tone(proba, threshold_value)

    return [
        _render_stat_card_html("Decisão", result.get("label", "—"), tone=card_tone),
        _render_stat_card_html(
            "Faixa de risco",
            result.get("risk_band", "—"),
            tone=_risk_band_tone(result.get("risk_band")),
        ),
        _render_stat_card_html("Classe prevista", prediction_label),
        _render_stat_card_html(
            "Régua de decisão",
            threshold_txt,
            note="Corte para reprovação",
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

