from __future__ import annotations


def renewal_pressure(days_to_term: int) -> float:
    """Weight nearer renewals more heavily. This is a scheduling factor, not a probability."""
    days = max(int(days_to_term), 0)
    if days <= 30:
        return 1.0
    if days <= 60:
        return 0.75
    if days <= 120:
        return 0.45
    return 0.2


def save_priority_score(
    lapse_probability: float,
    value_at_risk: float,
    days_to_term: int,
) -> float:
    """Expected commercial urgency: risk × revenue exposure × how soon renewal arrives."""
    score = float(lapse_probability) * float(value_at_risk) * renewal_pressure(days_to_term)
    return round(score, 2)


def save_lane(risk_band: str, days_to_term: int) -> str:
    band = risk_band.strip().lower()
    days = int(days_to_term)
    if band == "high" and days <= 30:
        return "call_today"
    if band in {"high", "medium"} and days <= 90:
        return "this_cycle"
    return "watch"


def save_desk_fields(
    *,
    lapse_probability: float,
    value_at_risk: float,
    days_to_term: int,
    risk_band: str,
) -> dict[str, float | str]:
    return {
        "renewal_pressure": renewal_pressure(days_to_term),
        "save_priority": save_priority_score(
            lapse_probability, value_at_risk, days_to_term
        ),
        "save_lane": save_lane(risk_band, days_to_term),
    }
