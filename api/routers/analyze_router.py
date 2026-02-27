"""
Analyze Router - /api/v1/analyze

POST /analyze → trigger AI-powered analysis of a repository
"""
from __future__ import annotations

import logging
import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies.dependency_injection import get_repository_store
from api.schemas.analyze_schemas import (
    AnalyzeRepositoryRequest,
    AnalyzeRepositoryResponse,
    SkillAnalysisResult,
    TopicAnalysisResult,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/analyze",
    response_model=AnalyzeRepositoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Run AI analysis on a repository",
)
def analyze_repository(
    request: AnalyzeRepositoryRequest,
    store=Depends(get_repository_store),
):
    """
    Trigger analysis for a single repository.

    In the current implementation the AI/NLP layer (ai-service) is a stub, so
    this endpoint performs basic heuristic analysis — complexity scoring via
    lines-of-code and topic inference from the primary language.

    When the ai-service becomes functional, this endpoint will forward the
    request and return the richer model output.
    """
    from uuid import UUID

    try:
        uid = UUID(request.repository_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid repository UUID: {request.repository_id}",
        )

    repos = store.get_by_ids([uid])
    if not repos:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{request.repository_id}' not found.",
        )

    repo = repos[0]

    # Skip if already analysed unless force flag is set
    if repo.last_analyzed_at and not request.force_reanalyze:
        pass  # fall through — return existing analysis data

    start = time.monotonic()

    # --- Heuristic analysis (placeholder for AI service) ---
    loc = repo.metadata.lines_of_code
    complexity = round(min(10.0, loc / 500.0), 2)
    estimated_hours = max(1, loc // 100)

    skill_result: SkillAnalysisResult | None = None
    if repo.primary_skill:
        skill_result = SkillAnalysisResult(
            skill_type=repo.primary_skill.skill_type.value,
            skill_level=repo.primary_skill.skill_level.value,
            confidence=0.85,
        )

    topics = [
        TopicAnalysisResult(name=t.name, category=t.category, relevance_score=1.0)
        for t in repo.topics
    ]

    # Persist updated complexity + analyzed_at
    repo_store = store
    try:
        object.__setattr__(repo, "complexity_score", complexity)
        object.__setattr__(repo, "learning_hours_estimate", estimated_hours)
        object.__setattr__(repo, "last_analyzed_at", datetime.now())
        repo_store.save(repo)
    except Exception as exc:
        logger.warning("Could not persist analysis result for %s: %s", repo.name, exc)

    duration = round(time.monotonic() - start, 4)

    return AnalyzeRepositoryResponse(
        repository_id=str(repo.repository_id),
        primary_skill=skill_result,
        topics_detected=topics,
        complexity_score=complexity,
        estimated_hours=estimated_hours,
        language_distribution={repo.primary_language: 1.0},
        has_tests=repo.metadata.has_tests,
        has_ci=repo.metadata.has_ci,
        has_documentation=repo.metadata.has_documentation,
        lines_of_code=loc,
        analysis_duration_seconds=duration,
        model_used="heuristic-v1",
        warnings=["AI service not yet connected — using heuristic analysis."],
    )
