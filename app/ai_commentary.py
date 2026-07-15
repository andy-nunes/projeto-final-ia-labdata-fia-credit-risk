"""Geração de parecer IA para apoiar a mesa de crédito (humano no loop)."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from scripts.integrations_config import GeminiConfig, get_integrations_config
from scripts.model_config import get_model_config

_PROMPT_VERSION = "ai_commentary_v1"
_DEFAULT_MODEL = "gemini-flash-lite-latest"
_REPO_ROOT = Path(__file__).resolve().parents[1]
_EDA_NOTEBOOK_PATH = Path(
    os.getenv("EDA_NOTEBOOK_PATH", str(_REPO_ROOT / "notebooks" / "01_exp_analysis.ipynb"))
)
_MAX_TEXT_CHARS = 420
_MAX_BRIEF_CHARS = 4500
_REQUIRED_RESPONSE_KEYS = (
    "summary",
    "insights",
    "recommended_checks",
    "manager_brief_md",
)


def _normalize_model_name(model_name: str) -> str:
    normalized = (model_name or "").strip()
    if normalized.startswith("models/"):
        return normalized.split("models/", 1)[1]
    return normalized or _DEFAULT_MODEL


def _model_candidates(primary_model: str, model_fallbacks: tuple[str, ...]) -> list[str]:
    primary = _normalize_model_name(primary_model)
    models: list[str] = []
    for model_name in [primary, *model_fallbacks]:
        normalized = _normalize_model_name(model_name)
        if normalized and normalized not in models:
            models.append(normalized)
    return models


def _is_retryable_unavailable(exc: Exception) -> bool:
    if not isinstance(exc, RuntimeError):
        return False
    message = str(exc)
    return "HTTP 503" in message or '"status": "UNAVAILABLE"' in message


def build_ai_commentary(score_payload: dict[str, Any]) -> dict[str, Any]:
    integrations = get_integrations_config()
    gemini_config = integrations.gemini
    context = _build_context(score_payload)
    feature_name_map = context.get("feature_name_map") or {}
    generated_at = datetime.now(timezone.utc).isoformat()
    model_names = _model_candidates(gemini_config.model, gemini_config.model_fallbacks)
    preferred_model = model_names[0]
    gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()

    if not gemini_api_key:
        return _unavailable_commentary(
            message="CredIA indisponível: GEMINI_API_KEY ausente.",
            model=preferred_model,
            generated_at=generated_at,
            status="unavailable_no_api_key",
        )

    tried_models: list[str] = []
    last_error: Exception | None = None
    for model_name in model_names:
        tried_models.append(model_name)
        try:
            llm_result = _call_gemini_with_guardrails(
                context,
                model_name=model_name,
                gemini_api_key=gemini_api_key,
                gemini_config=gemini_config,
            )
            return _normalize_llm_result(
                llm_result,
                generated_at=generated_at,
                model=model_name,
                status="ok",
                feature_name_map=feature_name_map,
            )
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if _is_retryable_unavailable(exc):
                continue
            break

    error_text = str(last_error) if last_error else "Erro desconhecido."
    if len(tried_models) > 1:
        error_text = f"Modelos testados: {', '.join(tried_models)}. {error_text}"
    return _unavailable_commentary(
        message="CredIA indisponível: falha ao conectar com Gemini.",
        model=preferred_model,
        generated_at=generated_at,
        status="unavailable_llm_error",
        error=error_text,
    )


def _call_gemini_with_guardrails(
    context: dict[str, Any],
    *,
    model_name: str,
    gemini_api_key: str,
    gemini_config: GeminiConfig,
) -> dict[str, Any]:
    normalized_model = _normalize_model_name(model_name)
    context_json = json.dumps(context, ensure_ascii=False)
    prompt = (
        "Você é o CredIA, assistente de crédito para apoiar gerente humano.\n"
        "Objetivo: trazer insights acionáveis e não repetir o óbvio da tela.\n"
        "Responda EXCLUSIVAMENTE com JSON válido usando as chaves:\n"
        '{\n'
        '  "summary": string,\n'
        '  "insights": string[],\n'
        '  "recommended_checks": string[],\n'
        '  "manager_brief_md": string\n'
        "}\n"
        "Guardrails obrigatórios:\n"
        "1) Use somente os dados do CONTEXTO.\n"
        "2) Não invente fatos, não peça dados externos.\n"
        "3) Não dê decisão final automatizada; mantenha humano no loop.\n"
        "4) Não exponha PII nem inferências sensíveis além do contexto.\n"
        "5) Texto objetivo para gerente (português-BR).\n"
        "6) Explique trade-offs e sinais de atenção de forma prática.\n"
        "7) Não repita literalmente probability/threshold sem interpretação.\n"
        "8) manager_brief_md deve vir em markdown bem formatado.\n\n"
        f"CONTEXTO:\n{context_json}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": gemini_config.generation.temperature,
            "topP": gemini_config.generation.top_p,
            "maxOutputTokens": gemini_config.generation.max_output_tokens,
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "required": list(_REQUIRED_RESPONSE_KEYS),
                "properties": {
                    "summary": {"type": "STRING"},
                    "insights": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "recommended_checks": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "manager_brief_md": {"type": "STRING"},
                },
            },
        },
    }

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{normalized_model}"
        f":generateContent?key={gemini_api_key}"
    )
    req = Request(
        url=url,
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(req, timeout=gemini_config.timeout_seconds) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} no Gemini: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Falha de rede ao chamar Gemini: {exc}") from exc

    text = _extract_response_text(body)
    parsed = _coerce_structured_response(text)
    if not isinstance(parsed, dict):
        raise ValueError("Gemini não retornou JSON de objeto.")
    missing = [key for key in _REQUIRED_RESPONSE_KEYS if key not in parsed]
    if missing:
        raise ValueError(f"JSON do Gemini sem chaves obrigatórias: {missing}")
    return parsed


def _build_context(score_payload: dict[str, Any]) -> dict[str, Any]:
    feature_name_map = _build_feature_name_map(score_payload)
    return {
        "client_id": score_payload.get("sk_id_curr"),
        "label": score_payload.get("label"),
        "prediction": score_payload.get("prediction"),
        "risk_band": score_payload.get("risk_band"),
        "probability": _safe_float(score_payload.get("probability")),
        "threshold": _safe_float(score_payload.get("threshold")),
        "top_risk_factors": _top_factors(score_payload.get("top_risk_factors")),
        "top_positive_factors": _top_factors(score_payload.get("top_positive_factors")),
        "applied_overrides_count": len(score_payload.get("applied_overrides") or {}),
        "automation_action": (score_payload.get("automation") or {}).get("action"),
        "automation_action_label": (score_payload.get("automation") or {}).get(
            "action_label"
        ),
        "input_features": score_payload.get("input") or {},
        "portfolio_context": _build_portfolio_context(score_payload),
        "eda_highlights": _load_eda_highlights(),
        "feature_name_map": feature_name_map,
    }


def _top_factors(raw_factors: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if not isinstance(raw_factors, list):
        return normalized
    for item in raw_factors[:5]:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        feature = str(item[0])
        impact = _safe_float(item[1]) or 0.0
        normalized.append({"feature": feature, "impact_pct": round(impact, 2)})
    return normalized


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_feature_name_map(score_payload: dict[str, Any]) -> dict[str, str]:
    """Mapa técnico -> rótulo de negócio para guiar a linguagem do CredIA."""
    try:
        from app.ui.constants import FEATURE_TRANSLATIONS
    except Exception:
        FEATURE_TRANSLATIONS = {}

    feature_names: list[str] = []
    input_features = score_payload.get("input") or {}
    feature_names.extend(str(name) for name in input_features.keys())
    for item in (score_payload.get("top_risk_factors") or [])[:8]:
        if isinstance(item, (list, tuple)) and item:
            feature_names.append(str(item[0]))
    for item in (score_payload.get("top_positive_factors") or [])[:8]:
        if isinstance(item, (list, tuple)) and item:
            feature_names.append(str(item[0]))
    unique_names = list(dict.fromkeys(feature_names))
    return {name: str(FEATURE_TRANSLATIONS.get(name, name)) for name in unique_names}


@lru_cache(maxsize=1)
def _load_eda_highlights() -> list[str]:
    """Extrai highlights textuais do notebook de EDA para contexto macro."""
    try:
        raw = json.loads(_EDA_NOTEBOOK_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []

    highlights: list[str] = []
    for cell in raw.get("cells", []):
        if cell.get("cell_type") != "markdown":
            continue
        source = "".join(cell.get("source", []))
        lines = [line.strip() for line in source.splitlines() if line.strip()]
        for line in lines:
            clean = line.lstrip("#-*> ").strip()
            if not clean:
                continue
            lower = clean.lower()
            if any(
                key in lower
                for key in (
                    "inadimpl",
                    "risco",
                    "renda",
                    "crédito",
                    "emprego",
                    "default",
                    "segment",
                    "perfil",
                )
            ):
                highlights.append(clean[:220])
            if len(highlights) >= 12:
                return highlights
    return highlights


@lru_cache(maxsize=1)
def _load_portfolio_frame() -> Any | None:
    """Carrega holdout de demo para dar contexto global ao CredIA."""
    try:
        import pandas as pd
        import s3fs

        integrations = get_integrations_config()
        path = integrations.minio.paths.demo_holdout_path_s3
        if str(path).startswith("s3://"):
            fs = s3fs.S3FileSystem(
                key=os.getenv("MINIO_ROOT_USER", "minioadmin"),
                secret=os.getenv("MINIO_ROOT_PASSWORD", "minioadmin"),
                client_kwargs={"endpoint_url": integrations.minio.endpoint_url},
            )
            with fs.open(path, "rb") as handle:
                return pd.read_parquet(handle, engine="pyarrow")
        return pd.read_parquet(path)
    except Exception:
        return None


def _build_portfolio_context(score_payload: dict[str, Any]) -> dict[str, Any]:
    """Resumo global do portfólio para evitar recomendação óbvia."""
    frame = _load_portfolio_frame()
    if frame is None:
        return {}

    input_features = score_payload.get("input") or {}
    factor_features = [
        str(item[0])
        for item in (score_payload.get("top_risk_factors") or [])[:3]
        if isinstance(item, (list, tuple)) and item
    ]
    selected_features = list(dict.fromkeys([*factor_features, *list(input_features.keys())[:4]]))

    context: dict[str, Any] = {"sample_size": int(len(frame)), "feature_benchmarks": {}}
    target_column = get_model_config().target_column
    if target_column in frame.columns:
        try:
            target_series = frame[target_column].dropna()
            if not target_series.empty:
                context["portfolio_default_rate"] = float(target_series.mean())
        except Exception:
            pass

    for feature in selected_features:
        if feature not in frame.columns:
            continue
        client_value = _safe_float(input_features.get(feature))
        if client_value is None:
            continue
        try:
            numeric_series = frame[feature]
            numeric_series = numeric_series.dropna().astype(float)
        except Exception:
            continue
        if numeric_series.empty:
            continue
        percentile = float((numeric_series <= client_value).mean() * 100.0)
        context["feature_benchmarks"][feature] = {
            "client_value": client_value,
            "p50": float(numeric_series.quantile(0.50)),
            "p75": float(numeric_series.quantile(0.75)),
            "p90": float(numeric_series.quantile(0.90)),
            "percentile": percentile,
        }
    return context


def _extract_response_text(raw: dict[str, Any]) -> str:
    candidates = raw.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("Resposta sem candidates.")

    first = candidates[0]
    content = first.get("content") if isinstance(first, dict) else None
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list) or not parts:
        raise ValueError("Resposta sem parts.")

    text = parts[0].get("text") if isinstance(parts[0], dict) else None
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Resposta do Gemini sem texto.")
    return text.strip()


def _extract_json_payload(text: str) -> Any:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = _strip_code_fences(cleaned)

    parsed_direct = _try_parse_json_lenient(cleaned)
    if parsed_direct is not None:
        return parsed_direct

    obj_text = _extract_first_json_object(cleaned)
    if obj_text is None:
        raise json.JSONDecodeError("Objeto JSON não encontrado.", cleaned, 0)
    parsed_object = _try_parse_json_lenient(obj_text)
    if parsed_object is not None:
        return parsed_object
    raise json.JSONDecodeError("Falha ao parsear JSON do Gemini.", obj_text, 0)


def _coerce_structured_response(text: str) -> dict[str, Any]:
    """Aceita JSON ideal, mas reaproveita markdown/texto quando vier sem schema."""
    try:
        parsed = _extract_json_payload(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    raw = (text or "").strip()
    if not raw:
        raise json.JSONDecodeError("Objeto JSON não encontrado.", text, 0)

    jsonish = _extract_from_jsonish_payload(raw)
    if jsonish is not None:
        return jsonish

    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    bullets = [line.lstrip("-* ").strip() for line in lines if line.startswith(("-", "*"))]
    insights = [item for item in bullets if item][:4]
    summary = lines[0][:220] if lines else "Parecer textual retornado pelo Gemini."
    checks = []
    for line in lines:
        lower = line.lower()
        if any(k in lower for k in ("valid", "checar", "confirm", "document", "comprov")):
            checks.append(line[:220])
        if len(checks) >= 4:
            break

    return {
        "summary": summary,
        "insights": insights or ["Gemini retornou resposta textual sem JSON estruturado."],
        "recommended_checks": checks,
        "manager_brief_md": raw[:_MAX_BRIEF_CHARS],
    }


def _extract_from_jsonish_payload(raw: str) -> dict[str, Any] | None:
    """Recupera campos quando o Gemini retorna JSON truncado/quebrado."""
    if not raw.startswith("{") or '"summary"' not in raw:
        return None

    summary = _extract_jsonish_string_field(raw, "summary")
    insights = _extract_jsonish_array_field(raw, "insights")
    checks = _extract_jsonish_array_field(raw, "recommended_checks")
    brief = _extract_jsonish_string_field(raw, "manager_brief_md")

    if not any([summary, insights, checks, brief]):
        return None

    return {
        "summary": summary or "Parecer parcial recuperado de resposta truncada.",
        "insights": insights
        or ["Resposta do Gemini veio truncada; parte do conteúdo foi recuperada."],
        "recommended_checks": checks or [],
        "manager_brief_md": brief
        or "### CredIA\nResposta parcialmente recuperada de payload truncado.",
    }


def _extract_jsonish_string_field(raw: str, field: str) -> str | None:
    key = f'"{field}"'
    key_idx = raw.find(key)
    if key_idx < 0:
        return None
    colon_idx = raw.find(":", key_idx + len(key))
    if colon_idx < 0:
        return None
    quote_idx = raw.find('"', colon_idx + 1)
    if quote_idx < 0:
        return None

    value_chars: list[str] = []
    escaped = False
    for ch in raw[quote_idx + 1 :]:
        if escaped:
            # Preserva a sequência escapada para normalização posterior.
            value_chars.append(f"\\{ch}")
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == '"':
            break
        value_chars.append(ch)

    value = "".join(value_chars).strip()
    if not value:
        return None
    return _unescape_jsonish_text(value)


def _extract_jsonish_array_field(raw: str, field: str) -> list[str]:
    key = f'"{field}"'
    key_idx = raw.find(key)
    if key_idx < 0:
        return []
    bracket_idx = raw.find("[", key_idx + len(key))
    if bracket_idx < 0:
        return []

    items: list[str] = []
    in_string = False
    escaped = False
    current: list[str] = []
    for ch in raw[bracket_idx + 1 :]:
        if escaped:
            if in_string:
                # Preserva escape para _unescape_jsonish_text processar \n, \t, etc.
                current.append(f"\\{ch}")
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == '"':
            in_string = not in_string
            if not in_string:
                value = _unescape_jsonish_text("".join(current).strip())
                if value:
                    items.append(value)
                current = []
            continue
        if in_string:
            current.append(ch)
            continue
        if ch == "]":
            break
        if len(items) >= 8:
            break
    return items


def _unescape_jsonish_text(value: str) -> str:
    return (
        value.replace("\\n", "\n")
        .replace("\\r", "\r")
        .replace("\\t", "\t")
        .replace('\\"', '"')
        .replace("\\\\", "\\")
        .strip()
    )


def _try_parse_json_lenient(text: str) -> Any | None:
    """Tenta parsear JSON e corrige quebras de linha dentro de strings."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        repaired = _escape_newlines_inside_strings(text)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            return None


