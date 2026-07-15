"""Aba Mesa de Crédito: dossiê, What-If e escoragem."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd
import streamlit as st

from app.abt_catalog import render_catalog
from app.ui.api import (
    _parse_http_error,
    api_get_client,
    api_post_ai_commentary,
    api_post_score,
)
from app.ui.components import (
    _build_audit_message,
    _build_score_stat_cards,
    _render_ai_commentary_html,
    _render_factor_row_html,
    _render_override_item_html,
    _render_triage_queue_html,
)
from app.ui.constants import (
    COMPLIANCE_404_MSG,
    FEATURE_TRANSLATIONS,
    ID_COLUMN,
    READONLY_FEATURES_DISPLAY_ORDER,
    READONLY_FEATURES_HIDDEN,
    TARGET_COLUMN,
    _CONFIG,
)
from app.ui.features import _render_editable_feature, _render_readonly_feature
from app.ui.formatting import _is_approved
from app.ui.session import (
    _clear_client_view_flags,
    _clear_dashboard_state,
    _clear_edit_widget_keys,
    _collect_overrides_from_session,
    _ensure_edit_widget_seeds,
    _seed_edit_widgets_from_features,
    _set_panel_flag,
)

_DOSSIER_TABLE_COLUMNS = ("Campo", "Variável", "Valor")
_DOSSIER_TABLE_CACHE_VERSION = 2

def _get_dossier_table(features: dict[str, Any], client_id: int) -> pd.DataFrame:
    """Reusa o DataFrame do dossiê completo quando o cliente não mudou."""
    from app.ui.formatting import _format_readonly_value as format_readonly

    cached = st.session_state.get("dossier_table_cache")
    if (
        isinstance(cached, dict)
        and cached.get("version") == _DOSSIER_TABLE_CACHE_VERSION
        and cached.get("client_id") == client_id
        and isinstance(cached.get("frame"), pd.DataFrame)
        and tuple(cached["frame"].columns) == _DOSSIER_TABLE_COLUMNS
    ):
        return cached["frame"]

    frame = pd.DataFrame(
        [
            [
                col_name,
                FEATURE_TRANSLATIONS.get(col_name, col_name),
                format_readonly(col_name, value),
            ]
            for col_name, value in features.items()
        ],
        columns=list(_DOSSIER_TABLE_COLUMNS),
    )
    st.session_state.dossier_table_cache = {
        "version": _DOSSIER_TABLE_CACHE_VERSION,
        "client_id": client_id,
        "frame": frame,
    }
    return frame

def _load_client_dossier(client_id_query: int) -> None:
    """Consulta API e persiste dossiê + seeds dos widgets What-If."""
    response = api_get_client(client_id_query)
    features_dict = response.get("features") or {}
    if not features_dict:
        st.error(f"Cliente {client_id_query} retornou dossiê vazio na API.")
        return

    previous_id = st.session_state.get("client_id")
    if previous_id != client_id_query:
        _clear_edit_widget_keys(previous_id)
    _clear_edit_widget_keys(client_id_query)

    st.session_state.client_features = features_dict
    st.session_state.client_id = client_id_query
    st.session_state.score_result = None
    _clear_client_view_flags()
    _seed_edit_widgets_from_features(features_dict, client_id_query)
    st.success(f"Cliente {client_id_query} localizado na base do Bureau.")

def _run_credit_score(features: dict[str, Any]) -> None:
    """Executa escoragem usando valores commitados pelo form de simulação."""
    client_id = int(st.session_state.client_id)
    overrides = _collect_overrides_from_session(client_id, features)
    result = api_post_score(client_id, overrides, emit_ai_commentary=False)
    result.pop("ai_commentary", None)
    st.session_state.score_result = result
    st.session_state.score_json_ready = False


def _run_ai_commentary(result: dict[str, Any]) -> None:
    """Gera parecer CredIA sob demanda sem rerodar o modelo de score."""
    score_payload = {**result}
    score_payload.pop("ai_commentary", None)
    ai_payload = api_post_ai_commentary(score_payload)
    ai_commentary = ai_payload.get("ai_commentary") or {}
    st.session_state.score_result = {**result, "ai_commentary": ai_commentary}

def _render_score_result(
    features: dict[str, Any],
    client_id: int,
    result: dict[str, Any],
) -> None:
    """Renderiza o parecer, cards, fatores e auditoria da última escoragem."""
    st.markdown(
        """
        <div class="section-band">
            <div class="section-kicker">Resultado</div>
            <div class="section-title">Escoragem de crédito</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    approved = _is_approved(result)
    box_class = "approved-box" if approved else "rejected-box"

    st.markdown(
        f'<div class="{box_class}"><h3>'
        f'{"✓ Parecer favorável" if approved else "✗ Parecer desfavorável"}'
        f"</h3></div>",
        unsafe_allow_html=True,
    )

    stat_cards = _build_score_stat_cards(result, client_id)
    st.markdown(
        f'<div class="stat-grid">{"".join(stat_cards)}</div>',
        unsafe_allow_html=True,
    )

    automation = result.get("automation") or {}
    if automation and not automation.get("error"):
        action = str(automation.get("action", "mesa_analise"))
        action_label = str(automation.get("action_label", action))
        event_path = automation.get("event_path") or ""
        st.markdown(
            _render_triage_queue_html(
                action=action,
                action_label=action_label,
                event_path=event_path or None,
            ),
            unsafe_allow_html=True,
        )
        # Espelha na aba Monitoramento para a demo de MLOps.
        st.session_state.latest_automation_event = {
            "client_id": client_id,
            "probability": result.get("probability"),
            "threshold": result.get("threshold"),
            "risk_band": result.get("risk_band"),
            "label": result.get("label"),
            "prediction": result.get("prediction"),
            "action": action,
            "action_label": action_label,
            "human_in_the_loop": automation.get("human_in_the_loop", True),
            "top_risk_factors": result.get("top_risk_factors") or [],
            "top_positive_factors": result.get("top_positive_factors") or [],
            "event_path": event_path,
            "storage": {
                "event_path": event_path,
                "latest_path": automation.get("latest_path"),
            },
        }
    elif automation.get("error"):
        st.warning(
            "Escoragem ok, mas a publicação do evento de automação falhou: "
            f"{automation.get('error')}"
        )

    ai_commentary = result.get("ai_commentary") or {}
    if ai_commentary:
        st.markdown(
            _render_ai_commentary_html(ai_commentary),
            unsafe_allow_html=True,
        )
        with st.expander("Auditoria IA (MVP)"):
            st.json(ai_commentary.get("audit") or {})
    else:
        st.caption("Parecer CredIA ainda não gerado para esta escoragem.")
        st.markdown('<div class="credia-action">', unsafe_allow_html=True)
        st.markdown('<div class="credia-btn">', unsafe_allow_html=True)
        if st.button(
            "Gerar parecer CredIA",
            key=f"btn_generate_credia_{client_id}",
            type="primary",
            use_container_width=True,
        ):
            with st.spinner("Gerando parecer CredIA..."):
                try:
                    _run_ai_commentary(result)
                except ConnectionError as exc:
                    st.error(str(exc))
                except RuntimeError as exc:
                    status, _ = _parse_http_error(exc)
                    st.error(f"Falha ao gerar CredIA (HTTP {status}): {exc}")
                else:
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    applied_overrides = result.get("applied_overrides") or {}
    with st.expander("Simulação aplicada"):
        if applied_overrides:
            override_items = [
                _render_override_item_html(feature_name, values)
                for feature_name, values in applied_overrides.items()
            ]
            st.markdown(
                f'<div class="override-list">{"".join(override_items)}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.write(
                "Nenhuma alteração aplicada; escoragem feita com o dossiê original."
            )

    if approved:
        st.markdown("#### Fatores Determinantes para Aprovação")
        factors = result.get("top_positive_factors") or []
        empty_msg = "Nenhum fator positivo identificado."
        factor_tone = "success"
    else:
        st.markdown("#### Motivos da Reprovação (Fatores de Risco)")
        factors = result.get("top_risk_factors") or []
        empty_msg = "Nenhum fator de risco identificado."
        factor_tone = "danger"

    if factors:
        factor_rows = []
        for feature_name, impact_pct in factors:
            tech_name = str(feature_name)
            business_label = FEATURE_TRANSLATIONS.get(tech_name, tech_name)
            factor_rows.append(
                _render_factor_row_html(
                    business_label,
                    tech_name,
                    float(impact_pct),
                    tone=factor_tone,
                )
            )
        st.markdown(
            f'<div class="factor-list">{"".join(factor_rows)}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.caption(empty_msg)

    target_raw = features.get(TARGET_COLUMN)
    if target_raw is not None:
        try:
            if isinstance(target_raw, float) and math.isnan(target_raw):
                target_raw = None
        except Exception:
            pass

    if target_raw is not None:
        target = int(target_raw)
        prediction = result.get("prediction")

        st.markdown("#### Auditoria do Modelo (Holdout)")

        audit_tone, audit_message = _build_audit_message(
            int(prediction),
            target,
            has_overrides=bool(applied_overrides),
        )
        if audit_tone == "success":
            st.success(audit_message)
        elif audit_tone == "error":
            st.error(audit_message)
        else:
            st.warning(audit_message)

    with st.expander("Saída técnica (JSON)"):
        if st.session_state.get("score_json_ready"):
            st.json(result)
        else:
            if st.button(
                "Exibir JSON da escoragem",
                key="btn_show_score_json",
                use_container_width=True,
            ):
                _set_panel_flag("score_json_ready", True)
            st.caption(
                "A saída completa é exibida sob demanda para manter a experiência fluida."
            )

def _render_client_workspace(features: dict[str, Any], client_id: int) -> None:
    """Dossiê interativo: What-If em form evita rerun a cada tecla/select."""
    _ensure_edit_widget_seeds(features, client_id)

    st.markdown(
        """
        <div class="section-band">
            <div class="section-kicker">Simulação</div>
            <div class="section-title">Simulação de cenário (What-If)</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.form("form_whatif_score", clear_on_submit=False):
        editable_features = list(_CONFIG.editable_features)
        for row_start in range(0, len(editable_features), 3):
            row_features = editable_features[row_start : row_start + 3]
            cols = st.columns(3)
            for col, feature_name in zip(cols, row_features):
                with col:
                    _render_editable_feature(features, feature_name, client_id)

        st.markdown('<div class="score-action">', unsafe_allow_html=True)
        st.markdown('<div class="score-btn">', unsafe_allow_html=True)
        run_score = st.form_submit_button(
            "Rodar Escoragem de Crédito",
            type="primary",
            use_container_width=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    if run_score:
        try:
            _run_credit_score(features)
        except ValueError as exc:
            st.error(str(exc))
        except ConnectionError as exc:
            st.error(str(exc))
        except RuntimeError as exc:
            status, _ = _parse_http_error(exc)
            if status == 404:
                st.error(COMPLIANCE_404_MSG)
            else:
                st.error(f"Falha na escoragem (HTTP {status}): {exc}")

    st.markdown(
        """
        <div class="section-band">
            <div class="section-kicker">Dossiê</div>
            <div class="section-title">Dados fixos do cliente</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    readonly_features = [
        col_name
        for col_name in READONLY_FEATURES_DISPLAY_ORDER
        if col_name not in READONLY_FEATURES_HIDDEN
        and col_name in _CONFIG.readonly_features
    ]
    for row_start in range(0, len(readonly_features), 3):
        row_features = readonly_features[row_start : row_start + 3]
        cols = st.columns(3)
        for col, col_name in zip(cols, row_features):
            with col:
                _render_readonly_feature(col_name, features.get(col_name))

    if st.session_state.get("dossier_table_ready"):
        st.markdown('<div class="dossier-actions">', unsafe_allow_html=True)
        unload_col, _ = st.columns([1, 2])
        with unload_col:
            if st.button(
                "Ocultar dossiê completo",
                key="btn_unload_dossier_table",
                use_container_width=True,
            ):
                _set_panel_flag(
                    "dossier_table_ready",
                    False,
                    dossier_table_cache=None,
                )
        st.markdown("</div>", unsafe_allow_html=True)
        with st.expander(
            "Ver dossiê completo (todas as variáveis da ABT)",
            expanded=True,
        ):
            st.dataframe(
                _get_dossier_table(features, client_id),
                use_container_width=True,
                hide_index=True,
                column_order=list(_DOSSIER_TABLE_COLUMNS),
            )
    else:
        st.markdown('<div class="dossier-actions">', unsafe_allow_html=True)
        if st.button(
            "Carregar dossiê completo (todas as variáveis da ABT)",
            key="btn_load_dossier_table",
            use_container_width=True,
        ):
            _set_panel_flag("dossier_table_ready", True)
        st.markdown("</div>", unsafe_allow_html=True)
        st.caption(
            "O dossiê completo da ABT só é montado sob demanda para não "
            "pesar cada interação da mesa."
        )

    result = st.session_state.score_result
    if result:
        _render_score_result(features, client_id, result)

def _render_mesa_tab() -> None:
    busca_col, limpar_col = st.columns([5, 1], vertical_alignment="bottom")
    with busca_col:
        with st.form("form_busca_cliente", clear_on_submit=False):
            busca_inner1, busca_inner2 = st.columns([3, 1], vertical_alignment="bottom")
            with busca_inner1:
                sk_id_input = st.text_input(
                    ID_COLUMN,
                    key="sk_id_input",
                    help=(
                        "Identificador do cliente na base do Bureau / "
                        "holdout de demonstração."
                    ),
                )
            with busca_inner2:
                consultar = st.form_submit_button(
                    "Consultar Cliente",
                    type="primary",
                    use_container_width=True,
                )
    with limpar_col:
        st.button(
            "Limpar",
            use_container_width=True,
            on_click=_clear_dashboard_state,
            key="btn_limpar",
        )

    if consultar:
        sk_id_text = str(sk_id_input or "").strip()
        if not sk_id_text.isdigit() or int(sk_id_text) < 1:
            # Não apaga dossiê já carregado quando a consulta é inválida.
            st.error(f"Informe um {ID_COLUMN} inteiro positivo.")
        else:
            try:
                _load_client_dossier(int(sk_id_text))
            except ConnectionError as exc:
                st.error(str(exc))
            except RuntimeError as exc:
                status, _ = _parse_http_error(exc)
                if status == 404:
                    st.error(COMPLIANCE_404_MSG)
                else:
                    st.error(f"Falha ao consultar cliente (HTTP {status}): {exc}")

    features = st.session_state.client_features
    if features:
        client_id = int(st.session_state.client_id)
        st.markdown(f"### Cliente *{client_id}*")
        _render_client_workspace(features, client_id)
    else:
        st.info(
            f"Informe um **{ID_COLUMN}** válido e clique em **Consultar Cliente** "
            "para carregar o dossiê a partir da API."
        )

def _render_catalog_tab() -> None:
    """Catálogo sob demanda: markdown grande não roda a cada rerun da mesa."""
    if st.session_state.get("catalog_ready"):
        unload_col, _ = st.columns([1, 3])
        with unload_col:
            if st.button(
                "Ocultar dicionário",
                key="btn_unload_catalog",
                use_container_width=True,
            ):
                _set_panel_flag("catalog_ready", False)
        render_catalog(show_back_link=True)
        return

    st.title("Variáveis da Análise de Risco")
    st.caption(
        "Dicionário de fatores do motor de decisão. Carregue sob demanda "
        "para não pesar a Mesa de Crédito."
    )
    if st.button(
        "Carregar dicionário de variáveis",
        type="secondary",
        key="btn_load_catalog",
    ):
        _set_panel_flag("catalog_ready", True)
    st.info(
        "O dicionário monta o markdown de todas as variáveis da ABT. "
        "Carregue quando for consultar as descrições de negócio."
    )

