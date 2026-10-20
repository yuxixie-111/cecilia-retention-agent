import pandas as pd
import pytest

from app.core.exceptions import DataValidationError
from pipelines.etl.transform import transform_clinic_data
from pipelines.etl.validate import validate_raw_data


def valid_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "clinic_id": "CLN-1",
                "segment": "SMB",
                "region": "NA",
                "clinic_notes": "phased rollout; needs role-based adoption training",
                "stocked_cabinets": 24,
                "active_cabinet_ratio_30d": 0.41,
                "buyer_count": 1,
                "tenure_months": 12,
                "monthly_contract_value": 500,
                "orders_30d": 10,
                "order_change_pct": -20,
                "service_tickets_90d": 2,
                "nps": 10,
                "days_to_term": 30,
                "invoice_failures_90d": 0,
                "stocking_complete": 1,
                "lapsed": 0,
                "snapshot_date": "2026-07-01",
            }
        ]
    )


def test_etl_validation_and_derived_features() -> None:
    frame = valid_frame()
    report = validate_raw_data(frame)
    transformed = transform_clinic_data(frame)
    assert report["rows"] == 1
    assert "activity_score" in transformed
    assert transformed.loc[0, "value_at_risk"] > 0


def test_validation_rejects_out_of_range_nps() -> None:
    frame = valid_frame()
    frame.loc[0, "nps"] = 200
    with pytest.raises(DataValidationError):
        validate_raw_data(frame)


def test_validation_supports_current_unlabeled_snapshot() -> None:
    frame = valid_frame().drop(columns=["lapsed"])
    report = validate_raw_data(frame, requires_label=False)
    transformed = transform_clinic_data(frame)
    assert report["requires_label"] is False
    assert "lapsed" in transformed.columns
