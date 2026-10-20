from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import container_dependency
from app.core.container import ApplicationContainer
from app.services.model_registry import get_model_registry_status
from app.services.save_desk import save_desk_fields

router = APIRouter(prefix="/v1/operations", tags=["operations"])


@router.get("/dashboard")
def dashboard(
    limit: int = Query(default=100, ge=1, le=1000),
    container: ApplicationContainer = Depends(container_dependency),
) -> dict:
    profiles = [
        container.clinic_repository.get(clinic_id)
        for clinic_id in container.clinic_repository.list_ids(limit=10_000)
    ]
    profile_by_id = {profile.clinic_id: profile for profile in profiles}
    scored: list[dict] = []
    for clinic_id, probability, risk_band in container.ml_service.score_many(profiles):
        profile = profile_by_id[clinic_id]
        desk = save_desk_fields(
            lapse_probability=probability,
            value_at_risk=profile.value_at_risk,
            days_to_term=profile.days_to_term,
            risk_band=risk_band,
        )
        scored.append(
            {
                "clinic_id": clinic_id,
                "segment": profile.segment,
                "region": profile.region,
                "monthly_contract_value": profile.monthly_contract_value,
                "value_at_risk": profile.value_at_risk,
                "days_to_term": profile.days_to_term,
                "order_change_pct": profile.order_change_pct,
                "service_tickets_90d": profile.service_tickets_90d,
                "invoice_failures_90d": profile.invoice_failures_90d,
                "lapse_probability": probability,
                "risk_band": risk_band,
                "renewal_pressure": desk["renewal_pressure"],
                "save_priority": desk["save_priority"],
                "save_lane": desk["save_lane"],
            }
        )

    scored.sort(key=lambda item: item["lapse_probability"], reverse=True)
    high_risk = [item for item in scored if item["risk_band"] == "high"]
    medium_risk = [item for item in scored if item["risk_band"] == "medium"]
    renewal_30d = [item for item in scored if item["days_to_term"] <= 30]

    with container.database.connect() as connection:
        pending_approvals = connection.execute(
            "SELECT COUNT(*) AS count FROM renewal_tickets WHERE status = 'pending_approval'"
        ).fetchone()["count"]

    return {
        "summary": {
            "total_clinics": len(scored),
            "high_risk_clinics": len(high_risk),
            "medium_risk_clinics": len(medium_risk),
            "term_within_30_days": len(renewal_30d),
            "pending_approvals": int(pending_approvals),
            "value_at_risk": round(sum(float(item["value_at_risk"]) for item in high_risk), 2),
            "call_today": sum(item["save_lane"] == "call_today" for item in scored),
        },
        "clinics": scored[:limit],
    }


@router.get("/evaluation")
def evaluation(container: ApplicationContainer = Depends(container_dependency)) -> dict:
    evaluation_path = Path("artifacts/evaluations/agent_eval.json")
    model_path = container.settings.model_metadata_path
    evaluation_payload = (
        json.loads(evaluation_path.read_text(encoding="utf-8"))
        if evaluation_path.exists()
        else {"metrics": {}, "cases": []}
    )
    model_payload = (
        json.loads(model_path.read_text(encoding="utf-8")) if model_path.exists() else {}
    )
    return {"agent_evaluation": evaluation_payload, "model": model_payload}


@router.get("/traces")
def traces(
    limit: int = Query(default=50, ge=1, le=500),
    container: ApplicationContainer = Depends(container_dependency),
) -> dict:
    with container.database.connect() as connection:
        predictions = [
            dict(row)
            for row in connection.execute(
                """
                SELECT p.analysis_id, p.clinic_id, p.probability, p.risk_band,
                       p.model_version, p.created_at,
                       t.id AS ticket_id, t.status AS ticket_status
                FROM predictions p
                LEFT JOIN renewal_tickets t ON t.analysis_id = p.analysis_id
                ORDER BY p.created_at DESC, p.id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        ]
        tickets = [
            dict(row)
            for row in connection.execute(
                """
                SELECT id, analysis_id, clinic_id, title, status, created_at
                FROM renewal_tickets
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        ]
        feedback = [
            dict(row)
            for row in connection.execute(
                """
                SELECT id, analysis_id, rating, comment, created_at
                FROM feedback
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        ]
        memory_count = connection.execute(
            "SELECT COUNT(*) AS count FROM clinic_memories"
        ).fetchone()["count"]
        session_message_count = connection.execute(
            "SELECT COUNT(*) AS count FROM session_messages"
        ).fetchone()["count"]

    provider_status = container.provider_status
    retrieval_status = container.knowledge_service.status
    provider_available = bool(
        provider_status.get("provider_available", provider_status.get("ollama_available", False))
    )
    return {
        "predictions": predictions,
        "tickets": tickets,
        "feedback": feedback,
        "runtime": {
            "prediction_count": len(predictions),
            "ticket_count": len(tickets),
            "feedback_count": len(feedback),
            "memory_count": int(memory_count),
            "session_message_count": int(session_message_count),
            "agent_provider": container.settings.agent_provider,
            "model": provider_status.get("model", container.settings.ollama_model),
            "requested_provider": provider_status.get("requested_provider", container.settings.agent_provider),
            "generation_mode": provider_status.get("generation_mode", "deterministic"),
            "model_ready": container.ml_service.ready,
            "provider_available": provider_available,
            "ollama_available": bool(provider_status.get("ollama_available", False)),
            "fallback_used": bool(provider_status.get("fallback_used", False)),
            "fallback_reason": provider_status.get("fallback_reason"),
            "last_successful_llm_call": provider_status.get("last_successful_llm_call"),
            "retrieval_requested_backend": retrieval_status["requested_backend"],
            "retrieval_active_backend": retrieval_status["active_backend"],
            "retrieval_degraded": retrieval_status["degraded"],
            "retrieval_error": retrieval_status["error"],
        },
    }


@router.get("/model-registry")
def model_registry(container: ApplicationContainer = Depends(container_dependency)) -> dict:
    settings = container.settings
    if not settings.mlflow_use_model_registry:
        return {
            "enabled": False,
            "reason": "MLFLOW_USE_MODEL_REGISTRY is disabled.",
        }

    try:
        status = get_model_registry_status(
            tracking_uri=settings.mlflow_tracking_uri,
            registered_model_name=settings.mlflow_registered_model_name,
            deployment_alias=settings.mlflow_deployment_alias,
        )
        return {"enabled": True, **status}
    except Exception as exc:  # noqa: BLE001
        return {
            "enabled": True,
            "error": str(exc),
            "registered_model_name": settings.mlflow_registered_model_name,
            "deployment_alias": settings.mlflow_deployment_alias,
            "aliases": {},
            "versions": [],
            "events": [],
        }
