"""
Database Connection and Session Management

Handles:
- AsyncPG connection pooling
- SQLAlchemy async engine
- Database session management
- Connection lifecycle
"""

from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy import text

from app.config import settings
from app.utils.logger import logger


# ============================================================
# SQLAlchemy Base
# ============================================================
Base = declarative_base()


# ============================================================
# Global Database Objects
# ============================================================
engine: Optional[AsyncEngine] = None
AsyncSessionLocal: Optional[async_sessionmaker[AsyncSession]] = None


# ============================================================
# Database Initialization
# ============================================================

async def init_db() -> None:
    """
    Initialize database engine and session factory.
    
    Called during application startup.
    """
    global engine, AsyncSessionLocal
    
    logger.info(
        "🔌 Initializing database connection",
        host=settings.database.host,
        port=settings.database.port,
        database=settings.database.database,
        user=settings.database.user,
        url_preview=settings.database.url.replace(settings.database.password, "***"),
    )
    
    try:
        # Create async engine
        engine = create_async_engine(
            settings.database.url,
            echo=settings.database.echo,
            pool_size=settings.database.pool_size,
            max_overflow=settings.database.max_overflow,
            pool_pre_ping=True,  # Verify connections before using
            pool_recycle=3600,   # Recycle connections after 1 hour
            connect_args={"ssl": False},  # Disable SSL for local development
        )
        
        # Create session factory
        AsyncSessionLocal = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
        
        # Test connection
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        
        logger.info("✅ Database connection successful")
        
    except Exception as e:
        logger.error(
            "❌ Failed to initialize database",
            error=str(e),
            url=settings.database.url.split("@")[-1],  # Don't log password
            exc_info=True,
        )
        raise


async def close_db() -> None:
    """
    Close database connections.
    
    Called during application shutdown.
    """
    global engine
    
    if engine:
        logger.info("🔌 Closing database connections")
        await engine.dispose()
        logger.info("✅ Database connections closed")


# ============================================================
# Database Session Dependency
# ============================================================

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a database session.
    
    Usage:
        @app.get("/users")
        async def get_users(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(User))
            return result.scalars().all()
    """
    if AsyncSessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ============================================================
# Database Health Check
# ============================================================

async def check_db_health() -> dict:
    """
    Check database connectivity and return health status.
    
    Returns:
        dict: Health status with connection info
    """
    try:
        if engine is None:
            return {
                "status": "unhealthy",
                "error": "Database not initialized",
            }
        
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()
        
        return {
            "status": "healthy",
            "database": settings.database.database,
            "host": settings.database.host,
            "port": settings.database.port,
            "version": version,
        }
    
    except Exception as e:
        logger.error("❌ Database health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "error": str(e),
        }


# ============================================================
# Utility Functions
# ============================================================

async def execute_raw_sql(sql: str) -> list:
    """
    Execute raw SQL query.
    
    Args:
        sql: SQL query string
        
    Returns:
        List of row dictionaries
    """
    if engine is None:
        raise RuntimeError("Database not initialized")
    
    async with engine.begin() as conn:
        result = await conn.execute(text(sql))
        return [dict(row) for row in result.mappings()]
