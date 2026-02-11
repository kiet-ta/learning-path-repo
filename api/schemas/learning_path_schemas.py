"""
Learning Path Schemas - API Layer
Pydantic models for learning path endpoints
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum

from .error_schemas import SuccessResponse
from .repository_schemas import SkillTypeEnum, SkillLevelEnum


class MilestoneEnum(str, Enum):
    """Learning milestone enumeration"""
    FOUNDATIONS = "foundations"
    CORE_SKILLS = "core_skills"
    ADVANCED_SYSTEMS = "advanced_systems"
    SPECIALIZED_TOPICS = "specialized_topics"


class GenerateLearningPathRequest(BaseModel):
    """Request model for generating learning path"""
    learner_id: str = Field(..., description="Learner identifier")
    name: str = Field(..., description="Learning path name")
    description: Optional[str] = Field(None, description="Learning path description")
    target_skill_types: Optional[List[SkillTypeEnum]] = Field(None, description="Target skill types to focus on")
    target_skill_level: Optional[SkillLevelEnum] = Field(None, description="Target skill level")
    max_repositories: Optional[int] = Field(None, ge=1, le=500, description="Maximum repositories in path")
    allow_parallel_learning: bool = Field(default=False, description="Allow parallel learning of repositories")
    max_parallel_nodes: int = Field(default=3, ge=1, le=10, description="Maximum parallel repositories")
    exclude_repository_ids: Optional[List[str]] = Field(None, description="Repository IDs to exclude")
    
    @validator('name')
    def validate_name(cls, v):
        """Validate learning path name"""
        if not v or not v.strip():
            raise ValueError("Learning path name cannot be empty")
        if len(v) > 100:
            raise ValueError("Learning path name cannot exceed 100 characters")
        return v.strip()


class LearningNodeResponse(BaseModel):
    """Learning path node response"""
    repository_id: str = Field(..., description="Repository ID")
    repository_name: str = Field(..., description="Repository name")
    order_index: int = Field(..., description="Order in learning path")
    milestone: MilestoneEnum = Field(..., description="Learning milestone")
    estimated_hours: int = Field(..., description="Estimated learning hours")
    skill_type: Optional[SkillTypeEnum] = Field(None, description="Primary skill type")
    skill_level: Optional[SkillLevelEnum] = Field(None, description="Skill level")
    complexity_score: float = Field(..., description="Complexity score")
    prerequisites: List[str] = Field(..., description="Prerequisite repository IDs")
    is_overridden: bool = Field(default=False, description="Whether manually overridden")
    override_reason: Optional[str] = Field(None, description="Override reason")


class MilestoneGroupResponse(BaseModel):
    """Milestone group response"""
    milestone: MilestoneEnum = Field(..., description="Milestone name")
    description: str = Field(..., description="Milestone description")
    estimated_hours: int = Field(..., description="Total estimated hours for milestone")
    repository_count: int = Field(..., description="Number of repositories in milestone")
    repositories: List[LearningNodeResponse] = Field(..., description="Repositories in milestone")


class LearningPathResponse(BaseModel):
    """Learning path response model"""
    id: int = Field(..., description="Learning path ID")
    version: int = Field(..., description="Learning path version")
    learner_id: str = Field(..., description="Learner identifier")
    name: str = Field(..., description="Learning path name")
    description: Optional[str] = Field(None, description="Learning path description")
    status: str = Field(..., description="Learning path status")
    total_estimated_hours: int = Field(..., description="Total estimated learning hours")
    total_repositories: int = Field(..., description="Total number of repositories")
    milestones: List[MilestoneGroupResponse] = Field(..., description="Learning milestones")
    generated_at: datetime = Field(..., description="Generation timestamp")
    last_optimized_at: Optional[datetime] = Field(None, description="Last optimization timestamp")


class GenerateLearningPathResponse(SuccessResponse):
    """Response model for learning path generation"""
    learning_path: LearningPathResponse = Field(..., description="Generated learning path")
    generation_stats: Dict[str, any] = Field(..., description="Generation statistics")
    warnings: List[str] = Field(default=[], description="Generation warnings")


class LearningPathListRequest(BaseModel):
    """Request model for listing learning paths"""
    learner_id: Optional[str] = Field(None, description="Filter by learner ID")
    status: Optional[str] = Field(None, description="Filter by status")
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")


class LearningPathSummaryResponse(BaseModel):
    """Learning path summary response"""
    id: int = Field(..., description="Learning path ID")
    version: int = Field(..., description="Learning path version")
    learner_id: str = Field(..., description="Learner identifier")
    name: str = Field(..., description="Learning path name")
    status: str = Field(..., description="Learning path status")
    total_estimated_hours: int = Field(..., description="Total estimated hours")
    total_repositories: int = Field(..., description="Total repositories")
    completion_percentage: float = Field(..., description="Completion percentage")
    generated_at: datetime = Field(..., description="Generation timestamp")


class OptimizeLearningPathRequest(BaseModel):
    """Request model for optimizing learning path"""
    learning_path_id: int = Field(..., description="Learning path ID to optimize")
    optimization_goals: Optional[List[str]] = Field(None, description="Optimization goals")
    preserve_overrides: bool = Field(default=True, description="Preserve manual overrides")


class LearningPathStatsResponse(BaseModel):
    """Learning path statistics response"""
    total_paths: int = Field(..., description="Total number of learning paths")
    active_paths: int = Field(..., description="Number of active paths")
    completed_paths: int = Field(..., description="Number of completed paths")
    average_completion_time: Optional[float] = Field(None, description="Average completion time in hours")
    most_common_skill_types: Dict[str, int] = Field(..., description="Most common skill types")
    average_path_length: float = Field(..., description="Average number of repositories per path")
