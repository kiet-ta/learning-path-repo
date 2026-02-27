"""
Repository Schemas - API Layer
Pydantic models for repository-related endpoints
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

from .error_schemas import PaginatedResponse


class SkillTypeEnum(str, Enum):
    """Skill type enumeration"""
    FRONTEND = "frontend"
    BACKEND = "backend"
    DATA_SCIENCE = "data_science"
    INFRASTRUCTURE = "infrastructure"
    MOBILE = "mobile"
    DEVOPS = "devops"
    MACHINE_LEARNING = "machine_learning"
    SECURITY = "security"


class SkillLevelEnum(str, Enum):
    """Skill level enumeration"""
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class TopicResponse(BaseModel):
    """Topic response model"""
    name: str = Field(..., description="Topic name")
    category: str = Field(..., description="Topic category")
    relevance_score: float = Field(..., description="Relevance score for this repository")


class RepositoryResponse(BaseModel):
    """Repository response model"""
    id: str = Field(..., description="Repository ID")
    name: str = Field(..., description="Repository name")
    path: str = Field(..., description="Repository path")
    primary_language: str = Field(..., description="Primary programming language")
    description: Optional[str] = Field(None, description="Repository description")
    skill_type: Optional[SkillTypeEnum] = Field(None, description="Primary skill type")
    skill_level: Optional[SkillLevelEnum] = Field(None, description="Skill level")
    complexity_score: float = Field(..., description="Complexity score (0-10)")
    estimated_hours: int = Field(..., description="Estimated learning hours")
    lines_of_code: int = Field(..., description="Total lines of code")
    file_count: int = Field(..., description="Number of files")
    topics: List[TopicResponse] = Field(..., description="Associated topics")
    last_analyzed_at: Optional[datetime] = Field(None, description="Last analysis timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")


class RepositoryListRequest(BaseModel):
    """Request model for listing repositories"""
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")
    skill_type: Optional[SkillTypeEnum] = Field(None, description="Filter by skill type")
    skill_level: Optional[SkillLevelEnum] = Field(None, description="Filter by skill level")
    language: Optional[str] = Field(None, description="Filter by programming language")
    search: Optional[str] = Field(None, description="Search in name and description")
    sort_by: str = Field(default="name", description="Sort field")
    sort_order: str = Field(default="asc", description="Sort order: asc, desc")
    
    @validator('sort_by')
    def validate_sort_by(cls, v):
        """Validate sort field"""
        allowed_fields = [
            'name', 'primary_language', 'skill_type', 'skill_level',
            'complexity_score', 'estimated_hours', 'lines_of_code',
            'last_analyzed_at', 'created_at'
        ]
        if v not in allowed_fields:
            raise ValueError(f"Sort field must be one of: {allowed_fields}")
        return v
    
    @validator('sort_order')
    def validate_sort_order(cls, v):
        """Validate sort order"""
        if v.lower() not in ['asc', 'desc']:
            raise ValueError("Sort order must be 'asc' or 'desc'")
        return v.lower()


class RepositoryListResponse(PaginatedResponse):
    """Response model for repository listing"""
    repositories: List[RepositoryResponse] = Field(..., description="List of repositories")
    filters_applied: Dict[str, Any] = Field(..., description="Applied filters")


class RepositoryDetailResponse(RepositoryResponse):
    """Detailed repository response model"""
    content_hash: str = Field(..., description="Content hash for change detection")
    dependencies: List[str] = Field(..., description="Repository dependencies")
    frameworks: List[str] = Field(..., description="Detected frameworks")
    has_readme: bool = Field(..., description="Whether repository has README")
    has_docs: bool = Field(..., description="Whether repository has documentation")
    documentation_coverage: float = Field(..., description="Documentation coverage score")
    test_coverage: float = Field(..., description="Test coverage score")
    has_tests: bool = Field(..., description="Whether repository has tests")
    has_ci_cd: bool = Field(..., description="Whether repository has CI/CD")


class RepositoryStatsResponse(BaseModel):
    """Repository statistics response"""
    total_repositories: int = Field(..., description="Total number of repositories")
    by_skill_type: Dict[str, int] = Field(..., description="Count by skill type")
    by_skill_level: Dict[str, int] = Field(..., description="Count by skill level")
    by_language: Dict[str, int] = Field(..., description="Count by programming language")
    average_complexity: float = Field(..., description="Average complexity score")
    total_estimated_hours: int = Field(..., description="Total estimated learning hours")
    last_scan_at: Optional[datetime] = Field(None, description="Last scan timestamp")
    stale_repositories: int = Field(..., description="Number of repositories needing re-analysis")
