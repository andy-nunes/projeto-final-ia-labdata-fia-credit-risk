"""Transformações base para construir a tabela analítica da camada Gold."""

from __future__ import annotations

from collections.abc import Collection, Mapping

import numpy as np
import pandas as pd


BUREAU_OVERDUE_STATUS = {"1", "2", "3", "4", "5"}

BUREAU_AGGREGATIONS = {
    "BUREAU_CNT_CREDITS": ("SK_ID_BUREAU", "count"),
    "BUREAU_CNT_ACTIVE": ("IS_ACTIVE", "sum"),
    "BUREAU_CNT_CLOSED": ("IS_CLOSED", "sum"),
    "BUREAU_CNT_BAD_DEBT": ("IS_BAD_DEBT", "sum"),
    "BUREAU_AMT_CREDIT_SUM_SUM": ("AMT_CREDIT_SUM", "sum"),
    "BUREAU_AMT_CREDIT_SUM_MEAN": ("AMT_CREDIT_SUM", "mean"),
    "BUREAU_AMT_CREDIT_SUM_MAX": ("AMT_CREDIT_SUM", "max"),
    "BUREAU_AMT_DEBT_SUM": ("AMT_CREDIT_SUM_DEBT", "sum"),
    "BUREAU_AMT_OVERDUE_SUM": ("AMT_CREDIT_SUM_OVERDUE", "sum"),
    "BUREAU_AMT_OVERDUE_MAX": ("AMT_CREDIT_SUM_OVERDUE", "max"),
    "BUREAU_CREDIT_DAY_OVERDUE_MAX": ("CREDIT_DAY_OVERDUE", "max"),
    "BUREAU_DAYS_CREDIT_MIN": ("DAYS_CREDIT", "min"),
}


def _safe_ratio(num: pd.Series, den: pd.Series) -> pd.Series:
    """Divide duas séries substituindo denominadores iguais a zero por nulo."""
    return num / den.replace(0, np.nan)


def enrich_application(frame: pd.DataFrame) -> pd.DataFrame:
    """Copia application e cria somente as features cujas entradas existem."""
    enriched = frame.copy()
    ext_columns = [
        column
        for column in ("EXT_SOURCE_1", "EXT_SOURCE_2", "EXT_SOURCE_3")
        if column in enriched.columns
    ]

    if ext_columns:
        enriched["EXT_SOURCE_MEAN"] = enriched[ext_columns].mean(
            axis=1, skipna=True
        )
        enriched["EXT_SOURCE_CNT"] = enriched[ext_columns].notna().sum(axis=1)
        for column in ext_columns:
            enriched[f"FLAG_{column}_MISSING"] = (
                enriched[column].isna().astype("int8")
            )

    if {"AMT_CREDIT", "AMT_INCOME_TOTAL"}.issubset(enriched.columns):
        enriched["CREDIT_INCOME_RATIO"] = _safe_ratio(
            enriched["AMT_CREDIT"], enriched["AMT_INCOME_TOTAL"]
        )

    if {"AMT_ANNUITY", "AMT_INCOME_TOTAL"}.issubset(enriched.columns):
        enriched["ANNUITY_INCOME_RATIO"] = _safe_ratio(
            enriched["AMT_ANNUITY"], enriched["AMT_INCOME_TOTAL"]
        )

    if "AMT_CREDIT" in enriched.columns:
        enriched["LOG_AMT_CREDIT"] = np.log1p(
            enriched["AMT_CREDIT"].clip(lower=0)
        )

    if "DAYS_EMPLOYED" in enriched.columns:
        enriched["DAYS_EMPLOYED_YEARS"] = (
            enriched["DAYS_EMPLOYED"].abs() / 365.25
        )

    return enriched


def filter_train_clients(
    frame: pd.DataFrame,
    train_ids: Collection[int],
    label: str,
) -> pd.DataFrame:
    """Restringe a tabela aos clientes de treino e registra a volumetria."""
    before = len(frame)
    filtered = frame[frame["SK_ID_CURR"].isin(train_ids)].copy()
    print(
        f" -> Filtro train_ids em {label}: {before:,} -> {len(filtered):,} linhas"
    )
    return filtered


