"""
Error Handler - API Layer

Maps domain exceptions and Pydantic validation errors to structured JSON
HTTP responses.  Centralised here so individual routers never need try/except
for domain exceptions.

HTTP status mapping:
  ValidationError          → 422 Unprocessable Entity
  BusinessRuleViolation    → 409 Conflict
  CircularDependencyError  → 409 Conflict
  InvalidLearningSequence  → 422 Unprocessable Entity
  EntityNotFoundError      → 404 Not Found
  DuplicateEntityError     → 409 Conflict
  RequestValidationError   → 422 Unprocessable Entity
  Unhandled Exception      → 500 Internal Server Error
"""
import logging
import traceback
import uuid
from datetime import datetime

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from domain.exceptions.domain_exceptions import (
    BusinessRuleViolation,
    CircularDependencyError,
    DomainError,
    DuplicateEntityError,
    EntityNotFoundError,
    InvalidLearningSequenceError,
    ValidationError,
)

logger = logging.getLogger(__name__)


def _error_body(
    error_code: str,
    message: str,
    details: str | None = None,
    request_id: str | None = None,
    **extra,
) -> dict:
    payload = {
        "error_code": error_code,
        "message": message,
        "timestamp": datetime.now().isoformat(),
        "request_id": request_id,
    }
    if details:
        payload["details"] = details
    payload.update(extra)
    return payload


def add_error_handlers(app: FastAPI) -> None:
    """Register all domain and system exception handlers on the app."""

    # ------------------------------------------------------------------ #
    # 1. Pydantic / FastAPI request validation errors
    # ------------------------------------------------------------------ #

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(request: Request, exc: RequestValidationError):
        errors = [
            {
                "field": ".".join(str(loc) for loc in err["loc"]),
                "message": err["msg"],
                "type": err["type"],
            }
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_body(
                error_code="VALIDATION_ERROR",
                message="Request validation failed",
                details=f"{len(errors)} field(s) failed validation",
                validation_errors=errors,
            ),
        )

    # ------------------------------------------------------------------ #
    # 2. Domain exceptions (specific → general order)
    # ------------------------------------------------------------------ #

    @app.exception_handler(ValidationError)
    async def domain_validation_handler(request: Request, exc: ValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_body(
                error_code="DOMAIN_VALIDATION_ERROR",
                message=exc.message,
                details=f"Field: {exc.field}",
            ),
        )

    @app.exception_handler(EntityNotFoundError)
    async def not_found_handler(request: Request, exc: EntityNotFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=_error_body(
                error_code="RESOURCE_NOT_FOUND",
                message=str(exc),
                resource_type=exc.entity_type,
                resource_id=exc.identifier,
            ),
        )

    @app.exception_handler(DuplicateEntityError)
    async def duplicate_handler(request: Request, exc: DuplicateEntityError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=_error_body(
                error_code="RESOURCE_CONFLICT",
                message=str(exc),
                conflicting_resource=exc.identifier,
            ),
        )

    @app.exception_handler(CircularDependencyError)
    async def circular_dep_handler(request: Request, exc: CircularDependencyError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=_error_body(
                error_code="CIRCULAR_DEPENDENCY",
                message=str(exc),
                cycle=exc.cycle,
            ),
        )

    @app.exception_handler(InvalidLearningSequenceError)
    async def invalid_sequence_handler(request: Request, exc: InvalidLearningSequenceError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_body(
                error_code="INVALID_LEARNING_SEQUENCE",
                message=str(exc),
                affected_nodes=exc.affected_nodes,
            ),
        )

    @app.exception_handler(BusinessRuleViolation)
    async def business_rule_handler(request: Request, exc: BusinessRuleViolation):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=_error_body(
                error_code="BUSINESS_RULE_VIOLATION",
                message=exc.message,
                rule=exc.rule,
            ),
        )

    # Catch-all for any remaining DomainError subclasses
    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_body(
                error_code="DOMAIN_ERROR",
                message=exc.message,
            ),
        )

    # ------------------------------------------------------------------ #
    # 3. Unhandled exceptions → 500
    # ------------------------------------------------------------------ #

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        correlation_id = str(uuid.uuid4())
        logger.error(
            "Unhandled exception [%s]: %s\n%s",
            correlation_id, exc, traceback.format_exc(),
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body(
                error_code="INTERNAL_SERVER_ERROR",
                message="An unexpected error occurred. Please try again or contact support.",
                correlation_id=correlation_id,
            ),
        )

