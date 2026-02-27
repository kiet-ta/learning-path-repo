"""
Milestone Grouper Service - Application Layer

Groups topologically-sorted LearningNode objects into named learning phases
(FOUNDATIONS → CORE_SKILLS → ADVANCED_SYSTEMS → SPECIALIZED_TOPICS).

Phase assignment is based on the repository's primary skill level, with
complexity score as a tiebreaker:
  - FOUNDATIONS:        BASIC or complexity < 3
  - CORE_SKILLS:        INTERMEDIATE or complexity 3–5
  - ADVANCED_SYSTEMS:   ADVANCED or complexity 5–7
  - SPECIALIZED_TOPICS: EXPERT or complexity > 7

The groups are returned in milestone order and internal node ordering
preserves the topological sort from TopologicalSorterService.
"""
import logging
from typing import Dict, List, Optional
from uuid import UUID

from domain.entities.learning_node import LearningNode
from domain.entities.skill import SkillLevel

from application.dto.milestone_group import MilestoneGroup, MilestonePhase, NodeItem

logger = logging.getLogger(__name__)

_MILESTONE_ORDER = [
    MilestonePhase.FOUNDATIONS,
    MilestonePhase.CORE_SKILLS,
    MilestonePhase.ADVANCED_SYSTEMS,
    MilestonePhase.SPECIALIZED_TOPICS,
]


class MilestoneGrouperService:
    """
    Groups sorted LearningNode objects into MilestoneGroup DTOs.
    """

    def group(self, sorted_nodes: List[LearningNode]) -> List[MilestoneGroup]:
        """
        Assign each node to a milestone phase and return groups in order.

        Args:
            sorted_nodes: Topologically-sorted list of LearningNode objects.

        Returns:
            List of MilestoneGroup DTOs, in phase order.
            Empty phases are omitted from the result.
        """
        buckets: Dict[MilestonePhase, List[NodeItem]] = {p: [] for p in _MILESTONE_ORDER}

        for order_index, node in enumerate(sorted_nodes):
            phase = self._assign_phase(node)
            item = self._node_to_item(node, order_index)
            buckets[phase].append(item)

        # Build output list, skip empty phases
        result: List[MilestoneGroup] = []
        for phase in _MILESTONE_ORDER:
            items = buckets[phase]
            if items:
                result.append(MilestoneGroup(phase=phase, nodes=items))

        logger.info(
            "Grouped %d nodes into %d milestones: %s",
            len(sorted_nodes),
            len(result),
            [f"{g.phase.value}({g.repository_count})" for g in result],
        )
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _assign_phase(self, node: LearningNode) -> MilestonePhase:
        """Map a LearningNode to a MilestonePhase."""
        skill = node.repository.primary_skill
        complexity = node.repository.complexity_score

        if skill:
            level = skill.skill_level
            if level == SkillLevel.BASIC:
                return MilestonePhase.FOUNDATIONS
            if level == SkillLevel.INTERMEDIATE:
                return MilestonePhase.CORE_SKILLS
            if level == SkillLevel.ADVANCED:
                return MilestonePhase.ADVANCED_SYSTEMS
            if level == SkillLevel.EXPERT:
                return MilestonePhase.SPECIALIZED_TOPICS

        # Fallback: complexity-based assignment
        if complexity < 3.0:
            return MilestonePhase.FOUNDATIONS
        if complexity < 5.0:
            return MilestonePhase.CORE_SKILLS
        if complexity < 7.0:
            return MilestonePhase.ADVANCED_SYSTEMS
        return MilestonePhase.SPECIALIZED_TOPICS

    def _node_to_item(self, node: LearningNode, order_index: int) -> NodeItem:
        """Convert a domain LearningNode to a lightweight NodeItem DTO."""
        skill = node.repository.primary_skill
        return NodeItem(
            node_id=node.node_id,
            repository_id=node.repository.repository_id,
            repository_name=node.repository.name,
            order_index=order_index,
            estimated_hours=node.estimated_hours,
            complexity_score=node.repository.complexity_score,
            skill_type=skill.skill_type.value if skill else "unknown",
            skill_level=skill.skill_level.value if skill else "basic",
            prerequisites=list(node.prerequisite_nodes),
        )

