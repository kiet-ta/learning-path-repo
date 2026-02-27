"""
SqliteLearningPathRepository - Infrastructure Layer

Implements the ILearningPathStore Protocol from the use-case layer.
Persists and retrieves LearningPath domain aggregates and their nodes
using the learning_paths / learning_path_nodes tables in SQLite.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from domain.entities.learning_path import LearningPath, PathStatus
from infrastructure.persistence.database.database_connection import DatabaseConnection

logger = logging.getLogger(__name__)


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


class SqliteLearningPathRepository:
    """
    SQLite-backed store for LearningPath domain aggregates.

    Implements the ILearningPathStore Protocol expected by:
        application/use_cases/generate_learning_path_use_case.py

    The mapping is intentionally minimal: we store the aggregate's key
    fields and reconstructed domain objects use the
    SqliteRepositoryMetadataRepository to re-hydrate nodes.
    """

    def __init__(self, db: DatabaseConnection) -> None:
        self._db = db

    # ── Protocol methods ──────────────────────────────────────────────────────

    def save(self, path: LearningPath) -> int:
        """
        Persist a LearningPath aggregate.

        Returns the auto-increment database row ID.  The caller stores this
        ID for subsequent get_by_id calls.
        """
        with self._db.transaction() as conn:
            # Upsert by (learner_id, version) — use path_id as a unique token
            # We store path_id in the 'name' column-adjacent unique slot via an
            # extra text column in a real migration; for the current schema we
            # derive "version" from the number of existing paths for this learner.
            existing = conn.execute(
                "SELECT id FROM learning_paths WHERE learner_id = ? ORDER BY version DESC LIMIT 1",
                (path.learner_id,),
            ).fetchone()

            version = (existing["version"] + 1) if existing else 1

            cur = conn.execute(
                """
                INSERT INTO learning_paths
                    (version, learner_id, name, description,
                     total_estimated_hours, total_repositories,
                     status, generated_at, last_optimized_at)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    version,
                    path.learner_id,
                    path.name,
                    path.description,
                    path.total_estimated_hours,
                    path.total_repositories,
                    path.status.value if isinstance(path.status, PathStatus) else str(path.status),
                    path.created_at.isoformat(),
                    path.last_optimized_at.isoformat() if path.last_optimized_at else None,
                ),
            )
            lp_row_id: int = cur.lastrowid

            # Persist nodes
            for idx, node in enumerate(path.nodes):
                repo_id = str(node.repository.repository_id)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO learning_path_nodes
                        (learning_path_id, repository_id, order_index,
                         milestone, estimated_hours,
                         is_overridden, override_reason)
                    VALUES (?,?,?,?,?,?,?)
                    """,
                    (
                        lp_row_id,
                        repo_id,
                        idx,
                        getattr(node, "milestone", None),
                        node.repository.learning_hours_estimate,
                        False,
                        None,
                    ),
                )

        return lp_row_id

    def get_by_learner(self, learner_id: str) -> List[dict]:
        """
        Return lightweight dicts (not full domain objects) for the API list
        endpoint — avoids the N+1 query of full reconstruction.

        Each dict has: id, learner_id, name, description, status,
        total_estimated_hours, total_repositories, generated_at, version.
        """
        rows = self._db.fetch_all(
            "SELECT * FROM learning_paths WHERE learner_id = ? ORDER BY version DESC",
            (learner_id,),
        )
        return [dict(row) for row in rows]

    def get_by_id(self, learning_path_id: int) -> Optional[dict]:
        """Return a single learning path row by its integer DB id."""
        row = self._db.fetch_one(
            "SELECT * FROM learning_paths WHERE id = ?",
            (learning_path_id,),
        )
        return dict(row) if row else None

    def get_nodes(self, learning_path_id: int) -> List[dict]:
        """Return ordered node rows for a learning path."""
        rows = self._db.fetch_all(
            """
            SELECT lpn.*, r.name AS repo_name, r.primary_language, r.skill_type, r.skill_level
            FROM learning_path_nodes lpn
            JOIN repositories r ON r.id = lpn.repository_id
            WHERE lpn.learning_path_id = ?
            ORDER BY lpn.order_index
            """,
            (learning_path_id,),
        )
        return [dict(row) for row in rows]

    def count_by_learner(self, learner_id: str) -> int:
        row = self._db.fetch_one(
            "SELECT COUNT(*) AS cnt FROM learning_paths WHERE learner_id = ?",
            (learner_id,),
        )
        return int(row["cnt"]) if row else 0