def aggregate_bureau(
    frame: pd.DataFrame,
    train_ids: Collection[int],
) -> pd.DataFrame:
    """Agrega contratos bureau por cliente seguindo as regras do notebook."""
    print("\n[GOLD] Agregando bureau_silver")
    filtered = filter_train_clients(frame, train_ids, "bureau")
    filtered["IS_ACTIVE"] = (filtered["CREDIT_ACTIVE"] == "ACTIVE").astype("int8")
    filtered["IS_CLOSED"] = (filtered["CREDIT_ACTIVE"] == "CLOSED").astype("int8")
    filtered["IS_BAD_DEBT"] = (
        filtered["CREDIT_ACTIVE"] == "BAD DEBT"
    ).astype("int8")

    aggregated = filtered.groupby("SK_ID_CURR", as_index=False).agg(
        **BUREAU_AGGREGATIONS
    )
    aggregated["HAS_BUREAU"] = np.int8(1)
    print(f" -> {len(aggregated):,} clientes com histórico bureau")
    return aggregated


def aggregate_bureau_balance(
    frame: pd.DataFrame,
    bureau_mapping: pd.DataFrame,
    train_ids: Collection[int],
) -> pd.DataFrame:
    """Agrega histórico mensal bureau e faz a ponte contrato-cliente."""
    print("\n[GOLD] Agregando bureau_balance_silver")
    balance = frame.copy()
    balance["IS_OVERDUE"] = balance["STATUS"].isin(BUREAU_OVERDUE_STATUS).astype("int8")
    balance["IS_CLOSED"] = (balance["STATUS"] == "C").astype("int8")
    balance["IS_UNKNOWN"] = (balance["STATUS"] == "X").astype("int8")

    per_bureau = balance.groupby("SK_ID_BUREAU", as_index=False).agg(
        BB_CNT_MONTHS=("MONTHS_BALANCE", "count"),
        BB_CNT_OVERDUE=("IS_OVERDUE", "sum"),
        BB_CNT_CLOSED=("IS_CLOSED", "sum"),
        BB_CNT_UNKNOWN=("IS_UNKNOWN", "sum"),
    )
    per_bureau["BB_RATE_OVERDUE"] = _safe_ratio(
        per_bureau["BB_CNT_OVERDUE"], per_bureau["BB_CNT_MONTHS"]
    )

    mapping = bureau_mapping[["SK_ID_BUREAU", "SK_ID_CURR"]].drop_duplicates()
    merged = per_bureau.merge(
        mapping,
        on="SK_ID_BUREAU",
        how="inner",
        validate="many_to_one",
    )
    merged = filter_train_clients(merged, train_ids, "bureau_balance (pós-join)")
    aggregated = merged.groupby("SK_ID_CURR", as_index=False).agg(
        BB_CNT_MONTHS=("BB_CNT_MONTHS", "sum"),
        BB_CNT_OVERDUE=("BB_CNT_OVERDUE", "sum"),
        BB_CNT_CLOSED=("BB_CNT_CLOSED", "sum"),
        BB_CNT_UNKNOWN=("BB_CNT_UNKNOWN", "sum"),
        BB_RATE_OVERDUE_MAX=("BB_RATE_OVERDUE", "max"),
        BB_RATE_OVERDUE_MEAN=("BB_RATE_OVERDUE", "mean"),
        BB_CONTRACTS_WITH_OVERDUE=(
            "BB_CNT_OVERDUE",
            lambda values: int((values > 0).sum()),
        ),
    )
    aggregated["HAS_BUREAU_BALANCE"] = np.int8(1)
    print(f" -> {len(aggregated):,} clientes com histórico bureau_balance")
    return aggregated


def aggregate_pos_cash(
    frame: pd.DataFrame,
    train_ids: Collection[int],
) -> pd.DataFrame:
    """Agrega meses, contratos e atrasos POS/CASH por cliente."""
    print("\n[GOLD] Agregando POS_CASH_balance_silver")
    filtered = filter_train_clients(frame, train_ids, "POS_CASH")
    filtered["DPD_GT0"] = (filtered["SK_DPD"] > 0).astype("int8")
    aggregated = filtered.groupby("SK_ID_CURR", as_index=False).agg(
        POS_CNT_MONTHS=("MONTHS_BALANCE", "count"),
        POS_SK_DPD_MAX=("SK_DPD", "max"),
        POS_SK_DPD_MEAN=("SK_DPD", "mean"),
        POS_CNT_DPD_GT0=("DPD_GT0", "sum"),
        POS_CNT_CONTRACTS=("SK_ID_PREV", "nunique"),
    )
    aggregated["POS_RATE_DPD"] = _safe_ratio(
        aggregated["POS_CNT_DPD_GT0"], aggregated["POS_CNT_MONTHS"]
    )
    aggregated["HAS_POS_CASH"] = np.int8(1)
    print(f" -> {len(aggregated):,} clientes com POS_CASH")
    return aggregated


