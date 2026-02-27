"""
Learning Path Response DTO - Application Layer

Carries the result of use case execution back to the API layer.
The API layer maps these to Pydantic schemas; the domain never sees Pydantic.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from .milestone_group import MilestoneGroup


@dataclass
class LearningPathResponse:
    """
    Output DTO returned by GenerateLearningPathUseCase.

    All IDs are plain strings (str(uuid)) so this DTO can safely cross
    serialisation boundaries without UUID import requirements in the API layer.
    """

    # Identity
    path_id: str
    learner_id: str
    name: str
    status: str

    # Content
    milestones: List[MilestoneGroup] = field(default_factory=list)

    # Metrics
    total_repositories: int = 0
    total_estimated_hours: int = 0
    completion_percentage: float = 0.0

    # Timestamps
    generated_at: datetime = field(default_factory=datetime.now)
    last_optimized_at: Optional[datetime] = None

    # Version for optimistic concurrency (auto-incremented by persistence layer)
    version: int = 1

    # Optional description
    description: str = ""

    # Generation diagnostics — surfaced as API warnings
    warnings: List[str] = field(default_factory=list)

    # Arbitrary statistics from services (e.g., repos_skipped, time_ms)
    generation_stats: Dict[str, object] = field(default_factory=dict)


@dataclass
class ScanRepositoriesResponse:
    """
    Output DTO returned by ScanRepositoriesUseCase.
    """

    scan_id: str
    scanned_count: int
    skipped_count: int
    failed_count: int
    total_duration_seconds: float
    repositories: List[Dict] = field(default_factory=list)   # raw scan results
    performance_stats: Dict[str, float] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

