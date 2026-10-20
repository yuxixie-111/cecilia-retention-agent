from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from app.repositories.database import Database
from pipelines.etl.extract import extract_csv
from pipelines.etl.load import load_feature_table
from pipelines.etl.transform import transform_clinic_data
from pipelines.etl.validate import validate_raw_data


def run_etl(
    history_raw_path: Path,
    current_raw_path: Path,
    database: Database,
    report_path: Path | None = None,
) -> dict:
    history_raw = extract_csv(history_raw_path)
    current_raw = extract_csv(current_raw_path)
    history_validation = validate_raw_data(history_raw, requires_label=True)
    current_validation = validate_raw_data(current_raw, requires_label=False)
    history_transformed = transform_clinic_data(history_raw)
    current_transformed = transform_clinic_data(current_raw)
    history_loaded_rows = load_feature_table(history_transformed, database, "clinic_history_features")
    current_loaded_rows = load_feature_table(current_transformed, database, "clinic_current_features")
    report = {
        "pipeline": "clinic_supply_etl",
        "status": "success",
        "run_at": datetime.now(UTC).isoformat(),
        "scenario": "clinic supply agreement renewal",
        "history_validation": history_validation,
        "current_validation": current_validation,
        "history_loaded_rows": history_loaded_rows,
        "current_loaded_rows": current_loaded_rows,
        "output_tables": ["clinic_history_features", "clinic_current_features"],
    }
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
