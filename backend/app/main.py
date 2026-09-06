"""Main FastAPI application entrypoint with lifespan events, routes, and health check endpoints."""

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict

from fastapi import FastAPI, Response, status
from fastapi.responses import JSONResponse

from app.api.auth import router as auth_router
from app.api.courses import router as public_courses_router
from app.api.dev import router as dev_router
from app.api.dev_courses import router as dev_courses_router
from app.api.dev_materials import router as dev_materials_router
from app.config import get_settings
from app.database import check_mongo_connection, db_manager

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("hots-backend")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager to handle startup and shutdown events."""
    logger.info("Starting up HOTS RAG Backend...")
    # Initialize MongoDB client connection
    db_manager.connect()

    # Check initial database connectivity (non-blocking warning if unreachable)
    is_connected, error_msg = check_mongo_connection()
    if is_connected:
        logger.info("Initial MongoDB connection verified successfully.")
    else:
        logger.warning(f"MongoDB not reachable at startup: {error_msg}. (Will retry on healthcheck)")

    yield

    logger.info("Shutting down HOTS RAG Backend...")
    db_manager.close()


settings = get_settings()

app = FastAPI(
    title="AI-Powered HOTS Question Generator API",
    description="Backend API for Higher Order Thinking Skills question generation using RAG.",
    version="0.1.0",
    lifespan=lifespan,
)

# Register routers
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(dev_router, prefix="/dev", tags=["Developer"])
app.include_router(dev_courses_router, prefix="/dev/courses", tags=["Course Management (Developer)"])
app.include_router(dev_materials_router, prefix="/dev/materials", tags=["Material Management (Developer)"])
app.include_router(public_courses_router, prefix="/courses", tags=["Courses (Student)"])


@app.get("/", tags=["Root"])
def read_root() -> Dict[str, str]:
    """Root endpoint verifying application availability (Public)."""
    return {"message": "HOTS RAG Backend is running"}


@app.get("/health", tags=["Health"])
def health_check(response: Response) -> Dict[str, Any]:
    """Health check endpoint verifying API service and MongoDB database connectivity (Public)."""
    is_db_healthy, error_reason = check_mongo_connection()

    if not is_db_healthy:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "api": "healthy",
                "database": "unreachable",
                "detail": "Database connection unavailable",
            },
        )

    return {
        "status": "healthy",
        "api": "healthy",
        "database": "healthy",
    }
