from fastapi import APIRouter, Depends, Query

from app.api.dependencies import container_dependency
from app.core.container import ApplicationContainer
from app.models.domain import ClinicProfile

router = APIRouter(prefix="/v1/clinics", tags=["clinics"])


@router.get("/high-risk")
def high_risk_clinics(
    limit: int = Query(default=10, ge=1, le=100),
    container: ApplicationContainer = Depends(container_dependency),
) -> list[dict]:
    profiles = [
        container.clinic_repository.get(clinic_id)
        for clinic_id in container.clinic_repository.list_ids(limit=10_000)
    ]
    profile_by_id = {profile.clinic_id: profile for profile in profiles}
    results = []
    for clinic_id, probability, risk_band in container.ml_service.score_many(profiles):
        profile = profile_by_id[clinic_id]
        results.append(
            {
                "clinic_id": clinic_id,
                "segment": profile.segment,
                "monthly_contract_value": profile.monthly_contract_value,
                "lapse_probability": probability,
                "risk_band": risk_band,
            }
        )
    return sorted(results, key=lambda item: item["lapse_probability"], reverse=True)[:limit]


@router.get("/{clinic_id}", response_model=ClinicProfile)
def get_clinic(
    clinic_id: str,
    container: ApplicationContainer = Depends(container_dependency),
) -> ClinicProfile:
    return container.clinic_repository.get(clinic_id)
