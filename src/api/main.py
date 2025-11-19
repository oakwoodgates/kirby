"""
Main FastAPI application for Kirby API.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog

from src.api.postgres_listener import PostgresNotificationListener
from src.api.routers import admin, candles, funding, health, starlistings, websocket
from src.api.websocket_manager import ConnectionManager
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

    # Initialize WebSocket components
    connection_manager = ConnectionManager(
        max_connections=settings.websocket_max_connections,
        heartbeat_interval=settings.websocket_heartbeat_interval,
    )
    websocket.set_connection_manager(connection_manager)
    logger.info(
        "WebSocket connection manager initialized",
        max_connections=settings.websocket_max_connections,
    )

    # Initialize and start PostgreSQL notification listener
    postgres_listener = PostgresNotificationListener(connection_manager)
    await postgres_listener.start()
    logger.info("PostgreSQL notification listener started")

    yield

    # Shutdown
    logger.info("Shutting down Kirby API")

    # Stop PostgreSQL listener
    await postgres_listener.stop()
    logger.info("PostgreSQL notification listener stopped")

    # Close database connections
    await close_db()
    logger.info("Database connections closed")


# Create FastAPI app
app = FastAPI(
    title="Kirby API",
    description="""
# Kirby Cryptocurrency Data Platform

High-performance market data ingestion and API platform for cryptocurrency exchanges.

## REST API

Access historical and real-time market data via these endpoints below.

**Authentication**: All endpoints require API key authentication via `Authorization: Bearer` header.

**Available Data**:
- 📊 **Candles** - OHLCV data at multiple intervals (1m, 15m, 4h, 1d)
- 💰 **Funding Rates** - Perpetual funding rates (1-minute precision)
- 📈 **Open Interest** - Open interest and volume data (1-minute precision)
- ⭐ **Starlistings** - Available trading pairs and markets

## WebSocket API

For **real-time streaming** data, connect to the WebSocket endpoint:

**Endpoint**: `ws://localhost:8000/ws?api_key=YOUR_API_KEY`

**Features**:
- Real-time candles, funding rates, and open interest updates
- Subscribe to multiple trading pairs simultaneously
- Historical data on connection (optional)
- Automatic heartbeat/keepalive

**📖 Full Documentation**: See [WebSocket API Documentation](https://github.com/oakwoodgates/kirby/blob/main/docs/WEBSOCKET_API.md)

---

**Version**: 1.3.0 | **Environment**: Production
""",
    version="1.3.0",
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
app.include_router(admin.router)
app.include_router(candles.router)
app.include_router(funding.router)
app.include_router(starlistings.router)
app.include_router(health.router)
app.include_router(websocket.router)


# Root endpoint
@app.get("/", tags=["root"])
async def root():
    """
    Root endpoint with API information.
    """
    return {
        "name": "Kirby API",
        "version": "1.3.0",
        "description": "High-performance cryptocurrency market data API",
        "environment": settings.environment,
        "endpoints": {
            "rest_api": "/docs" if settings.is_development else None,
            "websocket": "/ws?api_key=YOUR_API_KEY",
            "health": "/health",
        },
        "features": [
            "REST API - Historical and real-time candles, funding rates, open interest",
            "WebSocket API - Real-time streaming of market data",
            "Authentication - API key-based access control",
            "Multiple exchanges - Currently: Hyperliquid",
        ],
        "documentation": {
            "swagger": "/docs" if settings.is_development else None,
            "redoc": "/redoc" if settings.is_development else None,
            "websocket": "https://github.com/oakwoodgates/kirby/blob/main/docs/WEBSOCKET_API.md",
        },
    }
