"""
Progress Record Entity - Clean Architecture Domain Layer
Tracks learning progress with detailed analytics and business rules
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from uuid import uuid4, UUID
from enum import Enum

from ..exceptions.domain_exceptions import ValidationError, BusinessRuleViolation


class ProgressStatus(Enum):
    """Progress status enumeration"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class ActivityType(Enum):
    """Types of learning activities"""
    STARTED = "started"
    PROGRESS_UPDATE = "progress_update"
    MILESTONE_REACHED = "milestone_reached"
    PAUSED = "paused"
    RESUMED = "resumed"
    COMPLETED = "completed"
    NOTE_ADDED = "note_added"
    GOAL_SET = "goal_set"
    RESOURCE_ADDED = "resource_added"


@dataclass
class ProgressActivity:
    """Individual progress activity record"""
    activity_type: ActivityType
    timestamp: datetime
    description: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not isinstance(self.activity_type, ActivityType):
            raise ValidationError("activity_type", "Must be valid ActivityType")


@dataclass
class ProgressRecord:
    """
    Entity tracking learning progress for a repository
    Contains business logic for progress calculation and analytics
    """
    repository_id: UUID
    learner_id: str  # Could be user ID or session ID
    
    # Core progress data
    status: ProgressStatus = ProgressStatus.NOT_STARTED
    progress_percentage: float = 0.0
    
    # Time tracking
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_activity_at: Optional[datetime] = None
    total_time_spent_minutes: int = 0
    
    # Learning data
    learning_goals: List[str] = field(default_factory=list)
    milestones_completed: List[str] = field(default_factory=list)
    resources_used: List[str] = field(default_factory=list)
    notes: str = ""
    
    # Analytics
    activities: List[ProgressActivity] = field(default_factory=list)
    difficulty_rating: Optional[int] = None  # 1-5 scale, user feedback
    satisfaction_rating: Optional[int] = None  # 1-5 scale, user feedback
    
    # Metadata
    record_id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Validate progress record invariants"""
        self._validate_record()
    
    def _validate_record(self):
        """Business rule: Validate progress record data"""
        if not (0 <= self.progress_percentage <= 100):
            raise ValidationError("progress_percentage", "Progress must be between 0 and 100")
        
        if self.total_time_spent_minutes < 0:
            raise ValidationError("total_time_spent_minutes", "Time spent cannot be negative")
        
        if self.difficulty_rating is not None and not (1 <= self.difficulty_rating <= 5):
            raise ValidationError("difficulty_rating", "Difficulty rating must be between 1 and 5")
        
        if self.satisfaction_rating is not None and not (1 <= self.satisfaction_rating <= 5):
            raise ValidationError("satisfaction_rating", "Satisfaction rating must be between 1 and 5")
    
    def start_learning(self, goals: List[str] = None) -> None:
        """
        Business rule: Start learning process
        Validates state transition and initializes tracking
        """
        if self.status != ProgressStatus.NOT_STARTED:
            raise BusinessRuleViolation(f"Cannot start learning from {self.status.value} status")
        
        self.status = ProgressStatus.IN_PROGRESS
        self.started_at = datetime.now()
        self.last_activity_at = datetime.now()
        
        if goals:
            self.learning_goals = goals
            self._add_activity(ActivityType.GOAL_SET, f"Set {len(goals)} learning goals")
        
        self._add_activity(ActivityType.STARTED, "Started learning repository")
        self._update_timestamp()
    
    def update_progress(self, percentage: float, time_spent_minutes: int = 0, notes: str = "") -> None:
        """
        Business rule: Update learning progress
        Validates progress and handles automatic completion
        """
        if self.status not in [ProgressStatus.IN_PROGRESS, ProgressStatus.PAUSED]:
            raise BusinessRuleViolation(f"Cannot update progress from {self.status.value} status")
        
        if not (0 <= percentage <= 100):
            raise ValidationError("percentage", "Progress percentage must be between 0 and 100")
        
        if percentage < self.progress_percentage:
            raise BusinessRuleViolation("Progress percentage cannot decrease")
        
        old_percentage = self.progress_percentage
        self.progress_percentage = percentage
        self.total_time_spent_minutes += time_spent_minutes
        self.last_activity_at = datetime.now()
        
        if self.status == ProgressStatus.PAUSED:
            self.status = ProgressStatus.IN_PROGRESS
            self._add_activity(ActivityType.RESUMED, "Resumed learning")
        
        # Add progress activity
        progress_description = f"Progress updated from {old_percentage:.1f}% to {percentage:.1f}%"
        if time_spent_minutes > 0:
            progress_description += f" (+{time_spent_minutes} minutes)"
        
        self._add_activity(
            ActivityType.PROGRESS_UPDATE, 
            progress_description,
            {"old_percentage": old_percentage, "new_percentage": percentage, "time_spent": time_spent_minutes}
        )
        
        if notes:
            self.add_note(notes)
        
        # Auto-complete if 100%
        if percentage >= 100.0:
            self.complete_learning()
        
        self._update_timestamp()
    
    def pause_learning(self, reason: str = "") -> None:
        """
        Business rule: Pause learning process
        """
        if self.status != ProgressStatus.IN_PROGRESS:
            raise BusinessRuleViolation(f"Cannot pause learning from {self.status.value} status")
        
        self.status = ProgressStatus.PAUSED
        self.last_activity_at = datetime.now()
        
        pause_description = "Paused learning"
        if reason:
            pause_description += f": {reason}"
        
        self._add_activity(ActivityType.PAUSED, pause_description, {"reason": reason})
        self._update_timestamp()
    
    def complete_learning(self, completion_notes: str = "") -> None:
        """
        Business rule: Complete learning process
        Validates completion and finalizes tracking
        """
        if self.status not in [ProgressStatus.IN_PROGRESS, ProgressStatus.PAUSED]:
            raise BusinessRuleViolation(f"Cannot complete learning from {self.status.value} status")
        
        self.status = ProgressStatus.COMPLETED
        self.progress_percentage = 100.0
        self.completed_at = datetime.now()
        self.last_activity_at = datetime.now()
        
        if completion_notes:
            self.notes += f"\n\nCompletion Notes: {completion_notes}"
        
        self._add_activity(ActivityType.COMPLETED, "Completed learning repository")
        self._update_timestamp()
    
    def abandon_learning(self, reason: str = "") -> None:
        """
        Business rule: Abandon learning process
        """
        if self.status == ProgressStatus.COMPLETED:
            raise BusinessRuleViolation("Cannot abandon completed learning")
        
        self.status = ProgressStatus.ABANDONED
        self.last_activity_at = datetime.now()
        
        abandon_description = "Abandoned learning"
        if reason:
            abandon_description += f": {reason}"
            self.notes += f"\n\nAbandoned: {reason}"
        
        self._add_activity(ActivityType.NOTE_ADDED, abandon_description, {"reason": reason})
        self._update_timestamp()
    
    def add_milestone(self, milestone: str) -> None:
        """Add a completed milestone"""
        if milestone not in self.milestones_completed:
            self.milestones_completed.append(milestone)
            self.last_activity_at = datetime.now()
            
            self._add_activity(
                ActivityType.MILESTONE_REACHED, 
                f"Milestone reached: {milestone}",
                {"milestone": milestone}
            )
            self._update_timestamp()
    
    def add_note(self, note: str) -> None:
        """Add a learning note"""
        if not note.strip():
            return
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.notes += f"\n[{timestamp}] {note}"
        self.last_activity_at = datetime.now()
        
        self._add_activity(ActivityType.NOTE_ADDED, f"Note added: {note[:50]}...")
        self._update_timestamp()
    
    def add_resource(self, resource: str) -> None:
        """Add a learning resource"""
        if resource not in self.resources_used:
            self.resources_used.append(resource)
            self.last_activity_at = datetime.now()
            
            self._add_activity(
                ActivityType.RESOURCE_ADDED,
                f"Resource added: {resource}",
                {"resource": resource}
            )
            self._update_timestamp()
    
    def set_difficulty_rating(self, rating: int) -> None:
        """Set difficulty rating (1-5 scale)"""
        if not (1 <= rating <= 5):
            raise ValidationError("rating", "Difficulty rating must be between 1 and 5")
        
        self.difficulty_rating = rating
        self._update_timestamp()
    
    def set_satisfaction_rating(self, rating: int) -> None:
        """Set satisfaction rating (1-5 scale)"""
        if not (1 <= rating <= 5):
            raise ValidationError("rating", "Satisfaction rating must be between 1 and 5")
        
        self.satisfaction_rating = rating
        self._update_timestamp()
    
    def _add_activity(self, activity_type: ActivityType, description: str, metadata: Dict[str, Any] = None) -> None:
        """Add a progress activity"""
        activity = ProgressActivity(
            activity_type=activity_type,
            timestamp=datetime.now(),
            description=description,
            metadata=metadata or {}
        )
        self.activities.append(activity)
    
    def _update_timestamp(self) -> None:
        """Update the record timestamp"""
        self.updated_at = datetime.now()
    
    def get_learning_velocity(self) -> float:
        """
        Business logic: Calculate learning velocity (progress per hour)
        """
        if self.total_time_spent_minutes == 0:
            return 0.0
        
        hours_spent = self.total_time_spent_minutes / 60
        return self.progress_percentage / hours_spent
    
    def get_estimated_completion_time(self) -> Optional[datetime]:
        """
        Business logic: Estimate completion time based on current velocity
        """
        if self.status == ProgressStatus.COMPLETED:
            return self.completed_at
        
        velocity = self.get_learning_velocity()
        if velocity <= 0 or self.progress_percentage >= 100:
            return None
        
        remaining_progress = 100 - self.progress_percentage
        estimated_hours = remaining_progress / velocity
        
        return datetime.now() + timedelta(hours=estimated_hours)
    
    def get_activity_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get activity summary for the last N days"""
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_activities = [
            activity for activity in self.activities
            if activity.timestamp >= cutoff_date
        ]
        
        activity_counts = {}
        for activity in recent_activities:
            activity_type = activity.activity_type.value
            activity_counts[activity_type] = activity_counts.get(activity_type, 0) + 1
        
        return {
            "period_days": days,
            "total_activities": len(recent_activities),
            "activity_breakdown": activity_counts,
            "last_activity": self.last_activity_at.isoformat() if self.last_activity_at else None
        }
    
    def is_stale(self, days_threshold: int = 7) -> bool:
        """
        Business rule: Check if progress is stale (no recent activity)
        """
        if not self.last_activity_at:
            return True
        
        return (datetime.now() - self.last_activity_at).days > days_threshold
    
    def get_learning_insights(self) -> Dict[str, Any]:
        """
        Business logic: Generate learning insights and recommendations
        """
        insights = {
            "status": self.status.value,
            "progress": self.progress_percentage,
            "velocity": self.get_learning_velocity(),
            "time_efficiency": self._calculate_time_efficiency(),
            "engagement_score": self._calculate_engagement_score(),
            "recommendations": self._generate_recommendations()
        }
        
        estimated_completion = self.get_estimated_completion_time()
        if estimated_completion:
            insights["estimated_completion"] = estimated_completion.isoformat()
        
        return insights
    
    def _calculate_time_efficiency(self) -> float:
        """Calculate time efficiency based on progress and time spent"""
        if self.total_time_spent_minutes == 0:
            return 1.0
        
        # Assume 1% progress should take about 6 minutes (10 hours total for 100%)
        expected_minutes = self.progress_percentage * 6
        actual_minutes = self.total_time_spent_minutes
        
        if actual_minutes == 0:
            return 1.0
        
        return min(expected_minutes / actual_minutes, 2.0)  # Cap at 2x efficiency
    
    def _calculate_engagement_score(self) -> float:
        """Calculate engagement score based on activity patterns"""
        if not self.activities:
            return 0.0
        
        # Recent activity weight
        recent_activities = len([
            a for a in self.activities 
            if (datetime.now() - a.timestamp).days <= 7
        ])
        
        # Variety of activities
        activity_types = len(set(a.activity_type for a in self.activities))
        
        # Notes and milestones indicate engagement
        engagement_indicators = len(self.milestones_completed) + (1 if self.notes.strip() else 0)
        
        # Normalize to 0-1 scale
        score = (recent_activities * 0.4 + activity_types * 0.3 + engagement_indicators * 0.3) / 10
        return min(score, 1.0)
    
    def _generate_recommendations(self) -> List[str]:
        """Generate personalized learning recommendations"""
        recommendations = []
        
        if self.status == ProgressStatus.IN_PROGRESS:
            velocity = self.get_learning_velocity()
            if velocity < 2:  # Less than 2% per hour
                recommendations.append("Consider breaking learning into smaller, focused sessions")
            
            if self.is_stale(3):  # No activity for 3 days
                recommendations.append("Try to maintain consistent learning momentum")
            
            if len(self.milestones_completed) == 0 and self.progress_percentage > 25:
                recommendations.append("Set specific milestones to track your progress better")
        
        elif self.status == ProgressStatus.PAUSED:
            recommendations.append("Consider resuming your learning when you have time")
        
        elif self.status == ProgressStatus.NOT_STARTED:
            recommendations.append("Set clear learning goals before starting")
        
        if not self.learning_goals:
            recommendations.append("Define specific learning objectives to stay focused")
        
        return recommendations
    
    def __eq__(self, other) -> bool:
        """Progress records are equal if they track the same repository for same learner"""
        if not isinstance(other, ProgressRecord):
            return False
        return (
            self.repository_id == other.repository_id and
            self.learner_id == other.learner_id
        )
    
    def __hash__(self) -> int:
        """Hash based on repository and learner IDs"""
        return hash((self.repository_id, self.learner_id))
    
    def __str__(self) -> str:
        return f"ProgressRecord({self.repository_id}, {self.status.value}, {self.progress_percentage:.1f}%)"
