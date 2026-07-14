"""Automação de crédito pós-escoragem (item iv): triagem e eventos auditáveis.

Classifica a proposta em faixas de ação a partir do score e persiste o evento
no Data Lake. Não concede crédito automaticamente — humano no loop.

As filas são pastas físicas no MinIO:
``s3://artifacts/automation/queues/{action}/``
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import s3fs

from scripts.model_config import get_model_config


LOGGER = logging.getLogger(__name__)

MINIO_ENDPOINT_URL = os.getenv("MINIO_ENDPOINT_URL", "http://minio:9000")
MINIO_ROOT_USER = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_ROOT_PASSWORD = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
AUTOMATION_EVENTS_PREFIX = os.getenv(
    "AUTOMATION_EVENTS_PREFIX",
    "s3://artifacts/automation/queues",
)
AUTOMATION_LATEST_PATH = os.getenv(
    "AUTOMATION_LATEST_PATH",
    "s3://artifacts/automation/latest.json",
)

# Filas físicas no Data Lake (pastas). A “fila” = prefixo S3 + campo action.
QUEUE_FOLDERS = (
    "autoaprovacao_candidata",
    "mesa_analise",
    "recusa_candidata",
)


def get_s3_filesystem() -> s3fs.S3FileSystem:
    """Cria filesystem S3 apontando para o MinIO."""
    return s3fs.S3FileSystem(
        key=MINIO_ROOT_USER,
        secret=MINIO_ROOT_PASSWORD,
        client_kwargs={"endpoint_url": MINIO_ENDPOINT_URL},
    )


def classify_triage_action(probability: float, threshold: float) -> str:
    """Mapeia probabilidade × threshold para fila de negócio.

    Faixas alinhadas às bandas de risco do motor (Baixo / Moderado / Alto):
    - abaixo de 40% do corte → autoaprovação *candidata*
    - entre 40% do corte e o corte → mesa de análise
    - no/acima do corte → recusa *candidata*
    """
    low_band = threshold * 0.4
    if probability < low_band:
        return "autoaprovacao_candidata"
    if probability < threshold:
        return "mesa_analise"
    return "recusa_candidata"


def triage_label(action: str) -> str:
    """Rótulo amigável da ação de triagem."""
    labels = {
        "autoaprovacao_candidata": "Autoaprovação candidata (humano confirma política)",
        "mesa_analise": "Encaminhar à mesa de crédito (zona cinzenta)",
        "recusa_candidata": "Recusa candidata (parecer + auditoria XAI)",
    }
    return labels.get(action, action)


def queue_prefix_for_action(action: str) -> str:
    """Retorna o prefixo S3 da fila correspondente à ação de triagem."""
    folder = action if action in QUEUE_FOLDERS else "mesa_analise"
    return f"{AUTOMATION_EVENTS_PREFIX.rstrip('/')}/{folder}"


def build_automation_event(score_result: dict[str, Any]) -> dict[str, Any]:
    """Monta evento auditável a partir do resultado de ``/score``."""
    config = get_model_config()
    probability = float(score_result["probability"])
    threshold = float(score_result.get("threshold", config.business_threshold))
    action = classify_triage_action(probability, threshold)
    client_id = int(score_result.get("sk_id_curr") or score_result.get("client_id"))

    return {
        "event_type": "credit_decision_triage",
        "emitted_at": datetime.now(timezone.utc).isoformat(),
        "client_id": client_id,
        "probability": probability,
        "prediction": int(score_result.get("prediction", 0)),
        "threshold": threshold,
        "risk_band": score_result.get("risk_band"),
        "label": score_result.get("label"),
        "action": action,
        "action_label": triage_label(action),
        "human_in_the_loop": True,
        "top_risk_factors": score_result.get("top_risk_factors") or [],
        "top_positive_factors": score_result.get("top_positive_factors") or [],
        "applied_overrides": score_result.get("applied_overrides") or {},
        "artifacts": {
            "model_path": config.resolve_model_artifact_path(),
            "metadata_path": config.resolve_metadata_path(),
        },
    }


def publish_automation_event(
    event: dict[str, Any],
    *,
    fs: s3fs.S3FileSystem | None = None,
) -> dict[str, Any]:
    """Grava o evento na pasta da fila, latest da fila e latest global."""
    active_fs = fs or get_s3_filesystem()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    client_id = event.get("client_id", "unknown")
    action = str(event.get("action") or "mesa_analise")
    queue_prefix = queue_prefix_for_action(action)
    event_path = f"{queue_prefix}/{stamp}_{client_id}.json"
    queue_latest_path = f"{queue_prefix}/latest.json"
    payload = json.dumps(event, ensure_ascii=False, indent=2).encode("utf-8")

    for path in (event_path, queue_latest_path, AUTOMATION_LATEST_PATH):
        parent = path.rsplit("/", 1)[0]
        active_fs.makedirs(parent, exist_ok=True)
        with active_fs.open(path, "wb") as handle:
            handle.write(payload)

    LOGGER.info(
        "Evento de automação publicado: action=%s queue=%s path=%s",
        action,
        queue_prefix,
        event_path,
    )
    return {
        **event,
        "storage": {
            "event_path": event_path,
            "queue_prefix": queue_prefix,
            "queue_latest_path": queue_latest_path,
            "latest_path": AUTOMATION_LATEST_PATH,
        },
    }


def emit_from_score(
    score_result: dict[str, Any],
    *,
    fs: s3fs.S3FileSystem | None = None,
) -> dict[str, Any]:
    """Atalho: classifica e publica a partir do dicionário de escoragem."""
    event = build_automation_event(score_result)
    return publish_automation_event(event, fs=fs)
