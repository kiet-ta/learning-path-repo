"""
Repository Entity - Core domain model for code repositories
Following Domain-Driven Design principles
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum


class SkillLevel(Enum):
    """Skill level classification"""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class SkillType(Enum):
    """Skill type classification"""
    FRONTEND = "frontend"
    BACKEND = "backend"
    DATA_SCIENCE = "data_science"
    DEVOPS = "devops"
    MOBILE = "mobile"
    MACHINE_LEARNING = "machine_learning"
    INFRASTRUCTURE = "infrastructure"


@dataclass
class Repository:
    """
    Core Repository entity representing a code repository
    
    This is a domain entity that encapsulates repository business logic
    and maintains data integrity through validation.
    """
    name: str
    path: str
    primary_language: str
    description: Optional[str] = None
    topics: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    skill_level: Optional[SkillLevel] = None
    skill_type: Optional[SkillType] = None
    complexity_score: float = 0.0
    estimated_learning_hours: int = 0
    last_updated: Optional[datetime] = None
    readme_content: Optional[str] = None
    docs_content: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate entity after initialization"""
        self._validate()
    
    def _validate(self) -> None:
        """Validate repository data integrity"""
        if not self.name or not self.name.strip():
            raise ValueError("Repository name cannot be empty")
        
        if not self.path or not self.path.strip():
            raise ValueError("Repository path cannot be empty")
        
        if self.complexity_score < 0 or self.complexity_score > 10:
            raise ValueError("Complexity score must be between 0 and 10")
        
        if self.estimated_learning_hours < 0:
            raise ValueError("Estimated learning hours cannot be negative")
    
    def add_topic(self, topic: str) -> None:
        """Add a topic to the repository"""
        if topic and topic not in self.topics:
            self.topics.append(topic)
    
    def add_dependency(self, dependency: str) -> None:
        """Add a dependency to the repository"""
        if dependency and dependency not in self.dependencies:
            self.dependencies.append(dependency)
    
    def set_skill_classification(self, skill_type: SkillType, skill_level: SkillLevel) -> None:
        """Set skill classification for the repository"""
        self.skill_type = skill_type
        self.skill_level = skill_level
    
    def calculate_complexity_score(self) -> float:
        """
        Calculate complexity score based on various factors
        Business logic for complexity calculation
        """
        score = 0.0
        
        # Language complexity weight
        language_weights = {
            "python": 2.0,
            "javascript": 2.5,
            "typescript": 3.0,
            "java": 3.5,
            "c++": 4.0,
            "rust": 4.5,
            "go": 3.0,
        }
        
        score += language_weights.get(self.primary_language.lower(), 2.0)
        
        # Dependencies complexity
        score += min(len(self.dependencies) * 0.1, 2.0)
        
        # Topics complexity
        score += min(len(self.topics) * 0.2, 2.0)
        
        # Normalize to 0-10 scale
        self.complexity_score = min(score, 10.0)
        return self.complexity_score
    
    def estimate_learning_time(self) -> int:
        """
        Estimate learning time based on complexity and skill level
        Business logic for time estimation
        """
        base_hours = {
            SkillLevel.BEGINNER: 20,
            SkillLevel.INTERMEDIATE: 15,
            SkillLevel.ADVANCED: 10,
            SkillLevel.EXPERT: 5,
        }
        
        if not self.skill_level:
            self.skill_level = SkillLevel.INTERMEDIATE
        
        hours = base_hours[self.skill_level]
        
        # Adjust based on complexity
        complexity_multiplier = 1 + (self.complexity_score / 10)
        hours = int(hours * complexity_multiplier)
        
        self.estimated_learning_hours = hours
        return hours
    
    def is_prerequisite_for(self, other: "Repository") -> bool:
        """
        Determine if this repository is a prerequisite for another
        Business logic for dependency relationships
        """
        if not other or not self.topics:
            return False
        
        # Check if any of our topics are in other's dependencies
        return any(topic in other.dependencies for topic in self.topics)
    
    def get_learning_priority(self) -> int:
        """
        Calculate learning priority (lower number = higher priority)
        Business logic for prioritization
        """
        priority = 0
        
        # Skill level priority (beginner first)
        if self.skill_level == SkillLevel.BEGINNER:
            priority += 1
        elif self.skill_level == SkillLevel.INTERMEDIATE:
            priority += 2
        elif self.skill_level == SkillLevel.ADVANCED:
            priority += 3
        else:
            priority += 4
        
        # Complexity priority (simpler first)
        priority += int(self.complexity_score)
        
        # Dependencies priority (fewer dependencies first)
        priority += len(self.dependencies)
        
        return priority
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert repository to dictionary representation"""
        return {
            "name": self.name,
            "path": self.path,
            "primary_language": self.primary_language,
            "description": self.description,
            "topics": self.topics,
            "dependencies": self.dependencies,
            "skill_level": self.skill_level.value if self.skill_level else None,
            "skill_type": self.skill_type.value if self.skill_type else None,
            "complexity_score": self.complexity_score,
            "estimated_learning_hours": self.estimated_learning_hours,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Repository":
        """Create repository from dictionary representation"""
        # Convert enum strings back to enums
        if data.get("skill_level"):
            data["skill_level"] = SkillLevel(data["skill_level"])
        if data.get("skill_type"):
            data["skill_type"] = SkillType(data["skill_type"])
        
        # Convert datetime string back to datetime
        if data.get("last_updated"):
            data["last_updated"] = datetime.fromisoformat(data["last_updated"])
        
        return cls(**data)
