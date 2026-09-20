# Validation and ML methodology — planned, not implemented

Milestone 1 does not train models, expose ML metrics or generate probability estimates. Scanner scores are rule coverage only. This document sets acceptance criteria for the later implementation.

## Phase 6: deterministic strategy validation

Use explicitly dated, nonoverlapping train, validation and final-test ranges. Choose strategy families/parameters using train and validation only. Freeze the chosen specification and record its immutable data/input hashes before the final evaluation. Never present repeated test-set optimization as out-of-sample evidence.

Walk-forward reports will fit/select on expanding or rolling training windows and evaluate on later, nonoverlapping windows. Reports distinguish fold performance from a final isolated holdout. Warm-up uses earlier observations only, and positions reset at evaluation boundaries unless a continuous portfolio simulation is explicitly modeled. Purge observations whose forward target/event horizons overlap partition boundaries. Report trade counts, economic costs, degradation, unstable folds and sample-size limitations. Add tests that attempt to perturb final-test observations and assert selection is unchanged.

## Phase 7: probability models

Target: e.g. P(close[t+5]/close[t] − 1 > 0.02), labeled as a price-return probability, not an exact forecast or execution return. Trailing unavailable labels are dropped, never filled. Forward labels must remain unavailable to feature generation and preprocessing.

Start with regularized logistic regression and compare random forest / gradient boosting only if useful. Fit imputation/scaling/selection inside each training fold. Use chronological splits, no shuffled time-series train/test partitions. Align SPY/QQQ context by session and availability; do not fill future observations backward.

Compare to training-set prevalence and deterministic momentum baselines. Report precision, recall, F1 at a validation-selected threshold, ROC-AUC when both classes exist, PR-AUC, Brier score and calibration bins with counts. Calibration must use a training-internal chronological calibration window, never the final holdout. Single-class or inadequate samples yield unavailable metrics with reasons.

Report honestly when held-out ML fails to improve on a simple baseline. Persist target horizon/threshold, feature definitions, date partitions, random seeds, dependency versions, data hashes and model/configuration artifacts. No deep learning is planned for V1. Do not convert probabilities into unqualified investment recommendations.
