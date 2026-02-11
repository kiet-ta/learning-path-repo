"""
Error Schemas - API Layer
Pydantic models for structured error responses
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class ErrorResponse(BaseModel):
    """Standard error response model"""
    error_code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[str] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.now, description="Error timestamp")
    request_id: Optional[str] = Field(None, description="Request tracking ID")


class ValidationErrorDetail(BaseModel):
    """Validation error detail"""
    field: str = Field(..., description="Field that failed validation")
    message: str = Field(..., description="Validation error message")
    value: Optional[Any] = Field(None, description="Invalid value")


class ValidationErrorResponse(ErrorResponse):
    """Validation error response with field details"""
    error_code: str = Field(default="VALIDATION_ERROR")
    validation_errors: list[ValidationErrorDetail] = Field(..., description="Field validation errors")


class BusinessRuleErrorResponse(ErrorResponse):
    """Business rule violation error"""
    error_code: str = Field(default="BUSINESS_RULE_VIOLATION")
    rule_name: Optional[str] = Field(None, description="Name of violated business rule")


class NotFoundErrorResponse(ErrorResponse):
    """Resource not found error"""
    error_code: str = Field(default="RESOURCE_NOT_FOUND")
    resource_type: Optional[str] = Field(None, description="Type of resource not found")
    resource_id: Optional[str] = Field(None, description="ID of resource not found")


class ConflictErrorResponse(ErrorResponse):
    """Resource conflict error"""
    error_code: str = Field(default="RESOURCE_CONFLICT")
    conflicting_resource: Optional[str] = Field(None, description="Conflicting resource identifier")


class InternalServerErrorResponse(ErrorResponse):
    """Internal server error"""
    error_code: str = Field(default="INTERNAL_SERVER_ERROR")
    correlation_id: Optional[str] = Field(None, description="Error correlation ID for debugging")


# Success response wrapper
class SuccessResponse(BaseModel):
    """Standard success response wrapper"""
    success: bool = Field(default=True, description="Operation success indicator")
    message: Optional[str] = Field(None, description="Success message")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")


class PaginatedResponse(BaseModel):
    """Paginated response wrapper"""
    total_count: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there are more pages")
    has_previous: bool = Field(..., description="Whether there are previous pages")
