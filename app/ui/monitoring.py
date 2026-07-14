"""Aba Monitoramento MLOps: saúde, artefatos e última triagem automatizada."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import streamlit as st

from app.ui.api import (
    api_get_automation_latest,
    api_get_monitoring_latest,
    api_post_monitoring_run,
)
from app.ui.components import _render_stat_card_html, _render_triage_queue_html
from app.ui.session import _set_panel_flag


_STATUS_LABEL = {
    "ok": ("OK", "success"),
    "warn": ("Atenção", "warning"),
    "fail": ("Falha", "error"),
}

_DOMAIN_ORDER = ("api", "artifacts", "schema", "drift", "performance", "governance")
_DOMAIN_LABEL = {
    "api": "API",
    "artifacts": "Artefatos",
    "schema": "Contrato de Features",
    "drift": "Drift de Dados",
    "performance": "Performance",
    "governance": "Governança",
}
_CHECK_LABEL = {
    "api_health": "Disponibilidade da API",
    "feature_schema": "Integridade das variáveis",
    "data_drift": "Estabilidade dos dados (PSI)",
    "performance_baseline": "Referência de performance",
    "threshold_coherence": "Alinhamento da régua de decisão",
}

_ACTION_LABEL_SHORT = {
    "autoaprovacao_candidata": "Autoaprovação candidata",
    "mesa_analise": "Mesa de análise",
    "recusa_candidata": "Recusa candidata",
}


def _status_badge(status: str) -> None:
    """Exibe o overall/check status com o tom Streamlit adequado."""
    label, tone = _STATUS_LABEL.get(status, (status.upper(), "info"))
    message = f"Status: **{label}** (`{status}`)"
    if tone == "success":
        st.success(message)
    elif tone == "warning":
        st.warning(message)
    elif tone == "error":
        st.error(message)
    else:
        st.info(message)


def _normalize_check_name(name: str) -> str:
    """Converte nome técnico de check em rótulo amigável."""
    if name.startswith("artifact:"):
        path = name.removeprefix("artifact:")
        lower_path = path.lower()
        if "abt_train.parquet" in lower_path:
            return "ABT de treino disponível"
        if "abt_demo_holdout.parquet" in lower_path:
            return "ABT de holdout disponível"
        if "/abt/" in lower_path:
            return "Artefato ABT disponível"
        if "lightgbm" in path:
            return "Modelo publicado"
        if "model_metadata" in path:
            return "Metadados do modelo"
        return f"Artefato: {path.split('/')[-1]}"
    return _CHECK_LABEL.get(name, name.replace("_", " ").title())


def _check_domain(name: str) -> str:
    """Classifica cada check em um domínio de monitoramento."""
    if name == "api_health":
        return "api"
    if name.startswith("artifact:"):
        return "artifacts"
    if name in {"feature_schema"}:
        return "schema"
    if name in {"data_drift"}:
        return "drift"
    if name in {"performance_baseline"}:
        return "performance"
    return "governance"


def _status_tone(status: str) -> str:
    """Mapeia status para tom de card."""
    if status == "ok":
        return "success"
    if status == "warn":
        return "warning"
    if status == "fail":
        return "danger"
    return "neutral"


def _build_checks_table(checks: list[dict[str, Any]]) -> pd.DataFrame:
    """Monta DataFrame legível com status, domínio e detalhe."""
    rows: list[dict[str, str]] = []
    for check in checks:
        raw_name = str(check.get("name", "check"))
        status = str(check.get("status", "unknown")).lower()
        rows.append(
            {
                "Check": _normalize_check_name(raw_name),
                "Domínio": _DOMAIN_LABEL.get(_check_domain(raw_name), "Governança"),
                "Status": status.upper(),
                "Resumo": str(check.get("detail", "")),
            }
        )
    return pd.DataFrame(rows)


def _render_executive_summary(
    report: dict[str, Any],
    checks: list[dict[str, Any]],
) -> None:
    """Renderiza cards executivos para leitura rápida do monitoramento."""
    status_counts = Counter(str(check.get("status", "unknown")).lower() for check in checks)
    overall = str(report.get("overall_status", "unknown")).lower()
    generated_at = str(report.get("generated_at", "—"))

    summary_cards = [
        _render_stat_card_html(
            "Status geral",
            _STATUS_LABEL.get(overall, (overall.upper(), ""))[0],
            tone=_status_tone(overall),
            note=f"Atualizado em {generated_at}",
        ),
        _render_stat_card_html(
            "Checks totais",
            str(len(checks)),
            tone="neutral",
            note="Validações concluídas",
        ),
        _render_stat_card_html(
            "Falhas",
            str(status_counts.get("fail", 0)),
            tone="danger" if status_counts.get("fail", 0) else "neutral",
            note="Prioridade imediata",
        ),
        _render_stat_card_html(
            "Atenções",
            str(status_counts.get("warn", 0)),
            tone="warning" if status_counts.get("warn", 0) else "neutral",
            note="Requer acompanhamento",
        ),
        _render_stat_card_html(
            "OK",
            str(status_counts.get("ok", 0)),
            tone="success" if status_counts.get("ok", 0) else "neutral",
            note="Dentro do esperado",
        ),
    ]
    st.markdown(
        f'<div class="stat-grid stat-grid-5">{"".join(summary_cards)}</div>',
        unsafe_allow_html=True,
    )


def _render_domain_health(checks: list[dict[str, Any]]) -> None:
    """Mostra saúde por domínio para facilitar leitura não técnica."""
    domain_status: dict[str, str] = {}
    for domain in _DOMAIN_ORDER:
        domain_checks = [c for c in checks if _check_domain(str(c.get("name", ""))) == domain]
        if not domain_checks:
            continue
        current = "ok"
        for check in domain_checks:
            status = str(check.get("status", "unknown")).lower()
            if status == "fail":
                current = "fail"
                break
            if status == "warn":
                current = "warn"
            elif status not in {"ok", "warn"} and current == "ok":
                current = "warn"
        domain_status[domain] = current

    if not domain_status:
        return

    st.markdown("#### Saúde por domínio")
    cards = [
        _render_stat_card_html(
            _DOMAIN_LABEL.get(domain, domain.title()),
            _STATUS_LABEL.get(status, (status.upper(), ""))[0],
            tone=_status_tone(status),
            note=f"{status.upper()}",
        )
        for domain, status in domain_status.items()
    ]
    st.markdown(f'<div class="stat-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def _ensure_latest_automation_loaded() -> dict[str, Any] | None:
    """Usa evento da sessão ou busca o último publicado no MinIO."""
    cached = st.session_state.get("latest_automation_event")
    if isinstance(cached, dict) and cached.get("action"):
        return cached
    try:
        event = api_get_automation_latest()
        st.session_state.latest_automation_event = event
        return event
    except Exception:
        return None


def _parse_iso_datetime(value: Any) -> datetime | None:
    """Converte string ISO em datetime timezone-aware quando possível."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _automation_tone(action: str) -> str:
    """Mapeia fila de automação para tom de card."""
    if action == "autoaprovacao_candidata":
        return "success"
    if action == "recusa_candidata":
        return "danger"
    if action == "mesa_analise":
        return "warning"
    return "neutral"


