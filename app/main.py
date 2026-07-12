"""
API principal do sistema de escoragem de crédito usando FastAPI.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sys
import os
from typing import Dict, Any, Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.model_config import get_model_config
from scripts.predict import predict_by_client_id, fetch_client_data_by_id

_CONFIG = get_model_config()

app = FastAPI(
    title="API de Risco de Crédito - Home Credit",
    version="1.0.0"
)

# Atualizado para receber os dados editados pelo gerente
class ClientRequest(BaseModel):
    client_id: int
    features_override: Optional[Dict[str, Any]] = None

@app.get("/")
def health_check():
    return {
        "status": "Serviço de escoragem online e operacional.",
        "business_threshold": _CONFIG.business_threshold,
        "id_column": _CONFIG.id_column,
    }

# NOVA ROTA: Busca os dados do cliente para preencher a tela do Streamlit
@app.get("/client/{client_id}")
def get_client(client_id: int):
    """
    Busca os dados cadastrais do cliente no rastro do Bureau para popular
    os campos da interface de simulação do Streamlit.
    """
    try:
        df = fetch_client_data_by_id(client_id)
        
        # Serializa tipos de dados específicos do ecossistema Pandas (como int64 e float64) 
        # para tipos primitivos do Python compatíveis com o padrão de resposta JSON
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
        # Passa o dicionário de overrides para o motor de predição
        resultado = predict_by_client_id(request.client_id, overrides=request.features_override)
        return resultado
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de inferência: {str(e)}")