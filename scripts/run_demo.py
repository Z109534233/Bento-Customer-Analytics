from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.analytics import (  # noqa: E402
    annualized_customer_value,
    churn_heuristic,
    customer_product_preferences,
    load_order_items,
    load_orders,
    market_basket_rules,
    repurchase_analysis,
    rfm_analysis,
    valid_orders,
)

DATA = ROOT / "sample_data"
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)

orders = load_orders(DATA / "synthetic_orders.csv")
items = load_order_items(DATA / "synthetic_order_items.csv")
reference_date = "2025-06-30"

rfm = rfm_analysis(orders, reference_date)
repurchase = repurchase_analysis(orders)
value = annualized_customer_value(orders, reference_date)
churn = churn_heuristic(orders, reference_date)
rules = market_basket_rules(orders, items, min_support=0.015)
preferences = customer_product_preferences(orders, items)

rfm.to_csv(OUT / "rfm_segments.csv", index=False)
repurchase.to_csv(OUT / "repurchase_customers.csv", index=False)
value.to_csv(OUT / "annualized_customer_value.csv", index=False)
churn.to_csv(OUT / "churn_heuristic.csv", index=False)
rules.head(100).to_csv(OUT / "market_basket_rules.csv", index=False)
preferences.to_csv(OUT / "customer_preferences.csv", index=False)

valid = valid_orders(orders)
summary = {
    "dataset": "synthetic demonstration data only",
    "reference_date": reference_date,
    "valid_orders": int(valid["order_id"].nunique()),
    "customers": int(valid["customer_id"].nunique()),
    "revenue": round(float(valid["total_amount"].sum()), 2),
    "rfm_segments": {str(k): int(v) for k, v in rfm["segment"].value_counts().to_dict().items()},
    "churn_levels": {str(k): int(v) for k, v in churn["risk_level"].value_counts().to_dict().items()},
    "repurchase_customers": int(len(repurchase)),
    "median_repurchase_gap_days": round(float(repurchase["median_gap_days"].median()), 1) if len(repurchase) else None,
    "top_market_basket_rule": rules.iloc[0].to_dict() if len(rules) else None,
}

with open(OUT / "demo_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)

print(json.dumps(summary, ensure_ascii=False, indent=2))
