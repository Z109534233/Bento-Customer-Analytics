# Limitations and Responsible Interpretation

This project is intentionally explicit about what the metrics can and cannot support.

1. **RFM thresholds are heuristic.** They were selected for the project context and were not statistically optimised or externally validated.
2. **Annualised Customer Value is not full CLV.** It annualises observed spending relative to an observation window and does not model retention, contribution margin, lifetime or discount rates.
3. **Very new customers remain difficult to annualise.** The one-month floor reduces extreme extrapolation but does not remove uncertainty for short customer histories.
4. **Churn output is not a churn probability.** It is a recency-based alert rule. A production predictive churn model would require labels, train/test separation, calibration and out-of-sample validation.
5. **Association does not imply causation.** High lift identifies co-purchase patterns; it does not prove that recommending one item will cause purchase of another.
6. **Thresholds and rules may not transfer across stores or periods.** Customer behaviour can change with menu, pricing, promotions, seasonality and store mix.
7. **Synthetic public data cannot demonstrate real commercial effect.** The included dataset exists only to make the analytical code reproducible without exposing private client data.
8. **No public revenue forecast is claimed.** The original prototype included a what-if scenario screen. The public portfolio does not present it as statistical forecasting because it was a deterministic scenario calculation rather than a validated time-series model.
9. **AI-generated interpretation is secondary to computation.** In the original system, AI was used to explain dashboard outputs. Core metrics were computed deterministically before any model-generated commentary.


10. **The predictive extension is demonstrated on synthetic data.** Its metrics show that the implementation supports leakage-aware temporal evaluation; they are not evidence that the model will generalise to the original store or another business.
11. **Calibration is not stable across all held-out months.** In the synthetic walk-forward demo, ROC-AUC remains useful while the May Brier score deteriorates as the outcome base rate changes. A deployment setting would require recalibration, monitoring and retraining rules.
12. **Repeated customer snapshots are not independent observations.** Temporal holdouts prevent future-to-past leakage, but customers can appear in multiple training snapshots. A larger study could add customer-grouped sensitivity analyses and hierarchical or survival models.
