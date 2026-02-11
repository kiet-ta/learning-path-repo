"""
Learning Node Entity - Clean Architecture Domain Layer
Represents a node in the learning path with dependencies and progress tracking
"""
from dataclasses import dataclass, field
from typing import Set, List, Optional, Dict
from datetime import datetime, timedelta
from uuid import uuid4, UUID
from enum import Enum

from .repository import Repository
from .skill import Skill
from ..exceptions.domain_exceptions import ValidationError, BusinessRuleViolation, InvalidLearningSequenceError


class NodeStatus(Enum):
    """Status of a learning node"""
    NOT_STARTED = "not_started"
    AVAILABLE = "available"      # Prerequisites met, can start
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"          # Prerequisites not met
    SKIPPED = "skipped"


@dataclass
class LearningNode:
    """
    Entity representing a node in the learning path
    Contains business logic for dependency management and progress tracking
    """
    repository: Repository
    node_id: UUID = field(default_factory=uuid4)
    
    # Dependencies
    prerequisite_nodes: Set[UUID] = field(default_factory=set)
    dependent_nodes: Set[UUID] = field(default_factory=set)
    
    # Learning metadata
    estimated_hours: int = 0
    actual_hours: float = 0.0
    difficulty_override: Optional[int] = None  # Manual difficulty override (1-10)
    
    # Status and progress
    status: NodeStatus = NodeStatus.NOT_STARTED
    progress_percentage: float = 0.0
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Learning goals and notes
    learning_goals: List[str] = field(default_factory=list)
    completion_notes: str = ""
    
    def __post_init__(self):
        """Initialize node with repository data"""
        if self.estimated_hours == 0:
            self.estimated_hours = self.repository.learning_hours_estimate
        
        self._validate_node()
    
    def _validate_node(self):
        """Validate node invariants"""
        if not isinstance(self.repository, Repository):
            raise ValidationError("repository", "Must be a valid Repository entity")
        
        if self.estimated_hours < 0:
            raise ValidationError("estimated_hours", "Estimated hours cannot be negative")
        
        if not (0 <= self.progress_percentage <= 100):
            raise ValidationError("progress_percentage", "Progress must be between 0 and 100")
        
        if self.difficulty_override is not None and not (1 <= self.difficulty_override <= 10):
            raise ValidationError("difficulty_override", "Difficulty override must be between 1 and 10")
    
    def add_prerequisite(self, prerequisite_node_id: UUID) -> None:
        """
        Business rule: Add a prerequisite node
        Prevents self-dependency and circular dependencies
        """
        if prerequisite_node_id == self.node_id:
            raise BusinessRuleViolation("Node cannot be its own prerequisite")
        
        if prerequisite_node_id in self.dependent_nodes:
            raise BusinessRuleViolation("Cannot add prerequisite - would create circular dependency")
        
        self.prerequisite_nodes.add(prerequisite_node_id)
        self._update_status_based_on_prerequisites()
    
    def add_dependent(self, dependent_node_id: UUID) -> None:
        """
        Business rule: Add a dependent node
        Prevents self-dependency and circular dependencies
        """
        if dependent_node_id == self.node_id:
            raise BusinessRuleViolation("Node cannot depend on itself")
        
        if dependent_node_id in self.prerequisite_nodes:
            raise BusinessRuleViolation("Cannot add dependent - would create circular dependency")
        
        self.dependent_nodes.add(dependent_node_id)
    
    def can_start_learning(self, completed_node_ids: Set[UUID]) -> bool:
        """
        Business rule: Check if learning can start
        All prerequisites must be completed
        """
        if self.status in [NodeStatus.COMPLETED, NodeStatus.IN_PROGRESS]:
            return False
        
        return self.prerequisite_nodes.issubset(completed_node_ids)
    
    def start_learning(self, completed_node_ids: Set[UUID], goals: List[str] = None) -> None:
        """
        Business rule: Start learning this node
        Validates prerequisites and updates status
        """
        if not self.can_start_learning(completed_node_ids):
            missing_prereqs = self.prerequisite_nodes - completed_node_ids
            raise InvalidLearningSequenceError(str(self.node_id), list(map(str, missing_prereqs)))
        
        if self.status == NodeStatus.COMPLETED:
            raise BusinessRuleViolation("Cannot restart completed node")
        
        self.status = NodeStatus.IN_PROGRESS
        self.started_at = datetime.now()
        self.progress_percentage = 0.0
        
        if goals:
            self.learning_goals = goals
    
    def update_progress(self, percentage: float, hours_spent: float = 0.0) -> None:
        """
        Business rule: Update learning progress
        Validates progress and updates status
        """
        if not (0 <= percentage <= 100):
            raise ValidationError("percentage", "Progress percentage must be between 0 and 100")
        
        if self.status != NodeStatus.IN_PROGRESS:
            raise BusinessRuleViolation("Can only update progress for in-progress nodes")
        
        self.progress_percentage = percentage
        self.actual_hours += hours_spent
        
        # Auto-complete if 100%
        if percentage >= 100.0:
            self.complete_learning()
    
    def complete_learning(self, completion_notes: str = "") -> None:
        """
        Business rule: Mark node as completed
        Updates status and timestamps
        """
        if self.status != NodeStatus.IN_PROGRESS:
            raise BusinessRuleViolation("Can only complete in-progress nodes")
        
        self.status = NodeStatus.COMPLETED
        self.completed_at = datetime.now()
        self.progress_percentage = 100.0
        self.completion_notes = completion_notes
    
    def skip_learning(self, reason: str = "") -> None:
        """
        Business rule: Skip this learning node
        Allows progression without completion
        """
        if self.status == NodeStatus.COMPLETED:
            raise BusinessRuleViolation("Cannot skip completed node")
        
        self.status = NodeStatus.SKIPPED
        self.completion_notes = f"Skipped: {reason}"
        self.progress_percentage = 0.0
    
    def reset_progress(self) -> None:
        """
        Business rule: Reset node progress
        Allows restarting learning
        """
        if self.status == NodeStatus.IN_PROGRESS:
            raise BusinessRuleViolation("Cannot reset in-progress node")
        
        self.status = NodeStatus.NOT_STARTED
        self.progress_percentage = 0.0
        self.actual_hours = 0.0
        self.started_at = None
        self.completed_at = None
        self.completion_notes = ""
    
    def _update_status_based_on_prerequisites(self) -> None:
        """Update status based on prerequisite completion"""
        if self.status in [NodeStatus.COMPLETED, NodeStatus.IN_PROGRESS, NodeStatus.SKIPPED]:
            return  # Don't change these statuses
        
        # This would need to be called with actual completed node data
        # For now, just set to blocked if has prerequisites
        if self.prerequisite_nodes:
            self.status = NodeStatus.BLOCKED
        else:
            self.status = NodeStatus.AVAILABLE
    
    def get_effective_difficulty(self) -> int:
        """
        Business logic: Get effective difficulty score
        Uses override if set, otherwise repository complexity
        """
        if self.difficulty_override is not None:
            return self.difficulty_override
        
        return int(self.repository.complexity_score)
    
    def get_learning_velocity(self) -> float:
        """
        Business logic: Calculate learning velocity (progress per hour)
        """
        if self.actual_hours == 0:
            return 0.0
        
        return self.progress_percentage / self.actual_hours
    
    def get_estimated_completion_date(self) -> Optional[datetime]:
        """
        Business logic: Estimate completion date based on current progress
        """
        if self.status == NodeStatus.COMPLETED:
            return self.completed_at
        
        if self.status != NodeStatus.IN_PROGRESS or self.progress_percentage == 0:
            return None
        
        velocity = self.get_learning_velocity()
        if velocity <= 0:
            return None
        
        remaining_progress = 100 - self.progress_percentage
        estimated_hours_remaining = remaining_progress / velocity
        
        return datetime.now() + timedelta(hours=estimated_hours_remaining)
    
    def get_time_efficiency(self) -> float:
        """
        Business logic: Calculate time efficiency (estimated vs actual)
        """
        if self.actual_hours == 0:
            return 1.0
        
        return self.estimated_hours / self.actual_hours
    
    def is_overdue(self, expected_completion_hours: int) -> bool:
        """
        Business rule: Check if node is overdue based on expected completion time
        """
        if not self.started_at or self.status == NodeStatus.COMPLETED:
            return False
        
        elapsed_hours = (datetime.now() - self.started_at).total_seconds() / 3600
        return elapsed_hours > expected_completion_hours
    
    def get_learning_insights(self) -> Dict[str, any]:
        """
        Business logic: Generate learning insights and recommendations
        """
        insights = {
            "status": self.status.value,
            "progress": self.progress_percentage,
            "efficiency": self.get_time_efficiency(),
            "velocity": self.get_learning_velocity(),
            "recommendations": []
        }
        
        # Generate recommendations
        recommendations = []
        
        if self.status == NodeStatus.IN_PROGRESS:
            if self.progress_percentage < 20 and self.actual_hours > self.estimated_hours * 0.5:
                recommendations.append("Consider breaking down learning into smaller tasks")
            
            if self.get_learning_velocity() < 5:  # Less than 5% per hour
                recommendations.append("Try different learning resources or approaches")
            
            if self.is_overdue(self.estimated_hours * 1.5):
                recommendations.append("Consider seeking help or additional resources")
        
        elif self.status == NodeStatus.BLOCKED:
            recommendations.append("Complete prerequisite nodes first")
        
        elif self.status == NodeStatus.NOT_STARTED and not self.prerequisite_nodes:
            recommendations.append("This node is ready to start - no prerequisites needed")
        
        insights["recommendations"] = recommendations
        return insights
    
    def __eq__(self, other) -> bool:
        """Nodes are equal if they have the same ID"""
        if not isinstance(other, LearningNode):
            return False
        return self.node_id == other.node_id
    
    def __hash__(self) -> int:
        """Hash based on node ID"""
        return hash(self.node_id)
    
    def __str__(self) -> str:
        return f"LearningNode({self.repository.name}, status={self.status.value})"
