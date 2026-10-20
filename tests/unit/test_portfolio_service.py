from app.core.config import get_settings
from app.repositories.clinic_repository import ClinicRepository
from app.repositories.database import Database
from app.services.ml_service import MLService
from app.services.portfolio_service import PortfolioService


def test_portfolio_service_returns_ranked_filtered_clinics() -> None:
    settings = get_settings()
    database = Database(settings.database_path)
    repository = ClinicRepository(database)
    ml_service = MLService(settings.model_path, settings.risk_high, settings.risk_medium)
    service = PortfolioService(repository, ml_service)

    rows = service.ranked_clinics(limit=5)

    assert len(rows) == 5
    assert rows[0]["lapse_probability"] >= rows[-1]["lapse_probability"]
    assert all("clinic_id" in row for row in rows)
    assert all(row["ranking_basis"] == "lapse_probability_desc" for row in rows)
    assert all("save_priority" in row and "save_lane" in row for row in rows)

    by_priority = service.ranked_clinics(limit=5, rank_by="save_priority")
    assert by_priority[0]["save_priority"] >= by_priority[-1]["save_priority"]
    assert all(row["ranking_basis"] == "save_priority_desc" for row in by_priority)
