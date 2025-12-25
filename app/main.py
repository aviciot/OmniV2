"""
OMNI2 FastAPI Application Entry Point

This is the main application module that initializes the FastAPI app,
configures middleware, registers routers, and sets up startup/shutdown events.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.config import settings
from app.database import init_db, close_db
from app.routers import health
from app.utils.logger import setup_logging, logger


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager for startup and shutdown events.
    
    Handles:
    - Database connection initialization
    - Configuration loading
    - Resource cleanup on shutdown
    """
    # Startup
    logger.info("🚀 Starting OMNI2 Bridge Application", version=__version__)
    
    try:
        # Initialize database connection
        await init_db()
        logger.info("✅ Database connection established")
        
        # Log configuration
        logger.info(
            "📋 Configuration loaded",
            environment=settings.app.environment,
            debug=settings.app.debug,
            reload=settings.app.reload,
        )
        
        # TODO: Initialize MCP discovery service
        # TODO: Load users from database
        # TODO: Start health check scheduler
        
        yield
        
    finally:
        # Shutdown
        logger.info("🛑 Shutting down OMNI2 Bridge Application")
        
        # Close database connections
        await close_db()
        logger.info("✅ Database connections closed")
        
        # TODO: Cleanup MCP connections
        # TODO: Save any pending audit logs


# Initialize FastAPI application
app = FastAPI(
    title="OMNI2 Bridge",
    description=(
        "Intelligent MCP orchestration layer with LLM-based routing. "
        "Routes natural language queries to appropriate Model Context Protocol servers."
    ),
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


# ============================================================
# CORS Middleware
# ============================================================
if settings.security.cors_enabled:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.security.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info("✅ CORS middleware enabled", origins=settings.security.cors_origins)


# ============================================================
# Global Exception Handler
# ============================================================
@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception):
    """Handle all unhandled exceptions."""
    logger.error(
        "❌ Unhandled exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=True,
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc) if settings.app.debug else "An unexpected error occurred",
            "path": request.url.path,
        },
    )


# ============================================================
# Register Routers
# ============================================================
app.include_router(health.router, tags=["Health"])

# TODO: Add more routers as we build them
# app.include_router(query.router, prefix="/query", tags=["Query"])
# app.include_router(tools.router, prefix="/mcp", tags=["MCP Tools"])
# app.include_router(admin.router, prefix="/admin", tags=["Admin"])
# app.include_router(slack.router, prefix="/slack", tags=["Slack"])


# ============================================================
# Root Endpoint
# ============================================================
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "OMNI2 Bridge",
        "version": __version__,
        "description": "Intelligent MCP orchestration with LLM routing",
        "docs": "/docs",
        "health": "/health",
        "status": "running",
    }


# ============================================================
# Setup Logging
# ============================================================
# Initialize logging when module is imported
setup_logging()

logger.info("✅ OMNI2 application module loaded")
