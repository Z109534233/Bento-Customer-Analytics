from __future__ import annotations

from collections import Counter
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

CANCELLED_TOKENS = {
    "取消", "已取消", "訂單取消", "cancel", "cancelled", "canceled",
    "void", "voided", "refund", "refunded",
}


def load_orders(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["order_time"])
    required = {"order_id", "customer_id", "order_status", "order_time", "total_amount"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"orders data is missing columns: {sorted(missing)}")
    return df


def load_order_items(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {"order_id", "product_name", "quantity", "unit_price"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"order_items data is missing columns: {sorted(missing)}")
    return df


def valid_orders(orders: pd.DataFrame) -> pd.DataFrame:
    """Exclude cancelled/voided/refunded orders and rows without a customer id."""
    df = orders.copy()
    status = df["order_status"].fillna("").astype(str).str.strip().str.lower()
    bad = status.isin(CANCELLED_TOKENS)
    bad |= status.str.contains("取消|cancel|void|refund", regex=True, na=False)
    customer = df["customer_id"].fillna("").astype(str).str.strip()
    amount = pd.to_numeric(df["total_amount"], errors="coerce")
    keep = ~bad & customer.ne("") & amount.notna() & amount.ge(0)
    return df.loc[keep].copy()


def _classify_r(days: int) -> str:
    if days <= 7:
        return "High"
    if days <= 14:
        return "Mid-High"
    if days <= 21:
        return "Mid"
    return "Low"


def _classify_f(n_orders: int) -> str:
    if n_orders >= 8:
        return "High"
    if n_orders >= 4:
        return "Mid"
    return "Low"


def _classify_m(spend: float) -> str:
    if spend >= 1200:
        return "High"
    if spend >= 800:
        return "Mid-High"
    if spend >= 400:
        return "Mid"
    return "Low"


def _segment(r: str, f: str, m: str) -> str:
    # Public refactor of the original rule-based 8-segment logic.
    if r == "High" and f == "High" and m == "High":
        return "Top Customers"
    if r in {"High", "Mid-High"} and f == "High" and m in {"Mid-High", "High"}:
        return "Loyal Repeat"
    if r == "High" and f == "Mid" and m in {"Mid", "Mid-High"}:
        return "Potential Loyalists"
    if r == "High" and f == "Low" and m == "High":
        return "High Spending"
    if r == "Mid" and f == "Mid" and m == "Mid":
        return "Developing"
    if r == "Low" and f == "High" and m in {"Mid-High", "High"}:
        return "At Risk"
    if r == "Low" and f == "Low" and m == "Low":
        return "Dormant"
    if r == "High" and f == "Low" and m == "Low":
        return "New Customers"

    # Catch-all rules retained from the operational prototype.
    if r == "High" and f == "High" and m != "Low":
        return "Loyal Repeat"
    if r == "Mid-High" and f == "High":
        return "Loyal Repeat"
    if r == "High" and f == "Mid":
        return "Potential Loyalists"
    if r == "High" and m == "High":
        return "High Spending"
    if r == "Low" and (f == "High" or m in {"High", "Mid-High"}):
        return "At Risk"
    if r == "Low" and f == "Low":
        return "Dormant"
    if r == "High" and f == "Low":
        return "New Customers"
    return "Developing"


def rfm_analysis(orders: pd.DataFrame, reference_date: str | pd.Timestamp | None = None) -> pd.DataFrame:
    df = valid_orders(orders)
    if df.empty:
        return pd.DataFrame()

    ref = pd.Timestamp(reference_date) if reference_date is not None else df["order_time"].max().normalize()
    agg = (
        df.groupby("customer_id", as_index=False)
        .agg(
            last_purchase=("order_time", "max"),
            frequency=("order_id", "nunique"),
            monetary=("total_amount", "sum"),
        )
    )
    agg["recency_days"] = (ref - agg["last_purchase"].dt.normalize()).dt.days.clip(lower=0).astype(int)
    agg["r_level"] = agg["recency_days"].map(_classify_r)
    agg["f_level"] = agg["frequency"].map(_classify_f)
    agg["m_level"] = agg["monetary"].map(_classify_m)
    agg["segment"] = [
        _segment(r, f, m) for r, f, m in zip(agg["r_level"], agg["f_level"], agg["m_level"])
    ]
    agg["avg_order_value"] = (agg["monetary"] / agg["frequency"]).round(2)
    return agg.sort_values(["segment", "monetary"], ascending=[True, False]).reset_index(drop=True)


def repurchase_analysis(orders: pd.DataFrame) -> pd.DataFrame:
    """Median gap between distinct purchase dates for customers with >=2 purchase dates."""
    df = valid_orders(orders).copy()
    if df.empty:
        return pd.DataFrame()
    df["order_date"] = df["order_time"].dt.normalize()
    out = []
    for customer_id, g in df.groupby("customer_id"):
        dates = sorted(g["order_date"].drop_duplicates().tolist())
        if len(dates) < 2:
            continue
        gaps = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
        gaps = [x for x in gaps if x > 0]
        if not gaps:
            continue
        med = float(np.median(gaps))
        if med <= 3:
            bucket = "1-3 days"
        elif med <= 7:
            bucket = "4-7 days"
        elif med <= 14:
            bucket = "8-14 days"
        elif med <= 30:
            bucket = "15-30 days"
        else:
            bucket = "30+ days"
        out.append(
            {
                "customer_id": customer_id,
                "median_gap_days": round(med, 1),
                "repurchase_bucket": bucket,
                "orders": int(g["order_id"].nunique()),
                "total_spend": round(float(g["total_amount"].sum()), 2),
                "avg_order_value": round(float(g["total_amount"].sum() / g["order_id"].nunique()), 2),
            }
        )
    return pd.DataFrame(out).sort_values("median_gap_days").reset_index(drop=True) if out else pd.DataFrame()


def annualized_customer_value(
    orders: pd.DataFrame,
    reference_date: str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """
    Annualised spend proxy, NOT a full lifetime-value model.

    annualized_value = total_spend / observed_months * 12
    observed_months runs from first purchase to the analysis reference date and is
    floored at one month to avoid extreme annualisation for very new customers.
    """
    df = valid_orders(orders)
    if df.empty:
        return pd.DataFrame()

    ref = pd.Timestamp(reference_date) if reference_date is not None else df["order_time"].max().normalize()
    agg = (
        df.groupby("customer_id", as_index=False)
        .agg(
            orders=("order_id", "nunique"),
            total_spend=("total_amount", "sum"),
            first_purchase=("order_time", "min"),
            last_purchase=("order_time", "max"),
        )
    )
    exposure_days = (ref - agg["first_purchase"].dt.normalize()).dt.days.clip(lower=0) + 1
    agg["observed_months"] = (exposure_days / 30.0).clip(lower=1.0).round(2)
    agg["annualized_value"] = (agg["total_spend"] / agg["observed_months"] * 12.0).round(2)
    agg["avg_order_value"] = (agg["total_spend"] / agg["orders"]).round(2)
    return agg.sort_values("annualized_value", ascending=False).reset_index(drop=True)


def churn_heuristic(orders: pd.DataFrame, reference_date: str | pd.Timestamp | None = None) -> pd.DataFrame:
    """Recency-based operational alert, not a probabilistic churn model."""
    df = valid_orders(orders)
    if df.empty:
        return pd.DataFrame()
    ref = pd.Timestamp(reference_date) if reference_date is not None else df["order_time"].max().normalize()
    agg = (
        df.groupby("customer_id", as_index=False)
        .agg(
            last_purchase=("order_time", "max"),
            orders=("order_id", "nunique"),
            total_spend=("total_amount", "sum"),
        )
    )
    agg["days_since_last"] = (ref - agg["last_purchase"].dt.normalize()).dt.days.clip(lower=0).astype(int)

    def level(days: int) -> str:
        if days >= 22:
            return "Very High"
        if days >= 15:
            return "High"
        if days >= 8:
            return "Medium"
        return "Low"

    agg["risk_level"] = agg["days_since_last"].map(level)
    return agg.sort_values(["days_since_last", "total_spend"], ascending=[False, False]).reset_index(drop=True)


def market_basket_rules(
    orders: pd.DataFrame,
    items: pd.DataFrame,
    min_support: float = 0.01,
) -> pd.DataFrame:
    """Generate directional two-item association rules with support, confidence and lift."""
    good_order_ids = set(valid_orders(orders)["order_id"].astype(str))
    x = items.copy()
    x["order_id"] = x["order_id"].astype(str)
    x = x[x["order_id"].isin(good_order_ids)].copy()
    x = x[x["product_name"].notna() & (pd.to_numeric(x["quantity"], errors="coerce") > 0)]
    baskets = x.groupby("order_id")["product_name"].apply(lambda s: sorted(set(s.astype(str)))).tolist()
    n_orders = len(baskets)
    if n_orders == 0:
        return pd.DataFrame()

    item_counts = Counter()
    pair_counts = Counter()
    for basket in baskets:
        item_counts.update(basket)
        pair_counts.update(combinations(basket, 2))

    rows = []
    for (a, b), ab_count in pair_counts.items():
        support = ab_count / n_orders
        if support < min_support:
            continue
        for antecedent, consequent in ((a, b), (b, a)):
            confidence = ab_count / item_counts[antecedent]
            consequent_prob = item_counts[consequent] / n_orders
            lift = confidence / consequent_prob if consequent_prob else 0.0
            rows.append(
                {
                    "antecedent": antecedent,
                    "consequent": consequent,
                    "co_occurrence": int(ab_count),
                    "support": round(support, 4),
                    "confidence": round(confidence, 4),
                    "lift": round(lift, 4),
                }
            )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["lift", "support"], ascending=[False, False]).reset_index(drop=True)


def customer_product_preferences(orders: pd.DataFrame, items: pd.DataFrame) -> pd.DataFrame:
    good = valid_orders(orders)[["order_id", "customer_id"]].copy()
    good["order_id"] = good["order_id"].astype(str)
    x = items.copy()
    x["order_id"] = x["order_id"].astype(str)
    x = x.merge(good, on="order_id", how="inner")
    x = x[x["product_name"].notna()].copy()
    x["quantity"] = pd.to_numeric(x["quantity"], errors="coerce")
    x["unit_price"] = pd.to_numeric(x["unit_price"], errors="coerce")
    x = x[x["quantity"].gt(0) & x["unit_price"].ge(0)]
    x["line_value"] = x["quantity"] * x["unit_price"]
    agg = x.groupby(["customer_id", "product_name"], as_index=False).agg(
        units=("quantity", "sum"), spend=("line_value", "sum")
    )
    agg = agg.sort_values(["customer_id", "units", "spend"], ascending=[True, False, False])
    top = agg.groupby("customer_id", as_index=False).first()
    return top.rename(columns={"product_name": "top_product", "units": "top_product_units", "spend": "top_product_spend"})