def aggregate_credit_card(
    frame: pd.DataFrame,
    train_ids: Collection[int],
) -> pd.DataFrame:
    """Agrega utilização, atrasos, saldos e saques de cartão por cliente."""
    print("\n[GOLD] Agregando credit_card_balance_silver")
    filtered = filter_train_clients(frame, train_ids, "credit_card")
    filtered["DPD_GT0"] = (filtered["SK_DPD"] > 0).astype("int8")
    filtered["UTILIZATION"] = _safe_ratio(
        filtered["AMT_BALANCE"], filtered["AMT_CREDIT_LIMIT_ACTUAL"]
    )
    aggregated = filtered.groupby("SK_ID_CURR", as_index=False).agg(
        CC_CNT_MONTHS=("MONTHS_BALANCE", "count"),
        CC_SK_DPD_MAX=("SK_DPD", "max"),
        CC_SK_DPD_MEAN=("SK_DPD", "mean"),
        CC_CNT_DPD_GT0=("DPD_GT0", "sum"),
        CC_AMT_BALANCE_MEAN=("AMT_BALANCE", "mean"),
        CC_AMT_BALANCE_MAX=("AMT_BALANCE", "max"),
        CC_AMT_LIMIT_MEAN=("AMT_CREDIT_LIMIT_ACTUAL", "mean"),
        CC_UTILIZATION_MEAN=("UTILIZATION", "mean"),
        CC_UTILIZATION_MAX=("UTILIZATION", "max"),
        CC_CNT_DRAWINGS_ATM_SUM=("CNT_DRAWINGS_ATM_CURRENT", "sum"),
    )
    aggregated["CC_RATE_DPD"] = _safe_ratio(
        aggregated["CC_CNT_DPD_GT0"], aggregated["CC_CNT_MONTHS"]
    )
    aggregated["HAS_CREDIT_CARD"] = np.int8(1)
    print(f" -> {len(aggregated):,} clientes com cartão")
    return aggregated


def aggregate_previous_application(
    frame: pd.DataFrame,
    train_ids: Collection[int],
) -> pd.DataFrame:
    """Agrega propostas anteriores, status, montantes e taxas por cliente."""
    print("\n[GOLD] Agregando previous_application_silver")
    filtered = filter_train_clients(frame, train_ids, "previous_application")
    filtered["IS_APPROVED"] = (
        filtered["NAME_CONTRACT_STATUS"] == "APPROVED"
    ).astype("int8")
    filtered["IS_REFUSED"] = (
        filtered["NAME_CONTRACT_STATUS"] == "REFUSED"
    ).astype("int8")
    filtered["IS_CANCELED"] = (
        filtered["NAME_CONTRACT_STATUS"] == "CANCELED"
    ).astype("int8")
    aggregated = filtered.groupby("SK_ID_CURR", as_index=False).agg(
        PREV_CNT_APPS=("SK_ID_PREV", "count"),
        PREV_CNT_APPROVED=("IS_APPROVED", "sum"),
        PREV_CNT_REFUSED=("IS_REFUSED", "sum"),
        PREV_CNT_CANCELED=("IS_CANCELED", "sum"),
        PREV_AMT_APPLICATION_MEAN=("AMT_APPLICATION", "mean"),
        PREV_AMT_APPLICATION_MAX=("AMT_APPLICATION", "max"),
        PREV_AMT_CREDIT_MEAN=("AMT_CREDIT", "mean"),
        PREV_DAYS_DECISION_MIN=("DAYS_DECISION", "min"),
    )
    aggregated["PREV_APPROVAL_RATE"] = _safe_ratio(
        aggregated["PREV_CNT_APPROVED"], aggregated["PREV_CNT_APPS"]
    )
    aggregated["PREV_REFUSAL_RATE"] = _safe_ratio(
        aggregated["PREV_CNT_REFUSED"], aggregated["PREV_CNT_APPS"]
    )
    aggregated["HAS_PREVIOUS_APP"] = np.int8(1)
    print(f" -> {len(aggregated):,} clientes com previous_application")
    return aggregated


