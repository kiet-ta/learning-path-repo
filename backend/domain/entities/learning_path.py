"""
Learning Path Entity - Core domain model for learning paths
Represents the ordered sequence of repositories for optimal learning
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum

from .repository import Repository, SkillLevel, SkillType


class PathStatus(Enum):
    """Learning path status"""
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


@dataclass
class LearningPathNode:
    """
    Represents a single node in the learning path
    Contains repository and its position/metadata in the path
    """
    repository: Repository
    order: int
    prerequisites: List[str] = field(default_factory=list)
    estimated_completion_date: Optional[datetime] = None
    is_completed: bool = False
    completion_date: Optional[datetime] = None
    notes: str = ""
    
    def mark_completed(self) -> None:
        """Mark this node as completed"""
        self.is_completed = True
        self.completion_date = datetime.now()
    
    def add_prerequisite(self, repo_name: str) -> None:
        """Add a prerequisite repository"""
        if repo_name not in self.prerequisites:
            self.prerequisites.append(repo_name)
    
    def can_start(self, completed_repos: List[str]) -> bool:
        """Check if this node can be started based on prerequisites"""
        return all(prereq in completed_repos for prereq in self.prerequisites)


@dataclass
class LearningPath:
    """
    Core Learning Path entity representing an ordered learning sequence
    
    This entity encapsulates the business logic for managing learning paths,
    including ordering, prerequisites, and progress tracking.
    """
    name: str
    description: str
    nodes: List[LearningPathNode] = field(default_factory=list)
    status: PathStatus = PathStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    target_skill_types: List[SkillType] = field(default_factory=list)
    total_estimated_hours: int = 0
    completion_percentage: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate entity after initialization"""
        self._validate()
        self._calculate_totals()
    
    def _validate(self) -> None:
        """Validate learning path data integrity"""
        if not self.name or not self.name.strip():
            raise ValueError("Learning path name cannot be empty")
        
        if not self.description or not self.description.strip():
            raise ValueError("Learning path description cannot be empty")
        
        # Validate node ordering
        orders = [node.order for node in self.nodes]
        if len(orders) != len(set(orders)):
            raise ValueError("Duplicate node orders found")
    
    def add_repository(self, repository: Repository, prerequisites: List[str] = None) -> None:
        """
        Add a repository to the learning path
        Business logic for proper ordering and prerequisite management
        """
        if prerequisites is None:
            prerequisites = []
        
        # Determine order based on existing nodes
        order = len(self.nodes) + 1
        
        # Create new node
        node = LearningPathNode(
            repository=repository,
            order=order,
            prerequisites=prerequisites
        )
        
        self.nodes.append(node)
        self._calculate_totals()
        self.updated_at = datetime.now()
    
    def remove_repository(self, repo_name: str) -> bool:
        """Remove a repository from the learning path"""
        original_count = len(self.nodes)
        self.nodes = [node for node in self.nodes if node.repository.name != repo_name]
        
        if len(self.nodes) < original_count:
            self._reorder_nodes()
            self._calculate_totals()
            self.updated_at = datetime.now()
            return True
        return False
    
    def reorder_repository(self, repo_name: str, new_order: int) -> bool:
        """
        Reorder a repository in the learning path
        Business logic for maintaining valid ordering
        """
        node = self.get_node_by_name(repo_name)
        if not node:
            return False
        
        # Validate new order
        if new_order < 1 or new_order > len(self.nodes):
            raise ValueError(f"Invalid order: {new_order}")
        
        # Remove node and reinsert at new position
        self.nodes.remove(node)
        node.order = new_order
        
        # Adjust other nodes
        for other_node in self.nodes:
            if other_node.order >= new_order:
                other_node.order += 1
        
        self.nodes.append(node)
        self.nodes.sort(key=lambda x: x.order)
        self.updated_at = datetime.now()
        return True
    
    def _reorder_nodes(self) -> None:
        """Reorder nodes to maintain sequential ordering"""
        self.nodes.sort(key=lambda x: x.order)
        for i, node in enumerate(self.nodes, 1):
            node.order = i
    
    def get_node_by_name(self, repo_name: str) -> Optional[LearningPathNode]:
        """Get a node by repository name"""
        for node in self.nodes:
            if node.repository.name == repo_name:
                return node
        return None
    
    def mark_repository_completed(self, repo_name: str) -> bool:
        """Mark a repository as completed"""
        node = self.get_node_by_name(repo_name)
        if node:
            node.mark_completed()
            self._calculate_completion_percentage()
            self.updated_at = datetime.now()
            return True
        return False
    
    def get_next_available_repositories(self) -> List[LearningPathNode]:
        """
        Get repositories that can be started next
        Business logic for prerequisite checking
        """
        completed_repos = [
            node.repository.name for node in self.nodes if node.is_completed
        ]
        
        available = []
        for node in self.nodes:
            if not node.is_completed and node.can_start(completed_repos):
                available.append(node)
        
        return sorted(available, key=lambda x: x.order)
    
    def get_completion_stats(self) -> Dict[str, Any]:
        """Get detailed completion statistics"""
        total_nodes = len(self.nodes)
        completed_nodes = sum(1 for node in self.nodes if node.is_completed)
        
        completed_hours = sum(
            node.repository.estimated_learning_hours
            for node in self.nodes if node.is_completed
        )
        
        return {
            "total_repositories": total_nodes,
            "completed_repositories": completed_nodes,
            "completion_percentage": self.completion_percentage,
            "total_estimated_hours": self.total_estimated_hours,
            "completed_hours": completed_hours,
            "remaining_hours": self.total_estimated_hours - completed_hours,
        }
    
    def _calculate_totals(self) -> None:
        """Calculate total estimated hours"""
        self.total_estimated_hours = sum(
            node.repository.estimated_learning_hours for node in self.nodes
        )
        self._calculate_completion_percentage()
    
    def _calculate_completion_percentage(self) -> None:
        """Calculate completion percentage"""
        if not self.nodes:
            self.completion_percentage = 0.0
            return
        
        completed_count = sum(1 for node in self.nodes if node.is_completed)
        self.completion_percentage = (completed_count / len(self.nodes)) * 100
    
    def optimize_order(self) -> None:
        """
        Optimize the learning path order based on dependencies and complexity
        Business logic for intelligent path optimization
        """
        # Sort by learning priority (lower = higher priority)
        self.nodes.sort(key=lambda node: (
            node.repository.get_learning_priority(),
            len(node.prerequisites),
            node.repository.complexity_score
        ))
        
        # Reassign orders
        for i, node in enumerate(self.nodes, 1):
            node.order = i
        
        self.updated_at = datetime.now()
    
    def validate_prerequisites(self) -> List[str]:
        """
        Validate that all prerequisites are satisfied
        Returns list of validation errors
        """
        errors = []
        repo_names = {node.repository.name for node in self.nodes}
        
        for node in self.nodes:
            for prereq in node.prerequisites:
                if prereq not in repo_names:
                    errors.append(
                        f"Repository '{node.repository.name}' has missing prerequisite: '{prereq}'"
                    )
        
        return errors
    
    def get_skill_distribution(self) -> Dict[str, int]:
        """Get distribution of skill types in the path"""
        distribution = {}
        for node in self.nodes:
            skill_type = node.repository.skill_type
            if skill_type:
                key = skill_type.value
                distribution[key] = distribution.get(key, 0) + 1
        return distribution
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert learning path to dictionary representation"""
        return {
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "target_skill_types": [st.value for st in self.target_skill_types],
            "total_estimated_hours": self.total_estimated_hours,
            "completion_percentage": self.completion_percentage,
            "nodes": [
                {
                    "repository": node.repository.to_dict(),
                    "order": node.order,
                    "prerequisites": node.prerequisites,
                    "is_completed": node.is_completed,
                    "completion_date": node.completion_date.isoformat() if node.completion_date else None,
                    "notes": node.notes,
                }
                for node in self.nodes
            ],
            "metadata": self.metadata,
        }
