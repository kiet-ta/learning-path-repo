"""
Override Schemas - API Layer
Pydantic models for manual override endpoints
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class OverrideTypeEnum(str, Enum):
    REORDER = "reorder"
    SKIP = "skip"
    MILESTONE = "milestone"
    NOTE = "note"


# ── Requests ──────────────────────────────────────────────────────────────────

class CreateOverrideRequest(BaseModel):
    """Create a new manual override for a repository in a learner's path."""
    learner_id: str = Field(..., description="Learner identifier")
    repository_id: str = Field(..., description="Repository UUID to override")
    override_type: OverrideTypeEnum = Field(..., description="Type of override")
    target_order: Optional[int] = Field(
        None, ge=0, description="Desired order index (REORDER)"
    )
    target_milestone: Optional[str] = Field(
        None, description="Target milestone phase (MILESTONE)"
    )
    reason: Optional[str] = Field(None, max_length=1024, description="Human-readable reason")


# ── Responses ─────────────────────────────────────────────────────────────────

class OverrideResponse(BaseModel):
    """Persisted override record."""
    override_id: int = Field(..., description="Database row ID")
    learner_id: str
    repository_id: str
    override_type: OverrideTypeEnum
    target_order: Optional[int] = None
    target_milestone: Optional[str] = None
    reason: Optional[str] = None
    created_at: str  # ISO-8601 timestamp


class DeleteOverrideResponse(BaseModel):
    """Confirmation of override deletion."""
    success: bool = True
    message: str
