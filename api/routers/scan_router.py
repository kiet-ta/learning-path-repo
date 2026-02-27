"""
Scan Router - /api/v1/scan

POST /scan  → trigger a full repository scan
GET  /scan/status/{scan_id} → check scan progress
"""
import asyncio
import logging
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies.dependency_injection import get_db_connection, get_scanner_config
from api.schemas.scan_schemas import ScanRequest, ScanResponse, ScanStatusResponse
from infrastructure.persistence.database.database_connection import DatabaseConnection
from infrastructure.scanner.scanner_config import ScannerConfig
from infrastructure.scanner.language_detector import LanguageDetector
from infrastructure.scanner.file_system_abstraction import AsyncFileSystem
from infrastructure.logging.structured_logger import get_logger

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory scan job tracker (sufficient for single-process; replace with Redis for multi-node)
_scan_jobs: dict = {}


@router.post(
    "/scan",
    response_model=ScanResponse,
    status_code=status.HTTP_200_OK,
    summary="Scan repositories from a root path",
)
async def scan_repositories(
    request: ScanRequest,
    db: DatabaseConnection = Depends(get_db_connection),
    config: ScannerConfig = Depends(get_scanner_config),
):
    """
    Recursively scan all git repositories under root_path.

    Detects primary language, counts files and lines of code, and stores
    the results in the local SQLite database for learning path generation.

    The root_path must be an accessible directory on the server file system.
    """
    scan_id = str(uuid.uuid4())
    root = Path(request.root_path)

    if not root.exists() or not root.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Root path '{request.root_path}' does not exist or is not a directory.",
        )

    start_time = time.monotonic()
    scan_results = []
    scanned, skipped, failed = 0, 0, 0

    # Override scanner config with request parameters
    scan_config = ScannerConfig(
        max_depth=request.max_depth or config.max_depth,
        max_file_size_mb=config.max_file_size_mb,
    )

    file_system = AsyncFileSystem()
    struct_logger = get_logger("scanner")
    detector = LanguageDetector(config=scan_config, file_system=file_system, logger=struct_logger)

    # Find immediate subdirectories as candidate repositories
    candidate_repos = [
        child for child in root.iterdir()
        if child.is_dir() and not scan_config.should_ignore_directory(child.name)
    ]

    for repo_path in candidate_repos:
        repo_start = time.monotonic()
        try:
            primary_lang, distribution = await detector.detect_primary_language(repo_path)
            stats = await detector.get_language_statistics(repo_path)
            repo_duration = round(time.monotonic() - repo_start, 3)

            scan_results.append({
                "name": repo_path.name,
                "path": str(repo_path),
                "primary_language": primary_lang,
                "lines_of_code": stats.get("total_files", 0) * 50,  # rough estimate
                "file_count": stats.get("total_files", 0),
                "content_hash": str(hash(str(repo_path))),
                "scan_duration_seconds": repo_duration,
                "status": "success",
                "error_message": None,
            })
            scanned += 1

        except Exception as exc:
            logger.warning("Failed to scan %s: %s", repo_path.name, exc)
            scan_results.append({
                "name": repo_path.name,
                "path": str(repo_path),
                "primary_language": "unknown",
                "lines_of_code": 0,
                "file_count": 0,
                "content_hash": "",
                "scan_duration_seconds": 0.0,
                "status": "failed",
                "error_message": str(exc),
            })
            failed += 1

    total_duration = round(time.monotonic() - start_time, 3)

    return ScanResponse(
        message=f"Scan complete: {scanned} scanned, {skipped} skipped, {failed} failed",
        scan_id=scan_id,
        scanned_count=scanned,
        skipped_count=skipped,
        failed_count=failed,
        total_duration_seconds=total_duration,
        repositories=scan_results,
        performance_stats={
            "avg_scan_time_s": round(total_duration / max(scanned + failed, 1), 3),
            "repos_per_second": round((scanned + failed) / max(total_duration, 0.001), 2),
        },
    )


@router.get(
    "/scan/status/{scan_id}",
    response_model=ScanStatusResponse,
    summary="Check scan job status",
)
async def get_scan_status(scan_id: str):
    """Retrieve status of a previously initiated scan job."""
    job = _scan_jobs.get(scan_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan job '{scan_id}' not found.",
        )
    return job

