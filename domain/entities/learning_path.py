"""
Learning Path Entity - Clean Architecture Domain Layer
Aggregate root managing the complete learning path with topological sorting
"""
from dataclasses import dataclass, field
from typing import List, Set, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
from uuid import uuid4, UUID
from enum import Enum

from .learning_node import LearningNode, NodeStatus
from .dependency_relation import DependencyRelation, DependencyType, DependencyStrength
from .repository import Repository
from ..exceptions.domain_exceptions import (
    ValidationError, BusinessRuleViolation, CircularDependencyError, InvalidLearningSequenceError
)


class PathStatus(Enum):
    """Learning path status"""
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


@dataclass
class LearningPath:
    """
    Aggregate root for learning path
    Manages nodes, dependencies, and learning sequence with business rules
    """
    name: str
    description: str
    learner_id: str
    
    # Core data
    path_id: UUID = field(default_factory=uuid4)
    nodes: List[LearningNode] = field(default_factory=list)
    dependencies: Set[DependencyRelation] = field(default_factory=set)
    
    # Status and metadata
    status: PathStatus = PathStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    last_optimized_at: Optional[datetime] = None
    
    # Computed properties
    total_estimated_hours: int = 0
    total_repositories: int = 0
    completion_percentage: float = 0.0
    
    # Configuration
    allow_parallel_learning: bool = False
    max_parallel_nodes: int = 3
    
    def __post_init__(self):
        """Validate learning path invariants"""
        self._validate_path()
        self._recalculate_metrics()
    
    def _validate_path(self):
        """Business rule: Validate learning path"""
        if not self.name or not self.name.strip():
            raise ValidationError("name", "Learning path name cannot be empty")
        
        if not self.learner_id or not self.learner_id.strip():
            raise ValidationError("learner_id", "Learner ID cannot be empty")
        
        if self.max_parallel_nodes < 1:
            raise ValidationError("max_parallel_nodes", "Must allow at least 1 parallel node")
    
    def add_repository(self, repository: Repository, prerequisites: List[UUID] = None) -> LearningNode:
        """
        Business rule: Add a repository to the learning path
        Creates a learning node and validates dependencies
        """
        # Check if repository already exists
        for node in self.nodes:
            if node.repository == repository:
                raise BusinessRuleViolation(f"Repository {repository.name} already in learning path")
        
        # Create new learning node
        node = LearningNode(repository=repository)
        
        # Add prerequisites if provided
        if prerequisites:
            for prereq_id in prerequisites:
                if not self._node_exists(prereq_id):
                    raise ValidationError("prerequisites", f"Prerequisite node {prereq_id} not found")
                node.add_prerequisite(prereq_id)
        
        self.nodes.append(node)
        self._recalculate_metrics()
        self._update_timestamp()
        
        return node
    
    def remove_repository(self, node_id: UUID) -> bool:
        """
        Business rule: Remove a repository from the learning path
        Handles dependent node cleanup
        """
        node = self._get_node_by_id(node_id)
        if not node:
            return False
        
        # Check if other nodes depend on this
        dependent_nodes = [n for n in self.nodes if node_id in n.prerequisite_nodes]
        if dependent_nodes:
            dependent_names = [n.repository.name for n in dependent_nodes]
            raise BusinessRuleViolation(
                f"Cannot remove node - required by: {', '.join(dependent_names)}"
            )
        
        # Remove node
        self.nodes = [n for n in self.nodes if n.node_id != node_id]
        
        # Remove related dependencies
        self.dependencies = {
            dep for dep in self.dependencies
            if dep.source_repository_id != node.repository.repository_id
            and dep.target_repository_id != node.repository.repository_id
        }
        
        self._recalculate_metrics()
        self._update_timestamp()
        return True
    
    def add_dependency(self, source_node_id: UUID, target_node_id: UUID, 
                      dependency_type: DependencyType, strength: DependencyStrength,
                      created_by: str = "system") -> DependencyRelation:
        """
        Business rule: Add a dependency between two nodes
        Validates circular dependencies and creates relation
        """
        source_node = self._get_node_by_id(source_node_id)
        target_node = self._get_node_by_id(target_node_id)
        
        if not source_node or not target_node:
            raise ValidationError("node_id", "Source or target node not found")
        
        # Create dependency relation
        relation = DependencyRelation(
            source_repository_id=source_node.repository.repository_id,
            target_repository_id=target_node.repository.repository_id,
            dependency_type=dependency_type,
            strength=strength,
            created_by=created_by
        )
        
        # Add to dependencies set
        self.dependencies.add(relation)
        
        # Update node prerequisites if blocking dependency
        if relation.is_blocking_dependency():
            target_node.add_prerequisite(source_node_id)
        
        # Validate no circular dependencies
        self._validate_no_cycles()
        
        self._update_timestamp()
        return relation
    
    def optimize_learning_sequence(self) -> None:
        """
        Business logic: Optimize learning path using topological sort
        Reorders nodes based on dependencies, skills, and complexity
        """
        # Perform topological sort
        sorted_nodes = self._topological_sort()
        
        # Apply additional optimization heuristics
        optimized_nodes = self._apply_learning_heuristics(sorted_nodes)
        
        self.nodes = optimized_nodes
        self.last_optimized_at = datetime.now()
        self._update_timestamp()
    
    def _topological_sort(self) -> List[LearningNode]:
        """
        Topological sort algorithm for dependency ordering
        Returns nodes in valid learning order
        """
        # Build adjacency list
        in_degree = {node.node_id: 0 for node in self.nodes}
        adjacency = {node.node_id: [] for node in self.nodes}
        
        for node in self.nodes:
            for prereq_id in node.prerequisite_nodes:
                adjacency[prereq_id].append(node.node_id)
                in_degree[node.node_id] += 1
        
        # Kahn's algorithm
        queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
        sorted_ids = []
        
        while queue:
            # Sort queue by learning priority for stable ordering
            queue.sort(key=lambda nid: self._get_node_by_id(nid).repository.get_recommended_learning_order())
            
            current_id = queue.pop(0)
            sorted_ids.append(current_id)
            
            for neighbor_id in adjacency[current_id]:
                in_degree[neighbor_id] -= 1
                if in_degree[neighbor_id] == 0:
                    queue.append(neighbor_id)
        
        # Check for cycles
        if len(sorted_ids) != len(self.nodes):
            raise CircularDependencyError(self._find_cycle())
        
        # Return nodes in sorted order
        node_map = {node.node_id: node for node in self.nodes}
        return [node_map[node_id] for node_id in sorted_ids]
    
    def _apply_learning_heuristics(self, sorted_nodes: List[LearningNode]) -> List[LearningNode]:
        """
        Apply learning heuristics to optimize sequence
        Groups similar skills, balances difficulty
        """
        # Group by skill type while maintaining topological order
        skill_groups = {}
        for node in sorted_nodes:
            if node.repository.primary_skill:
                skill_type = node.repository.primary_skill.skill_type
                if skill_type not in skill_groups:
                    skill_groups[skill_type] = []
                skill_groups[skill_type].append(node)
            else:
                if None not in skill_groups:
                    skill_groups[None] = []
                skill_groups[None].append(node)
        
        # Reorder within groups by complexity (simple first)
        for skill_type, nodes in skill_groups.items():
            nodes.sort(key=lambda n: n.repository.complexity_score)
        
        # Flatten back to list, maintaining skill grouping
        optimized = []
        for skill_type in sorted(skill_groups.keys(), key=lambda x: str(x) if x else ""):
            optimized.extend(skill_groups[skill_type])
        
        return optimized
    
    def _validate_no_cycles(self) -> None:
        """Validate that no circular dependencies exist"""
        try:
            self._topological_sort()
        except CircularDependencyError:
            raise  # Re-raise the circular dependency error
    
    def _find_cycle(self) -> List[str]:
        """Find a cycle in the dependency graph"""
        visited = set()
        rec_stack = set()
        
        def dfs(node_id: UUID, path: List[UUID]) -> Optional[List[UUID]]:
            visited.add(node_id)
            rec_stack.add(node_id)
            path.append(node_id)
            
            node = self._get_node_by_id(node_id)
            if node:
                for prereq_id in node.prerequisite_nodes:
                    if prereq_id not in visited:
                        cycle = dfs(prereq_id, path.copy())
                        if cycle:
                            return cycle
                    elif prereq_id in rec_stack:
                        # Found cycle
                        cycle_start = path.index(prereq_id)
                        return path[cycle_start:] + [prereq_id]
            
            rec_stack.remove(node_id)
            return None
        
        for node in self.nodes:
            if node.node_id not in visited:
                cycle = dfs(node.node_id, [])
                if cycle:
                    return [str(nid) for nid in cycle]
        
        return []
    
    def get_next_available_nodes(self) -> List[LearningNode]:
        """
        Business logic: Get nodes that can be started next
        Respects prerequisites and parallel learning limits
        """
        completed_ids = {node.node_id for node in self.nodes if node.status == NodeStatus.COMPLETED}
        in_progress_ids = {node.node_id for node in self.nodes if node.status == NodeStatus.IN_PROGRESS}
        
        # Check parallel learning limit
        if not self.allow_parallel_learning:
            if in_progress_ids:
                return []  # Can't start new nodes if one is in progress
        else:
            if len(in_progress_ids) >= self.max_parallel_nodes:
                return []  # Reached parallel limit
        
        # Find available nodes
        available = []
        for node in self.nodes:
            if node.status == NodeStatus.NOT_STARTED:
                if node.can_start_learning(completed_ids):
                    available.append(node)
        
        # Sort by recommended order
        available.sort(key=lambda n: n.repository.get_recommended_learning_order())
        
        return available
    
    def get_learning_statistics(self) -> Dict[str, Any]:
        """
        Business logic: Calculate comprehensive learning statistics
        """
        total_nodes = len(self.nodes)
        completed_nodes = sum(1 for node in self.nodes if node.status == NodeStatus.COMPLETED)
        in_progress_nodes = sum(1 for node in self.nodes if node.status == NodeStatus.IN_PROGRESS)
        
        total_hours = sum(node.estimated_hours for node in self.nodes)
        completed_hours = sum(
            node.estimated_hours for node in self.nodes 
            if node.status == NodeStatus.COMPLETED
        )
        
        return {
            "total_repositories": total_nodes,
            "completed_repositories": completed_nodes,
            "in_progress_repositories": in_progress_nodes,
            "completion_percentage": self.completion_percentage,
            "total_estimated_hours": total_hours,
            "completed_hours": completed_hours,
            "remaining_hours": total_hours - completed_hours,
            "average_complexity": sum(n.repository.complexity_score for n in self.nodes) / total_nodes if total_nodes > 0 else 0,
        }
    
    def get_skill_distribution(self) -> Dict[str, int]:
        """Get distribution of skill types in the path"""
        distribution = {}
        for node in self.nodes:
            if node.repository.primary_skill:
                skill_type = node.repository.primary_skill.skill_type.value
                distribution[skill_type] = distribution.get(skill_type, 0) + 1
        return distribution
    
    def _recalculate_metrics(self) -> None:
        """Recalculate path metrics"""
        self.total_repositories = len(self.nodes)
        self.total_estimated_hours = sum(node.estimated_hours for node in self.nodes)
        
        if self.total_repositories > 0:
            completed_count = sum(1 for node in self.nodes if node.status == NodeStatus.COMPLETED)
            self.completion_percentage = (completed_count / self.total_repositories) * 100
        else:
            self.completion_percentage = 0.0
    
    def _update_timestamp(self) -> None:
        """Update the path timestamp"""
        self.updated_at = datetime.now()
    
    def _node_exists(self, node_id: UUID) -> bool:
        """Check if a node exists in the path"""
        return any(node.node_id == node_id for node in self.nodes)
    
    def _get_node_by_id(self, node_id: UUID) -> Optional[LearningNode]:
        """Get a node by its ID"""
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        return None
    
    def __str__(self) -> str:
        return f"LearningPath({self.name}, {self.total_repositories} repos, {self.completion_percentage:.1f}% complete)"