def _render_automation_event(event: dict[str, Any]) -> None:
    """Painel humano da última automação de triagem."""
    action = str(event.get("action") or "mesa_analise")
    action_label = str(event.get("action_label") or action)
    client_id = event.get("client_id", "—")
    probability = event.get("probability")
    threshold = event.get("threshold")
    risk_band = event.get("risk_band") or "—"
    hitl = bool(event.get("human_in_the_loop", True))
    emitted_at = _parse_iso_datetime(event.get("emitted_at"))
    storage = event.get("storage") or {}
    event_path = storage.get("event_path") or event.get("event_path")

    event_age_txt = "—"
    freshness_tone = "neutral"
    if emitted_at:
        now = datetime.now(timezone.utc)
        elapsed = now - emitted_at.astimezone(timezone.utc)
        minutes = max(0, int(elapsed.total_seconds() // 60))
        if minutes < 60:
            event_age_txt = f"{minutes} min"
        else:
            event_age_txt = f"{minutes // 60} h"
        freshness_tone = "success" if minutes <= 60 else "warning"

    st.markdown(
        """
        <div class="section-band">
            <div class="section-kicker">Automação (item iv)</div>
            <div class="section-title">Encaminhamento sugerido da última análise</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        _render_triage_queue_html(
            action=action,
            action_label=action_label,
            event_path=str(event_path) if event_path else None,
        ),
        unsafe_allow_html=True,
    )

    summary_cards = [
        _render_stat_card_html(
            "Fila sugerida",
            _ACTION_LABEL_SHORT.get(action, action),
            tone=_automation_tone(action),
            note="Sugestão do motor",
        ),
        _render_stat_card_html(
            "Atualização do evento",
            event_age_txt,
            tone=freshness_tone,
            note="Tempo desde o registro",
        ),
        _render_stat_card_html(
            "Humano no loop",
            "Ativo" if hitl else "Inativo",
            tone="success" if hitl else "danger",
            note="Decisão final do analista",
        ),
        _render_stat_card_html(
            "Cliente",
            str(client_id),
            tone="neutral",
            note="SK_ID_CURR",
        ),
        _render_stat_card_html(
            "Faixa de risco",
            str(risk_band),
            tone="warning",
            note=str(event.get("label") or ""),
        ),
    ]
    st.markdown(
        f'<div class="stat-grid stat-grid-5">{"".join(summary_cards)}</div>',
        unsafe_allow_html=True,
    )

    score_cards = [
        _render_stat_card_html(
            "Probabilidade",
            f"{float(probability):.1%}" if probability is not None else "—",
            tone="neutral",
            note="Chance estimada de inadimplência",
        ),
        _render_stat_card_html(
            "Threshold de decisão",
            f"{float(threshold):.0%}" if threshold is not None else "—",
            tone="neutral",
            note="Régua vigente",
        ),
        _render_stat_card_html(
            "Evento no lake",
            "Publicado" if event_path else "Indisponível",
            tone="success" if event_path else "warning",
            note="Rastro de auditoria",
        ),
    ]
    st.markdown(f'<div class="stat-grid">{"".join(score_cards)}</div>', unsafe_allow_html=True)

    with st.expander("Principais fatores da recomendação (XAI)"):
        risks = event.get("top_risk_factors") or []
        protects = event.get("top_positive_factors") or []
        c1, c2 = st.columns(2)
        with c1:
            st.write("Fatores de risco")
            if risks:
                st.dataframe(
                    [{"feature": f, "impacto_%": round(float(v), 2)} for f, v in risks],
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.caption("Sem fatores de risco no evento.")
        with c2:
            st.write("Fatores de proteção")
            if protects:
                st.dataframe(
                    [
                        {"feature": f, "impacto_%": round(float(v), 2)}
                        for f, v in protects
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.caption("Sem fatores de proteção no evento.")

    with st.expander("Detalhamento técnico (auditoria)"):
        st.caption(f"Ação técnica: `{action}`")
        if event_path:
            st.caption(f"Evento: `{event_path}`")
        st.json(event)


def _render_monitoring_tab() -> None:
    """Aba de monitoramento: roda checagens e lê o último relatório/evento."""
    st.markdown(
        """
        <div class="section-band">
            <div class="section-kicker">MLOps</div>
            <div class="section-title">Monitoramento em produção</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        "Visão executiva da saúde do serviço, consistência dos artefatos "
        "e estabilidade dos dados/modelo. Baseado na DAG `05_monitor_health`."
    )

    col_run, col_refresh = st.columns(2)
    with col_run:
        run_clicked = st.button(
            "Executar monitoramento agora",
            use_container_width=True,
            type="primary",
            key="btn_run_monitoring",
        )
    with col_refresh:
        refresh_clicked = st.button(
            "Atualizar visão mais recente",
            use_container_width=True,
            key="btn_refresh_monitoring",
        )

    if run_clicked:
        try:
            with st.spinner("Executando checagens..."):
                report = api_post_monitoring_run()
            st.session_state.monitoring_report = report
            st.session_state.monitoring_report_error = None
            _set_panel_flag("monitoring_ready", True)
        except Exception as exc:  # noqa: BLE001
            st.session_state.monitoring_report_error = str(exc)
            st.session_state.monitoring_report = None

    if refresh_clicked or (
        st.session_state.get("monitoring_ready")
        and st.session_state.get("monitoring_report") is None
        and not st.session_state.get("monitoring_report_error")
    ):
        try:
            report = api_get_monitoring_latest()
            st.session_state.monitoring_report = report
            st.session_state.monitoring_report_error = None
            st.session_state.monitoring_ready = True
        except Exception as exc:  # noqa: BLE001
            st.session_state.monitoring_report_error = str(exc)

    err = st.session_state.get("monitoring_report_error")
    report = st.session_state.get("monitoring_report")

    if err:
        st.error(
            "Não foi possível carregar a visão de monitoramento. "
            "Execute o monitoramento pelo botão acima ou pela DAG `05_monitor_health`.\n\n"
            f"Detalhe: {err}"
        )
    elif not report:
        st.info(
            "Ainda não existe relatório carregado. Clique em "
            "**Executar monitoramento agora** para gerar `s3://artifacts/monitoring/latest.json`."
        )
    else:
        overall = str(report.get("overall_status", "unknown"))
        _status_badge(overall)

        checks = report.get("checks") or []
        _render_executive_summary(report, checks)
        _render_domain_health(checks)

        st.markdown("#### Detalhamento das validações")
        selected_status = st.selectbox(
            "Exibir validações por status",
            options=["Todos", "Falha", "Atenção", "OK"],
            key="monitoring_status_filter",
        )
        status_map = {"Falha": "FAIL", "Atenção": "WARN", "OK": "OK"}
        table_df = _build_checks_table(checks)
        if selected_status != "Todos":
            table_df = table_df[table_df["Status"] == status_map[selected_status]]

        if table_df.empty:
            st.info("Não há validações para o filtro selecionado.")
        else:
            st.dataframe(table_df, use_container_width=True, hide_index=True)

        runbook = (report.get("runbook") or {}).get(overall)
        if runbook:
            st.info(f"Próxima ação recomendada ({overall}): {runbook}")

        artifacts = report.get("artifacts") or {}
        if artifacts:
            with st.expander("Caminhos dos artefatos de monitoramento"):
                st.caption(
                    "Referências dos artefatos: "
                    + ", ".join(f"`{k}={v}`" for k, v in artifacts.items())
                )

    # Última triagem: sessão local ou último evento no MinIO
    latest_auto = _ensure_latest_automation_loaded()
    if latest_auto:
        _render_automation_event(latest_auto)
    else:
        st.markdown(
            """
            <div class="section-band">
                <div class="section-kicker">Automação (item iv)</div>
                <div class="section-title">Encaminhamento sugerido da última análise</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(
            "Ainda não há evento de automação registrado. Faça uma escoragem na "
            "**Mesa de Crédito** para visualizar a recomendação de fila aqui e no MinIO."
        )
