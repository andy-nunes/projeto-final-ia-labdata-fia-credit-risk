"""Relatório da matriz de confusão no split de teste (threshold de negócio).

Usa o mesmo particionamento de 3 vias do treino (`split_abt_three_way`),
para o resultado bater com `artifacts/model_metadata.json`.
"""

import pandas as pd
from sklearn.metrics import confusion_matrix

from scripts.train import compute_metrics, split_abt_three_way
from scripts.model_config import get_model_config
from scripts.predict import (
    build_prediction_matrix,
    load_model,
    normalize_prediction_input,
)


def main() -> None:
    model = load_model()
    config = get_model_config()

    df_full = pd.read_parquet(config.resolve_abt_path())
    threshold = config.business_threshold

    _, df_test, _ = split_abt_three_way(df_full, config)

    print(
        f"✓ Base de Teste isolada com sucesso: {len(df_test):,} linhas "
        f"({(len(df_test) / len(df_full)):.1%} da ABT Full) "
        "[split oficial 3 vias do treino]"
    )

    y_true = df_test[config.target_column].astype(int)
    X_pred = build_prediction_matrix(df_test, config)
    X_pred_norm = normalize_prediction_input(model, X_pred)

    probs = model.predict_proba(X_pred_norm)[:, 1]
    y_pred = (probs >= threshold).astype(int)
    metrics = compute_metrics(y_true.to_numpy(), probs, config)

    cm = confusion_matrix(y_true, y_pred)
    cm_df = pd.DataFrame(
        cm,
        index=["Real: Adimplente (0)", "Real: Inadimplente (1)"],
        columns=["Previsto: Aprovado (0)", "Previsto: Reprovado (1)"],
    )

    print(
        "\n================= MATRIZ DE CONFUSÃO OFICIAL "
        f"(TEST SPLIT {config.split_test:.1%} - THRESHOLD {threshold:.0%}) ================="
    )
    print(cm_df.to_string())
    print(
        "================================================================"
        "================================\n"
    )

    vn, fp, fn, vp = cm.ravel()
    total = len(y_true)
    defaults_total = int((y_true == 1).sum())
    print("--- DIAGNÓSTICO PARA O SLIDE DE AVALIAÇÃO ---")
    print(
        f"✓ Verdadeiros Negativos (Aprovados em dia)       : "
        f"{vn:6d} ({vn / total:.1%})"
    )
    print(
        f"✓ Verdadeiros Positivos (Calotes barrados)       : "
        f"{vp:6d} ({vp / total:.1%})"
    )
    print(
        f"⚠ Falsos Positivos    (Bons clientes reprovados) : "
        f"{fp:6d} ({fp / total:.1%}) | Custo de Oportunidade"
    )
    print(
        f"🛑 Falsos Negativos    (Calotes aprovados)        : "
        f"{fn:6d} ({fn / total:.1%}) | ERRO CRÍTICO MINIMIZADO"
    )
    print("---------------------------------------------")
    print("--- MÉTRICAS DE DISCRIMINAÇÃO E CAPTURA ---")
    print(
        f"Recall (inadimplentes barrados)                 : "
        f"{metrics['recall_inadimplente']:.2%} "
        f"({vp:,} de {defaults_total:,} calotes reais)"
    )
    print(
        f"Precision (reprovados que eram calotes)         : "
        f"{metrics['precision_inadimplente']:.2%}"
    )
    print(f"ROC-AUC (área sob curva ROC)                    : {metrics['roc_auc']:.4f}")
    print(f"PR-AUC  (área sob curva Precision-Recall)       : {metrics['pr_auc']:.4f}")
    print(f"F2-Score (β={config.f_beta:g}, prioriza recall)              : {metrics['f2']:.4f}")
    print(
        f"Taxa de reprovação no threshold {threshold:.0%}           : "
        f"{metrics['taxa_reprovacao']:.2%}"
    )
    print("---------------------------------------------")


if __name__ == "__main__":
    main()
