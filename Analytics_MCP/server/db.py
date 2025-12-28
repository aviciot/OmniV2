# server/db.py
"""Database connection for OMNI2 Analytics MCP - Read-only access to audit logs."""

import os
import logging
import asyncpg
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class DatabaseConnection:
    """Async PostgreSQL connection for reading OMNI2 audit data."""
    
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self._db_url = os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:postgres@postgres:5432/omni"
        )
    
    async def connect(self):
        """Initialize connection pool."""
        if self.pool is None:
            try:
                self.pool = await asyncpg.create_pool(
                    self._db_url,
                    min_size=2,
                    max_size=5,
                    command_timeout=30
                )
                logger.info("✅ Connected to OMNI2 database (read-only)")
            except Exception as e:
                logger.error(f"❌ Database connection failed: {e}")
                raise
    
    async def close(self):
        """Close connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("🔌 Database connection closed")
    
    async def fetch_all(self, query: str, *args) -> List[Dict[str, Any]]:
        """Execute SELECT query and return all rows as dicts."""
        if not self.pool:
            await self.connect()
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(row) for row in rows]
    
    async def fetch_one(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """Execute SELECT query and return first row as dict."""
        if not self.pool:
            await self.connect()
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None
    
    async def fetch_value(self, query: str, *args) -> Any:
        """Execute SELECT query and return single value."""
        if not self.pool:
            await self.connect()
        
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args)


# Global database instance
db = DatabaseConnection()
