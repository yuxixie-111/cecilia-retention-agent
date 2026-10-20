from __future__ import annotations


def approved_interventions() -> list[dict[str, str | bool]]:
    return [
        {
            "name": "stocking_visit",
            "summary": "Send a field visit to finish cabinet setup, par levels, and the first replenishment cycle.",
            "best_for": "Idle cabinets, incomplete stocking, or a rollout that never left the dock.",
            "owner": "Field Supply",
            "approval_required": False,
        },
        {
            "name": "order_reset",
            "summary": "Reset par levels on the cabinets whose orders fell the most.",
            "best_for": "A drop in standing orders or a clinic buying around the agreement.",
            "owner": "Field Supply",
            "approval_required": False,
        },
        {
            "name": "term_review",
            "summary": "Hold a term review with fill rate, backorders, cabinet use, and a dated recovery plan.",
            "best_for": "Agreements inside 60 days of term, or a medical director who has not seen the numbers.",
            "owner": "Account Lead",
            "approval_required": True,
        },
        {
            "name": "service_review",
            "summary": "Open a service review for short shipments, damage, and missed delivery windows.",
            "best_for": "Repeated service tickets or a clinic that stopped reordering after a bad shipment.",
            "owner": "Clinic Supply + Service",
            "approval_required": False,
        },
        {
            "name": "buyer_coverage",
            "summary": "Name a buyer for each cabinet and a backup when that person is out.",
            "best_for": "No buyer, or a single buyer covering too many rooms.",
            "owner": "Field Supply Lead",
            "approval_required": False,
        },
        {
            "name": "priced_commitment",
            "summary": "Offer a limited price change only when the clinic commits to cabinet use or a stocking date.",
            "best_for": "Price friction after the service and stocking issues are already being worked.",
            "owner": "Account Lead",
            "approval_required": True,
        },
    ]
