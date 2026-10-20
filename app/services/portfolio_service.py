from __future__ import annotations

from app.repositories.clinic_repository import ClinicRepository
from app.services.ml_service import MLService
from app.services.save_desk import save_desk_fields


class PortfolioService:
    """Read-only portfolio analytics used by dashboards and conversational tools."""

    def __init__(self, repository: ClinicRepository, ml_service: MLService):
        self.repository = repository
        self.ml_service = ml_service

    def ranked_clinics(
        self,
        *,
        limit: int = 10,
        segment: str | None = None,
        term_within_days: int | None = None,
        risk_band: str | None = None,
        rank_by: str = "lapse_probability",
    ) -> list[dict]:
        limit = min(max(int(limit), 1), 1_000)
        profiles = [
            self.repository.get(clinic_id)
            for clinic_id in self.repository.list_ids(limit=10_000)
        ]
        profile_by_id = {profile.clinic_id: profile for profile in profiles}
        rows: list[dict] = []
        for clinic_id, probability, predicted_band in self.ml_service.score_many(profiles):
            profile = profile_by_id[clinic_id]
            if segment and profile.segment.lower() != segment.strip().lower():
                continue
            if term_within_days is not None and profile.days_to_term > term_within_days:
                continue
            if risk_band and predicted_band != risk_band.strip().lower():
                continue
            desk = save_desk_fields(
                lapse_probability=probability,
                value_at_risk=profile.value_at_risk,
                days_to_term=profile.days_to_term,
                risk_band=predicted_band,
            )
            rows.append(
                {
                    "clinic_id": clinic_id,
                    "segment": profile.segment,
                    "region": profile.region,
                    "monthly_contract_value": profile.monthly_contract_value,
                    "value_at_risk": profile.value_at_risk,
                    "days_to_term": profile.days_to_term,
                    "term_timing": (
                        "within_30_days"
                        if profile.days_to_term <= 30
                        else "within_60_days"
                        if profile.days_to_term <= 60
                        else "more_than_60_days"
                    ),
                    "active_cabinet_ratio_30d": profile.active_cabinet_ratio_30d,
                    "order_change_pct": profile.order_change_pct,
                    "service_tickets_90d": profile.service_tickets_90d,
                    "lapse_probability": probability,
                    "risk_band": predicted_band,
                    "renewal_pressure": desk["renewal_pressure"],
                    "save_priority": desk["save_priority"],
                    "save_lane": desk["save_lane"],
                    "ranking_basis": "lapse_probability_desc",
                }
            )
        if rank_by == "save_priority":
            rows.sort(key=lambda item: float(item["save_priority"]), reverse=True)
            for row in rows:
                row["ranking_basis"] = "save_priority_desc"
        else:
            rows.sort(key=lambda item: item["lapse_probability"], reverse=True)
        return rows[:limit]

    def summary(self) -> dict[str, int | float]:
        rows = self.ranked_clinics(limit=1_000)
        return {
            "clinic_count": len(rows),
            "high_risk_count": sum(row["risk_band"] == "high" for row in rows),
            "medium_risk_count": sum(row["risk_band"] == "medium" for row in rows),
            "term_within_30_days": sum(row["days_to_term"] <= 30 for row in rows),
            "high_risk_value_at_risk": round(
                sum(
                    float(row["value_at_risk"])
                    for row in rows
                    if row["risk_band"] == "high"
                ),
                2,
            ),
            "call_today": sum(row["save_lane"] == "call_today" for row in rows),
        }
