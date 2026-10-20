import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import container_dependency
from app.api.main import app
from app.core.config import get_settings
from app.core.container import ApplicationContainer


@pytest.fixture
def client_factory(tmp_path: Path):
    def build(**overrides) -> TestClient:
        settings = get_settings()
        database_path = tmp_path / "retention.db"
        model_path = tmp_path / "lapse_model.joblib"
        metadata_path = tmp_path / "lapse_model_metadata.json"
        shutil.copy2(settings.database_path, database_path)
        shutil.copy2(settings.model_path, model_path)
        if settings.model_metadata_path.exists():
            shutil.copy2(settings.model_metadata_path, metadata_path)
        test_settings = replace(
            settings,
            database_path=database_path,
            model_path=model_path,
            model_metadata_path=metadata_path,
            retrieval_backend="lexical",
            retrieval_chroma_persist_path=tmp_path / "chroma",
            **overrides,
        )
        container = ApplicationContainer(test_settings)
        app.dependency_overrides[container_dependency] = lambda: container
        return TestClient(app)

    yield build
    app.dependency_overrides.clear()


@pytest.mark.slow
def test_health_and_analysis_api(client_factory) -> None:
    client = client_factory()
    health = client.get("/health")
    assert health.status_code == 200
    clinic_id = client.get("/v1/clinics/high-risk?limit=1").json()[0]["clinic_id"]
    response = client.post(
        "/v1/analysis",
        json={"clinic_id": clinic_id, "session_id": "api-test", "create_ticket": False},
    )
    assert response.status_code == 200
    assert response.json()["data"]["prediction"]["clinic_id"] == clinic_id


def test_operations_dashboard(client_factory) -> None:
    client = client_factory()
    response = client.get("/v1/operations/dashboard?limit=20")
    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["total_clinics"] > 0
    assert len(payload["clinics"]) == 20
    assert (
        payload["clinics"][0]["lapse_probability"]
        >= payload["clinics"][-1]["lapse_probability"]
    )


def test_operations_evaluation_and_traces(client_factory) -> None:
    client = client_factory()
    evaluation = client.get("/v1/operations/evaluation")
    traces = client.get("/v1/operations/traces")
    registry = client.get("/v1/operations/model-registry")
    assert evaluation.status_code == 200
    assert traces.status_code == 200
    assert registry.status_code == 200
    assert "agent_evaluation" in evaluation.json()
    assert "runtime" in traces.json()
    assert "enabled" in registry.json()


def test_deterministic_analysis_api(client_factory) -> None:
    client = client_factory(agent_provider="deterministic")
    clinic_id = client.get("/v1/clinics/high-risk?limit=1").json()[0]["clinic_id"]
    response = client.post(
        "/v1/analysis",
        json={"clinic_id": clinic_id, "session_id": "deterministic-api-test"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["provider"] == "deterministic"
    assert payload["model"] == "rules-v1"


def test_retention_chat_ranks_clinics_with_tools(client_factory) -> None:
    client = client_factory(agent_provider="deterministic")
    response = client.post(
        "/v1/chat",
        json={
            "message": "Show me the 3 highest-risk clinics",
            "session_id": "chat-api-test",
            "history": [],
        },
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["provider"] == "deterministic_chat"
    assert payload["tools_used"] == ["list_high_risk_clinics"]
    assert "Top 3" in payload["answer"]
    assert payload["answer"].count("CLN-") == 3


def test_retention_chat_explains_discount_with_clinic_evidence(client_factory) -> None:
    client = client_factory(agent_provider="deterministic")
    response = client.post(
        "/v1/chat",
        json={
            "message": "Why shouldn't clinic 02 get a discount?",
            "session_id": "chat-discount-test",
        },
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert "CLN-0002" in payload["answer"]
    assert "can never get a discount" in payload["answer"]
    assert "get_clinic_profile" in payload["tools_used"]
    assert "predict_lapse" in payload["tools_used"]
    assert "search_renewal_playbooks" in payload["tools_used"]
