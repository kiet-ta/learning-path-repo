"""
Override Manager Service - Application Layer

Applies manual user overrides to a learning path after it has been
generated. Overrides can reorder nodes, skip repositories, or force
a specific milestone assignment.

Override types (matching infrastructure/persistence/models/override_model.py):
  - REORDER   — force a node to a specific order_index position
  - SKIP      — exclude a node from the active path
  - MILESTONE — force a node into a specific milestone phase
  - NOTE      — attach a user note (no structural change)
"""
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID

from application.dto.milestone_group import MilestoneGroup, MilestonePhase, NodeItem

logger = logging.getLogger(__name__)


class OverrideType(str, Enum):
    REORDER = "reorder"
    SKIP = "skip"
    MILESTONE = "milestone"
    NOTE = "note"


@dataclass
class OverrideInstruction:
    """Represents a single user-supplied override for one node."""

    repository_id: UUID
    override_type: OverrideType
    # For REORDER: target position (0-based)
    target_order: Optional[int] = None
    # For MILESTONE: target phase name
    target_milestone: Optional[str] = None
    # For NOTE / reason tracking
    reason: str = ""


class OverrideManagerService:
    """
    Applies override instructions to a generated list of MilestoneGroups.

    The service does not persist overrides — persistence is handled by
    the use case via the repository layer after applying.
    """

    def apply(
        self,
        milestones: List[MilestoneGroup],
        overrides: List[OverrideInstruction],
    ) -> List[MilestoneGroup]:
        """
        Apply a list of OverrideInstructions to milestone groups.

        Args:
            milestones: MilestoneGroup list from MilestoneGrouperService.
            overrides:  User-supplied override instructions.

        Returns:
            Updated list of MilestoneGroups (non-destructive — original
            milestones list is not mutated; a new structure is returned).
        """
        if not overrides:
            return milestones

        # Build a flat ordered list of NodeItems and an index by repo_id
        flat_nodes = [node for group in milestones for node in group.nodes]
        repo_node_map: Dict[UUID, NodeItem] = {n.repository_id: n for n in flat_nodes}

        skip_ids: set = set()

        for override in overrides:
            node = repo_node_map.get(override.repository_id)
            if node is None:
                logger.warning("Override target repo %s not found in path", override.repository_id)
                continue

            if override.override_type == OverrideType.SKIP:
                skip_ids.add(override.repository_id)
                logger.info("Skipping repository %s per override", node.repository_name)

            elif override.override_type == OverrideType.MILESTONE:
                target = self._parse_milestone(override.target_milestone)
                if target:
                    # Will be reassigned during re-bucketing below
                    node = NodeItem(
                        node_id=node.node_id,
                        repository_id=node.repository_id,
                        repository_name=node.repository_name,
                        order_index=node.order_index,
                        estimated_hours=node.estimated_hours,
                        complexity_score=node.complexity_score,
                        skill_type=node.skill_type,
                        skill_level=node.skill_level,
                        prerequisites=node.prerequisites,
                        is_overridden=True,
                        override_reason=override.reason or f"Moved to {target.value}",
                    )
                    repo_node_map[override.repository_id] = node
                    # Store target milestone decision on the item for re-bucketing
                    object.__setattr__(node, "_forced_milestone", target)

            elif override.override_type == OverrideType.REORDER:
                node = NodeItem(
                    node_id=node.node_id,
                    repository_id=node.repository_id,
                    repository_name=node.repository_name,
                    order_index=override.target_order if override.target_order is not None else node.order_index,
                    estimated_hours=node.estimated_hours,
                    complexity_score=node.complexity_score,
                    skill_type=node.skill_type,
                    skill_level=node.skill_level,
                    prerequisites=node.prerequisites,
                    is_overridden=True,
                    override_reason=override.reason or "Manual reorder",
                )
                repo_node_map[override.repository_id] = node

        # Rebuild milestone groups, applying skips and forced milestone assignments
        result_buckets: Dict[MilestonePhase, List[NodeItem]] = {
            g.phase: [] for g in milestones
        }
        # Ensure all known phases exist
        for phase in MilestonePhase:
            result_buckets.setdefault(phase, [])

        for node in repo_node_map.values():
            if node.repository_id in skip_ids:
                continue
            forced = getattr(node, "_forced_milestone", None)
            if forced:
                result_buckets[forced].append(node)
            else:
                # Keep in original milestone
                original_phase = self._find_original_phase(milestones, node.repository_id)
                if original_phase:
                    result_buckets[original_phase].append(node)

        # Sort each bucket by order_index and return non-empty groups
        from application.dto.milestone_group import _MILESTONE_ORDER as ORDER
        output = []
        for phase in ORDER:
            items = sorted(result_buckets.get(phase, []), key=lambda n: n.order_index)
            if items:
                output.append(MilestoneGroup(phase=phase, nodes=items))

        return output

    def _parse_milestone(self, value: Optional[str]) -> Optional[MilestonePhase]:
        if not value:
            return None
        try:
            return MilestonePhase(value.lower())
        except ValueError:
            logger.warning("Unknown milestone phase '%s'", value)
            return None

    def _find_original_phase(
        self, milestones: List[MilestoneGroup], repo_id: UUID
    ) -> Optional[MilestonePhase]:
        for group in milestones:
            for node in group.nodes:
                if node.repository_id == repo_id:
                    return group.phase
        return None

