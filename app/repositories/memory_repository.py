from __future__ import annotations

from app.models.domain import MemoryItem
from app.repositories.database import Database


class MemoryRepository:
    def __init__(self, database: Database):
        self.database = database

    def add_session_message(
        self, session_id: str, clinic_id: str, role: str, content: str
    ) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO session_messages(session_id, clinic_id, role, content)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, clinic_id, role, content),
            )

    def get_session_messages(
        self, session_id: str, clinic_id: str, limit: int
    ) -> list[dict[str, str]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT role, content, created_at
                FROM session_messages
                WHERE session_id = ? AND clinic_id = ?
                ORDER BY id DESC LIMIT ?
                """,
                (session_id, clinic_id, limit),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def add_clinic_memory(self, item: MemoryItem) -> int:
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO clinic_memories(clinic_id, memory_type, content, importance)
                VALUES (?, ?, ?, ?)
                """,
                (item.clinic_id, item.memory_type, item.content, item.importance),
            )
            return int(cursor.lastrowid)

    def get_clinic_memories(self, clinic_id: str, limit: int) -> list[MemoryItem]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT id AS memory_id, clinic_id, memory_type, content, importance, created_at
                FROM clinic_memories
                WHERE clinic_id = ?
                ORDER BY importance DESC, id DESC LIMIT ?
                """,
                (clinic_id, limit),
            ).fetchall()
        return [MemoryItem.model_validate(dict(row)) for row in rows]
