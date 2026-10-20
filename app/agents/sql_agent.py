from app.models.domain import ClinicProfile
from app.services.sql_service import SQLService


class SQLAgent:
    def __init__(self, service: SQLService):
        self.service = service

    async def get_profile(self, clinic_id: str) -> ClinicProfile:
        return self.service.clinic_profile(clinic_id)

    async def get_benchmark(self, segment: str) -> dict:
        return self.service.segment_benchmark(segment)
