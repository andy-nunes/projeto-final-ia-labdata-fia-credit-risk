"""Formatadores e helpers de apresentação de valores."""

from __future__ import annotations

import math
from typing import Any

from app.ui.constants import (
    DURATION_FEATURES,
    FEATURE_TRANSLATIONS,
    MONEY_READONLY_FEATURES,
    SCORE_FEATURES,
)

def _get_label(tech_name: str) -> str:
    """Retorna apenas o nome comercial; fallback para o nome técnico limpo."""
    return FEATURE_TRANSLATIONS.get(tech_name, tech_name)

def _is_missing_value(value: Any) -> bool:
    """Indica se o valor deve ser tratado como ausência de informação."""
    if value is None or value == "":
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    try:
        import pandas as pd

        if pd.isna(value):
            return True
    except (ImportError, TypeError, ValueError):
        pass
    return False

def _format_duration_from_days(abs_days: float) -> str:
    """Converte dias absolutos em meses (<12) ou anos inteiros (>=12 meses)."""
    months = abs_days / (365.25 / 12.0)
    if months < 12:
        return f"{int(round(months))} meses"
    return f"{int(abs_days / 365.25)} anos"

def _format_delay_mean(abs_days: float) -> str:
    """Formata média de atraso em dias, meses ou anos conforme a magnitude."""
    if abs_days < 30:
        return f"{int(round(abs_days))} dias"
    if abs_days < 365:
        months = abs_days / (365.25 / 12.0)
        return f"{int(round(months))} meses"
    return f"{int(abs_days / 365.25)} anos"

def _format_brl(value: float) -> str:
    """Formata número no padrão monetário brasileiro (R$ 1.250.600,00)."""
    formatted = f"{value:,.2f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"

def _parse_money_input(raw_value: Any) -> float | None:
    """Tenta converter texto de input monetário em float; None se inválido."""
    if raw_value is None:
        return None
    text = str(raw_value).strip()
    if not text or text == "Sem Info":
        return None
    normalized = text.replace("R$", "").replace(" ", "")
    if "," in normalized and "." in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")
    elif "," in normalized:
        normalized = normalized.replace(",", ".")
    try:
        parsed = float(normalized)
    except ValueError:
        return None
    if math.isnan(parsed):
        return None
    return parsed

def _is_binary_flag_column(col_name: str) -> bool:
    """Indica se a coluna segue o padrão de flag binária da ABT."""
    return (
        col_name.startswith(("FLAG_", "REG_", "LIVE_", "HAS_"))
        or col_name.endswith("_FLAG")
    )

def _is_days_column(col_name: str) -> bool:
    """Indica se a coluna representa duração/tempo em dias."""
    return "DAYS_" in col_name or "_DAYS_" in col_name

def _is_count_like_column(col_name: str) -> bool:
    """Indica se a coluna representa contagem, hora ou dia (inteiro limpo)."""
    if _is_days_column(col_name):
        return False
    return (
        col_name in {"CNT_CHILDREN", "CNT_FAM_MEMBERS"}
        or col_name.startswith(("CNT_", "HOUR_"))
        or "_CNT_" in col_name
        or col_name.endswith(("_CNT", "_HOUR", "_DAY"))
        or "_HOUR" in col_name
    )

def _format_readonly_value(col_name: str, value: Any) -> str:
    """Formata valor somente leitura com unidades comerciais de negócio."""
    if _is_missing_value(value):
        return "Sem Info"

    val_str = str(value).strip()
    if not val_str:
        return "Sem Info"

    # Flags binárias: cobre 0/1 e Y/N antes da conversão numérica estrita.
    if _is_binary_flag_column(col_name):
        upper = val_str.upper()
        if upper in {"1", "1.0", "Y", "YES"}:
            return "Sim"
        if upper in {"0", "0.0", "N", "NO"}:
            return "Não"

    try:
        num_val = float(value)
        if math.isnan(num_val):
            return "Sem Info"
    except (TypeError, ValueError):
        return val_str

    if _is_binary_flag_column(col_name):
        if num_val == 1.0:
            return "Sim"
        if num_val == 0.0:
            return "Não"

    if col_name in SCORE_FEATURES:
        return str(int(round(num_val * 1000)))

    if col_name == "DAYS_BIRTH":
        return f"{int(abs(num_val) / 365.25)} anos"

    if col_name in DURATION_FEATURES:
        return _format_duration_from_days(abs(num_val))

    if col_name == "INST_DIAS_ATRASO_MEAN":
        return _format_delay_mean(abs(num_val))

    if col_name in MONEY_READONLY_FEATURES:
        return _format_brl(num_val)

    if _is_days_column(col_name):
        return _format_delay_mean(abs(num_val))

    if _is_count_like_column(col_name) and num_val == int(num_val):
        return str(int(num_val))

    return val_str

def _safe_str(value: Any) -> str:
    if value is None:
        return "Sem Info"
    try:
        import math

        if isinstance(value, float) and math.isnan(value):
            return "Sem Info"
    except Exception:
        pass
    text = str(value).strip()
    if not text:
        return "Sem Info"
    return text

def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default

def _is_approved(result: dict[str, Any]) -> bool:
    label = str(result.get("label", "")).lower()
    band = str(result.get("risk_band", "")).lower()
    prediction = result.get("prediction")
    if prediction == 0 or "aprovado" in label or "baixo" in band:
        return True
    return False

def _format_int_br(value: int) -> str:
    return f"{int(value):,}".replace(",", ".")

def _format_pct_br(value: float, *, digits: int = 1) -> str:
    return f"{value * 100:.{digits}f}%".replace(".", ",")

def _format_decimal_br(value: float, *, digits: int = 4) -> str:
    return f"{value:.{digits}f}".replace(".", ",")

def _format_risk_pct(value: float) -> str:
    return f"{float(value) * 100:.2f}%"

