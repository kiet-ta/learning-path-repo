"""
Progress Router - /api/v1/progress

GET   /progress/{learner_id}                 → all progress records for a learner
GET   /progress/{learner_id}/{repository_id} → specific record
PATCH /progress/{learner_id}/{repository_id} → update progress
"""
from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status

from api.schemas.progress_schemas import (
    ProgressListResponse,
    ProgressRecordResponse,
    ProgressStatusEnum,
    UpdateProgressRequest,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_progress_repo():
    from api.dependencies.dependency_injection import get_db_connection
    from infrastructure.persistence.repositories.sqlite_progress_repository import (
        SqliteProgressRepository,
    )
    return SqliteProgressRepository(db=get_db_connection())


def _row_to_schema(row: dict) -> ProgressRecordResponse:
    def _dt(v) -> datetime | None:
        if not v:
            return None
        try:
            return datetime.fromisoformat(str(v))
        except (ValueError, TypeError):
            return None

    return ProgressRecordResponse(
        record_id=str(row.get("id", "")),
        repository_id=str(row.get("repository_id", "")),
        learner_id=str(row.get("learner_id", "")),
        status=ProgressStatusEnum(row.get("status", "not_started")),
        progress_percentage=float(row.get("progress_percentage", 0.0)),
        started_at=_dt(row.get("started_at")),
        completed_at=_dt(row.get("completed_at")),
        last_activity_at=_dt(row.get("last_activity_at")),
        total_time_spent_minutes=int(row.get("total_time_minutes", 0)),
        difficulty_rating=row.get("difficulty_rating"),
        satisfaction_rating=row.get("satisfaction_rating"),
        notes=row.get("notes", "") or "",
        created_at=_dt(row.get("created_at")) or datetime.now(),
        updated_at=_dt(row.get("updated_at")) or datetime.now(),
    )


@router.get(
    "/progress/{learner_id}",
    response_model=ProgressListResponse,
    summary="Get all progress records for a learner",
)
def get_learner_progress(
    learner_id: str,
    repo=Depends(_get_progress_repo),
):
    rows = repo.get_by_learner(learner_id)
    records = [_row_to_schema(r) for r in rows]
    completed = sum(1 for r in records if r.status == ProgressStatusEnum.COMPLETED)
    in_progress = sum(1 for r in records if r.status == ProgressStatusEnum.IN_PROGRESS)
    total = len(records)
    avg = (sum(r.progress_percentage for r in records) / total) if total else 0.0

    return ProgressListResponse(
        learner_id=learner_id,
        records=records,
        total_count=total,
        completed_count=completed,
        in_progress_count=in_progress,
        overall_completion_percentage=round(avg, 2),
    )


@router.get(
    "/progress/{learner_id}/{repository_id}",
    response_model=ProgressRecordResponse,
    summary="Get progress for a specific repository",
)
def get_progress_record(
    learner_id: str,
    repository_id: str,
    repo=Depends(_get_progress_repo),
):
    row = repo.get_by_repository_and_learner(repository_id, learner_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No progress record found for learner '{learner_id}' and repository '{repository_id}'.",
        )
    return _row_to_schema(row)


@router.patch(
    "/progress/{learner_id}/{repository_id}",
    response_model=ProgressRecordResponse,
    summary="Create or update progress for a repository",
)
def update_progress(
    learner_id: str,
    repository_id: str,
    request: UpdateProgressRequest,
    repo=Depends(_get_progress_repo),
):
    # Read existing to compute defaults
    existing = repo.get_by_repository_and_learner(repository_id, learner_id)

    current_pct = float(existing.get("progress_percentage", 0.0)) if existing else 0.0
    current_status = existing.get("status", "not_started") if existing else "not_started"
    current_notes = existing.get("notes", "") if existing else ""

    new_pct = request.progress_percentage if request.progress_percentage is not None else current_pct
    new_status = request.status.value if request.status else current_status
    new_notes = request.notes if request.notes is not None else current_notes

    repo.upsert(
        repository_id=repository_id,
        learner_id=learner_id,
        status=new_status,
        progress_percentage=new_pct,
        notes=new_notes,
        difficulty_rating=request.difficulty_rating,
        satisfaction_rating=request.satisfaction_rating,
        time_spent_minutes=request.time_spent_minutes or 0,
    )

    updated = repo.get_by_repository_and_learner(repository_id, learner_id)
    return _row_to_schema(updated)
