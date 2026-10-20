from __future__ import annotations

from app.models.domain import (
    ActionItem,
    ClinicProfile,
    KnowledgeHit,
    MemoryItem,
    PredictionResult,
    Recommendation,
)


class RecommendationService:
    """Deterministic business-policy engine used as the free local fallback and test oracle."""

    def generate(
        self,
        profile: ClinicProfile,
        prediction: PredictionResult,
        knowledge: list[KnowledgeHit],
        memories: list[MemoryItem],
    ) -> Recommendation:
        actions: list[ActionItem] = []
        risky_features = {driver.feature for driver in prediction.top_drivers if driver.direction == "risk"}
        negative_outcomes = [
            memory.content.lower()
            for memory in memories
            if memory.memory_type == "intervention_outcome_negative"
        ]
        discount_previously_ineffective = any(
            token in content
            for content in negative_outcomes
            for token in ("discount", "折扣")
        )

        if "service_tickets_90d" in risky_features or profile.service_tickets_90d >= 3:
            actions.append(
                ActionItem(
                    priority=1,
                    action="Open a service review for short shipments and damaged cabinets within 48 hours.",
                    owner="Clinic Supply + Service",
                    rationale="Open service tickets are a leading lapse signal for this clinic.",
                    expected_impact="Clear the service backlog before anyone talks about the term price.",
                    approval_required=False,
                )
            )
        if (
            not profile.stocking_complete
            or profile.active_cabinet_ratio_30d < 0.35
            or profile.buyer_count == 0
        ):
            actions.append(
                ActionItem(
                    priority=len(actions) + 1,
                    action="Send a stocking visit to finish cabinet setup and name a buyer for each room.",
                    owner="Field Supply + Clinic Operations",
                    rationale="Unfinished stocking, idle cabinets, or no buyer means the clinic is not pulling the agreement.",
                    expected_impact="Get cabinets into daily use before the term conversation.",
                    approval_required=False,
                )
            )
        if "order_change_pct" in risky_features or profile.order_change_pct <= -20:
            actions.append(
                ActionItem(
                    priority=len(actions) + 1,
                    action="Review the two cabinets whose orders fell the most and reset their par levels.",
                    owner="Field Supply",
                    rationale="Order volume is down against this clinic's own baseline.",
                    expected_impact="Bring standing orders back before the clinic switches suppliers.",
                    approval_required=False,
                )
            )
        if not profile.stocking_complete:
            actions.append(
                ActionItem(
                    priority=len(actions) + 1,
                    action="Finish the stocking checklist with dates and a medical director sponsor.",
                    owner="Field Supply Lead",
                    rationale="Incomplete stocking leaves the contract unused and weakens term intent.",
                    expected_impact="Put every contracted cabinet into service.",
                    approval_required=False,
                )
            )
        if profile.days_to_term <= 60:
            actions.append(
                ActionItem(
                    priority=len(actions) + 1,
                    action="Hold a term review and show fill rate, backorders, and cabinet use before any price talk.",
                    owner="Account Lead",
                    rationale=f"The supply agreement reaches term in {profile.days_to_term} days.",
                    expected_impact="Create decision clarity and preserve negotiating leverage.",
                    approval_required=True,
                )
            )
        if profile.invoice_failures_90d > 0:
            actions.append(
                ActionItem(
                    priority=len(actions) + 1,
                    action="Confirm the invoice contact and clear failed invoices before the term date.",
                    owner="Finance Operations",
                    rationale="Recent invoice failures put the agreement at risk even when cabinets are in use.",
                    expected_impact="Remove a billing reason to let the contract lapse.",
                    approval_required=False,
                )
            )
        if prediction.risk_band == "high" and not any(
            action.approval_required for action in actions[:4]
        ):
            actions = actions[:3]
            actions.append(
                ActionItem(
                    priority=len(actions) + 1,
                    action=(
                        "Hold an executive retention review before any clinic-facing "
                        "commercial commitment."
                    ),
                    owner="Clinic Success Leadership",
                    rationale="High-risk accounts require an explicit human approval checkpoint.",
                    expected_impact="Align accountability, escalation level, and approved commitments.",
                    approval_required=True,
                )
            )

        if not actions:
            actions.append(
                ActionItem(
                    priority=1,
                    action="Maintain proactive quarterly value reviews and monitor leading engagement indicators.",
                    owner="Clinic Success Manager",
                    rationale="No single severe operational driver requires immediate escalation.",
                    expected_impact="Sustain adoption and detect deterioration early.",
                    approval_required=False,
                )
            )

        memory_warning = any("discount" in memory.content.lower() for memory in memories)
        do_not_do = ["Do not send an automated outreach without account-owner review."]
        if memory_warning:
            do_not_do.append("Do not repeat a blanket discount; prior memory indicates discounting was already used.")
        if discount_previously_ineffective:
            do_not_do.append(
                "Do not propose another generic discount; prior feedback indicates discount intervention was ineffective."
            )
            actions.append(
                ActionItem(
                    priority=len(actions) + 1,
                    action="Replace discount-led retention with a targeted adoption recovery plan tied to measurable workflow outcomes.",
                    owner="Clinic Success Leadership",
                    rationale="Historical feedback indicates previous discount interventions did not improve retention outcomes.",
                    expected_impact="Improve renewal probability through value realization rather than repeated price concessions.",
                    approval_required=True,
                )
            )
        if prediction.risk_band == "high":
            do_not_do.append("Do not wait for the next quarterly business review to intervene.")

        evidence = [
            f"Model risk: {prediction.lapse_probability:.1%} ({prediction.risk_band}).",
            *[
                f"{driver.feature}: {driver.clinic_value} ({driver.probability_impact:+.1%} impact)"
                for driver in prediction.top_drivers[:3]
            ],
            *[
                f"{hit.document} — {hit.section} (retrieval score {hit.score:.2f})"
                for hit in knowledge[:2]
            ],
        ]
        return Recommendation(
            executive_summary=(
                f"{profile.clinic_id} has {prediction.risk_band} lapse risk at "
                f"{prediction.lapse_probability:.1%}. Prioritize operational recovery before incentives, "
                "then align renewal stakeholders around measurable value."
            ),
            actions=actions[:4],
            do_not_do=do_not_do,
            evidence=evidence,
            confidence=min(0.95, 0.65 + len(prediction.top_drivers) * 0.04 + len(knowledge) * 0.03),
            generated_by="deterministic_policy_engine",
            requires_human_approval=any(
                action.approval_required for action in actions[:4]
            ),
            risk_assessment=f"{prediction.risk_band.title()} lapse risk based on the model prediction and clinic context.",
            rationale="Deterministic policy engine prioritized evidence-backed recovery actions and an explicit approval checkpoint for high-risk accounts.",
            recommended_actions=[action.action for action in actions[:4]],
        )
