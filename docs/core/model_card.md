# Lapse Model Card

## Intended use
Rank clinic accounts for proactive retention analysis and provide directional risk drivers. The model is not an automated eligibility, pricing, credit, employment, or legal decision system.

## Model
Class-weighted Logistic Regression classifier with numeric imputation/scaling and categorical one-hot encoding. Training uses a stratified holdout. Artifacts include preprocessing, classifier, feature list, baseline values, and model version.

## Explanation method
For a single clinic, each feature is replaced with its training-data baseline while other features remain fixed. The difference in predicted lapse probability is reported as a model-agnostic counterfactual impact. These impacts are local sensitivity estimates, not causal effects.

## Decision and risk thresholds
Training reports an F1-optimized binary decision threshold for model diagnostics. Clinic-facing low/medium/high risk thresholds are business configuration, are persisted in the model artifact, and are consumed by both online and batch inference so the two serving paths remain consistent.

## Limitations
- Training data is synthetic and does not represent a real company's population.
- Probability calibration is not implemented in v0.1.
- Correlated features can make single-feature counterfactual impacts unstable.
- Business interventions require experimentation or causal analysis before claiming treatment lift.
