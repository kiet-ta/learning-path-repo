"""
Learning Path Router - /api/v1/learning-paths

POST /learning-paths           → generate a new learning path
GET  /learning-paths           → list learning paths for a learner
GET  /learning-paths/{id}      → get a specific learning path
POST /learning-paths/{id}/optimize → re-optimise ordering
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.dependencies.use_case_factory import get_generate_learning_path_use_case
from api.schemas.learning_path_schemas import (
    GenerateLearningPathRequest,
    GenerateLearningPathResponse,
    LearningPathResponse,
    LearningPathSummaryResponse,
    MilestoneGroupResponse,
    LearningNodeResponse,
)
from application.dto.learning_path_request import GenerateLearningPathRequest as DTORequest
from application.dto.milestone_group import MilestoneGroup
from application.use_cases.generate_learning_path_use_case import GenerateLearningPathUseCase

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Response converters (DTO → API schema)
# ---------------------------------------------------------------------------

def _node_to_schema(node) -> LearningNodeResponse:
    return LearningNodeResponse(
        repository_id=str(node.repository_id),
        repository_name=node.repository_name,
        order_index=node.order_index,
        milestone=node.skill_level,   # overloaded field; maps phase by index
        estimated_hours=node.estimated_hours,
        skill_type=node.skill_type,
        skill_level=node.skill_level,
        complexity_score=node.complexity_score,
        prerequisites=[str(p) for p in node.prerequisites],
        is_overridden=node.is_overridden,
        override_reason=node.override_reason or None,
    )


def _milestone_to_schema(group: MilestoneGroup) -> MilestoneGroupResponse:
    return MilestoneGroupResponse(
        milestone=group.phase.value,
        description=group.description,
        estimated_hours=group.estimated_hours,
        repository_count=group.repository_count,
        repositories=[_node_to_schema(n) for n in group.nodes],
    )


def _response_to_schema(response) -> LearningPathResponse:
    return LearningPathResponse(
        id=hash(response.path_id) % 100000,   # surrogate int id until DB returns real id
        version=response.version,
        learner_id=response.learner_id,
        name=response.name,
        description=response.description or None,
        status=response.status,
        total_estimated_hours=response.total_estimated_hours,
        total_repositories=response.total_repositories,
        milestones=[_milestone_to_schema(m) for m in response.milestones],
        generated_at=response.generated_at,
        last_optimized_at=response.last_optimized_at,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/learning-paths",
    response_model=GenerateLearningPathResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a new learning path",
)
async def generate_learning_path(
    request: GenerateLearningPathRequest,
    use_case: GenerateLearningPathUseCase = Depends(get_generate_learning_path_use_case),
):
    """
    Generate a personalised learning path from scanned repositories.

    The path is built using topological sort + skill-level grouping.
    Repositories must have been scanned via POST /api/v1/scan first.
    """
    dto = DTORequest(
        learner_id=request.learner_id,
        name=request.name,
        description=request.description or "",
        target_skill_types=[s.value for s in (request.target_skill_types or [])],
        target_skill_level=request.target_skill_level.value if request.target_skill_level else None,
        max_repositories=request.max_repositories,
        allow_parallel_learning=request.allow_parallel_learning,
        max_parallel_nodes=request.max_parallel_nodes,
        exclude_repository_ids=[str(rid) for rid in (request.exclude_repository_ids or [])],
    )

    response = use_case.execute(dto)

    return GenerateLearningPathResponse(
        message="Learning path generated successfully",
        learning_path=_response_to_schema(response),
        generation_stats=response.generation_stats,
        warnings=response.warnings,
    )


@router.get(
    "/learning-paths",
    response_model=List[LearningPathSummaryResponse],
    summary="List learning paths for a learner",
)
async def list_learning_paths(
    learner_id: str = Query(..., description="Learner identifier"),
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    path_store=Depends(lambda: __import__(
        "api.dependencies.dependency_injection", fromlist=["get_learning_path_store"]
    ).get_learning_path_store()),
):
    """List all learning paths for a given learner."""
    all_paths = path_store.get_by_learner(learner_id)
    if status_filter:
        all_paths = [p for p in all_paths if p.status == status_filter]

    # Pagination
    start = (page - 1) * page_size
    page_items = all_paths[start: start + page_size]

    return [
        LearningPathSummaryResponse(
            id=hash(p.path_id) % 100000,
            version=p.version,
            learner_id=p.learner_id,
            name=p.name,
            status=p.status,
            total_estimated_hours=p.total_estimated_hours,
            total_repositories=p.total_repositories,
            completion_percentage=p.completion_percentage,
            generated_at=p.generated_at,
        )
        for p in page_items
    ]

