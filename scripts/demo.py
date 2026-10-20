from __future__ import annotations

import asyncio

from app.core.container import get_container


async def main() -> None:
    container = get_container()
    candidates = []
    for clinic_id in container.clinic_repository.list_ids(limit=200):
        profile = container.clinic_repository.get(clinic_id)
        prediction = container.ml_service.predict(profile, top_n=3)
        candidates.append((prediction.lapse_probability, clinic_id))
    clinic_id = max(candidates)[1]
    result = await container.workflow.analyze(
        clinic_id, session_id="local-demo", create_ticket=True
    )
    print(result.report_markdown)
    print(f"\nAnalysis ID: {result.analysis_id}")
    print(f"Ticket ID: {result.ticket_id}")
    print(f"Provider: {result.recommendation.generated_by}")


if __name__ == "__main__":
    asyncio.run(main())
