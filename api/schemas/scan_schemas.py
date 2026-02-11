"""
Scan Schemas - API Layer
Pydantic models for repository scanning endpoints
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict
from datetime import datetime
from pathlib import Path

from .error_schemas import SuccessResponse


class ScanRequest(BaseModel):
    """Request model for repository scanning"""
    root_path: str = Field(..., description="Root directory path to scan for repositories")
    force_rescan: bool = Field(default=False, description="Force rescan even if content hash unchanged")
    include_patterns: Optional[List[str]] = Field(None, description="Patterns to include (glob format)")
    exclude_patterns: Optional[List[str]] = Field(None, description="Patterns to exclude (glob format)")
    max_depth: Optional[int] = Field(default=5, description="Maximum directory depth to scan")
    
    @validator('root_path')
    def validate_root_path(cls, v):
        """Validate root path exists and is accessible"""
        path = Path(v)
        if not path.exists():
            raise ValueError(f"Root path does not exist: {v}")
        if not path.is_dir():
            raise ValueError(f"Root path is not a directory: {v}")
        return str(path.absolute())
    
    @validator('max_depth')
    def validate_max_depth(cls, v):
        """Validate max depth is reasonable"""
        if v is not None and (v < 1 or v > 20):
            raise ValueError("Max depth must be between 1 and 20")
        return v


class RepositoryScanResult(BaseModel):
    """Individual repository scan result"""
    name: str = Field(..., description="Repository name")
    path: str = Field(..., description="Repository path")
    primary_language: str = Field(..., description="Primary programming language")
    lines_of_code: int = Field(..., description="Total lines of code")
    file_count: int = Field(..., description="Number of files")
    content_hash: str = Field(..., description="Content hash for change detection")
    scan_duration_seconds: float = Field(..., description="Time taken to scan this repository")
    status: str = Field(..., description="Scan status: success, failed, skipped")
    error_message: Optional[str] = Field(None, description="Error message if scan failed")


class ScanResponse(SuccessResponse):
    """Response model for repository scanning"""
    scan_id: str = Field(..., description="Unique scan operation ID")
    scanned_count: int = Field(..., description="Number of repositories successfully scanned")
    skipped_count: int = Field(..., description="Number of repositories skipped (unchanged)")
    failed_count: int = Field(..., description="Number of repositories that failed to scan")
    total_duration_seconds: float = Field(..., description="Total scan duration")
    repositories: List[RepositoryScanResult] = Field(..., description="Detailed scan results")
    performance_stats: Dict[str, float] = Field(..., description="Performance statistics")


class ScanStatusRequest(BaseModel):
    """Request model for checking scan status"""
    scan_id: str = Field(..., description="Scan operation ID to check")


class ScanStatusResponse(BaseModel):
    """Response model for scan status"""
    scan_id: str = Field(..., description="Scan operation ID")
    status: str = Field(..., description="Scan status: running, completed, failed")
    progress_percentage: float = Field(..., description="Scan progress (0-100)")
    current_repository: Optional[str] = Field(None, description="Currently scanning repository")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")
    repositories_processed: int = Field(..., description="Number of repositories processed")
    total_repositories: int = Field(..., description="Total repositories to scan")
