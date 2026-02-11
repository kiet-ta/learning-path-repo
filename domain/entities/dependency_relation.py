"""
Dependency Relation Entity - Clean Architecture Domain Layer
Represents dependency relationships between repositories with business rules
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import uuid4, UUID
from enum import Enum

from ..exceptions.domain_exceptions import ValidationError, BusinessRuleViolation


class DependencyType(Enum):
    """Types of dependencies between repositories"""
    PREREQUISITE = "prerequisite"      # Must learn A before B
    RECOMMENDED = "recommended"        # A helps with learning B
    RELATED = "related"               # A and B are related topics
    ALTERNATIVE = "alternative"       # A or B can be learned (not both needed)


class DependencyStrength(Enum):
    """Strength of dependency relationship"""
    WEAK = "weak"          # Nice to have
    MODERATE = "moderate"  # Recommended
    STRONG = "strong"      # Highly recommended
    CRITICAL = "critical"  # Required


@dataclass
class DependencyRelation:
    """
    Entity representing a dependency relationship between two repositories
    Contains business logic for dependency validation and management
    """
    source_repository_id: UUID
    target_repository_id: UUID
    dependency_type: DependencyType
    strength: DependencyStrength
    
    # Metadata
    relation_id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=datetime.now)
    created_by: str = "system"  # "system" or "user" for manual overrides
    
    # Optional details
    reason: Optional[str] = None
    confidence_score: float = 1.0  # 0-1, for AI-generated dependencies
    
    def __post_init__(self):
        """Validate dependency relation invariants"""
        self._validate_relation()
    
    def _validate_relation(self):
        """Business rule: Validate dependency relation"""
        if self.source_repository_id == self.target_repository_id:
            raise BusinessRuleViolation("Repository cannot depend on itself")
        
        if not isinstance(self.dependency_type, DependencyType):
            raise ValidationError("dependency_type", "Must be a valid DependencyType")
        
        if not isinstance(self.strength, DependencyStrength):
            raise ValidationError("strength", "Must be a valid DependencyStrength")
        
        if not (0 <= self.confidence_score <= 1):
            raise ValidationError("confidence_score", "Confidence score must be between 0 and 1")
    
    def is_blocking_dependency(self) -> bool:
        """
        Business rule: Check if this dependency blocks learning progression
        Only PREREQUISITE dependencies with STRONG or CRITICAL strength block
        """
        return (
            self.dependency_type == DependencyType.PREREQUISITE and
            self.strength in [DependencyStrength.STRONG, DependencyStrength.CRITICAL]
        )
    
    def is_user_override(self) -> bool:
        """Check if this dependency was manually created by user"""
        return self.created_by == "user"
    
    def can_be_ignored(self) -> bool:
        """
        Business rule: Check if dependency can be safely ignored
        Weak dependencies and low-confidence AI suggestions can be ignored
        """
        if self.is_user_override():
            return False  # Never ignore user overrides
        
        return (
            self.strength == DependencyStrength.WEAK or
            self.confidence_score < 0.5
        )
    
    def get_learning_impact_score(self) -> float:
        """
        Business logic: Calculate impact score on learning path (0-1)
        Higher score means more important for learning sequence
        """
        # Base score from dependency type
        type_scores = {
            DependencyType.PREREQUISITE: 1.0,
            DependencyType.RECOMMENDED: 0.7,
            DependencyType.RELATED: 0.4,
            DependencyType.ALTERNATIVE: 0.2
        }
        
        # Strength multiplier
        strength_multipliers = {
            DependencyStrength.CRITICAL: 1.0,
            DependencyStrength.STRONG: 0.8,
            DependencyStrength.MODERATE: 0.6,
            DependencyStrength.WEAK: 0.3
        }
        
        base_score = type_scores[self.dependency_type]
        strength_mult = strength_multipliers[self.strength]
        
        # Apply confidence score
        final_score = base_score * strength_mult * self.confidence_score
        
        # User overrides get bonus
        if self.is_user_override():
            final_score = min(final_score * 1.2, 1.0)
        
        return final_score
    
    def create_reverse_relation(self) -> 'DependencyRelation':
        """
        Business logic: Create reverse relation for bidirectional dependencies
        Used for RELATED and ALTERNATIVE types
        """
        if self.dependency_type not in [DependencyType.RELATED, DependencyType.ALTERNATIVE]:
            raise BusinessRuleViolation(
                f"Cannot create reverse relation for {self.dependency_type.value} dependency"
            )
        
        return DependencyRelation(
            source_repository_id=self.target_repository_id,
            target_repository_id=self.source_repository_id,
            dependency_type=self.dependency_type,
            strength=self.strength,
            created_by=self.created_by,
            reason=f"Reverse of: {self.reason}" if self.reason else None,
            confidence_score=self.confidence_score
        )
    
    def update_confidence(self, new_confidence: float, reason: str = "") -> None:
        """Update confidence score with validation"""
        if not (0 <= new_confidence <= 1):
            raise ValidationError("confidence", "Confidence must be between 0 and 1")
        
        self.confidence_score = new_confidence
        if reason:
            self.reason = f"{self.reason}; Updated: {reason}" if self.reason else reason
    
    def __eq__(self, other) -> bool:
        """Dependencies are equal if they connect the same repositories"""
        if not isinstance(other, DependencyRelation):
            return False
        return (
            self.source_repository_id == other.source_repository_id and
            self.target_repository_id == other.target_repository_id
        )
    
    def __hash__(self) -> int:
        """Hash based on source and target repository IDs"""
        return hash((self.source_repository_id, self.target_repository_id))
    
    def __str__(self) -> str:
        return f"Dependency({self.source_repository_id} -> {self.target_repository_id}, {self.dependency_type.value})"
