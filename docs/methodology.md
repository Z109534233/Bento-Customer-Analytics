# Methodology

## 1. RFM segmentation

The operational prototype used three behavioural dimensions:

- **Recency:** days since the most recent purchase.
- **Frequency:** number of distinct orders.
- **Monetary:** cumulative spend.

The public refactor retains the original project-specific thresholds so the logic remains auditable:

- Recency: `<=7` days = High, `8-14` = Mid-High, `15-21` = Mid, `>21` = Low.
- Frequency: `>=8` orders = High, `4-7` = Mid, `<4` = Low.
- Monetary: `>=1200` = High, `800-1199` = Mid-High, `400-799` = Mid, `<400` = Low.

These rules generate operational segments such as Top Customers, Loyal Repeat, Potential Loyalists, At Risk, Dormant and New Customers. The thresholds were designed for the project context rather than statistically estimated as universal customer-behaviour cut-offs.

## 2. Repurchase analysis

For each customer, orders are reduced to **distinct purchase dates**. Consecutive gaps are calculated in days, and the customer's typical repurchase interval is represented by the **median** gap. The median is used instead of the mean to reduce sensitivity to unusually long gaps.

Repurchase buckets:

- 1-3 days
- 4-7 days
- 8-14 days
- 15-30 days
- 30+ days

## 3. Annualised customer value

The original dashboard labelled this metric as `CLV(12M)`. In the public edition it is renamed **Annualised Customer Value** because it is a spending-rate proxy, not a complete lifetime-value model.

`annualised value = total observed spend / observed months * 12`

The observation window runs from the customer's first valid purchase to the analysis reference date. It is floored at one month so a customer observed for only a few days is not annualised using an extremely small denominator.

A full CLV model would normally require additional assumptions such as retention, contribution margin, customer lifetime and discounting.

## 4. Churn alert heuristic

The operational dashboard used a transparent rule based on days since last purchase:

- 0-7 days: Low
- 8-14 days: Medium
- 15-21 days: High
- 22+ days: Very High

The public refactor reports the categorical alert level and the underlying days-since-last value. It deliberately does not convert this rule into a probability-like score because no labelled churn model was estimated or calibrated.

## 5. Market basket analysis

Orders are treated as baskets of unique products. For a rule `A -> B`:

- `support(A,B) = orders containing A and B / all valid orders`
- `confidence(A->B) = orders containing A and B / orders containing A`
- `lift(A->B) = confidence(A->B) / P(B)`

The public edition emits rules in both directions so confidence is interpreted correctly for each antecedent.

## 6. Product preference analysis

Valid order items are aggregated at the customer-product level. The product with the highest purchased quantity is selected as the customer's top product, with spend used as the tie-breaker.

## 7. Reproducibility

The public dataset is generated from a fixed random seed. The repository also includes automated unit tests and a GitHub Actions workflow so the core analytics can be re-run and checked independently.


## 8. Bootstrap uncertainty

The public extension adds percentile bootstrap intervals rather than reporting point estimates alone.

- Customer-level median repurchase gaps are resampled across customers.
- Market-basket lift is bootstrapped at the **order/basket level**, preserving the within-order item structure.

The default public demo uses 5,000 bootstrap resamples and reports 95% intervals.

## 9. Future 30-day repurchase model

The modelling target is whether a customer places at least one valid order in the 30 days after a snapshot date.

Features are built using only data available by the snapshot date:

- recency in days
- order frequency and spend in the previous 90 days
- lifetime order count and lifetime spend
- average order value
- tenure in days

A standardised logistic regression with balanced class weights is evaluated using an **expanding-window temporal split**. For each test snapshot, training data contain only earlier snapshots. This is more appropriate than a random row split for a time-dependent customer-behaviour task because it reduces look-ahead leakage.

Evaluation reports ROC-AUC, Average Precision and Brier score. ROC-AUC measures ranking discrimination, Average Precision is informative under changing class balance, and Brier score assesses probability accuracy/calibration.
