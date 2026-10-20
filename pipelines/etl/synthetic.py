from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def _build_clinic_frame(rows: int, seed: int, include_labels: bool) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    segments = rng.choice(["Community", "Specialty", "Health System"], rows, p=[0.5, 0.3, 0.2])
    regions = rng.choice(["Northeast", "Midwest", "South", "West"], rows, p=[0.3, 0.25, 0.25, 0.2])
    stocked_cabinets = np.where(
        segments == "Community",
        rng.integers(2, 12, rows),
        np.where(segments == "Specialty", rng.integers(8, 24, rows), rng.integers(20, 60, rows)),
    )
    tenure = rng.integers(1, 73, rows)
    buyer_count = np.where(
        segments == "Health System",
        rng.poisson(3.2, rows),
        np.where(segments == "Specialty", rng.poisson(2.0, rows), rng.poisson(1.0, rows)),
    ).clip(0, 10)
    onboarding = rng.binomial(1, np.clip(0.62 + tenure / 180, 0.6, 0.95), rows)
    active_seat_ratio = np.clip(
        rng.normal(0.34 + onboarding * 0.16 + buyer_count * 0.03, 0.12, rows),
        0.03,
        0.98,
    )
    monthly_contract_value = (stocked_cabinets * rng.normal(900, 80, rows) * (1.0 + buyer_count * 0.03)).clip(1500)
    logins = rng.poisson(np.clip(stocked_cabinets * active_seat_ratio * 2.3, 3, 900))
    usage_change = rng.normal(-3 + onboarding * 6, 22, rows).clip(-80, 80)
    support_tickets = rng.poisson(np.clip(1.2 + (usage_change < -20) * 1.8 + (active_seat_ratio < 0.25) * 0.7, 0.3, 12))
    nps = np.round(
        rng.normal(35 + onboarding * 15 + usage_change * 0.35 + active_seat_ratio * 20 - support_tickets * 4, 22, rows)
    ).clip(-100, 100).astype(int)
    days_to_term = rng.integers(1, 366, rows)
    payment_failures = rng.binomial(3, np.clip(0.04 + (segments == "Community") * 0.04, 0.01, 0.22), rows)

    deployment_stages = [
        "still stocking the first cabinets after go-live",
        "running a limited formulary at two departments",
        "expanding the supply list across the clinic",
        "on a steady replenishment cadence",
        "recovering from a stalled cabinet rollout",
    ]
    business_priorities = [
        "needs a clearer cost-per-cabinet review before term",
        "is cutting backorders and emergency purchases",
        "prefers standing orders over one-off buys",
        "wants faster service on damaged or short shipments",
        "needs a named buyer for each cabinet",
        "is working through invoice disputes",
        "wants the medical director on the term review",
    ]
    communication_styles = [
        "responds to a short monthly supply review",
        "wants the term packet before any price talk",
        "likes a call when a cabinet drops below par",
        "prefers email for invoice questions",
    ]
    clinic_notes = [
        f"{deployment_stages[i % len(deployment_stages)]}; {business_priorities[(i * 3) % len(business_priorities)]}; {communication_styles[(i * 5) % len(communication_styles)]}."
        for i in range(rows)
    ]

    logit = (
        -0.8
        - 0.055 * logins
        - 0.023 * nps
        - 0.022 * tenure
        - 1.0 * onboarding
        - 0.025 * usage_change
        + 0.55 * support_tickets
        + 0.90 * payment_failures
        + 1.20 * (days_to_term < 45)
        + 0.50 * (segments == "Community")
        + rng.normal(0, 0.3, rows)
    )
    lapse_probability = 1 / (1 + np.exp(-logit - 2.0 * active_seat_ratio - 0.22 * buyer_count + 0.0003 * stocked_cabinets))
    lapsed = rng.binomial(1, lapse_probability) if include_labels else np.array([None] * rows)

    frame = pd.DataFrame(
        {
            "clinic_id": [f"CLN-{index:04d}" for index in range(1, rows + 1)],
            "segment": segments,
            "region": regions,
            "clinic_notes": clinic_notes,
            "stocked_cabinets": stocked_cabinets,
            "active_cabinet_ratio_30d": active_seat_ratio.round(4),
            "buyer_count": buyer_count,
            "tenure_months": tenure,
            "monthly_contract_value": monthly_contract_value.round(2),
            "orders_30d": logins,
            "order_change_pct": usage_change.round(2),
            "service_tickets_90d": support_tickets,
            "nps": nps,
            "days_to_term": days_to_term,
            "invoice_failures_90d": payment_failures,
            "stocking_complete": onboarding,
            "lapsed": lapsed,
            "snapshot_date": pd.Timestamp.today().normalize().date().isoformat(),
        }
    )
    return frame


def generate_clinic_data(output_path: Path, rows: int = 800, seed: int = 42) -> pd.DataFrame:
    """Backward-compatible helper that writes labeled historical data."""
    frame = _build_clinic_frame(rows=rows, seed=seed, include_labels=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_path, index=False)
    return frame


def generate_clinic_datasets(
    history_output_path: Path,
    current_output_path: Path,
    *,
    history_rows: int = 1200,
    current_rows: int = 300,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    history = _build_clinic_frame(rows=history_rows, seed=seed, include_labels=True)
    current = _build_clinic_frame(rows=current_rows, seed=seed + 1, include_labels=False).drop(columns=["lapsed"])
    history_output_path.parent.mkdir(parents=True, exist_ok=True)
    current_output_path.parent.mkdir(parents=True, exist_ok=True)
    history.to_csv(history_output_path, index=False)
    current.to_csv(current_output_path, index=False)
    return history, current
