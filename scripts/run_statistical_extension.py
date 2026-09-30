from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.analytics import (  # noqa: E402
    load_order_items,
    load_orders,
    market_basket_rules,
    repurchase_analysis,
)
from src.modeling import (  # noqa: E402
    bootstrap_median_ci,
    bootstrap_rule_lift_ci,
    build_repurchase_snapshot_dataset,
    walk_forward_logistic_evaluation,
)

DATA = ROOT / "sample_data"
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)

orders_path = DATA / "synthetic_orders.csv"
items_path = DATA / "synthetic_order_items.csv"

if not orders_path.exists() or not items_path.exists():
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "generate_synthetic_data.py")],
        check=True,
    )

orders = load_orders(orders_path)
items = load_order_items(items_path)

repurchase = repurchase_analysis(orders)
median_ci = bootstrap_median_ci(repurchase["median_gap_days"], n_boot=5000)

rules = market_basket_rules(orders, items, min_support=0.015)
top_rule = rules.iloc[0]
lift_ci = bootstrap_rule_lift_ci(
    orders,
    items,
    antecedent=str(top_rule["antecedent"]),
    consequent=str(top_rule["consequent"]),
    n_boot=5000,
)

snapshots = ["2025-02-28", "2025-03-31", "2025-04-30", "2025-05-31"]
model_data = build_repurchase_snapshot_dataset(
    orders,
    snapshots,
    horizon_days=30,
)
evaluation, _ = walk_forward_logistic_evaluation(model_data, horizon_days=30)

model_data.to_csv(OUT / "repurchase_model_snapshots.csv", index=False)
evaluation.to_csv(OUT / "repurchase_model_walk_forward.csv", index=False)

summary = {
    "dataset": "synthetic demonstration data only",
    "uncertainty": {
        "median_repurchase_days": median_ci,
        "top_rule": {
            "antecedent": str(top_rule["antecedent"]),
            "consequent": str(top_rule["consequent"]),
            "lift": float(top_rule["lift"]),
            "lift_bootstrap_ci": lift_ci,
        },
    },
    "repurchase_model": {
        "target": "at least one valid purchase in the following 30 days",
        "validation": "expanding-window temporal holdout",
        "features": [
            "recency_days",
            "frequency_90d",
            "monetary_90d",
            "lifetime_orders",
            "lifetime_spend",
            "avg_order_value",
            "tenure_days",
        ],
        "walk_forward_results": [
            {
                "test_snapshot": row["test_snapshot"].strftime("%Y-%m-%d"),
                "train_rows": int(row["train_rows"]),
                "test_rows": int(row["test_rows"]),
                "positive_rate": round(float(row["positive_rate"]), 4),
                "roc_auc": round(float(row["roc_auc"]), 4),
                "average_precision": round(float(row["average_precision"]), 4),
                "brier_score": round(float(row["brier_score"]), 4),
            }
            for _, row in evaluation.iterrows()
        ],
        "mean_roc_auc": round(float(evaluation["roc_auc"].mean()), 4),
        "mean_average_precision": round(float(evaluation["average_precision"].mean()), 4),
        "mean_brier_score": round(float(evaluation["brier_score"].mean()), 4),
    },
}

with open(OUT / "statistical_extension_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)

print(json.dumps(summary, ensure_ascii=False, indent=2))
