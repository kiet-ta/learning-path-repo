"""
Learning Path Request DTO - Application Layer

Carries validated input from the API layer into the use case.
Plain dataclasses — no Pydantic, no HTTP concepts, no infrastructure imports.
"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class GenerateLearningPathRequest:
    """
    Input DTO for the GenerateLearningPathUseCase.

    Created by the API layer from a validated Pydantic schema and passed
    directly to the use case.  All values are already validated and normalised.
    """

    learner_id: str
    name: str

    # Optional metadata
    description: str = ""

    # Skill filtering — stored as string values of domain SkillType / SkillLevel enums
    target_skill_types: List[str] = field(default_factory=list)
    target_skill_level: Optional[str] = None

    # Path shape config
    max_repositories: Optional[int] = None         # None = no limit
    allow_parallel_learning: bool = False
    max_parallel_nodes: int = 3

    # Exclusions — repository IDs (str representation of UUID)
    exclude_repository_ids: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.learner_id or not self.learner_id.strip():
            raise ValueError("learner_id cannot be empty")
        if not self.name or not self.name.strip():
            raise ValueError("name cannot be empty")
        if self.max_parallel_nodes < 1:
            raise ValueError("max_parallel_nodes must be >= 1")


@dataclass
class ScanRepositoriesRequest:
    """
    Input DTO for the ScanRepositoriesUseCase.
    """

    root_path: str
    force_rescan: bool = False
    include_patterns: List[str] = field(default_factory=list)
    exclude_patterns: List[str] = field(default_factory=list)
    max_depth: int = 5

    def __post_init__(self) -> None:
        if not self.root_path or not self.root_path.strip():
            raise ValueError("root_path cannot be empty")
        if not 1 <= self.max_depth <= 20:
            raise ValueError("max_depth must be between 1 and 20")

