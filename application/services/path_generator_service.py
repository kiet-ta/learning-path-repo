"""
Path Generator Service - Application Layer

Orchestrates the full learning path generation pipeline:

  repositories → GraphBuilderService → TopologicalSorterService
              → MilestoneGrouperService → OverrideManagerService
              → LearningPathResponse DTO

This service is the only one that composes the other services.
It does NOT interact with the persistence layer directly — the use case
is responsible for loading repositories and saving the result.
"""
import logging
import time
from typing import List, Optional
from uuid import UUID

from domain.entities.repository import Repository

from application.dto.learning_path_request import GenerateLearningPathRequest
from application.dto.learning_path_response import LearningPathResponse
from application.services.graph_builder import GraphBuilderService
from application.services.milestone_grouper import MilestoneGrouperService
from application.services.override_manager import OverrideInstruction, OverrideManagerService
from application.services.topological_sorter import TopologicalSorterService

logger = logging.getLogger(__name__)


class PathGeneratorService:
    """
    Orchestrates the entire learning path generation pipeline.

    Inject the four sub-services through the constructor so each can be
    unit-tested and swapped independently.

    Usage:
        service = PathGeneratorService(
            GraphBuilderService(),
            TopologicalSorterService(),
            MilestoneGrouperService(),
            OverrideManagerService(),
        )
        response = service.generate(request, repositories)
    """

    def __init__(
        self,
        graph_builder: Optional[GraphBuilderService] = None,
        topological_sorter: Optional[TopologicalSorterService] = None,
        milestone_grouper: Optional[MilestoneGrouperService] = None,
        override_manager: Optional[OverrideManagerService] = None,
    ) -> None:
        self._graph = graph_builder or GraphBuilderService()
        self._sorter = topological_sorter or TopologicalSorterService()
        self._grouper = milestone_grouper or MilestoneGrouperService()
        self._overrides = override_manager or OverrideManagerService()

    def generate(
        self,
        request: GenerateLearningPathRequest,
        repositories: List[Repository],
        pending_overrides: Optional[List[OverrideInstruction]] = None,
    ) -> LearningPathResponse:
        """
        Run the full pipeline and return a LearningPathResponse DTO.

        Args:
            request:           Validated input DTO from the use case.
            repositories:      Repository entities loaded by the use case.
            pending_overrides: Any existing overrides to re-apply (e.g.,
                               when regenerating an existing path).

        Returns:
            LearningPathResponse containing milestones and metrics.
        """
        start_time = time.monotonic()
        warnings: List[str] = []

        # 1. Filter repositories by target skill types (if specified)
        filtered_repos = self._filter_by_skill(repositories, request.target_skill_types)
        if len(filtered_repos) < len(repositories):
            warnings.append(
                f"Filtered to {len(filtered_repos)} repositories matching "
                f"skill types: {request.target_skill_types}"
            )

        # 2. Apply max_repositories cap
        if request.max_repositories and len(filtered_repos) > request.max_repositories:
            filtered_repos = filtered_repos[: request.max_repositories]
            warnings.append(
                f"Capped to {request.max_repositories} repositories (max_repositories limit)."
            )

        # 3. Build dependency graph
        exclude_uuids = [UUID(rid) for rid in request.exclude_repository_ids if rid]
        learning_path = self._graph.build(
            learner_id=request.learner_id,
            name=request.name,
            description=request.description,
            repositories=filtered_repos,
            allow_parallel=request.allow_parallel_learning,
            max_parallel=request.max_parallel_nodes,
            exclude_ids=exclude_uuids,
        )

        if not learning_path.nodes:
            warnings.append("No repositories available after filtering and exclusions.")

        # 4. Topological sort
        sorted_nodes = self._sorter.sort(learning_path)

        # 5. Group into milestones
        milestones = self._grouper.group(sorted_nodes)

        # 6. Apply any pending overrides
        if pending_overrides:
            milestones = self._overrides.apply(milestones, pending_overrides)

        # 7. Assemble response DTO
        elapsed_ms = (time.monotonic() - start_time) * 1000
        stats = learning_path.get_learning_statistics()
        stats["generation_time_ms"] = round(elapsed_ms, 2)
        stats["repositories_considered"] = len(repositories)
        stats["repositories_included"] = len(learning_path.nodes)

        response = LearningPathResponse(
            path_id=str(learning_path.path_id),
            learner_id=learning_path.learner_id,
            name=learning_path.name,
            description=request.description,
            status=learning_path.status.value,
            milestones=milestones,
            total_repositories=learning_path.total_repositories,
            total_estimated_hours=learning_path.total_estimated_hours,
            completion_percentage=learning_path.completion_percentage,
            last_optimized_at=learning_path.last_optimized_at,
            warnings=warnings,
            generation_stats=stats,
        )

        logger.info(
            "Generated path '%s' for learner '%s': %d repos, %d milestones, %.1fms",
            request.name, request.learner_id,
            response.total_repositories, len(milestones), elapsed_ms,
        )
        return response

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _filter_by_skill(
        self, repositories: List[Repository], target_skill_types: List[str]
    ) -> List[Repository]:
        """
        If target_skill_types is non-empty, return only repositories whose
        primary skill type matches one of the targets.
        Repositories without a skill are always included as foundational content.
        """
        if not target_skill_types:
            return repositories

        target_set = {s.lower() for s in target_skill_types}
        return [
            r for r in repositories
            if not r.primary_skill or r.primary_skill.skill_type.value in target_set
        ]

