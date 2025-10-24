"""
Main FastAPI application for Kirby cryptocurrency data platform.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src.api.middleware import RequestLoggingMiddleware, setup_cors
from src.api.routes import health, candles, funding, open_interest, listings, market
from src.config.settings import settings
from src.db.asyncpg_pool import init_pool, close_pool
from src.db.session import init_db, close_db
from src.utils.logger import get_logger, setup_logging

# Setup logging
setup_logging(log_level=settings.LOG_LEVEL, log_format=settings.LOG_FORMAT)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.

    Args:
        app: FastAPI application instance
    """
    # Startup
    logger.info("Starting Kirby API server...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Log level: {settings.LOG_LEVEL}")

    # Initialize database connections
    logger.info("Initializing database connections...")
    await init_pool()  # For asyncpg (writes)
    init_db()  # For SQLAlchemy (reads)
    logger.info("Database connections initialized")

    yield

    # Shutdown
    logger.info("Shutting down Kirby API server...")
    await close_pool()  # Close asyncpg pool
    await close_db()  # Close SQLAlchemy engine
    logger.info("Database connections closed")


# Create FastAPI application
app = FastAPI(
    title="Kirby API",
    description="Cryptocurrency data ingestion platform and API",
    version="0.1.0",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
)

# Setup middleware
setup_cors(app)
app.add_middleware(RequestLoggingMiddleware)

# Include routers
app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(candles.router, prefix="/api/v1", tags=["Market Data"])
app.include_router(funding.router, prefix="/api/v1", tags=["Market Data"])
app.include_router(open_interest.router, prefix="/api/v1", tags=["Market Data"])
app.include_router(listings.router, prefix="/api/v1", tags=["Listings"])
app.include_router(market.router, prefix="/api/v1", tags=["Market Data"])


# Root endpoint
@app.get("/")
async def root():
    """
    Root endpoint with API information.
    """
    return {
        "name": "Kirby API",
        "version": "0.1.0",
        "description": "Cryptocurrency data ingestion platform and API",
        "docs": "/api/v1/docs",
        "health": "/api/v1/health",
    }


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    Global exception handler for unhandled errors.

    Args:
        request: Request object
        exc: Exception

    Returns:
        JSONResponse with error details
    """
    logger.error(
        f"Unhandled exception: {exc}",
        extra={
            "method": request.method,
            "path": request.url.path,
            "error": str(exc),
        },
        exc_info=True
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc) if settings.ENVIRONMENT == "development" else "An error occurred",
        }
    )