def _strip_code_fences(text: str) -> str:
    """Remove fence markdown opcional (```json ... ```)."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    stripped = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", stripped)
    stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def _extract_first_json_object(text: str) -> str | None:
    """Extrai o primeiro objeto JSON balanceado respeitando strings/escapes."""
    start = text.find("{")
    if start < 0:
        return None

    depth = 0
    in_string = False
    escaped = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]
    return None


def _escape_newlines_inside_strings(text: str) -> str:
    """Escapa quebras de linha cruas em strings JSON não conformes."""
    output: list[str] = []
    in_string = False
    escaped = False
    for ch in text:
        if escaped:
            output.append(ch)
            escaped = False
            continue
        if ch == "\\":
            output.append(ch)
            escaped = True
            continue
        if ch == '"':
            output.append(ch)
            in_string = not in_string
            continue
        if in_string and ch == "\n":
            output.append("\\n")
            continue
        if in_string and ch == "\r":
            output.append("\\r")
            continue
        output.append(ch)
    return "".join(output)


def _normalize_llm_result(
    llm_result: dict[str, Any],
    *,
    generated_at: str,
    model: str,
    status: str,
    feature_name_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    insights_raw = llm_result.get("insights")
    insights: list[str] = []
    if isinstance(insights_raw, list):
        insights = [_clip_text(item, max_chars=220) for item in insights_raw if str(item).strip()][:5]
    checks_raw = llm_result.get("recommended_checks")
    checks: list[str] = []
    if isinstance(checks_raw, list):
        checks = [_clip_text(item, max_chars=220) for item in checks_raw if str(item).strip()][:5]

    names_map = feature_name_map or {}
    commentary = {
        "available": True,
        "message": "CredIA disponível.",
        "summary": _clip_text(
            _replace_feature_tokens(str(llm_result.get("summary") or ""), names_map)
        ),
        "insights": [
            _replace_feature_tokens(item, names_map) for item in insights
        ],
        "recommended_checks": [
            _replace_feature_tokens(item, names_map) for item in checks
        ],
        "manager_brief_md": _normalize_markdown_text(
            _replace_feature_tokens(
                str(llm_result.get("manager_brief_md") or ""),
                names_map,
            )
        ),
        "human_in_the_loop": True,
        "audit": {
            "provider": "gemini",
            "model": model,
            "status": status,
            "prompt_version": _PROMPT_VERSION,
            "generated_at": generated_at,
            "source": "score_output",
            "policy_enforced": True,
        },
    }
    return _ensure_required_fields(commentary)


def _replace_feature_tokens(text: str, feature_name_map: dict[str, str]) -> str:
    """Substitui tokens técnicos por rótulos de negócio no texto final."""
    if not text or not feature_name_map:
        return text
    replaced = text
    keys = sorted(feature_name_map.keys(), key=len, reverse=True)
    for key in keys:
        label = feature_name_map.get(key) or key
        if label == key:
            continue
        pattern = rf"\b{re.escape(key)}\b"
        replaced = re.sub(pattern, f"{label} ({key})", replaced)
    return replaced


def _unavailable_commentary(
    *,
    message: str,
    model: str,
    generated_at: str,
    status: str,
    error: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "available": False,
        "message": _clip_text(message, max_chars=220),
        "summary": "IA indisponível nesta execução.",
        "insights": [],
        "recommended_checks": [],
        "manager_brief_md": (
            "### CredIA indisponível\n"
            "- Não foi possível obter resposta do Gemini nesta tentativa.\n"
            "- Prossiga com análise manual usando fatores determinantes e política da mesa."
        ),
        "human_in_the_loop": True,
        "audit": {
            "provider": "gemini",
            "model": model,
            "status": status,
            "prompt_version": _PROMPT_VERSION,
            "generated_at": generated_at,
            "source": "score_output",
        },
    }
    if error:
        payload["audit"]["error"] = _clip_text(error, max_chars=220)
    return _ensure_required_fields(payload)


def _clip_text(value: Any, *, max_chars: int = _MAX_TEXT_CHARS) -> str:
    text = str(value or "").strip()
    if not text:
        return "Não informado."
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 1].rstrip()}…"


def _normalize_markdown_text(value: Any) -> str:
    text = _unescape_jsonish_text(str(value or "").strip())
    if not text:
        return "### CredIA\nSem briefing disponível nesta execução."
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(?i)\ban[aá]lise de cr[eé]dito\b", "Apoio à decisão de crédito", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return _clip_text(text, max_chars=_MAX_BRIEF_CHARS)


def _ensure_required_fields(commentary: dict[str, Any]) -> dict[str, Any]:
    commentary["available"] = bool(commentary.get("available", True))
    commentary["message"] = _clip_text(commentary.get("message"), max_chars=220)
    commentary["summary"] = _clip_text(commentary.get("summary"))
    if not isinstance(commentary.get("insights"), list):
        commentary["insights"] = []
    commentary["insights"] = [_clip_text(item, max_chars=220) for item in commentary["insights"]]
    if not isinstance(commentary.get("recommended_checks"), list):
        commentary["recommended_checks"] = []
    commentary["recommended_checks"] = [
        _clip_text(item, max_chars=220) for item in commentary["recommended_checks"]
    ]
    commentary["manager_brief_md"] = _normalize_markdown_text(
        commentary.get("manager_brief_md")
    )
    commentary["human_in_the_loop"] = True
    if not isinstance(commentary.get("audit"), dict):
        commentary["audit"] = {}
    return commentary
