"""Cliente HTTP da API FastAPI usada pelo dashboard."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.ui.constants import API_BASE_URL

def api_get_client(client_id: int) -> dict[str, Any]:
    """GET /client/{id} — retorna features ou levanta com status HTTP."""
    url = f"{API_BASE_URL}/client/{client_id}"
    req = Request(url, method="GET", headers={"Accept": "application/json"})
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(json.dumps({"status": exc.code, "body": body})) from exc
    except URLError as exc:
        raise ConnectionError(
            f"API indisponível em {API_BASE_URL}. Verifique se o uvicorn está rodando."
        ) from exc

def api_post_score(
    client_id: int,
    features_override: dict[str, Any],
    *,
    emit_automation: bool = True,
    emit_ai_commentary: bool = False,
) -> dict[str, Any]:
    """POST /score com client_id + features_override (+ triagem opcional)."""
    payload = json.dumps(
        {
            "client_id": client_id,
            "features_override": features_override,
            "emit_automation": emit_automation,
            "emit_ai_commentary": emit_ai_commentary,
        }
    ).encode("utf-8")
    req = Request(
        f"{API_BASE_URL}/score",
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(json.dumps({"status": exc.code, "body": body})) from exc
    except URLError as exc:
        raise ConnectionError(
            f"API indisponível em {API_BASE_URL}. Verifique se o uvicorn está rodando."
        ) from exc


def api_post_ai_commentary(score_payload: dict[str, Any]) -> dict[str, Any]:
    """POST /score/ai-commentary para gerar parecer CredIA sob demanda."""
    payload = json.dumps({"score_payload": score_payload}).encode("utf-8")
    req = Request(
        f"{API_BASE_URL}/score/ai-commentary",
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(json.dumps({"status": exc.code, "body": body})) from exc
    except URLError as exc:
        raise ConnectionError(
            f"API indisponível em {API_BASE_URL}. Verifique se o uvicorn está rodando."
        ) from exc


def api_post_monitoring_run() -> dict[str, Any]:
    """POST /monitoring/run — executa checagens e grava relatório no MinIO."""
    req = Request(
        f"{API_BASE_URL}/monitoring/run",
        data=b"{}",
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(json.dumps({"status": exc.code, "body": body})) from exc
    except URLError as exc:
        raise ConnectionError(
            f"API indisponível em {API_BASE_URL}. Verifique se o uvicorn está rodando."
        ) from exc


def api_get_monitoring_latest() -> dict[str, Any]:
    """GET /monitoring/latest — último relatório publicado no lake."""
    req = Request(
        f"{API_BASE_URL}/monitoring/latest",
        method="GET",
        headers={"Accept": "application/json"},
    )
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(json.dumps({"status": exc.code, "body": body})) from exc
    except URLError as exc:
        raise ConnectionError(
            f"API indisponível em {API_BASE_URL}. Verifique se o uvicorn está rodando."
        ) from exc


def api_get_automation_latest() -> dict[str, Any]:
    """GET /automation/latest — último evento de triagem no lake."""
    req = Request(
        f"{API_BASE_URL}/automation/latest",
        method="GET",
        headers={"Accept": "application/json"},
    )
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(json.dumps({"status": exc.code, "body": body})) from exc
    except URLError as exc:
        raise ConnectionError(
            f"API indisponível em {API_BASE_URL}. Verifique se o uvicorn está rodando."
        ) from exc


def _parse_http_error(exc: RuntimeError) -> tuple[int | None, str]:
    try:
        payload = json.loads(str(exc))
        return payload.get("status"), payload.get("body", str(exc))
    except Exception:
        return None, str(exc)

