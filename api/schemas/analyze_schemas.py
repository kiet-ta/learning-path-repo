"""
Analyze Schemas - API Layer
Pydantic models for AI-powered repository analysis endpoints
"""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# ── Requests ──────────────────────────────────────────────────────────────────

class AnalyzeRepositoryRequest(BaseModel):
    """Trigger AI analysis on a repository."""
    repository_id: str = Field(..., description="Repository UUID to analyse")
    force_reanalyze: bool = Field(
        default=False, description="Re-run even if already analysed"
    )


# ── Responses ─────────────────────────────────────────────────────────────────

class SkillAnalysisResult(BaseModel):
    skill_type: str
    skill_level: str
    confidence: float = Field(..., ge=0.0, le=1.0)


class TopicAnalysisResult(BaseModel):
    name: str
    category: str
    relevance_score: float = Field(..., ge=0.0, le=1.0)


class AnalyzeRepositoryResponse(BaseModel):
    """Result of an AI analysis run."""
    repository_id: str
    primary_skill: Optional[SkillAnalysisResult] = None
    topics_detected: List[TopicAnalysisResult] = Field(default_factory=list)
    complexity_score: float = Field(..., ge=0.0, le=10.0)
    estimated_hours: int
    language_distribution: Dict[str, float] = Field(default_factory=dict)
    has_tests: bool
    has_ci: bool
    has_documentation: bool
    lines_of_code: int
    analysis_duration_seconds: float
    model_used: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
