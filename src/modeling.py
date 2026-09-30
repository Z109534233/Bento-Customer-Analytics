from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.analytics import valid_orders

FEATURE_COLUMNS = [
    "recency_days",
    "frequency_90d",
    "monetary_90d",
    "lifetime_orders",
    "lifetime_spend",
    "avg_order_value",
    "tenure_days",
]


def build_repurchase_snapshot_dataset(
    orders: pd.DataFrame,
    snapshot_dates: Iterable[str | pd.Timestamp],
    horizon_days: int = 30,
) -> pd.DataFrame:
    """
    Build leakage-aware customer snapshots for a future repurchase task.

    Features use only transactions available up to the end of each snapshot date.
    The target is 1 when the customer makes at least one valid purchase in the
    following horizon_days, otherwise 0.
    """
    df = valid_orders(orders).copy()
    if df.empty:
        return pd.DataFrame()

    df["order_time"] = pd.to_datetime(df["order_time"])
    rows: list[dict] = []

    for snapshot_date in snapshot_dates:
        snap = pd.Timestamp(snapshot_date).normalize()
        snapshot_end = snap + pd.Timedelta(days=1)
        future_end = snapshot_end + pd.Timedelta(days=horizon_days)

        history = df[df["order_time"] < snapshot_end].copy()
        future = df[
            (df["order_time"] >= snapshot_end)
            & (df["order_time"] < future_end)
        ].copy()
        future_customers = set(future["customer_id"].astype(str))

        for customer_id, g in history.groupby("customer_id"):
            g = g.sort_values("order_time")
            first_purchase = g["order_time"].min().normalize()
            last_purchase = g["order_time"].max().normalize()

            recent = g[g["order_time"] >= snapshot_end - pd.Timedelta(days=90)]
            lifetime_orders = int(g["order_id"].nunique())
            lifetime_spend = float(g["total_amount"].sum())

            rows.append(
                {
                    "customer_id": str(customer_id),
                    "snapshot_date": snap,
                    "recency_days": int((snap - last_purchase).days),
                    "frequency_90d": int(recent["order_id"].nunique()),
                    "monetary_90d": float(recent["total_amount"].sum()),
                    "lifetime_orders": lifetime_orders,
                    "lifetime_spend": lifetime_spend,
                    "avg_order_value": float(lifetime_spend / lifetime_orders),
                    "tenure_days": int((snap - first_purchase).days + 1),
                    f"repurchase_{horizon_days}d": int(str(customer_id) in future_customers),
                }
            )

    return pd.DataFrame(rows).sort_values(["snapshot_date", "customer_id"]).reset_index(drop=True)


def walk_forward_logistic_evaluation(
    dataset: pd.DataFrame,
    horizon_days: int = 30,
    random_state: int = 20260930,
) -> tuple[pd.DataFrame, Pipeline]:
    """
    Expanding-window temporal validation for repurchase classification.

    Each test snapshot is evaluated using only earlier snapshots for training.
    This avoids using future periods to train a model evaluated on the past.
    """
    target = f"repurchase_{horizon_days}d"
    required = {"snapshot_date", "customer_id", target, *FEATURE_COLUMNS}
    missing = required - set(dataset.columns)
    if missing:
        raise ValueError(f"snapshot dataset is missing columns: {sorted(missing)}")

    data = dataset.copy()
    data["snapshot_date"] = pd.to_datetime(data["snapshot_date"])
    snapshots = sorted(data["snapshot_date"].drop_duplicates())

    if len(snapshots) < 2:
        raise ValueError("at least two snapshot dates are required for walk-forward evaluation")

    rows = []
    fitted_model: Pipeline | None = None

    for test_date in snapshots[1:]:
        train = data[data["snapshot_date"] < test_date]
        test = data[data["snapshot_date"] == test_date]

        if train[target].nunique() < 2 or test[target].nunique() < 2:
            continue

        model = Pipeline(
            [
                ("scale", StandardScaler()),
                (
                    "model",
                    LogisticRegression(
                        max_iter=2000,
                        class_weight="balanced",
                        random_state=random_state,
                    ),
                ),
            ]
        )
        model.fit(train[FEATURE_COLUMNS], train[target])
        prob = model.predict_proba(test[FEATURE_COLUMNS])[:, 1]

        rows.append(
            {
                "test_snapshot": test_date,
                "train_rows": int(len(train)),
                "test_rows": int(len(test)),
                "positive_rate": float(test[target].mean()),
                "roc_auc": float(roc_auc_score(test[target], prob)),
                "average_precision": float(average_precision_score(test[target], prob)),
                "brier_score": float(brier_score_loss(test[target], prob)),
            }
        )
        fitted_model = model

    if fitted_model is None:
        raise ValueError("no evaluable walk-forward split contained both target classes")

    return pd.DataFrame(rows), fitted_model


def bootstrap_median_ci(
    values: Iterable[float],
    n_boot: int = 5000,
    confidence: float = 0.95,
    random_state: int = 20260930,
) -> dict[str, float]:
    """Percentile bootstrap confidence interval for a median."""
    arr = np.asarray(list(values), dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        raise ValueError("values must contain at least one finite observation")

    rng = np.random.default_rng(random_state)
    stats = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        stats[i] = np.median(rng.choice(arr, size=arr.size, replace=True))

    alpha = 1 - confidence
    lower, upper = np.quantile(stats, [alpha / 2, 1 - alpha / 2])
    return {
        "estimate": float(np.median(arr)),
        "lower": float(lower),
        "upper": float(upper),
        "confidence": float(confidence),
        "n_boot": int(n_boot),
    }


def bootstrap_rule_lift_ci(
    orders: pd.DataFrame,
    items: pd.DataFrame,
    antecedent: str,
    consequent: str,
    n_boot: int = 5000,
    confidence: float = 0.95,
    random_state: int = 20260930,
) -> dict[str, float]:
    """
    Order-level bootstrap confidence interval for a two-item association-rule lift.

    Whole baskets are resampled so the transaction structure is preserved.
    """
    good_order_ids = set(valid_orders(orders)["order_id"].astype(str))
    x = items.copy()
    x["order_id"] = x["order_id"].astype(str)
    x = x[x["order_id"].isin(good_order_ids)].copy()
    baskets = (
        x.groupby("order_id")["product_name"]
        .apply(lambda s: set(s.dropna().astype(str)))
        .tolist()
    )
    if not baskets:
        raise ValueError("no valid baskets are available")

    def lift(sample_baskets: list[set[str]]) -> float:
        n = len(sample_baskets)
        count_a = sum(antecedent in basket for basket in sample_baskets)
        count_b = sum(consequent in basket for basket in sample_baskets)
        count_ab = sum(
            antecedent in basket and consequent in basket
            for basket in sample_baskets
        )
        if count_a == 0 or count_b == 0:
            return np.nan
        confidence_ab = count_ab / count_a
        prob_b = count_b / n
        return confidence_ab / prob_b

    estimate = lift(baskets)
    rng = np.random.default_rng(random_state)
    stats = np.empty(n_boot, dtype=float)

    for i in range(n_boot):
        idx = rng.integers(0, len(baskets), size=len(baskets))
        sampled = [baskets[j] for j in idx]
        stats[i] = lift(sampled)

    stats = stats[np.isfinite(stats)]
    alpha = 1 - confidence
    lower, upper = np.quantile(stats, [alpha / 2, 1 - alpha / 2])

    return {
        "estimate": float(estimate),
        "lower": float(lower),
        "upper": float(upper),
        "confidence": float(confidence),
        "n_boot": int(n_boot),
    }
