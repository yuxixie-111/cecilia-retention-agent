---
name: save-desk-triage
description: Triage near-term renewal accounts by save priority, which combines lapse probability, revenue at risk, and renewal timing. Use when deciding who the retention desk should call first, or when a high-risk account renews within 45 days.
---

# Save desk triage

## Evidence contract

1. Use the supplied save priority, save lane, lapse probability, revenue at risk, and days to renewal. Do not invent a queue position.
2. `call_today` means high risk and renewal within 30 days. `this_cycle` means high or medium risk with renewal within 90 days. `watch` is everything else.
3. Save priority is lapse probability × revenue at risk × renewal pressure. It ranks commercial urgency. It is not a predicted save rate.
4. Read [references/queue-rules.md](references/queue-rules.md) before recommending who to contact or which offer to discuss.

## Triage

1. Name the lane, save priority, renewal window, and the two facts that moved the account up the queue.
2. Prefer a human conversation for `call_today` accounts before any discount.
3. Separate a model risk signal from a verified clinic complaint. Do not treat correlation as the reason they will leave.
4. Hand value-proof work to `roi-value-story` and rollout blockers to `deployment-recovery` instead of repeating those playbooks here.

## Contribute to the response

- `risk_assessment`: include the lane and why the timing matters.
- `evidence`: cite profile fields, the model band, and the save-priority inputs actually supplied.
- `recommended_actions`: one next owner and one next step. Do not stack a discount on top of an unproven complaint.
- `do_not_do`: no invented quotes, no blanket discounts, and no claim that save priority is a causal lift.
- `confidence`: lower it when revenue, renewal date, or the model score is missing.
- `requires_human_approval`: set it for clinic-facing commitments, discounts, record changes, or tickets.
