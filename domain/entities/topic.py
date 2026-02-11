"""
Topic Entity - Clean Architecture Domain Layer
Represents learning topics with hierarchical relationships and business rules
"""
from dataclasses import dataclass, field
from typing import Set, List, Optional
from uuid import uuid4, UUID
from ..exceptions.domain_exceptions import ValidationError, BusinessRuleViolation


@dataclass
class Topic:
    """
    Entity representing a learning topic
    Contains business logic for topic relationships and categorization
    """
    name: str
    description: str
    category: str
    keywords: Set[str] = field(default_factory=set)
    parent_topics: Set[str] = field(default_factory=set)  # Topic names that are prerequisites
    child_topics: Set[str] = field(default_factory=set)   # Topic names that depend on this
    difficulty_weight: float = 1.0  # Multiplier for learning difficulty
    topic_id: UUID = field(default_factory=uuid4)
    
    def __post_init__(self):
        """Validate topic invariants"""
        self._validate_name()
        self._validate_difficulty_weight()
        self._validate_category()
    
    def _validate_name(self):
        """Business rule: Topic name must be non-empty and unique"""
        if not self.name or not self.name.strip():
            raise ValidationError("name", "Topic name cannot be empty")
        
        if len(self.name) > 100:
            raise ValidationError("name", "Topic name cannot exceed 100 characters")
    
    def _validate_difficulty_weight(self):
        """Business rule: Difficulty weight must be positive"""
        if self.difficulty_weight <= 0:
            raise ValidationError("difficulty_weight", "Difficulty weight must be positive")
        
        if self.difficulty_weight > 5.0:
            raise ValidationError("difficulty_weight", "Difficulty weight cannot exceed 5.0")
    
    def _validate_category(self):
        """Business rule: Category must be valid"""
        valid_categories = {
            "programming_language", "framework", "library", "tool", 
            "concept", "methodology", "platform", "database", "architecture"
        }
        
        if self.category not in valid_categories:
            raise ValidationError("category", f"Category must be one of: {valid_categories}")
    
    def add_keyword(self, keyword: str) -> None:
        """Add a keyword to this topic"""
        if not keyword or not keyword.strip():
            raise ValidationError("keyword", "Keyword cannot be empty")
        
        self.keywords.add(keyword.strip().lower())
    
    def add_parent_topic(self, parent_topic_name: str) -> None:
        """
        Business rule: Add a parent topic (prerequisite)
        Prevents self-reference and validates hierarchy
        """
        if parent_topic_name == self.name:
            raise BusinessRuleViolation("Topic cannot be its own parent")
        
        if parent_topic_name in self.child_topics:
            raise BusinessRuleViolation(f"Cannot add {parent_topic_name} as parent - would create cycle")
        
        self.parent_topics.add(parent_topic_name)
    
    def add_child_topic(self, child_topic_name: str) -> None:
        """
        Business rule: Add a child topic (dependent topic)
        Prevents self-reference and validates hierarchy
        """
        if child_topic_name == self.name:
            raise BusinessRuleViolation("Topic cannot be its own child")
        
        if child_topic_name in self.parent_topics:
            raise BusinessRuleViolation(f"Cannot add {child_topic_name} as child - would create cycle")
        
        self.child_topics.add(child_topic_name)
    
    def is_prerequisite_for(self, other_topic: 'Topic') -> bool:
        """Check if this topic is a prerequisite for another topic"""
        return self.name in other_topic.parent_topics
    
    def has_prerequisite(self, prerequisite_topic: 'Topic') -> bool:
        """Check if this topic has a specific prerequisite"""
        return prerequisite_topic.name in self.parent_topics
    
    def get_learning_complexity(self) -> float:
        """
        Business logic: Calculate learning complexity based on topic characteristics
        """
        base_complexity = 1.0
        
        # More prerequisites increase complexity
        prerequisite_factor = 1 + (len(self.parent_topics) * 0.2)
        
        # Category-based complexity
        category_weights = {
            "programming_language": 1.5,
            "framework": 1.3,
            "library": 1.0,
            "tool": 0.8,
            "concept": 1.2,
            "methodology": 1.4,
            "platform": 1.1,
            "database": 1.2,
            "architecture": 1.6
        }
        
        category_factor = category_weights.get(self.category, 1.0)
        
        return base_complexity * prerequisite_factor * category_factor * self.difficulty_weight
    
    def can_be_learned_after(self, completed_topics: Set[str]) -> bool:
        """
        Business rule: Check if topic can be learned given completed topics
        All parent topics must be completed
        """
        return self.parent_topics.issubset(completed_topics)
    
    def get_missing_prerequisites(self, completed_topics: Set[str]) -> Set[str]:
        """Get list of missing prerequisite topics"""
        return self.parent_topics - completed_topics
    
    def matches_keyword(self, search_term: str) -> bool:
        """Check if topic matches a search term"""
        search_lower = search_term.lower()
        
        # Check name
        if search_lower in self.name.lower():
            return True
        
        # Check keywords
        return any(search_lower in keyword for keyword in self.keywords)
    
    def __eq__(self, other) -> bool:
        """Topics are equal if they have the same name"""
        if not isinstance(other, Topic):
            return False
        return self.name == other.name
    
    def __hash__(self) -> int:
        """Hash based on topic name for set operations"""
        return hash(self.name)
    
    def __str__(self) -> str:
        return f"Topic({self.name}, category={self.category})"
