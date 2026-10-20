from __future__ import annotations

from app.core.exceptions import ClinicNotFoundError
from app.models.domain import ClinicProfile
from app.repositories.database import Database


class ClinicRepository:
    def __init__(self, database: Database):
        self.database = database

    def get(self, clinic_id: str) -> ClinicProfile:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM clinic_current_features WHERE clinic_id = ?", (clinic_id,)
            ).fetchone()
        if row is None:
            raise ClinicNotFoundError(f"Clinic {clinic_id!r} was not found")
        payload = dict(row)
        payload.setdefault("clinic_notes", "")
        payload["stocking_complete"] = bool(payload["stocking_complete"])
        return ClinicProfile.model_validate(payload)

    def list_ids(self, limit: int = 100) -> list[str]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT clinic_id FROM clinic_current_features ORDER BY clinic_id LIMIT ?", (limit,)
            ).fetchall()
        return [str(row["clinic_id"]) for row in rows]

    def segment_benchmark(self, segment: str) -> dict[str, float | int | str]:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    segment,
                    COUNT(*) AS clinic_count,
                    AVG(orders_30d) AS avg_orders_30d,
                    AVG(active_cabinet_ratio_30d) AS avg_active_cabinet_ratio_30d,
                    AVG(buyer_count) AS avg_buyer_count,
                    AVG(order_change_pct) AS avg_order_change_pct,
                    AVG(service_tickets_90d) AS avg_service_tickets_90d,
                    AVG(nps) AS avg_nps,
                    AVG(lapsed) AS observed_lapse_rate
                FROM clinic_history_features
                WHERE segment = ?
                GROUP BY segment
                """,
                (segment,),
            ).fetchone()
        return dict(row) if row else {"segment": segment, "clinic_count": 0}
