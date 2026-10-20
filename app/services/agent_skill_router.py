from __future__ import annotations

from app.models.domain import ClinicProfile, MemoryItem, PredictionResult


def recommended_agent_skills(
    profile: ClinicProfile,
    prediction: PredictionResult,
    memories: list[MemoryItem],
) -> list[dict[str, str]]:
    """Select relevant formal skills while leaving their instructions unloaded."""
    selected: list[dict[str, str]] = [
        {
            "skill": "account-diagnosis",
            "reason": "Every recommendation starts with grounded evidence and model signals.",
        }
    ]
    if (
        not profile.stocking_complete
        or profile.active_cabinet_ratio_30d < 0.35
        or profile.service_tickets_90d >= 3
    ):
        selected.append(
            {
                "skill": "deployment-recovery",
                "reason": (
                    "Rollout, activation, or unresolved support weakness requires "
                    "a verified recovery sequence."
                ),
            }
        )
    if profile.order_change_pct <= -15 or profile.active_cabinet_ratio_30d < 0.40:
        selected.append(
            {
                "skill": "adoption-reactivation",
                "reason": "The usage profile indicates workflow-level reactivation is needed.",
            }
        )
    if any(memory.memory_type.startswith("intervention_") for memory in memories):
        selected.append(
            {
                "skill": "memory-aware-strategy",
                "reason": "Prior intervention history should change the next plan.",
            }
        )
    if prediction.risk_band == "high" or profile.days_to_term <= 60 or profile.buyer_count <= 1:
        selected.append(
            {
                "skill": "stakeholder-alignment",
                "reason": "Risk, timing, or champion coverage requires approval-aware coordination.",
            }
        )
    if "roi" in profile.clinic_notes.lower() or profile.monthly_contract_value >= 10_000:
        selected.append(
            {
                "skill": "roi-value-story",
                "reason": "Value proof and ROI framing are important in this account context.",
            }
        )
    if prediction.risk_band == "high" and profile.days_to_term <= 45:
        selected.append(
            {
                "skill": "save-desk-triage",
                "reason": "High risk and a near renewal should be ordered on the save desk before a discount.",
            }
        )
    return selected
