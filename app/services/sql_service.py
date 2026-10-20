from app.models.domain import ClinicProfile
from app.repositories.clinic_repository import ClinicRepository


class SQLService:
    """Read-only, allow-listed analytical queries used by the SQL agent."""

    def __init__(self, repository: ClinicRepository):
        self.repository = repository

    def clinic_profile(self, clinic_id: str) -> ClinicProfile:
        return self.repository.get(clinic_id)

    def segment_benchmark(self, segment: str) -> dict[str, float | int | str]:
        benchmark = self.repository.segment_benchmark(segment)
        return {
            key: round(value, 4) if isinstance(value, float) else value
            for key, value in benchmark.items()
        }
