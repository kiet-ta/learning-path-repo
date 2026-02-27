"""
Progress Schemas - API Layer
Pydantic models for learning progress endpoints
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class ProgressStatusEnum(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


# ── Requests ──────────────────────────────────────────────────────────────────

class UpdateProgressRequest(BaseModel):
    """Partial update for a progress record."""
    progress_percentage: Optional[float] = Field(
        None, ge=0.0, le=100.0, description="Progress 0–100"
    )
    status: Optional[ProgressStatusEnum] = Field(None, description="New status")
    notes: Optional[str] = Field(None, max_length=4096, description="Learner notes")
    difficulty_rating: Optional[int] = Field(None, ge=1, le=5, description="Difficulty 1–5")
    satisfaction_rating: Optional[int] = Field(None, ge=1, le=5, description="Satisfaction 1–5")
    time_spent_minutes: Optional[int] = Field(
        None, ge=0, description="Additional minutes to add to total"
    )


# ── Responses ─────────────────────────────────────────────────────────────────

class ProgressRecordResponse(BaseModel):
    """Single progress record."""
    record_id: str = Field(..., description="Progress record UUID")
    repository_id: str = Field(..., description="Repository UUID")
    learner_id: str = Field(..., description="Learner identifier")
    status: ProgressStatusEnum
    progress_percentage: float
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_activity_at: Optional[datetime] = None
    total_time_spent_minutes: int
    difficulty_rating: Optional[int] = None
    satisfaction_rating: Optional[int] = None
    notes: str = ""
    created_at: datetime
    updated_at: datetime


class ProgressListResponse(BaseModel):
    """List of progress records for a learner."""
    learner_id: str
    records: List[ProgressRecordResponse]
    total_count: int
    completed_count: int
    in_progress_count: int
    overall_completion_percentage: float
