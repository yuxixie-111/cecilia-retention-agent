from __future__ import annotations

import pandas as pd

from app.core.exceptions import DataValidationError

BASE_REQUIRED_COLUMNS = {
    "clinic_id",
    "segment",
    "region",
    "clinic_notes",
    "stocked_cabinets",
    "active_cabinet_ratio_30d",
    "buyer_count",
    "tenure_months",
    "monthly_contract_value",
    "orders_30d",
    "order_change_pct",
    "service_tickets_90d",
    "nps",
    "days_to_term",
    "invoice_failures_90d",
    "stocking_complete",
    "snapshot_date",
}


def validate_raw_data(frame: pd.DataFrame, *, requires_label: bool = True) -> dict[str, int | float | bool]:
    required_columns = set(BASE_REQUIRED_COLUMNS)
    if requires_label:
        required_columns.add("lapsed")
    missing = required_columns.difference(frame.columns)
    errors: list[str] = []
    if missing:
        errors.append(f"Missing required columns: {sorted(missing)}")
    if frame.empty:
        errors.append("Dataset is empty")
    if "clinic_id" in frame and frame["clinic_id"].duplicated().any():
        errors.append("clinic_id must be unique")
    checks = {
        "monthly_contract_value": (0, None),
        "stocked_cabinets": (1, None),
        "active_cabinet_ratio_30d": (0, 1),
        "buyer_count": (0, None),
        "tenure_months": (0, None),
        "orders_30d": (0, None),
        "service_tickets_90d": (0, None),
        "nps": (-100, 100),
        "days_to_term": (0, 366),
        "invoice_failures_90d": (0, None),
        "stocking_complete": (0, 1),
        "lapsed": (0, 1),
    }
    for column, (minimum, maximum) in checks.items():
        if column not in frame:
            continue
        if minimum is not None and (frame[column] < minimum).any():
            errors.append(f"{column} contains values below {minimum}")
        if maximum is not None and (frame[column] > maximum).any():
            errors.append(f"{column} contains values above {maximum}")
    null_rate = float(frame[list(required_columns.intersection(frame.columns))].isna().mean().max())
    if null_rate > 0.05:
        errors.append(f"Maximum required-column null rate {null_rate:.1%} exceeds 5%")
    if errors:
        raise DataValidationError("; ".join(errors))
    return {
        "rows": int(len(frame)),
        "columns": int(len(frame.columns)),
        "duplicate_clinics": int(frame["clinic_id"].duplicated().sum()),
        "max_null_rate": null_rate,
        "requires_label": requires_label,
    }
