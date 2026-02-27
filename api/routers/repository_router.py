"""
Repository Router - /api/v1/repositories

GET  /repositories            → paginated list with filters
GET  /repositories/{id}       → single repository detail
GET  /repositories/stats      → aggregate statistics
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.dependencies.dependency_injection import get_repository_store
from api.schemas.repository_schemas import (
    RepositoryDetailResponse,
    RepositoryListResponse,
    RepositoryResponse,
    RepositoryStatsResponse,
    TopicResponse,
)
from domain.entities.repository import Repository

router = APIRouter()
logger = logging.getLogger(__name__)


def _repo_to_schema(repo: Repository) -> RepositoryResponse:
    topics = [
        TopicResponse(
            name=t.name,
            category=t.category,
            relevance_score=1.0,
        )
        for t in repo.topics
    ]
    return RepositoryResponse(
        id=str(repo.repository_id),
        name=repo.name,
        path=repo.path,
        primary_language=repo.primary_language,
        description=repo.description,
        skill_type=repo.primary_skill.skill_type.value if repo.primary_skill else None,
        skill_level=repo.primary_skill.level.value if repo.primary_skill else None,
        complexity_score=repo.complexity_score,
        estimated_hours=repo.learning_hours_estimate,
        lines_of_code=repo.metadata.lines_of_code,
        file_count=repo.metadata.file_count,
        topics=topics,
        last_analyzed_at=repo.last_analyzed_at,
        created_at=repo.created_at,
    )


@router.get(
    "/repositories",
    response_model=RepositoryListResponse,
    summary="List repositories with optional filters and pagination",
)
def list_repositories(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    skill_type: Optional[str] = Query(None, description="Filter by skill type"),
    skill_level: Optional[str] = Query(None, description="Filter by skill level"),
    language: Optional[str] = Query(None, description="Filter by programming language"),
    search: Optional[str] = Query(None, description="Search name/description"),
    sort_by: str = Query("name", description="Sort field"),
    sort_order: str = Query("asc", description="asc or desc"),
    store=Depends(get_repository_store),
):
    repos, total = store.get_paginated(
        page=page,
        page_size=page_size,
        skill_type=skill_type,
        skill_level=skill_level,
        language=language,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    import math
    total_pages = math.ceil(total / page_size) if page_size else 1
    return RepositoryListResponse(
        total_count=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1,
        repositories=[_repo_to_schema(r) for r in repos],
        filters_applied={
            "skill_type": skill_type,
            "skill_level": skill_level,
            "language": language,
            "search": search,
        },
    )


@router.get(
    "/repositories/stats",
    response_model=RepositoryStatsResponse,
    summary="Aggregate statistics across all repositories",
)
def get_repository_stats(store=Depends(get_repository_store)):
    repos = store.get_all()

    by_skill_type: dict = {}
    by_skill_level: dict = {}
    by_language: dict = {}
    total_hours = 0
    complexity_sum = 0.0

    for repo in repos:
        by_language[repo.primary_language] = by_language.get(repo.primary_language, 0) + 1
        if repo.primary_skill:
            st = repo.primary_skill.skill_type.value
            sl = repo.primary_skill.level.value
            by_skill_type[st] = by_skill_type.get(st, 0) + 1
            by_skill_level[sl] = by_skill_level.get(sl, 0) + 1
        total_hours += repo.learning_hours_estimate
        complexity_sum += repo.complexity_score

    count = len(repos)
    return RepositoryStatsResponse(
        total_repositories=count,
        by_skill_type=by_skill_type,
        by_skill_level=by_skill_level,
        by_language=by_language,
        average_complexity=round(complexity_sum / count, 2) if count else 0.0,
        total_estimated_hours=total_hours,
        last_scan_at=None,
        stale_repositories=0,
    )


@router.get(
    "/repositories/{repository_id}",
    response_model=RepositoryDetailResponse,
    summary="Get full detail of a single repository",
)
def get_repository(repository_id: str, store=Depends(get_repository_store)):
    from uuid import UUID
    try:
        uid = UUID(repository_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid repository UUID: {repository_id}",
        )

    repos = store.get_by_ids([uid])
    if not repos:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )
    repo = repos[0]
    base = _repo_to_schema(repo)
    return RepositoryDetailResponse(
        **base.model_dump(),
        content_hash=repo.content_hash or "",
        dependencies=[],
        frameworks=[],
        has_readme=repo.metadata.has_documentation,
        has_docs=repo.metadata.has_documentation,
        documentation_coverage=0.0,
        test_coverage=0.0,
        has_tests=repo.metadata.has_tests,
        has_ci_cd=repo.metadata.has_ci,
    )
