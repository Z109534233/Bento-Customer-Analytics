from __future__ import annotations

from pathlib import Path
import random

import numpy as np
import pandas as pd

SEED = 20260930
random.seed(SEED)
rng = np.random.default_rng(SEED)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "sample_data"
OUT.mkdir(exist_ok=True)

products = [
    ("Grilled Chicken Bento", 120),
    ("Braised Pork Bento", 110),
    ("Fried Pork Chop Bento", 125),
    ("Mackerel Bento", 135),
    ("Vegetable Bento", 95),
    ("Chicken Leg Bento", 130),
    ("Tea Egg", 20),
    ("Miso Soup", 30),
    ("Seasonal Vegetables", 35),
    ("Milk Tea", 35),
    ("Black Tea", 25),
    ("Braised Tofu", 30),
]

start = pd.Timestamp("2025-01-01")
end = pd.Timestamp("2025-06-30")

customers = []
for i in range(1, 121):
    if i <= 20:
        profile = "loyal"
    elif i <= 45:
        profile = "regular"
    elif i <= 70:
        profile = "new"
    elif i <= 95:
        profile = "at_risk"
    else:
        profile = "dormant"
    customers.append((f"C{i:04d}", profile))

orders = []
items = []
order_seq = 1

for customer_id, profile in customers:
    if profile == "loyal":
        n = int(rng.integers(12, 19))
        lo, hi = pd.Timestamp("2025-03-01"), end
        spend_bias = 1.15
    elif profile == "regular":
        n = int(rng.integers(5, 10))
        lo, hi = pd.Timestamp("2025-02-01"), end
        spend_bias = 1.0
    elif profile == "new":
        n = int(rng.integers(1, 4))
        lo, hi = pd.Timestamp("2025-06-15"), end
        spend_bias = 0.95
    elif profile == "at_risk":
        n = int(rng.integers(4, 10))
        lo, hi = start, pd.Timestamp("2025-06-10")
        spend_bias = 1.05
    else:
        n = int(rng.integers(1, 4))
        lo, hi = start, pd.Timestamp("2025-05-15")
        spend_bias = 0.9

    span = max(1, (hi - lo).days)
    dates = sorted({lo + pd.Timedelta(days=int(rng.integers(0, span + 1))) for _ in range(n * 2)})[:n]
    while len(dates) < n:
        dates = sorted(set(dates + [lo + pd.Timedelta(days=int(rng.integers(0, span + 1)))]))

    # Make the synthetic profiles visibly distinct in the reproducible demo.
    if profile == "loyal":
        dates[-1] = pd.Timestamp("2025-06-28") + pd.Timedelta(days=int(rng.integers(0, 3)))
    elif profile == "regular":
        dates[-1] = pd.Timestamp("2025-06-18") + pd.Timedelta(days=int(rng.integers(0, 13)))
    elif profile == "new":
        dates[-1] = pd.Timestamp("2025-06-26") + pd.Timedelta(days=int(rng.integers(0, 5)))
    dates = sorted(set(dates))
    while len(dates) < n:
        candidate = lo + pd.Timedelta(days=int(rng.integers(0, span + 1)))
        dates = sorted(set(dates + [candidate]))

    for order_idx, dt in enumerate(dates[:n]):
        order_id = f"O{order_seq:06d}"
        order_seq += 1
        # Keep at least one valid order per synthetic customer.
        status = "completed" if order_idx == 0 or rng.random() > 0.025 else random.choice(["cancelled", "refund"])
        store_id = int(rng.choice([1, 2]))

        main_idx = int(rng.integers(0, 6))
        chosen = [products[main_idx]]
        if rng.random() < 0.42:
            chosen.append(products[int(rng.integers(6, len(products)))])
        if rng.random() < 0.18:
            extra_pool = [p for p in products[6:] if p not in chosen]
            if extra_pool:
                chosen.append(random.choice(extra_pool))

        # Add a planted but realistic association: chicken bento -> tea egg.
        if chosen[0][0] == "Grilled Chicken Bento" and rng.random() < 0.55 and products[6] not in chosen:
            chosen.append(products[6])

        total = 0
        for product_name, unit_price in chosen:
            qty = 1 if rng.random() < 0.9 else 2
            price = int(round(unit_price * spend_bias))
            total += qty * price
            items.append(
                {
                    "order_id": order_id,
                    "product_name": product_name,
                    "quantity": qty,
                    "unit_price": price,
                }
            )

        orders.append(
            {
                "order_id": order_id,
                "customer_id": customer_id,
                "order_status": status,
                "store_id": store_id,
                "order_time": dt + pd.Timedelta(hours=int(rng.integers(10, 20)), minutes=int(rng.integers(0, 60))),
                "total_amount": total,
            }
        )

pd.DataFrame(orders).sort_values("order_time").to_csv(OUT / "synthetic_orders.csv", index=False)
pd.DataFrame(items).to_csv(OUT / "synthetic_order_items.csv", index=False)
print(f"Generated {len(orders)} orders and {len(items)} order-item rows with seed {SEED}.")
