"""
Repository Entity - Clean Architecture Domain Layer
Aggregate root representing a code repository with analysis capabilities
"""
from dataclasses import dataclass, field
from typing import Set, List, Optional, Dict, Any
from datetime import datetime
from uuid import uuid4, UUID
import hashlib

from .skill import Skill, SkillType, SkillLevel
from .topic import Topic
from ..exceptions.domain_exceptions import ValidationError, BusinessRuleViolation
from ..value_objects.repository_metadata import RepositoryMetadata


@dataclass
class Repository:
    """
    Aggregate root representing a code repository
    Contains business logic for repository analysis and learning assessment
    """
    name: str
    path: str
    primary_language: str
    description: Optional[str] = None
    
    # Core attributes
    repository_id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=datetime.now)
    last_analyzed_at: Optional[datetime] = None
    
    # Analysis results
    topics: Set[Topic] = field(default_factory=set)
    primary_skill: Optional[Skill] = None
    secondary_skills: Set[Skill] = field(default_factory=set)
    
    # Metadata for analysis
    metadata: RepositoryMetadata = field(default_factory=lambda: RepositoryMetadata())
    
    # Computed properties
    complexity_score: float = 0.0
    learning_hours_estimate: int = 0
    content_hash: Optional[str] = None  # For incremental updates
    
    def __post_init__(self):
        """Validate repository invariants"""
        self._validate_name()
        self._validate_path()
        self._validate_language()
        
        # Generate content hash if not provided
        if self.content_hash is None:
            self.content_hash = self._generate_content_hash()
    
    def _validate_name(self):
        """Business rule: Repository name must be valid"""
        if not self.name or not self.name.strip():
            raise ValidationError("name", "Repository name cannot be empty")
        
        if len(self.name) > 255:
            raise ValidationError("name", "Repository name cannot exceed 255 characters")
        
        # Repository name should be filesystem-safe
        invalid_chars = set('<>:"/\|?*')
        if any(char in self.name for char in invalid_chars):
            raise ValidationError("name", f"Repository name contains invalid characters: {invalid_chars}")
    
    def _validate_path(self):
        """Business rule: Repository path must be valid"""
        if not self.path or not self.path.strip():
            raise ValidationError("path", "Repository path cannot be empty")
    
    def _validate_language(self):
        """Business rule: Primary language must be supported"""
        supported_languages = {
            'python', 'javascript', 'typescript', 'java', 'c++', 'c#', 'c',
            'go', 'rust', 'kotlin', 'swift', 'php', 'ruby', 'scala', 'r',
            'matlab', 'shell', 'dockerfile', 'yaml', 'json', 'html', 'css'
        }
        
        if self.primary_language.lower() not in supported_languages:
            raise ValidationError("primary_language", f"Language {self.primary_language} not supported")
    
    def add_topic(self, topic: Topic) -> None:
        """
        Business rule: Add a topic to this repository
        Validates topic relevance and prevents duplicates
        """
        if not isinstance(topic, Topic):
            raise ValidationError("topic", "Must be a valid Topic entity")
        
        # Check if topic already exists
        if topic in self.topics:
            return  # Already exists, no need to add
        
        self.topics.add(topic)
        self._recalculate_complexity()
    
    def set_primary_skill(self, skill: Skill) -> None:
        """
        Business rule: Set the primary skill for this repository
        Must be compatible with repository's primary language
        """
        if not isinstance(skill, Skill):
            raise ValidationError("skill", "Must be a valid Skill entity")
        
        # Validate skill compatibility with language
        language_skill_mapping = {
            'python': {SkillType.BACKEND, SkillType.DATA_SCIENCE, SkillType.MACHINE_LEARNING},
            'javascript': {SkillType.FRONTEND, SkillType.BACKEND},
            'typescript': {SkillType.FRONTEND, SkillType.BACKEND},
            'java': {SkillType.BACKEND, SkillType.MOBILE},
            'kotlin': {SkillType.BACKEND, SkillType.MOBILE},
            'swift': {SkillType.MOBILE},
            'go': {SkillType.BACKEND, SkillType.INFRASTRUCTURE, SkillType.DEVOPS},
            'rust': {SkillType.BACKEND, SkillType.INFRASTRUCTURE},
            'dockerfile': {SkillType.DEVOPS, SkillType.INFRASTRUCTURE},
        }
        
        compatible_skills = language_skill_mapping.get(self.primary_language.lower(), set())
        if compatible_skills and skill.skill_type not in compatible_skills:
            raise BusinessRuleViolation(
                f"Skill type {skill.skill_type.value} not compatible with language {self.primary_language}"
            )
        
        self.primary_skill = skill
        self._recalculate_complexity()
    
    def add_secondary_skill(self, skill: Skill) -> None:
        """Add a secondary skill to this repository"""
        if not isinstance(skill, Skill):
            raise ValidationError("skill", "Must be a valid Skill entity")
        
        # Cannot be the same as primary skill
        if self.primary_skill and skill == self.primary_skill:
            raise BusinessRuleViolation("Secondary skill cannot be the same as primary skill")
        
        self.secondary_skills.add(skill)
        self._recalculate_complexity()
    
    def analyze_content(self, content_data: Dict[str, Any]) -> None:
        """
        Business logic: Analyze repository content and update metadata
        This is called by infrastructure analyzers
        """
        # Update metadata
        self.metadata = self.metadata.update_from_analysis(content_data)
        
        # Update analysis timestamp
        self.last_analyzed_at = datetime.now()
        
        # Recalculate derived properties
        self._recalculate_complexity()
        self._estimate_learning_hours()
        
        # Update content hash for incremental updates
        self.content_hash = self._generate_content_hash()
    
    def _recalculate_complexity(self) -> None:
        """
        Business logic: Calculate repository complexity score (0-10)
        Based on multiple factors including skills, topics, and metadata
        """
        base_score = 1.0
        
        # Language complexity factor
        language_complexity = {
            'python': 2.0, 'javascript': 2.5, 'typescript': 3.0,
            'java': 3.5, 'c++': 4.5, 'c': 4.0, 'rust': 4.8,
            'go': 3.2, 'kotlin': 3.3, 'swift': 3.1,
            'php': 2.8, 'ruby': 2.6, 'scala': 4.2
        }
        base_score += language_complexity.get(self.primary_language.lower(), 2.0)
        
        # Primary skill complexity
        if self.primary_skill:
            base_score += self.primary_skill.get_learning_difficulty() * 0.3
        
        # Secondary skills add complexity
        for skill in self.secondary_skills:
            base_score += skill.get_learning_difficulty() * 0.1
        
        # Topic complexity
        topic_complexity = sum(topic.get_learning_complexity() for topic in self.topics)
        base_score += min(topic_complexity * 0.2, 2.0)
        
        # Metadata-based complexity
        if self.metadata.lines_of_code > 10000:
            base_score += 1.5
        elif self.metadata.lines_of_code > 5000:
            base_score += 1.0
        elif self.metadata.lines_of_code > 1000:
            base_score += 0.5
        
        if self.metadata.file_count > 100:
            base_score += 1.0
        elif self.metadata.file_count > 50:
            base_score += 0.5
        
        # Dependencies add complexity
        dependency_factor = min(len(self.metadata.dependencies) * 0.1, 1.5)
        base_score += dependency_factor
        
        # Normalize to 0-10 scale
        self.complexity_score = min(base_score, 10.0)
    
    def _estimate_learning_hours(self) -> None:
        """
        Business logic: Estimate learning hours based on complexity and skills
        """
        base_hours = 20  # Minimum learning time
        
        # Complexity factor
        complexity_hours = self.complexity_score * 8
        
        # Skill-based hours
        skill_hours = 0
        if self.primary_skill:
            skill_hours += self.primary_skill.estimate_learning_hours()
        
        for skill in self.secondary_skills:
            skill_hours += skill.estimate_learning_hours() * 0.3
        
        # Topic-based hours
        topic_hours = sum(topic.get_learning_complexity() * 5 for topic in self.topics)
        
        # Size-based adjustment
        size_multiplier = 1.0
        if self.metadata.lines_of_code > 10000:
            size_multiplier = 1.5
        elif self.metadata.lines_of_code > 5000:
            size_multiplier = 1.2
        
        total_hours = (base_hours + complexity_hours + skill_hours + topic_hours) * size_multiplier
        self.learning_hours_estimate = int(min(total_hours, 200))  # Cap at 200 hours
    
    def _generate_content_hash(self) -> str:
        """Generate hash for incremental update detection"""
        content_string = f"{self.name}:{self.primary_language}:{self.metadata.lines_of_code}:{len(self.topics)}"
        return hashlib.md5(content_string.encode()).hexdigest()
    
    def has_changed_since_analysis(self, previous_hash: str) -> bool:
        """Check if repository has changed since last analysis"""
        return self.content_hash != previous_hash
    
    def can_be_prerequisite_for(self, other_repository: 'Repository') -> bool:
        """
        Business rule: Check if this repository can be a prerequisite for another
        Based on skill progression and topic dependencies
        """
        if not other_repository:
            return False
        
        # Skill-based prerequisite check
        if self.primary_skill and other_repository.primary_skill:
            if self.primary_skill.can_be_prerequisite_for(other_repository.primary_skill):
                return True
        
        # Topic-based prerequisite check
        our_topic_names = {topic.name for topic in self.topics}
        their_topic_names = {topic.name for topic in other_repository.topics}
        
        # Check if any of our topics are prerequisites for their topics
        for their_topic in other_repository.topics:
            if their_topic.parent_topics.intersection(our_topic_names):
                return True
        
        # Complexity-based prerequisite (simpler repositories first)
        return self.complexity_score < other_repository.complexity_score
    
    def get_learning_prerequisites(self) -> Set[str]:
        """
        Business logic: Get prerequisite topic names for learning this repository
        """
        prerequisites = set()
        
        # Collect all topic prerequisites
        for topic in self.topics:
            prerequisites.update(topic.parent_topics)
        
        # Add skill-based prerequisites
        if self.primary_skill and self.primary_skill.skill_level != SkillLevel.BASIC:
            # Require basic level of same skill type
            basic_skill_name = f"{self.primary_skill.skill_type.value}:basic"
            prerequisites.add(basic_skill_name)
        
        return prerequisites
    
    def is_suitable_for_skill_level(self, target_skill_level: SkillLevel) -> bool:
        """
        Business rule: Check if repository is suitable for target skill level
        """
        if not self.primary_skill:
            return target_skill_level == SkillLevel.BASIC
        
        # Repository should match or be slightly above target level
        skill_gap = abs(
            [SkillLevel.BASIC, SkillLevel.INTERMEDIATE, SkillLevel.ADVANCED, SkillLevel.EXPERT].index(self.primary_skill.skill_level) -
            [SkillLevel.BASIC, SkillLevel.INTERMEDIATE, SkillLevel.ADVANCED, SkillLevel.EXPERT].index(target_skill_level)
        )
        
        return skill_gap <= 1  # Allow one level difference
    
    def get_recommended_learning_order(self) -> int:
        """
        Business logic: Get recommended learning order (lower = earlier)
        """
        order = 0
        
        # Skill level priority (basic first)
        if self.primary_skill:
            skill_order = {
                SkillLevel.BASIC: 1,
                SkillLevel.INTERMEDIATE: 3,
                SkillLevel.ADVANCED: 5,
                SkillLevel.EXPERT: 7
            }
            order += skill_order[self.primary_skill.skill_level]
        
        # Complexity priority (simpler first)
        order += int(self.complexity_score)
        
        # Topic dependency priority (fewer prerequisites first)
        prerequisite_count = sum(len(topic.parent_topics) for topic in self.topics)
        order += prerequisite_count
        
        return order
    
    def __eq__(self, other) -> bool:
        """Repositories are equal if they have the same path"""
        if not isinstance(other, Repository):
            return False
        return self.path == other.path
    
    def __hash__(self) -> int:
        """Hash based on repository path"""
        return hash(self.path)
    
    def __str__(self) -> str:
        skill_str = f", skill={self.primary_skill}" if self.primary_skill else ""
        return f"Repository({self.name}, lang={self.primary_language}{skill_str})"
