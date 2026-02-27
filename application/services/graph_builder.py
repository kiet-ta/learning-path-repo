"""
Graph Builder Service - Application Layer

Constructs a LearningPath aggregate from a flat list of Repository entities
by auto-detecting prerequisite relationships between them.

Relationship detection heuristics (in priority order):
  1. Topic dependency — if repo A has topics that are prerequisites of repo B's topics
  2. Skill progression — BASIC → INTERMEDIATE → ADVANCED → EXPERT within same SkillType
  3. Complexity ordering — simpler repos become soft prerequisites for complex ones
  4. Language ecosystem — e.g., HTML/CSS before JavaScript before TypeScript

This service does NOT call the persistence layer — it works entirely on
in-memory domain objects.
"""
import logging
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from domain.entities.dependency_relation import DependencyRelation, DependencyStrength, DependencyType
from domain.entities.learning_path import LearningPath
from domain.entities.repository import Repository
from domain.entities.skill import SkillLevel, SkillType

logger = logging.getLogger(__name__)

# Complexity thresholds that separate "simple" from "complex" repos
_SIMPLE_THRESHOLD = 3.0
_COMPLEX_THRESHOLD = 6.0

# Skill level progression order
_SKILL_LEVEL_ORDER: Dict[str, int] = {
    SkillLevel.BASIC.value: 0,
    SkillLevel.INTERMEDIATE.value: 1,
    SkillLevel.ADVANCED.value: 2,
    SkillLevel.EXPERT.value: 3,
}


class GraphBuilderService:
    """
    Builds a LearningPath aggregate (dependency graph) from a list of
    Repository domain entities.

    Usage:
        service = GraphBuilderService()
        learning_path = service.build(
            learner_id="user-123",
            name="My Path",
            repositories=repo_list,
        )
    """

    def build(
        self,
        learner_id: str,
        name: str,
        repositories: List[Repository],
        description: str = "",
        allow_parallel: bool = False,
        max_parallel: int = 3,
        exclude_ids: Optional[List[UUID]] = None,
    ) -> LearningPath:
        """
        Build a LearningPath from a list of Repository entities.

        Args:
            learner_id:      Unique ID of the learner this path belongs to.
            name:            Human-readable name for the path.
            repositories:    Flat list of Repository domain entities.
            description:     Optional path description.
            allow_parallel:  Whether parallel learning nodes are permitted.
            max_parallel:    Max simultaneous in-progress nodes.
            exclude_ids:     Repository UUIDs to omit from the path.

        Returns:
            Populated LearningPath aggregate with dependencies set.
        """
        exclude_set: set = set(exclude_ids or [])
        filtered = [r for r in repositories if r.repository_id not in exclude_set]

        # Sort by natural learning order before building path
        filtered.sort(key=lambda r: r.get_recommended_learning_order())

        # Create aggregate root
        path = LearningPath(
            name=name,
            description=description,
            learner_id=learner_id,
            allow_parallel_learning=allow_parallel,
            max_parallel_nodes=max_parallel,
        )

        # Add every repository as a node (no prerequisites yet)
        node_map: Dict[UUID, UUID] = {}  # repo_id → node_id
        for repo in filtered:
            try:
                node = path.add_repository(repo)
                node_map[repo.repository_id] = node.node_id
            except Exception as exc:
                logger.warning("Skipping repo %s: %s", repo.name, exc)
                continue

        # Detect and add dependency relationships
        dependency_pairs = self._detect_dependencies(filtered)
        for (source_repo, target_repo, dep_type, strength) in dependency_pairs:
            source_node_id = node_map.get(source_repo.repository_id)
            target_node_id = node_map.get(target_repo.repository_id)
            if not source_node_id or not target_node_id:
                continue
            try:
                path.add_dependency(source_node_id, target_node_id, dep_type, strength)
            except Exception as exc:
                # Circular dependency or other violation — skip silently, log
                logger.debug("Skipping dependency %s→%s: %s", source_repo.name, target_repo.name, exc)

        logger.info(
            "Built learning path '%s' with %d repositories and %d dependencies",
            name, len(path.nodes), len(path.dependencies),
        )
        return path

    # ------------------------------------------------------------------
    # Dependency detection
    # ------------------------------------------------------------------

    def _detect_dependencies(
        self, repositories: List[Repository]
    ) -> List[Tuple[Repository, Repository, DependencyType, DependencyStrength]]:
        """
        Return a list of (source, target, type, strength) dependency tuples.

        source must be learned before target.
        """
        results: List[Tuple[Repository, Repository, DependencyType, DependencyStrength]] = []

        for i, source in enumerate(repositories):
            for target in repositories[i + 1:]:
                dep = self._infer_dependency(source, target)
                if dep:
                    results.append((source, target, dep[0], dep[1]))

        return results

    def _infer_dependency(
        self, source: Repository, target: Repository
    ) -> Optional[Tuple[DependencyType, DependencyStrength]]:
        """
        Determine if source should be a prerequisite for target.

        Returns (DependencyType, DependencyStrength) or None.
        """
        # 1. Topic-based prerequisite
        source_topic_names = {t.name for t in source.topics}
        for topic in target.topics:
            if topic.parent_topics.intersection(source_topic_names):
                return DependencyType.PREREQUISITE, DependencyStrength.STRONG

        # 2. Skill-level progression (same SkillType, lower level → higher level)
        if (
            source.primary_skill
            and target.primary_skill
            and source.primary_skill.skill_type == target.primary_skill.skill_type
        ):
            src_order = _SKILL_LEVEL_ORDER.get(source.primary_skill.skill_level.value, 0)
            tgt_order = _SKILL_LEVEL_ORDER.get(target.primary_skill.skill_level.value, 0)
            if src_order < tgt_order:
                return DependencyType.PREREQUISITE, DependencyStrength.MODERATE

        # 3. Compatible skill type progression (e.g., BACKEND before DATA_SCIENCE)
        if source.primary_skill and target.primary_skill:
            compatible = SkillType.get_compatible_types(target.primary_skill.skill_type)
            if (
                source.primary_skill.skill_type in compatible
                and source.complexity_score < target.complexity_score
            ):
                return DependencyType.RECOMMENDED, DependencyStrength.WEAK

        # 4. Complexity-based soft ordering
        if (
            source.complexity_score < _SIMPLE_THRESHOLD
            and target.complexity_score > _COMPLEX_THRESHOLD
        ):
            return DependencyType.RECOMMENDED, DependencyStrength.WEAK

        return None

