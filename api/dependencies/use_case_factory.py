"""
Use Case Factory - API Layer

Creates fully-wired use case instances from injected store dependencies.
Routers import from here, never from application/ directly, keeping
the coupling one-way: api → use_case_factory → application.
"""
from fastapi import Depends

from application.services.graph_builder import GraphBuilderService
from application.services.milestone_grouper import MilestoneGrouperService
from application.services.override_manager import OverrideManagerService
from application.services.path_generator_service import PathGeneratorService
from application.services.topological_sorter import TopologicalSorterService
from application.use_cases.generate_learning_path_use_case import GenerateLearningPathUseCase

from .dependency_injection import (
    get_learning_path_store,
    get_override_store,
    get_repository_store,
)


def get_path_generator_service() -> PathGeneratorService:
    """Create PathGeneratorService with all sub-services wired."""
    return PathGeneratorService(
        graph_builder=GraphBuilderService(),
        topological_sorter=TopologicalSorterService(),
        milestone_grouper=MilestoneGrouperService(),
        override_manager=OverrideManagerService(),
    )


def get_generate_learning_path_use_case(
    repo_store=Depends(get_repository_store),
    path_store=Depends(get_learning_path_store),
    override_store=Depends(get_override_store),
) -> GenerateLearningPathUseCase:
    """
    FastAPI dependency that creates a fully-wired GenerateLearningPathUseCase.

    Inject into router handlers via:
        use_case: GenerateLearningPathUseCase = Depends(get_generate_learning_path_use_case)
    """
    return GenerateLearningPathUseCase(
        repo_store=repo_store,
        path_store=path_store,
        override_store=override_store,
        path_generator=get_path_generator_service(),
    )

