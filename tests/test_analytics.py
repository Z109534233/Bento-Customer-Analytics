from pathlib import Path
import sys

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.analytics import (  # noqa: E402
    annualized_customer_value,
    churn_heuristic,
    customer_product_preferences,
    load_orders,
    market_basket_rules,
    repurchase_analysis,
    rfm_analysis,
    valid_orders,
)


def _orders():
    return pd.DataFrame(
        [
            ["O1", "C1", "completed", pd.Timestamp("2025-06-29"), 600],
            ["O2", "C1", "completed", pd.Timestamp("2025-06-30"), 700],
            ["O3", "C2", "completed", pd.Timestamp("2025-05-01"), 200],
            ["O4", "C2", "cancelled", pd.Timestamp("2025-06-30"), 999],
            ["O5", "C3", "refund", pd.Timestamp("2025-06-20"), 500],
        ],
        columns=["order_id", "customer_id", "order_status", "order_time", "total_amount"],
    )


def test_valid_orders_excludes_cancelled_and_refunded():
    out = valid_orders(_orders())
    assert set(out.order_id) == {"O1", "O2", "O3"}


def test_rfm_excludes_cancelled():
    out = rfm_analysis(_orders(), "2025-06-30")
    c2 = out[out.customer_id == "C2"].iloc[0]
    assert c2.monetary == 200
    assert c2.recency_days == 60


def test_repurchase_median_gap():
    out = repurchase_analysis(_orders())
    c1 = out[out.customer_id == "C1"].iloc[0]
    assert c1.median_gap_days == 1.0


def test_annualised_value_uses_reference_date_exposure():
    out = annualized_customer_value(_orders(), "2025-06-30")
    c2 = out[out.customer_id == "C2"].iloc[0]
    assert c2.observed_months > 1
    assert c2.annualized_value < 2400


def test_churn_threshold():
    out = churn_heuristic(_orders(), "2025-06-30")
    c2 = out[out.customer_id == "C2"].iloc[0]
    assert c2.risk_level == "Very High"
    assert "risk_score" not in out.columns


def test_market_basket_lift():
    orders = _orders().iloc[:2].copy()
    items = pd.DataFrame(
        [
            ["O1", "A", 1, 10],
            ["O1", "B", 1, 10],
            ["O2", "A", 1, 10],
            ["O2", "B", 1, 10],
        ],
        columns=["order_id", "product_name", "quantity", "unit_price"],
    )
    out = market_basket_rules(orders, items, min_support=0)
    assert len(out) == 2
    assert set(out.antecedent) == {"A", "B"}
    assert (out.lift == 1.0).all()


def test_customer_preference_ignores_cancelled_order():
    orders = _orders().iloc[:4].copy()
    items = pd.DataFrame(
        [
            ["O1", "A", 1, 10],
            ["O2", "A", 1, 10],
            ["O3", "B", 2, 20],
            ["O4", "SHOULD_NOT_COUNT", 99, 999],
        ],
        columns=["order_id", "product_name", "quantity", "unit_price"],
    )
    out = customer_product_preferences(orders, items)
    c2 = out[out.customer_id == "C2"].iloc[0]
    assert c2.top_product == "B"


def test_load_orders_rejects_missing_columns(tmp_path):
    path = tmp_path / "bad.csv"
    pd.DataFrame({"order_id": ["O1"]}).to_csv(path, index=False)
    with pytest.raises(ValueError):
        load_orders(path)
