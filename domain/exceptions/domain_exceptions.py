"""
Domain Exceptions - Clean Architecture Domain Layer

Defines all exceptions that can be raised by domain entities.
These exceptions encode business rule violations and data invariant failures.
The domain layer raises ONLY these exceptions — never HTTPException or stdlib exceptions.
"""
from typing import List, Optional


class DomainError(Exception):
    """Base class for all domain exceptions.

    Why a custom base: allows API layer to catch all domain errors in one
    handler and map them to appropriate HTTP status codes without importing
    individual exception types.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return self.message


class ValidationError(DomainError):
    """Raised when entity field-level validation fails.

    Example:
        raise ValidationError("name", "Repository name cannot be empty")

    Maps to HTTP 422 Unprocessable Entity.
    """

    def __init__(self, field: str, message: str) -> None:
        self.field = field
        self.message = message
        super().__init__(f"Validation failed for '{field}': {message}")


class BusinessRuleViolation(DomainError):
    """Raised when a business rule or aggregate invariant is violated.

    Example:
        raise BusinessRuleViolation("Cannot remove node — it is a prerequisite for 3 others")

    Maps to HTTP 409 Conflict or HTTP 422 depending on context.
    """

    def __init__(self, message: str, rule: Optional[str] = None) -> None:
        self.rule = rule
        super().__init__(message)


class CircularDependencyError(DomainError):
    """Raised when a circular dependency is detected in the learning path.

    Args:
        cycle: Ordered list of node/repository IDs (as strings) forming the cycle.

    Example:
        raise CircularDependencyError(["node-a", "node-b", "node-c", "node-a"])

    Maps to HTTP 409 Conflict.
    """

    def __init__(self, cycle: List[str]) -> None:
        self.cycle = cycle
        cycle_repr = " → ".join(cycle)
        super().__init__(f"Circular dependency detected: {cycle_repr}")


class InvalidLearningSequenceError(DomainError):
    """Raised when a learning path sequence violates ordering invariants.

    Use when nodes cannot be legally ordered (e.g., all nodes are mutually
    dependent and topological sort is impossible even after cycle resolution).

    Maps to HTTP 422 Unprocessable Entity.
    """

    def __init__(self, message: str, affected_nodes: Optional[List[str]] = None) -> None:
        self.affected_nodes = affected_nodes or []
        super().__init__(message)


class EntityNotFoundError(DomainError):
    """Raised when a referenced entity does not exist.

    Example:
        raise EntityNotFoundError("LearningPath", str(path_id))

    Maps to HTTP 404 Not Found.
    """

    def __init__(self, entity_type: str, identifier: str) -> None:
        self.entity_type = entity_type
        self.identifier = identifier
        super().__init__(f"{entity_type} with identifier '{identifier}' not found")


class DuplicateEntityError(DomainError):
    """Raised when an entity already exists and duplicates are not allowed.

    Example:
        raise DuplicateEntityError("Repository", repo.path)

    Maps to HTTP 409 Conflict.
    """

    def __init__(self, entity_type: str, identifier: str) -> None:
        self.entity_type = entity_type
        self.identifier = identifier
        super().__init__(f"{entity_type} '{identifier}' already exists")
