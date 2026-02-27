"""
SqliteProgressRepository - Infrastructure Layer

Persists and retrieves ProgressRecord data using the
progress_records table in SQLite.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from infrastructure.persistence.database.database_connection import DatabaseConnection

logger = logging.getLogger(__name__)


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


class SqliteProgressRepository:
    """
    SQLite-backed store for progress records.

    Works with lightweight dicts (not full ProgressRecord domain objects)
    to keep the persistence layer decoupled from the heavier entity graph
    while still providing all the data the API needs.
    """

    def __init__(self, db: DatabaseConnection) -> None:
        self._db = db

    # ── Query methods ─────────────────────────────────────────────────────────

    def get_by_learner(self, learner_id: str) -> List[dict]:
        """All progress records for a learner, newest activity first."""
        rows = self._db.fetch_all(
            """
            SELECT * FROM progress_records
            WHERE learner_id = ?
            ORDER BY COALESCE(last_activity_at, created_at) DESC
            """,
            (learner_id,),
        )
        return [dict(row) for row in rows]

    def get_by_id(self, record_id: int) -> Optional[dict]:
        """Retrieve a single progress record by its integer row id."""
        row = self._db.fetch_one(
            "SELECT * FROM progress_records WHERE id = ?",
            (record_id,),
        )
        return dict(row) if row else None

    def get_by_repository_and_learner(
        self, repository_id: str, learner_id: str
    ) -> Optional[dict]:
        """Retrieve the unique record for (repository, learner)."""
        row = self._db.fetch_one(
            "SELECT * FROM progress_records WHERE repository_id = ? AND learner_id = ?",
            (repository_id, learner_id),
        )
        return dict(row) if row else None

    # ── Mutation methods ──────────────────────────────────────────────────────

    def upsert(
        self,
        repository_id: str,
        learner_id: str,
        status: str,
        progress_percentage: float,
        notes: str = "",
        difficulty_rating: Optional[int] = None,
        satisfaction_rating: Optional[int] = None,
        time_spent_minutes: int = 0,
    ) -> int:
        """Insert or update a progress record. Returns row id."""
        now = datetime.now().isoformat()

        existing = self.get_by_repository_and_learner(repository_id, learner_id)

        if existing:
            row_id: int = existing["id"]
            new_total = (existing.get("total_time_minutes") or 0) + time_spent_minutes
            started_at = existing.get("started_at")
            if not started_at and status == "in_progress":
                started_at = now
            completed_at = existing.get("completed_at")
            if not completed_at and status == "completed":
                completed_at = now

            with self._db.transaction() as conn:
                conn.execute(
                    """
                    UPDATE progress_records SET
                        status = ?,
                        progress_percentage = ?,
                        notes = ?,
                        difficulty_rating = COALESCE(?, difficulty_rating),
                        satisfaction_rating = COALESCE(?, satisfaction_rating),
                        total_time_minutes = ?,
                        started_at = ?,
                        completed_at = ?,
                        last_activity_at = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        status,
                        progress_percentage,
                        notes,
                        difficulty_rating,
                        satisfaction_rating,
                        new_total,
                        started_at,
                        completed_at,
                        now,
                        now,
                        row_id,
                    ),
                )
            return row_id

        # New record
        started_at = now if status == "in_progress" else None
        completed_at = now if status == "completed" else None
        with self._db.transaction() as conn:
            cur = conn.execute(
                """
                INSERT INTO progress_records
                    (repository_id, learner_id, status, progress_percentage,
                     notes, difficulty_rating, satisfaction_rating,
                     total_time_minutes, started_at, completed_at,
                     last_activity_at, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    repository_id,
                    learner_id,
                    status,
                    progress_percentage,
                    notes,
                    difficulty_rating,
                    satisfaction_rating,
                    time_spent_minutes,
                    started_at,
                    completed_at,
                    now,
                    now,
                    now,
                ),
            )
            return cur.lastrowid

    def delete(self, record_id: int) -> bool:
        """Delete a progress record. Returns True if a row was deleted."""
        with self._db.transaction() as conn:
            cur = conn.execute(
                "DELETE FROM progress_records WHERE id = ?", (record_id,)
            )
            return cur.rowcount > 0
