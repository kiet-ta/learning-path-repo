"""
Dependency Injection - API Layer

Provides FastAPI dependency functions that create and cache infrastructure
and application layer objects. Uses Python's lru_cache for singletons.

Pattern: each get_*() function is a FastAPI dependency (callable that
FastAPI calls per-request or once at startup via lru_cache).

All paths come from environment variables with safe defaults so the app
can start with zero configuration for local development.
"""
import os
from functools import lru_cache
from pathlib import Path

from infrastructure.persistence.database.database_connection import DatabaseConnection
from infrastructure.scanner.scanner_config import ScannerConfig
from infrastructure.logging.structured_logger import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def get_db_connection() -> DatabaseConnection:
    """
    Singleton DatabaseConnection instance.

    Reads DATABASE_URL env var — expects format: sqlite:///path/to/file.db
    Falls back to ./data/learning_path.db for local dev.
    """
    database_url = os.getenv("DATABASE_URL", "sqlite:///data/learning_path.db")

    # Parse sqlite:///path/to/file.db  →  path/to/file.db
    if database_url.startswith("sqlite:///"):
        db_path_str = database_url[len("sqlite:///"):]
    elif database_url.startswith("sqlite://"):
        db_path_str = database_url[len("sqlite://"):]
    else:
        db_path_str = database_url

    db_path = Path(db_path_str)
    logger.info("Initialising database connection", db_path=str(db_path.absolute()))
    return DatabaseConnection(db_path=db_path)


@lru_cache(maxsize=1)
def get_scanner_config() -> ScannerConfig:
    """
    Singleton ScannerConfig with environment-driven overrides.
    """
    max_depth = int(os.getenv("SCANNER_MAX_DEPTH", "10"))
    max_file_mb = float(os.getenv("SCANNER_MAX_FILE_SIZE_MB", "10.0"))
    return ScannerConfig(max_depth=max_depth, max_file_size_mb=max_file_mb)


# ---------------------------------------------------------------------------
# Repository store factories (lazy imports to avoid circular deps)
# ---------------------------------------------------------------------------

def get_repository_store():
    """FastAPI dependency: returns a SqliteRepositoryMetadataRepository."""
    from infrastructure.persistence.repositories.sqlite_repository_metadata_repository import (
        SqliteRepositoryMetadataRepository,
    )
    return SqliteRepositoryMetadataRepository(db=get_db_connection())


def get_learning_path_store():
    """FastAPI dependency: returns a SqliteLearningPathRepository."""
    from infrastructure.persistence.repositories.sqlite_learning_path_repository import (
        SqliteLearningPathRepository,
    )
    return SqliteLearningPathRepository(db=get_db_connection())


def get_override_store():
    """FastAPI dependency: returns an override repository (stub for now)."""

    class _NoOpOverrideStore:
        """In-memory stub until SqliteOverrideRepository is implemented."""
        def get_by_learner(self, learner_id: str):
            return []

    return _NoOpOverrideStore()

