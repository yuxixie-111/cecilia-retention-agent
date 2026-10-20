from __future__ import annotations

import numpy as np
import pandas as pd


def transform_clinic_data(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    if "clinic_notes" not in result.columns:
        result["clinic_notes"] = ""
    result["clinic_notes"] = result["clinic_notes"].fillna("").astype(str)
    if "stocked_cabinets" not in result.columns:
        result["stocked_cabinets"] = 25
    if "active_cabinet_ratio_30d" not in result.columns:
        result["active_cabinet_ratio_30d"] = 0.45
    if "buyer_count" not in result.columns:
        result["buyer_count"] = 1
    if "lapsed" not in result.columns:
        result["lapsed"] = pd.NA
    result["snapshot_date"] = pd.to_datetime(result["snapshot_date"]).dt.date.astype(str)
    numeric_columns = [
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
        "lapsed",
    ]
    for column in numeric_columns:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    result["service_ticket_rate"] = (
        result["service_tickets_90d"] / np.maximum(result["tenure_months"], 1)
    ).round(4)
    result["activity_score"] = (
        0.55 * np.clip(result["orders_30d"] / 40, 0, 1)
        + 0.25 * np.clip((result["order_change_pct"] + 50) / 100, 0, 1)
        + 0.20 * result["stocking_complete"]
    ).round(4)
    result["term_pressure"] = np.clip((90 - result["days_to_term"]) / 90, 0, 1).round(4)
    result["value_at_risk"] = (
        result["monthly_contract_value"]
        * 12
        * (0.35 + 0.65 * result["term_pressure"])
    ).round(2)
    ordered_columns = [
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
        "service_ticket_rate",
        "activity_score",
        "term_pressure",
        "value_at_risk",
        "snapshot_date",
        "lapsed",
    ]
    return result[ordered_columns]
