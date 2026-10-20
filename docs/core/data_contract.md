# Data Contract

The project uses two raw CSV inputs for a B2B AI desk subscription retention scenario:

- `data/raw/clinic_history.csv`: historical accounts with features and lapse labels for training.
- `data/raw/current_clinics.csv`: active clinic snapshot without lapse labels for live scoring.

| Field | Type | Constraint |
|---|---|---|
| clinic_id | string | required, unique |
| segment | string | SMB, Mid-Market, Enterprise |
| region | string | categorical |
| clinic_notes | string | optional descriptive profile notes for personalized recommendations |
| stocked_cabinets | integer | >= 1 |
| active_cabinet_ratio_30d | float | 0 to 1 |
| buyer_count | integer | >= 0 |
| tenure_months | integer | >= 0 |
| monthly_contract_value | float | >= 0 |
| orders_30d | integer | >= 0 |
| order_change_pct | float | expected -100 to 100 |
| service_tickets_90d | integer | >= 0 |
| nps | integer | -100 to 100 |
| days_to_term | integer | 0 to 366 |
| invoice_failures_90d | integer | >= 0 |
| stocking_complete | integer | 0 or 1 |
| lapsed | integer | 0 or 1, required only in the historical dataset |
| snapshot_date | date | ISO date |

Derived features include support-ticket rate, engagement score, renewal urgency, and annualized revenue at risk.
