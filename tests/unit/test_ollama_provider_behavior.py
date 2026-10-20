from __future__ import annotations

import pytest

from app.agents.providers.microsoft_ollama import MicrosoftOllamaRecommendationProvider
from app.core.exceptions import AgentProviderError
from app.models.domain import ActionItem, ClinicProfile, PredictionResult, Recommendation


@pytest.fixture
def sample_profile() -> ClinicProfile:
    return ClinicProfile(
        clinic_id="CLN-001",
        segment="growth",
        region="us-east",
        clinic_notes="IT-led deployment; needs stronger adoption plan.",
        stocked_cabinets=250,
        active_cabinet_ratio_30d=0.22,
        buyer_count=0,
        tenure_months=18,
        monthly_contract_value=12000.0,
        orders_30d=20,
        order_change_pct=-25.0,
        service_tickets_90d=4,
        nps=20,
        days_to_term=45,
        invoice_failures_90d=1,
        stocking_complete=True,
        service_ticket_rate=0.25,
        activity_score=0.7,
        term_pressure=0.8,
        value_at_risk=8000.0,
        lapsed=1,
    )


@pytest.fixture
def sample_prediction() -> PredictionResult:
    return PredictionResult(
        clinic_id="CLN-001",
        lapse_probability=0.83,
        risk_band="high",
        top_drivers=[],
        model_version="test-v1",
    )


@pytest.mark.asyncio
async def test_structured_response_parsing(sample_profile: ClinicProfile, sample_prediction: PredictionResult) -> None:
    provider = MicrosoftOllamaRecommendationProvider("http://localhost:11434", "qwen2.5:7b", None)
    provider.ollama_available = True

    async def fake_chat(prompt: str, *, retry: bool = False) -> str:
        return '{"executive_summary": "summary", "risk_assessment": "high", "recommended_actions": ["Call the clinic"], "rationale": "Need follow-up", "evidence": ["Model risk 83%"], "do_not_do": ["Do not discount"], "confidence": 0.8, "requires_human_approval": true}'

    provider._chat = fake_chat  # type: ignore[assignment]
    recommendation = await provider.generate(sample_profile, sample_prediction, {}, [], [])
    assert recommendation.executive_summary == "summary"
    assert recommendation.actions[0].action == "Call the clinic"
    assert recommendation.requires_human_approval is True


@pytest.mark.asyncio
async def test_invalid_json_retries_once(sample_profile: ClinicProfile, sample_prediction: PredictionResult) -> None:
    provider = MicrosoftOllamaRecommendationProvider("http://localhost:11434", "qwen2.5:7b", None)
    provider.ollama_available = True

    calls: list[str] = []

    async def fake_chat(prompt: str, *, retry: bool = False) -> str:
        calls.append(prompt)
        if retry:
            return '{"executive_summary": "ok", "risk_assessment": "high", "recommended_actions": ["Follow up"], "rationale": "Need follow-up", "evidence": ["Model risk 83%"], "do_not_do": ["Do not discount"], "confidence": 0.8, "requires_human_approval": true}'
        return 'not-json'

    provider._chat = fake_chat  # type: ignore[assignment]
    recommendation = await provider.generate(sample_profile, sample_prediction, {}, [], [])
    assert recommendation.executive_summary == "ok"
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_confidence_percent_is_normalized(sample_profile: ClinicProfile, sample_prediction: PredictionResult) -> None:
    provider = MicrosoftOllamaRecommendationProvider("http://localhost:11434", "qwen2.5:7b", None)
    provider.ollama_available = True

    async def fake_chat(prompt: str, *, retry: bool = False) -> str:
        return '{"executive_summary": "summary", "risk_assessment": "high", "recommended_actions": ["Call the clinic"], "rationale": "Need follow-up", "evidence": ["Model risk 83%"], "do_not_do": ["Do not discount"], "confidence": 98, "requires_human_approval": true}'

    provider._chat = fake_chat  # type: ignore[assignment]
    recommendation = await provider.generate(sample_profile, sample_prediction, {}, [], [])
    assert recommendation.confidence == 0.98


@pytest.mark.asyncio
async def test_unavailable_ollama_raises_clear_error(sample_profile: ClinicProfile, sample_prediction: PredictionResult) -> None:
    provider = MicrosoftOllamaRecommendationProvider("http://localhost:11434", "qwen2.5:7b", None)
    provider.ollama_available = False
    with pytest.raises(AgentProviderError, match="Ollama is unavailable"):
        await provider.generate(sample_profile, sample_prediction, {}, [], [])


@pytest.mark.asyncio
async def test_reviewer_rejects_unsupported_claims(sample_profile: ClinicProfile, sample_prediction: PredictionResult) -> None:
    from app.agents.reviewer_agent import ReviewerAgent

    recommendation = Recommendation(
        executive_summary="Summary",
        actions=[
            ActionItem(
                priority=1,
                action="Call the clinic",
                owner="CSM",
                rationale="Need to engage",
                expected_impact="Reduce risk",
                approval_required=False,
            )
        ],
        do_not_do=["Do not discount"],
        evidence=["Clinic said they are thrilled with the product"],
        confidence=0.6,
        generated_by="test",
    )
    review = await ReviewerAgent().run(sample_profile, sample_prediction, recommendation)
    assert review.passed is False
    assert any("unsupported clinic claim" in issue.lower() for issue in review.issues)
