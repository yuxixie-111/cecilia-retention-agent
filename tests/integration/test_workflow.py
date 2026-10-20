import pytest

from app.core.container import get_container


@pytest.mark.slow
@pytest.mark.asyncio
async def test_end_to_end_workflow() -> None:
    container = get_container()
    clinic_id = container.clinic_repository.list_ids(limit=1)[0]
    result = await container.workflow.analyze(clinic_id, session_id="pytest", persist=False)
    assert 0 <= result.prediction.lapse_probability <= 1
    assert result.recommendation.actions
    assert "Retention Analysis" in result.report_markdown
    assert result.review.score >= 0.6
