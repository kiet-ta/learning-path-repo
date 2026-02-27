"""
Override Router - /api/v1/overrides

POST   /overrides               → create a manual override
GET    /overrides/{learner_id}  → list overrides for a learner
DELETE /overrides/{override_id} → remove an override
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from api.schemas.override_schemas import (
    CreateOverrideRequest,
    DeleteOverrideResponse,
    OverrideResponse,
    OverrideTypeEnum,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_override_repo():
    from api.dependencies.dependency_injection import get_db_connection
    return _SqliteOverrideRepository(db=get_db_connection())


# ---------------------------------------------------------------------------
# Lightweight inline repository (avoids a separate file until full impl needed)
# ---------------------------------------------------------------------------

class _SqliteOverrideRepository:
    """Minimal SQLite override repository using the overrides table."""

    def __init__(self, db) -> None:
        self._db = db

    def create(self, learner_id: str, repository_id: str, override_type: str,
               target_order=None, target_milestone=None, reason=None) -> int:
        now = datetime.now().isoformat()
        with self._db.transaction() as conn:
            cur = conn.execute(
                """
                INSERT INTO overrides
                    (repository_id, learner_id, override_type,
                     custom_order_index, custom_milestone, reason,
                     created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(repository_id, learner_id, override_type)
                DO UPDATE SET
                    custom_order_index = excluded.custom_order_index,
                    custom_milestone   = excluded.custom_milestone,
                    reason             = excluded.reason,
                    updated_at         = excluded.updated_at
                """,
                (repository_id, learner_id, override_type,
                 target_order, target_milestone, reason, now, now),
            )
            return cur.lastrowid

    def get_by_learner(self, learner_id: str) -> List[dict]:
        rows = self._db.fetch_all(
            "SELECT * FROM overrides WHERE learner_id = ? ORDER BY created_at DESC",
            (learner_id,),
        )
        return [dict(r) for r in rows]

    def delete(self, override_id: int) -> bool:
        with self._db.transaction() as conn:
            cur = conn.execute(
                "DELETE FROM overrides WHERE id = ?", (override_id,)
            )
            return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post(
    "/overrides",
    response_model=OverrideResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a manual override for a repository in a learner's path",
)
def create_override(
    request: CreateOverrideRequest,
    repo=Depends(_get_override_repo),
):
    row_id = repo.create(
        learner_id=request.learner_id,
        repository_id=request.repository_id,
        override_type=request.override_type.value,
        target_order=request.target_order,
        target_milestone=request.target_milestone,
        reason=request.reason,
    )
    return OverrideResponse(
        override_id=row_id,
        learner_id=request.learner_id,
        repository_id=request.repository_id,
        override_type=request.override_type,
        target_order=request.target_order,
        target_milestone=request.target_milestone,
        reason=request.reason,
        created_at=datetime.now().isoformat(),
    )


@router.get(
    "/overrides/{learner_id}",
    response_model=List[OverrideResponse],
    summary="List all overrides for a learner",
)
def list_overrides(learner_id: str, repo=Depends(_get_override_repo)):
    rows = repo.get_by_learner(learner_id)
    return [
        OverrideResponse(
            override_id=int(r["id"]),
            learner_id=r["learner_id"],
            repository_id=r["repository_id"],
            override_type=OverrideTypeEnum(r["override_type"]),
            target_order=r.get("custom_order_index"),
            target_milestone=r.get("custom_milestone"),
            reason=r.get("reason"),
            created_at=str(r.get("created_at", "")),
        )
        for r in rows
    ]


@router.delete(
    "/overrides/{override_id}",
    response_model=DeleteOverrideResponse,
    summary="Remove a manual override",
)
def delete_override(override_id: int, repo=Depends(_get_override_repo)):
    deleted = repo.delete(override_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Override '{override_id}' not found.",
        )
    return DeleteOverrideResponse(
        success=True,
        message=f"Override {override_id} deleted successfully.",
    )
