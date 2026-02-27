"""
SqliteRepositoryMetadataRepository - Infrastructure Layer

Implements the IRepositoryStore Protocol (defined in the use-case layer).
Persists and retrieves Repository domain entities via the SQLite
database defined in infrastructure/persistence/database/schema.py.

Table: repositories  (primary)
       repository_topics  (junction → topics)
       topics
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from domain.entities.repository import Repository
from domain.entities.skill import Skill, SkillLevel, SkillType
from domain.entities.topic import Topic
from domain.value_objects.repository_metadata import RepositoryMetadata
from infrastructure.persistence.database.database_connection import DatabaseConnection

logger = logging.getLogger(__name__)


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _row_to_repository(row, topics: List[Topic]) -> Repository:
    """Convert a sqlite3.Row (from repositories table) to a Repository entity."""
    skill: Optional[Skill] = None
    if row["skill_type"] and row["skill_level"]:
        try:
            skill = Skill(
                skill_type=SkillType(row["skill_type"].lower()),
                skill_level=SkillLevel(row["skill_level"].lower()),
            )
        except (ValueError, KeyError):
            pass  # unknown enum value — leave skill as None

    meta = RepositoryMetadata(
        lines_of_code=row["lines_of_code"] or 0,
        file_count=row["file_count"] or 0,
    )

    repo = Repository.__new__(Repository)
    # Bypass __post_init__ validation by setting attrs directly after creation.
    # We trust data persisted in the DB is already valid.
    object.__setattr__(repo, "repository_id", UUID(row["id"]))
    object.__setattr__(repo, "name", row["name"])
    object.__setattr__(repo, "path", row["path"])
    object.__setattr__(repo, "primary_language", row["primary_language"])
    object.__setattr__(repo, "description", row["description"])
    object.__setattr__(repo, "content_hash", row["content_hash"])
    object.__setattr__(repo, "complexity_score", float(row["complexity_score"] or 0.0))
    object.__setattr__(repo, "learning_hours_estimate", int(row["estimated_hours"] or 0))
    object.__setattr__(repo, "created_at", _parse_dt(row["created_at"]) or datetime.now())
    object.__setattr__(repo, "last_analyzed_at", _parse_dt(row["last_analyzed_at"]))
    object.__setattr__(repo, "primary_skill", skill)
    object.__setattr__(repo, "secondary_skills", set())
    object.__setattr__(repo, "topics", set(topics))
    object.__setattr__(repo, "metadata", meta)
    return repo


class SqliteRepositoryMetadataRepository:
    """
    SQLite-backed store for Repository domain entities.

    Implements the IRepositoryStore Protocol expected by:
        application/use_cases/generate_learning_path_use_case.py
    """

    def __init__(self, db: DatabaseConnection) -> None:
        self._db = db

    # ── Protocol methods ──────────────────────────────────────────────────────

    def get_all(self) -> List[Repository]:
        """Return every repository in the database."""
        rows = self._db.fetch_all("SELECT * FROM repositories ORDER BY name")
        return [self._hydrate(row) for row in rows]

    def get_by_ids(self, ids: List[UUID]) -> List[Repository]:
        """Return repositories matching the given UUIDs."""
        if not ids:
            return []
        placeholders = ",".join("?" * len(ids))
        str_ids = [str(i) for i in ids]
        rows = self._db.fetch_all(
            f"SELECT * FROM repositories WHERE id IN ({placeholders})", tuple(str_ids)
        )
        return [self._hydrate(row) for row in rows]

    def get_by_learner(self, learner_id: str) -> List[Repository]:
        """
        Return repositories that belong to at least one learning path for learner_id.
        Falls back to all repositories if no paths exist for the learner.
        """
        rows = self._db.fetch_all(
            """
            SELECT DISTINCT r.*
            FROM repositories r
            JOIN learning_path_nodes lpn ON lpn.repository_id = r.id
            JOIN learning_paths lp       ON lp.id = lpn.learning_path_id
            WHERE lp.learner_id = ?
            ORDER BY r.name
            """,
            (learner_id,),
        )
        if rows:
            return [self._hydrate(row) for row in rows]
        return self.get_all()

    # ── Extended query methods ─────────────────────────────────────────────────

    def get_paginated(
        self,
        page: int = 1,
        page_size: int = 20,
        skill_type: Optional[str] = None,
        skill_level: Optional[str] = None,
        language: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: str = "name",
        sort_order: str = "asc",
    ) -> tuple[List[Repository], int]:
        """Return (repositories_page, total_count) with optional filters."""
        allowed_sort = {
            "name", "primary_language", "skill_type", "skill_level",
            "complexity_score", "estimated_hours", "lines_of_code",
            "last_analyzed_at", "created_at",
        }
        col = sort_by if sort_by in allowed_sort else "name"
        direction = "DESC" if sort_order.lower() == "desc" else "ASC"

        where_clauses: List[str] = []
        params: List = []

        if skill_type:
            where_clauses.append("skill_type = ?")
            params.append(skill_type)
        if skill_level:
            where_clauses.append("skill_level = ?")
            params.append(skill_level)
        if language:
            where_clauses.append("primary_language = ?")
            params.append(language)
        if search:
            where_clauses.append("(name LIKE ? OR description LIKE ?)")
            like = f"%{search}%"
            params.extend([like, like])

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        count_row = self._db.fetch_one(
            f"SELECT COUNT(*) as cnt FROM repositories {where_sql}", tuple(params)
        )
        total = int(count_row["cnt"]) if count_row else 0

        offset = (page - 1) * page_size
        rows = self._db.fetch_all(
            f"SELECT * FROM repositories {where_sql} ORDER BY {col} {direction} LIMIT ? OFFSET ?",
            tuple(params + [page_size, offset]),
        )
        return [self._hydrate(row) for row in rows], total

    def save(self, repo: Repository) -> None:
        """Insert or replace a repository (upsert)."""
        with self._db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO repositories
                    (id, name, path, primary_language, description, content_hash,
                     skill_type, skill_level, complexity_score, estimated_hours,
                     lines_of_code, file_count, last_analyzed_at, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    path=excluded.path,
                    primary_language=excluded.primary_language,
                    description=excluded.description,
                    content_hash=excluded.content_hash,
                    skill_type=excluded.skill_type,
                    skill_level=excluded.skill_level,
                    complexity_score=excluded.complexity_score,
                    estimated_hours=excluded.estimated_hours,
                    lines_of_code=excluded.lines_of_code,
                    file_count=excluded.file_count,
                    last_analyzed_at=excluded.last_analyzed_at,
                    updated_at=excluded.updated_at
                """,
                (
                    str(repo.repository_id),
                    repo.name,
                    repo.path,
                    repo.primary_language,
                    repo.description,
                    repo.content_hash,
                    repo.primary_skill.skill_type.value if repo.primary_skill else None,
                    repo.primary_skill.skill_level.value if repo.primary_skill else None,
                    repo.complexity_score,
                    repo.learning_hours_estimate,
                    repo.metadata.lines_of_code,
                    repo.metadata.file_count,
                    repo.last_analyzed_at.isoformat() if repo.last_analyzed_at else None,
                    repo.created_at.isoformat(),
                    datetime.now().isoformat(),
                ),
            )

    # ── Private helpers ────────────────────────────────────────────────────────

    def _hydrate(self, row) -> Repository:
        topics = self._load_topics(row["id"])
        return _row_to_repository(row, topics)

    def _load_topics(self, repo_id: str) -> List[Topic]:
        rows = self._db.fetch_all(
            """
            SELECT t.name, t.category, rt.relevance_score
            FROM topics t
            JOIN repository_topics rt ON rt.topic_id = t.id
            WHERE rt.repository_id = ?
            """,
            (repo_id,),
        )
        _VALID_CATEGORIES = {
            "programming_language", "framework", "library", "tool",
            "concept", "methodology", "platform", "database", "architecture",
        }
        topics = []
        for r in rows:
            try:
                raw_cat = (r["category"] or "concept").lower()
                category = raw_cat if raw_cat in _VALID_CATEGORIES else "concept"
                topics.append(
                    Topic(
                        name=r["name"],
                        description=r["name"],  # DB has no description column; use name
                        category=category,
                    )
                )
            except Exception:
                pass  # skip malformed topic rows
        return topics
