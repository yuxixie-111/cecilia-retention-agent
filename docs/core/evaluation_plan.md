# Evaluation Plan

## Deterministic tests
- ETL schema, uniqueness, null-rate, and range validation.
- Repository query correctness.
- Prediction probability and explanation schema.
- Reviewer guardrails.
- API contract and smoke tests.

## Golden dataset
The bootstrap process selects representative high-, medium-, and low-risk accounts and records expected risk band, required action concepts, and minimum reviewer score. CI measures risk-band accuracy, action keyword coverage, reviewer pass rate, evidence rate, latency, and fallback rate. Golden evaluation runs with workflow persistence disabled, ignores existing memory, records provider/model provenance, and fails the job when required metric floors are missed.

## LLM-specific evaluation
When Ollama is enabled, compare the LLM provider with the deterministic baseline on the same golden cases. Add tool-call correctness, unsupported-claim rate, memory-use correctness, output-schema validity, token count, and cost. Do not use an LLM judge as the only evaluator; combine it with deterministic assertions and human review.
