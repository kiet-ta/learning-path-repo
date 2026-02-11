"""
FastAPI Application - API Layer
Main application entry point with dependency injection
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from .routers import (
    scan_router, analyze_router, learning_path_router,
    repository_router, progress_router, override_router, health_router
)
from .middleware.error_handler import add_error_handlers
from .middleware.logging_middleware import LoggingMiddleware
from .middleware.performance_middleware import PerformanceMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Create FastAPI application
app = FastAPI(
    title="Auto Learning Path Generator API",
    description="API for generating personalized learning paths from repository analysis",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add custom middleware
app.add_middleware(PerformanceMiddleware)
app.add_middleware(LoggingMiddleware)

# Add error handlers
add_error_handlers(app)

# Include routers
app.include_router(health_router.router, prefix="/api/v1", tags=["Health"])
app.include_router(scan_router.router, prefix="/api/v1", tags=["Scan"])
app.include_router(analyze_router.router, prefix="/api/v1", tags=["Analyze"])
app.include_router(learning_path_router.router, prefix="/api/v1", tags=["Learning Path"])
app.include_router(repository_router.router, prefix="/api/v1", tags=["Repositories"])
app.include_router(progress_router.router, prefix="/api/v1", tags=["Progress"])
app.include_router(override_router.router, prefix="/api/v1", tags=["Overrides"])

@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    logging.info("Starting Auto Learning Path Generator API")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logging.info("Shutting down Auto Learning Path Generator API")
