"""
Health Check Endpoint

Provides application health status including:
- API availability
- Database connectivity
- MCP server health
- System information
"""

from datetime import datetime
from typing import Dict

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.config import settings
from app.database import check_db_health, get_db
from app.models import MCPServer
from app.utils.logger import logger
from sqlalchemy import select


router = APIRouter()


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)) -> Dict:
    """
    Health check endpoint.
    
    Returns:
        - status: overall health (healthy/degraded/unhealthy)
        - version: application version
        - timestamp: current server time
        - database: database connection status
        - mcps: MCP server health summary
    """
    logger.debug("Health check requested")
    
    # Check database
    db_health = await check_db_health()
    
    # Check MCP servers (if any registered)
    mcp_health = {"status": "unknown", "servers": []}
    try:
        result = await db.execute(
            select(MCPServer).where(MCPServer.is_enabled == True)
        )
        mcp_servers = result.scalars().all()
        
        if mcp_servers:
            healthy_count = sum(1 for mcp in mcp_servers if mcp.is_healthy)
            total_count = len(mcp_servers)
            
            mcp_health = {
                "status": "healthy" if healthy_count == total_count else "degraded",
                "healthy": healthy_count,
                "total": total_count,
                "servers": [
                    {
                        "name": mcp.name,
                        "url": mcp.url,
                        "healthy": mcp.is_healthy,
                        "last_seen": mcp.last_seen.isoformat() if mcp.last_seen else None,
                    }
                    for mcp in mcp_servers
                ],
            }
        else:
            mcp_health = {
                "status": "no_servers",
                "message": "No MCP servers registered yet",
            }
    
    except Exception as e:
        logger.error("Failed to check MCP health", error=str(e))
        mcp_health = {
            "status": "error",
            "error": str(e),
        }
    
    # Determine overall status
    if db_health["status"] == "healthy":
        if mcp_health["status"] in ["healthy", "no_servers", "unknown"]:
            overall_status = "healthy"
        elif mcp_health["status"] == "degraded":
            overall_status = "degraded"
        else:
            overall_status = "degraded"
    else:
        overall_status = "unhealthy"
    
    return {
        "status": overall_status,
        "version": __version__,
        "timestamp": datetime.utcnow().isoformat(),
        "environment": settings.app.environment,
        "database": db_health,
        "mcps": mcp_health,
        "uptime": "N/A",  # TODO: Track uptime
    }


@router.get("/health/ready")
async def readiness_check() -> Dict:
    """
    Kubernetes-style readiness probe.
    
    Returns 200 if app is ready to serve traffic.
    """
    db_health = await check_db_health()
    
    if db_health["status"] == "healthy":
        return {"ready": True}
    else:
        return {"ready": False, "reason": "Database unavailable"}


@router.get("/health/live")
async def liveness_check() -> Dict:
    """
    Kubernetes-style liveness probe.
    
    Returns 200 if app is alive (even if degraded).
    """
    return {
        "alive": True,
        "version": __version__,
        "timestamp": datetime.utcnow().isoformat(),
    }