def aggregate_installments(
    frame: pd.DataFrame,
    train_ids: Collection[int],
) -> pd.DataFrame:
    """Colapsa pagamentos fracionados e agrega parcelas por cliente."""
    print("\n[GOLD] Agregando installments_payments_silver")
    filtered = filter_train_clients(frame, train_ids, "installments")
    installment = filtered.groupby(
        ["SK_ID_PREV", "SK_ID_CURR", "NUM_INSTALMENT_NUMBER"],
        as_index=False,
    ).agg(
        AMT_INSTALMENT=("AMT_INSTALMENT", "max"),
        AMT_PAYMENT=("AMT_PAYMENT", "sum"),
        DIAS_DE_ATRASO=("DIAS_DE_ATRASO", "max"),
    )
    installment["AMT_GAP"] = (
        installment["AMT_INSTALMENT"] - installment["AMT_PAYMENT"]
    ).clip(lower=0)
    installment["FLAG_ATRASO"] = (
        installment["DIAS_DE_ATRASO"] > 0
    ).astype("int8")
    installment["FLAG_CALOTE"] = (
        installment["AMT_PAYMENT"] == 0
    ).astype("int8")
    installment["FLAG_UNDERPAY"] = (installment["AMT_GAP"] > 0).astype("int8")
    print(f" -> Passo 1: {len(installment):,} parcelas únicas (pós-fracionamento)")

    aggregated = installment.groupby("SK_ID_CURR", as_index=False).agg(
        INST_CNT_PARCELAS=("NUM_INSTALMENT_NUMBER", "count"),
        INST_AMT_INSTALMENT_SUM=("AMT_INSTALMENT", "sum"),
        INST_AMT_PAYMENT_SUM=("AMT_PAYMENT", "sum"),
        INST_AMT_GAP_SUM=("AMT_GAP", "sum"),
        INST_DIAS_ATRASO_MEAN=("DIAS_DE_ATRASO", "mean"),
        INST_DIAS_ATRASO_MAX=("DIAS_DE_ATRASO", "max"),
        INST_CNT_ATRASO=("FLAG_ATRASO", "sum"),
        INST_CNT_CALOTE=("FLAG_CALOTE", "sum"),
        INST_CNT_UNDERPAY=("FLAG_UNDERPAY", "sum"),
    )
    aggregated["INST_PAYMENT_RATIO"] = _safe_ratio(
        aggregated["INST_AMT_PAYMENT_SUM"],
        aggregated["INST_AMT_INSTALMENT_SUM"],
    )
    aggregated["INST_RATE_ATRASO"] = _safe_ratio(
        aggregated["INST_CNT_ATRASO"], aggregated["INST_CNT_PARCELAS"]
    )
    aggregated["INST_RATE_CALOTE"] = _safe_ratio(
        aggregated["INST_CNT_CALOTE"], aggregated["INST_CNT_PARCELAS"]
    )
    aggregated["INST_RATE_UNDERPAY"] = _safe_ratio(
        aggregated["INST_CNT_UNDERPAY"], aggregated["INST_CNT_PARCELAS"]
    )
    aggregated["HAS_INSTALLMENTS"] = np.int8(1)
    print(f" -> Passo 2: {len(aggregated):,} clientes com installments")
    return aggregated


def build_abt_train(
    application: pd.DataFrame,
    aggregates: Mapping[str, pd.DataFrame],
) -> pd.DataFrame:
    """Une agregados à application preservando a ordem recebida e os nulos."""
    print("\n[GOLD] Merge final — abt_train")
    if application["SK_ID_CURR"].duplicated().any():
        raise ValueError("application contém SK_ID_CURR duplicado")

    abt = application.copy()
    base_rows = len(abt)

    for name, aggregate in aggregates.items():
        if aggregate["SK_ID_CURR"].duplicated().any():
            raise ValueError(
                f"Agregado {name} contém SK_ID_CURR duplicado"
            )
        columns_before = set(abt.columns)
        abt = abt.merge(
            aggregate,
            on="SK_ID_CURR",
            how="left",
            suffixes=("", f"_{name}"),
            validate="one_to_one",
        )
        new_columns = [
            column for column in abt.columns if column not in columns_before
        ]
        print(f" -> JOIN {name}: +{len(new_columns)} colunas | shape {abt.shape}")

    has_flags = [column for column in abt.columns if column.startswith("HAS_")]
    for column in has_flags:
        invalid = abt[column].notna() & ~abt[column].isin([0, 1])
        if invalid.any():
            raise ValueError(f"{column} deve conter somente 0, 1 ou nulo")
        abt[column] = abt[column].fillna(0).astype("int8")
    print(
        " -> Flags HAS_* preenchidas com 0 onde ausente "
        f"({len(has_flags)} flags)"
    )

    if len(abt) == base_rows:
        print(f" -> [PASS] Volumetria preservada ({base_rows:,} linhas)")
    else:
        print(f" -> [FAIL] linhas após merge: {len(abt):,}")
    return abt
