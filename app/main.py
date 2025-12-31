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
    logger.info("=" * 80)
    logger.info("🚀 OMNI2 Bridge Application - Starting Up")
    logger.info("=" * 80)
    logger.info(f"📦 Version: {__version__}")
    logger.info(f"🌍 Environment: {settings.app.environment}")
    logger.info(f"🐛 Debug Mode: {settings.app.debug}")
    logger.info(f"🔄 Auto-Reload: {settings.app.reload}")
    logger.info(f"🌐 Host: {settings.app.host}:{settings.app.port}")
    logger.info("-" * 80)
    logger.info("🤖 Anthropic Claude Configuration:")
    logger.info(f"   Model: {settings.llm.model}")
    logger.info(f"   Max Tokens: {settings.llm.max_tokens}")
    logger.info(f"   Timeout: {settings.llm.timeout}s")
    logger.info(f"   API Key: {'✅ Configured' if settings.llm.api_key else '❌ Missing'}")
    logger.info("-" * 80)
    logger.info("🗄️  Database Configuration:")
    logger.info(f"   Host: {settings.database.host}:{settings.database.port}")
    logger.info(f"   Database: {settings.database.database}")
    logger.info(f"   User: {settings.database.user}")
    logger.info(f"   Pool Size: {settings.database.pool_size} (max overflow: {settings.database.max_overflow})")
    logger.info("-" * 80)
    logger.info("🔐 Security:")
    logger.info(f"   CORS Enabled: {settings.security.cors_enabled}")
    logger.info(f"   Secret Key: {'✅ Configured' if settings.security.secret_key != 'change-this-in-production' else '⚠️  Using Default (Change in Production!)'}")
    logger.info("-" * 80)
    logger.info("📡 MCP Servers:")
    mcp_count = len(settings.mcps.mcps) if hasattr(settings.mcps, 'mcps') else 0
    logger.info(f"   Registered: {mcp_count} server(s)")
    if mcp_count > 0:
        for mcp in settings.mcps.mcps[:5]:  # Show first 5
            protocol = getattr(mcp, 'protocol', 'http')
            status = '✅ Enabled' if mcp.enabled else '❌ Disabled'
            logger.info(f"   • {mcp.name} ({protocol}) - {status}")
        if mcp_count > 5:
            logger.info(f"   ... and {mcp_count - 5} more")
    logger.info("=" * 80)
    
    try:
        # Initialize database connection
        logger.info("🔌 Connecting to database...")
        await init_db()
        logger.info("✅ Database connection established")
        
        # Log configuration summary
        logger.info("✅ Configuration loaded successfully")
        
        # TODO: Initialize MCP discovery service
        # TODO: Load users from database
        # TODO: Start health check scheduler
        
        logger.info("=" * 80)
        logger.info("✅ OMNI2 Bridge Application - Ready!")
        logger.info(f"📖 API Documentation: http://{settings.app.host}:{settings.app.port}/docs")
        logger.info(f"🏥 Health Check: http://{settings.app.host}:{settings.app.port}/health")
        logger.info("=" * 80)
        
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
from app.routers import tools, chat, audit, users

app.include_router(health.router, tags=["Health"])
app.include_router(tools.router, tags=["MCP Tools"])
app.include_router(chat.router, tags=["Chat"])
app.include_router(audit.router, tags=["Audit"])
app.include_router(users.router, tags=["Users"])

# TODO: Add more routers as we build them
# app.include_router(query.router, prefix="/query", tags=["Query"])
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
