from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.modeling import (  # noqa: E402
    bootstrap_median_ci,
    build_repurchase_snapshot_dataset,
    walk_forward_logistic_evaluation,
)


def _orders():
    rows = []
    oid = 1
    for customer_id, dates in {
        "C1": ["2025-01-01", "2025-01-20", "2025-02-10", "2025-03-05"],
        "C2": ["2025-01-03", "2025-02-15"],
        "C3": ["2025-01-10", "2025-03-20"],
        "C4": ["2025-01-12", "2025-02-25", "2025-03-25"],
    }.items():
        for dt in dates:
            rows.append(
                [
                    f"O{oid}",
                    customer_id,
                    "completed",
                    pd.Timestamp(dt),
                    100 + oid,
                ]
            )
            oid += 1
    return pd.DataFrame(
        rows,
        columns=[
            "order_id",
            "customer_id",
            "order_status",
            "order_time",
            "total_amount",
        ],
    )


def test_snapshot_features_do_not_use_future_orders():
    data = build_repurchase_snapshot_dataset(
        _orders(),
        ["2025-01-31"],
        horizon_days=30,
    )
    c1 = data[data.customer_id == "C1"].iloc[0]

    assert c1.lifetime_orders == 2
    assert c1.repurchase_30d == 1


def test_bootstrap_median_ci_is_deterministic():
    result = bootstrap_median_ci([1, 2, 3, 4, 5], n_boot=500, random_state=7)
    assert result["estimate"] == 3.0
    assert result["lower"] <= result["estimate"] <= result["upper"]


def test_walk_forward_returns_temporal_holdouts():
    # Synthetic snapshot table created directly so both classes exist per split.
    rows = []
    for snap, offset in [
        ("2025-01-31", 0),
        ("2025-02-28", 1),
        ("2025-03-31", 2),
    ]:
        for i in range(12):
            y = i % 2
            rows.append(
                {
                    "customer_id": f"C{i:02d}",
                    "snapshot_date": pd.Timestamp(snap),
                    "recency_days": i + offset,
                    "frequency_90d": 8 - (i % 5),
                    "monetary_90d": 100 + i * 10,
                    "lifetime_orders": 2 + i,
                    "lifetime_spend": 300 + i * 20,
                    "avg_order_value": 120 + i,
                    "tenure_days": 30 + i * 3,
                    "repurchase_30d": y,
                }
            )

    evaluation, _ = walk_forward_logistic_evaluation(pd.DataFrame(rows), horizon_days=30)
    assert list(evaluation["test_snapshot"].dt.strftime("%Y-%m-%d")) == [
        "2025-02-28",
        "2025-03-31",
    ]
    assert (evaluation["train_rows"] < evaluation["train_rows"].shift(-1).fillna(10**9)).iloc[0]
