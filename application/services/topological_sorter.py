"""
Topological Sorter Service - Application Layer

Delegates to the domain aggregate's optimise_learning_sequence() method,
which runs Kahn's algorithm with skill-grouping heuristics.

This service exists as an explicit application-layer boundary so:
  - The use case depends on this interface, not directly on domain logic
  - Alternative sorting strategies can be swapped in without touching the domain
  - Unit tests can mock sorting in isolation from graph construction
"""
import logging
from typing import List

from domain.entities.learning_node import LearningNode
from domain.entities.learning_path import LearningPath
from domain.exceptions.domain_exceptions import CircularDependencyError, InvalidLearningSequenceError

logger = logging.getLogger(__name__)


class TopologicalSorterService:
    """
    Sorts learning path nodes into a valid topological order.

    Delegates to LearningPath.optimize_learning_sequence() which uses
    Kahn's algorithm with priority-based stable ordering.
    """

    def sort(self, learning_path: LearningPath) -> List[LearningNode]:
        """
        Optimise and return nodes in topological learning order.

        Side-effect: mutates learning_path.nodes in-place (the domain
        aggregate re-assigns the sorted list).

        Args:
            learning_path: Populated LearningPath aggregate with dependencies.

        Returns:
            Ordered list of LearningNode objects (same instances, new order).

        Raises:
            InvalidLearningSequenceError: If sorting fails after circular
                dependency resolution attempts.
        """
        try:
            learning_path.optimize_learning_sequence()
            logger.info(
                "Sorted %d nodes for path '%s'",
                len(learning_path.nodes),
                learning_path.name,
            )
            return list(learning_path.nodes)

        except CircularDependencyError as exc:
            logger.warning(
                "Circular dependency detected in path '%s': %s — attempting resolution",
                learning_path.name, exc,
            )
            # Attempt recovery by removing weakest circular edges
            self._resolve_cycles(learning_path)
            try:
                learning_path.optimize_learning_sequence()
                return list(learning_path.nodes)
            except CircularDependencyError as inner:
                raise InvalidLearningSequenceError(
                    f"Could not resolve circular dependencies in path '{learning_path.name}': {inner}",
                    affected_nodes=inner.cycle,
                ) from inner

    def _resolve_cycles(self, learning_path: LearningPath) -> None:
        """
        Remove the weakest dependency edges that form cycles.

        Strategy: remove RECOMMENDED + WEAK edges first, then RELATED edges.
        Modifies learning_path.dependencies in-place.
        """
        from domain.entities.dependency_relation import DependencyStrength, DependencyType

        removable = {
            dep for dep in learning_path.dependencies
            if dep.strength == DependencyStrength.WEAK
            or dep.dependency_type in {DependencyType.RELATED, DependencyType.ALTERNATIVE}
        }

        for dep in removable:
            learning_path.dependencies.discard(dep)
            # Also clean up prerequisite_nodes on the target node
            for node in learning_path.nodes:
                if node.repository.repository_id == dep.target_repository_id:
                    source_node = learning_path._get_node_by_id(
                        next(
                            (n.node_id for n in learning_path.nodes
                             if n.repository.repository_id == dep.source_repository_id),
                            None,
                        )
                    )
                    if source_node:
                        node.prerequisite_nodes.discard(source_node.node_id)

        logger.debug(
            "Removed %d weak/optional dependency edges to resolve cycles",
            len(removable),
        )

