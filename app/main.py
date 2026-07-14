"""
API principal do sistema de escoragem de crédito usando FastAPI.
"""
from functools import lru_cache
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
import sys
import os
from typing import Dict, Any, Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.credit_automation import AUTOMATION_LATEST_PATH, emit_from_score
from scripts.mlops_monitoring import (
    MONITORING_LATEST_PATH,
    get_s3_filesystem,
    run_monitoring,
)
from scripts.model_config import get_model_config
from scripts.predict import predict_by_client_id, fetch_client_data_by_id

_CONFIG = get_model_config()

app = FastAPI(
    title="API de Risco de Crédito - Home Credit",
    version="1.0.0"
)


@lru_cache(maxsize=1)
def _catalog_explorer_html() -> str:
    """HTML do catalogo ABT, isolado da UI Streamlit para evitar segfault."""
    from app.abt_catalog import build_catalog_frame, render_catalog_explorer_html

    return render_catalog_explorer_html(build_catalog_frame())


class ClientRequest(BaseModel):
    client_id: int
    features_override: Optional[Dict[str, Any]] = None
    emit_automation: bool = Field(
        default=True,
        description="Se true, publica evento de triagem no MinIO após o score.",
    )


class AutomationWebhookRequest(BaseModel):
    """Payload opcionalmente igual ao retorno de /score (webhook externo)."""
    sk_id_curr: Optional[int] = None
    client_id: Optional[int] = None
    probability: float
    prediction: int
    threshold: Optional[float] = None
    risk_band: Optional[str] = None
    label: Optional[str] = None
    top_risk_factors: Optional[list] = None
    top_positive_factors: Optional[list] = None
    applied_overrides: Optional[Dict[str, Any]] = None


@app.get("/")
def health_check():
    return {
        "status": "Serviço de escoragem online e operacional.",
        "business_threshold": _CONFIG.business_threshold,
        "id_column": _CONFIG.id_column,
    }


@app.get("/client/{client_id}")
def get_client(client_id: int):
    """
    Busca os dados cadastrais do cliente no rastro do Bureau para popular
    os campos da interface de simulação do Streamlit.
    """
    try:
        df = fetch_client_data_by_id(client_id)

        import json
        features_dict = json.loads(df.iloc[0].to_json())

        return {"features": features_dict}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/score")
def get_score(request: ClientRequest):
    try:
        resultado = predict_by_client_id(
            request.client_id, overrides=request.features_override
        )
        if request.emit_automation:
            try:
                automation = emit_from_score(resultado)
                resultado = {
                    **resultado,
                    "automation": {
                        "action": automation.get("action"),
                        "action_label": automation.get("action_label"),
                        "human_in_the_loop": True,
                        "event_path": automation.get("storage", {}).get("event_path"),
                        "latest_path": automation.get("storage", {}).get("latest_path"),
                    },
                }
            except Exception as auto_exc:  # noqa: BLE001 — score não deve falhar
                resultado = {
                    **resultado,
                    "automation": {
                        "error": str(auto_exc),
                        "human_in_the_loop": True,
                    },
                }
        return resultado
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de inferência: {str(e)}")


@app.post("/webhooks/credit-decision")
def credit_decision_webhook(payload: AutomationWebhookRequest):
    """Webhook de automação: recebe um score e publica evento de triagem no lake."""
    try:
        score_like = payload.model_dump(exclude_none=True)
        if "sk_id_curr" not in score_like and "client_id" in score_like:
            score_like["sk_id_curr"] = score_like["client_id"]
        if "threshold" not in score_like:
            score_like["threshold"] = _CONFIG.business_threshold
        return emit_from_score(score_like)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Falha ao publicar evento de automação: {e}"
        ) from e


@app.get("/monitoring/latest")
def get_monitoring_latest():
    """Lê o último relatório de monitoramento publicado no MinIO."""
    import json

    path = MONITORING_LATEST_PATH
    try:
        fs = get_s3_filesystem()
        with fs.open(path, "rb") as handle:
            return json.loads(handle.read().decode("utf-8"))
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Relatório ausente em {path}. "
                "Dispare a DAG 05_monitor_health ou POST /monitoring/run."
            ),
        ) from e


@app.post("/monitoring/run")
def run_monitoring_endpoint():
    """Executa o monitoramento sob demanda (mesma lógica da DAG 05)."""
    try:
        return run_monitoring(fail_on_error=False)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Falha ao executar monitoramento: {e}"
        ) from e


@app.get("/automation/latest")
def get_automation_latest():
    """Lê o último evento de triagem publicado no MinIO."""
    import json

    path = AUTOMATION_LATEST_PATH
    try:
        fs = get_s3_filesystem()
        with fs.open(path, "rb") as handle:
            return json.loads(handle.read().decode("utf-8"))
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Evento ausente em {path}. "
                "Escorare um cliente com emit_automation=true ou chame "
                "POST /webhooks/credit-decision."
            ),
        ) from e


@app.get("/catalog/abt", response_class=HTMLResponse)
def get_catalog_abt():
    """Serve o explorador HTML do catalogo para iframe no Streamlit."""
    try:
        return HTMLResponse(content=_catalog_explorer_html())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha ao montar catálogo: {e}") from e
