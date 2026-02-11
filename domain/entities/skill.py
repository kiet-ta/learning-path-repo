"""
Skill Domain Models - Clean Architecture Domain Layer
Defines skill types, levels, and skill-related business logic
"""
from enum import Enum
from dataclasses import dataclass
from typing import List, Set, Optional
from ..exceptions.domain_exceptions import ValidationError, BusinessRuleViolation


class SkillType(Enum):
    """Enumeration of skill types in software development"""
    FRONTEND = "frontend"
    BACKEND = "backend" 
    DATA_SCIENCE = "data_science"
    INFRASTRUCTURE = "infrastructure"
    MOBILE = "mobile"
    DEVOPS = "devops"
    MACHINE_LEARNING = "machine_learning"
    SECURITY = "security"
    
    @classmethod
    def get_compatible_types(cls, skill_type: 'SkillType') -> Set['SkillType']:
        """Get skill types that are compatible for learning progression"""
        compatibility_map = {
            cls.FRONTEND: {cls.BACKEND, cls.MOBILE},
            cls.BACKEND: {cls.FRONTEND, cls.DATA_SCIENCE, cls.DEVOPS, cls.SECURITY},
            cls.DATA_SCIENCE: {cls.BACKEND, cls.MACHINE_LEARNING},
            cls.INFRASTRUCTURE: {cls.DEVOPS, cls.BACKEND, cls.SECURITY},
            cls.MOBILE: {cls.FRONTEND, cls.BACKEND},
            cls.DEVOPS: {cls.INFRASTRUCTURE, cls.BACKEND, cls.SECURITY},
            cls.MACHINE_LEARNING: {cls.DATA_SCIENCE, cls.BACKEND},
            cls.SECURITY: {cls.BACKEND, cls.INFRASTRUCTURE, cls.DEVOPS}
        }
        return compatibility_map.get(skill_type, set())


class SkillLevel(Enum):
    """Enumeration of skill proficiency levels"""
    BASIC = "basic"
    INTERMEDIATE = "intermediate" 
    ADVANCED = "advanced"
    EXPERT = "expert"
    
    def __lt__(self, other: 'SkillLevel') -> bool:
        """Enable comparison for skill level progression"""
        order = [self.BASIC, self.INTERMEDIATE, self.ADVANCED, self.EXPERT]
        return order.index(self) < order.index(other)
    
    def __le__(self, other: 'SkillLevel') -> bool:
        return self < other or self == other
    
    def can_progress_to(self, target_level: 'SkillLevel') -> bool:
        """Check if progression to target level is valid"""
        return self <= target_level
    
    def get_next_level(self) -> Optional['SkillLevel']:
        """Get the next skill level in progression"""
        progression = {
            self.BASIC: self.INTERMEDIATE,
            self.INTERMEDIATE: self.ADVANCED,
            self.ADVANCED: self.EXPERT,
            self.EXPERT: None
        }
        return progression.get(self)


@dataclass(frozen=True)
class Skill:
    """
    Value object representing a skill with type and level
    Immutable and contains skill-related business logic
    """
    skill_type: SkillType
    skill_level: SkillLevel
    
    def __post_init__(self):
        """Validate skill invariants"""
        if not isinstance(self.skill_type, SkillType):
            raise ValidationError("skill_type", "Must be a valid SkillType enum")
        if not isinstance(self.skill_level, SkillLevel):
            raise ValidationError("skill_level", "Must be a valid SkillLevel enum")
    
    def can_be_prerequisite_for(self, target_skill: 'Skill') -> bool:
        """
        Business rule: Check if this skill can be a prerequisite for target skill
        """
        # Same skill type with lower or equal level
        if self.skill_type == target_skill.skill_type:
            return self.skill_level <= target_skill.skill_level
        
        # Compatible skill types
        compatible_types = SkillType.get_compatible_types(self.skill_type)
        if target_skill.skill_type in compatible_types:
            # For cross-skill dependencies, require at least intermediate level
            return self.skill_level >= SkillLevel.INTERMEDIATE
        
        return False
    
    def get_learning_difficulty(self) -> int:
        """
        Business logic: Calculate learning difficulty score (1-10)
        """
        base_difficulty = {
            SkillLevel.BASIC: 2,
            SkillLevel.INTERMEDIATE: 4,
            SkillLevel.ADVANCED: 7,
            SkillLevel.EXPERT: 9
        }
        
        type_multiplier = {
            SkillType.FRONTEND: 1.0,
            SkillType.BACKEND: 1.2,
            SkillType.DATA_SCIENCE: 1.4,
            SkillType.INFRASTRUCTURE: 1.3,
            SkillType.MOBILE: 1.1,
            SkillType.DEVOPS: 1.5,
            SkillType.MACHINE_LEARNING: 1.6,
            SkillType.SECURITY: 1.4
        }
        
        difficulty = base_difficulty[self.skill_level] * type_multiplier[self.skill_type]
        return min(int(difficulty), 10)
    
    def estimate_learning_hours(self) -> int:
        """
        Business logic: Estimate learning hours based on skill type and level
        """
        base_hours = {
            SkillLevel.BASIC: 20,
            SkillLevel.INTERMEDIATE: 40,
            SkillLevel.ADVANCED: 80,
            SkillLevel.EXPERT: 120
        }
        
        type_factor = {
            SkillType.FRONTEND: 0.8,
            SkillType.BACKEND: 1.0,
            SkillType.DATA_SCIENCE: 1.3,
            SkillType.INFRASTRUCTURE: 1.2,
            SkillType.MOBILE: 0.9,
            SkillType.DEVOPS: 1.4,
            SkillType.MACHINE_LEARNING: 1.5,
            SkillType.SECURITY: 1.3
        }
        
        return int(base_hours[self.skill_level] * type_factor[self.skill_type])
    
    def __str__(self) -> str:
        return f"{self.skill_type.value}:{self.skill_level.value}"
