"""
Health Check Endpoint

Provides application health status including:
- API availability
- Database connectivity
- MCP server health
- System information
"""

from datetime import datetime
from typing import Dict, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.config import settings
from app.database import check_db_health, get_db
from app.models import MCPServer
from app.services.mcp_registry import get_mcp_registry
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
        - mcps: MCP server health summary (from database)
    """
    logger.debug("Health check requested")
    
    # Check database
    db_health = await check_db_health()
    
    # Check MCP servers from database
    mcp_health = {"status": "unknown", "servers": []}
    try:
        result = await db.execute(select(MCPServer))
        mcps = result.scalars().all()
        
        configured_mcps = []
        enabled_count = 0
        healthy_count = 0
        
        for mcp in mcps:
            mcp_info = {
                "name": mcp.name,
                "url": mcp.url,
                "protocol": mcp.protocol,
                "enabled": mcp.status == 'active',
                "status": mcp.health_status,
                "last_check": mcp.last_health_check.isoformat() if mcp.last_health_check else None
            }
            
            configured_mcps.append(mcp_info)
            
            if mcp.status == 'active':
                enabled_count += 1
                if mcp.health_status == 'healthy':
                    healthy_count += 1
        
        if enabled_count == 0:
            mcp_status = "no_servers"
        elif healthy_count == enabled_count:
            mcp_status = "healthy"
        elif healthy_count > 0:
            mcp_status = "degraded"
        else:
            mcp_status = "unhealthy"
        
        mcp_health = {
            "status": mcp_status,
            "healthy": healthy_count,
            "enabled": enabled_count,
            "configured": len(configured_mcps),
            "servers": configured_mcps
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
        "uptime": "N/A",
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


@router.get("/health/cache")
async def cache_stats() -> Dict:
    """
    Get tool schema cache statistics.
    
    Returns cache stats for all MCPs.
    """
    mcp_registry = get_mcp_registry()
    loaded_mcps = mcp_registry.get_loaded_mcps()
    tools = mcp_registry.get_tools()
    
    return {
        "success": True,
        "loaded_mcps": len(loaded_mcps),
        "total_tools": sum(len(t) for t in tools.values()),
        "mcps": loaded_mcps
    }


@router.post("/health/cache/invalidate")
async def invalidate_cache(
    server_name: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
) -> Dict:
    """
    Invalidate tool schema cache by reloading MCP.
    
    Args:
        server_name: Optional specific server to reload
    """
    mcp_registry = get_mcp_registry()
    
    if server_name:
        await mcp_registry.unload_mcp(server_name, db)
        result = await db.execute(select(MCPServer).where(MCPServer.name == server_name))
        mcp = result.scalar_one_or_none()
        if mcp:
            await mcp_registry.load_mcp(mcp, db)
    else:
        await mcp_registry.load_from_database(db)
    
    return {
        "success": True,
        "message": f"Cache invalidated for {server_name or 'all servers'}"
    }
