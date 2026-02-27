"""
Milestone Group DTO - Application Layer

Represents a named phase within a learning path.
Passed from MilestoneGrouper service to the response builder.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List
from uuid import UUID


class MilestonePhase(str, Enum):
    """Maps directly to MilestoneEnum in api/schemas/learning_path_schemas.py."""

    FOUNDATIONS = "foundations"
    CORE_SKILLS = "core_skills"
    ADVANCED_SYSTEMS = "advanced_systems"
    SPECIALIZED_TOPICS = "specialized_topics"


_MILESTONE_DESCRIPTIONS = {
    MilestonePhase.FOUNDATIONS: (
        "Core fundamentals and basic concepts — the essential starting point."
    ),
    MilestonePhase.CORE_SKILLS: (
        "Practical, production-relevant skills for day-to-day engineering work."
    ),
    MilestonePhase.ADVANCED_SYSTEMS: (
        "Complex system design, architecture, and cross-cutting concerns."
    ),
    MilestonePhase.SPECIALIZED_TOPICS: (
        "Expert-level and domain-specific repositories for deep specialisation."
    ),
}


@dataclass
class NodeItem:
    """Lightweight representation of a learning node within a milestone group."""

    node_id: UUID
    repository_id: UUID
    repository_name: str
    order_index: int
    estimated_hours: int
    complexity_score: float
    skill_type: str          # SkillType.value string
    skill_level: str         # SkillLevel.value string
    prerequisites: List[UUID] = field(default_factory=list)
    is_overridden: bool = False
    override_reason: str = ""


@dataclass
class MilestoneGroup:
    """
    A named learning phase containing an ordered list of NodeItems.

    Created by MilestoneGrouperService, consumed by response serialisers.
    """

    phase: MilestonePhase
    nodes: List[NodeItem] = field(default_factory=list)

    @property
    def description(self) -> str:
        return _MILESTONE_DESCRIPTIONS.get(self.phase, "")

    @property
    def repository_count(self) -> int:
        return len(self.nodes)

    @property
    def estimated_hours(self) -> int:
        return sum(n.estimated_hours for n in self.nodes)

