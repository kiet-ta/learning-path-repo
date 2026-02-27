"""
Generate Learning Path Use Case - Application Layer

Entry point for the learning path generation feature.
Orchestrates repository loading, generation pipeline, and persistence.

Follows the Command pattern: a single execute() method receives an input DTO,
does its work, and returns an output DTO.  No HTTP types cross this boundary.
"""
import logging
from typing import List, Optional, Protocol, runtime_checkable
from uuid import UUID

from domain.entities.repository import Repository
from domain.exceptions.domain_exceptions import EntityNotFoundError

from application.dto.learning_path_request import GenerateLearningPathRequest
from application.dto.learning_path_response import LearningPathResponse
from application.services.override_manager import OverrideInstruction
from application.services.path_generator_service import PathGeneratorService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Repository interfaces (Dependency Inversion)
# Concrete implementations live in infrastructure/persistence/repositories/
# ---------------------------------------------------------------------------

@runtime_checkable
class IRepositoryStore(Protocol):
    """Interface for loading Repository entities from the persistence layer."""

    def get_all(self) -> List[Repository]: ...
    def get_by_ids(self, ids: List[UUID]) -> List[Repository]: ...
    def get_by_learner(self, learner_id: str) -> List[Repository]: ...


@runtime_checkable
class ILearningPathStore(Protocol):
    """Interface for saving / loading LearningPathResponse DTOs."""

    def save(self, response: LearningPathResponse) -> LearningPathResponse: ...
    def get_by_id(self, path_id: str) -> Optional[LearningPathResponse]: ...
    def get_by_learner(self, learner_id: str) -> List[LearningPathResponse]: ...


@runtime_checkable
class IOverrideStore(Protocol):
    """Interface for loading persisted override instructions."""

    def get_by_learner(self, learner_id: str) -> List[OverrideInstruction]: ...


# ---------------------------------------------------------------------------
# Use Case
# ---------------------------------------------------------------------------

class GenerateLearningPathUseCase:
    """
    Generates a personalised learning path for a given learner.

    Dependencies are injected via constructor — this class never imports
    from infrastructure or api packages directly.

    Usage:
        use_case = GenerateLearningPathUseCase(
            repo_store=SqliteRepositoryStore(db),
            path_store=SqliteLearningPathStore(db),
            override_store=SqliteOverrideStore(db),
            path_generator=PathGeneratorService(),
        )
        response = use_case.execute(request)
    """

    def __init__(
        self,
        repo_store: IRepositoryStore,
        path_store: ILearningPathStore,
        override_store: IOverrideStore,
        path_generator: Optional[PathGeneratorService] = None,
    ) -> None:
        self._repos = repo_store
        self._paths = path_store
        self._overrides = override_store
        self._generator = path_generator or PathGeneratorService()

    def execute(self, request: GenerateLearningPathRequest) -> LearningPathResponse:
        """
        Generate a new learning path and persist it.

        Steps:
          1. Load all available repositories from the store.
          2. Load any existing override instructions for this learner.
          3. Run PathGeneratorService pipeline.
          4. Persist and return the response DTO.

        Args:
            request: Validated GenerateLearningPathRequest DTO.

        Returns:
            LearningPathResponse containing the generated path.

        Raises:
            EntityNotFoundError: If no repositories are available to build a path.
        """
        logger.info(
            "Generating learning path for learner '%s', name='%s'",
            request.learner_id, request.name,
        )

        # Step 1: Load repositories
        repositories: List[Repository] = self._repos.get_all()
        if not repositories:
            raise EntityNotFoundError(
                "Repository",
                "any — no repositories have been scanned yet. Run /api/v1/scan first.",
            )

        # Step 2: Load override instructions
        pending_overrides: List[OverrideInstruction] = self._overrides.get_by_learner(
            request.learner_id
        )

        # Step 3: Run generation pipeline
        response: LearningPathResponse = self._generator.generate(
            request=request,
            repositories=repositories,
            pending_overrides=pending_overrides or None,
        )

        # Step 4: Persist
        saved_response = self._paths.save(response)

        logger.info(
            "Learning path '%s' saved (id=%s, repos=%d)",
            saved_response.name, saved_response.path_id, saved_response.total_repositories,
        )
        return saved_response
