"""Health Router - GET /api/v1/health and /api/v1/health/db"""
import os

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.dependencies.dependency_injection import get_db_connection
from infrastructure.persistence.database.database_connection import DatabaseConnection

router = APIRouter()


@router.get("/health", summary="API health check")
async def health():
    """Returns API version and status. Used by load-balancer probes."""
    return {"status": "healthy", "version": "1.0.0", "service": "learning-path-api"}


@router.get("/health/db", summary="Database connectivity check")
async def health_db(db: DatabaseConnection = Depends(get_db_connection)):
    """Verifies database connectivity and returns table statistics."""
    try:
        stats = db.get_database_stats()
        return {"status": "healthy", "database": "connected", "stats": stats}
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "database": "unreachable", "error": str(exc)},
        )

