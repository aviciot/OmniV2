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
from app.services.mcp_client import MCPClient, get_mcp_client
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
        - mcps: MCP server health summary (from config)
    """
    logger.debug("Health check requested")
    
    # Check database
    db_health = await check_db_health()
    
    # Check MCP servers from config (enabled vs reachable)
    mcp_health = {"status": "unknown", "servers": []}
    try:
        mcp_client = get_mcp_client()  # Use singleton instance
        
        # Get configured MCPs from settings
        configured_mcps = []
        enabled_mcps = []
        
        for server_config in settings.mcps.mcps:
            mcp_info = {
                "name": server_config.name,
                "display_name": server_config.display_name,
                "protocol": server_config.protocol,
                "url": server_config.url if server_config.protocol in ["http", "sse"] else None,
                "enabled": server_config.enabled,
                "status": "unknown",
                "tools": 0
            }
            
            configured_mcps.append(mcp_info)
            
            if server_config.enabled:
                enabled_mcps.append(server_config.name)
                
                # Try to fetch tools to verify connectivity
                try:
                    tools_result = await mcp_client.list_tools(server_config.name)
                    server_tools = tools_result.get("servers", {}).get(server_config.name, {})
                    
                    if server_tools.get("status") == "healthy":
                        mcp_info["status"] = "healthy"
                        mcp_info["tools"] = len(server_tools.get("tools", []))
                    else:
                        mcp_info["status"] = "unhealthy"
                        mcp_info["error"] = server_tools.get("error", "Unknown error")
                except Exception as e:
                    mcp_info["status"] = "unreachable"
                    mcp_info["error"] = str(e)
        
        healthy_count = sum(1 for mcp in configured_mcps if mcp["status"] == "healthy" and mcp["enabled"])
        enabled_count = len(enabled_mcps)
        
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


@router.get("/health/cache")
async def cache_stats(mcp_client: MCPClient = Depends(get_mcp_client)) -> Dict:
    """
    Get tool schema cache statistics.
    
    Returns cache stats for all MCPs.
    """
    stats = mcp_client.get_cache_stats()
    return {
        "success": True,
        "cache_ttl_seconds": MCPClient.TOOL_CACHE_TTL,
        **stats
    }


@router.post("/health/cache/invalidate")
async def invalidate_cache(
    server_name: Optional[str] = None,
    mcp_client: MCPClient = Depends(get_mcp_client)
) -> Dict:
    """
    Invalidate tool schema cache.
    
    Args:
        server_name: Optional specific server to invalidate
    """
    mcp_client.invalidate_cache(server_name)
    return {
        "success": True,
        "message": f"Cache invalidated for {server_name or 'all servers'}"
    }
