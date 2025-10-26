"""
Main FastAPI application for Kirby API.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog

from src.api.routers import candles, health, starlistings
from src.config.settings import settings
from src.db.connection import close_db, init_db
from src.utils.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    """
    logger = structlog.get_logger("kirby.api")

    # Startup
    logger.info("Starting Kirby API", environment=settings.environment)

    # Set up logging
    setup_logging()

    # Initialize database connections
    await init_db()
    logger.info("Database connections initialized")

    yield

    # Shutdown
    logger.info("Shutting down Kirby API")
    await close_db()
    logger.info("Database connections closed")


# Create FastAPI app
app = FastAPI(
    title="Kirby API",
    description="High-performance cryptocurrency market data ingestion and API platform",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Custom exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with detailed messages."""
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation error",
            "errors": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors gracefully."""
    logger = structlog.get_logger("kirby.api.error")
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=True,
    )

    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "message": str(exc) if settings.is_development else "An error occurred",
        },
    )


# Include routers
app.include_router(candles.router)
app.include_router(starlistings.router)
app.include_router(health.router)


# Root endpoint
@app.get("/", tags=["root"])
async def root():
    """
    Root endpoint with API information.
    """
    return {
        "name": "Kirby API",
        "version": "0.1.0",
        "description": "High-performance cryptocurrency market data API",
        "environment": settings.environment,
        "docs": "/docs" if settings.is_development else None,
    }
