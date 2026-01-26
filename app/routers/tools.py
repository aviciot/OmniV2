"""
MCP Tools Router

Exposes MCP tool discovery and execution endpoints.
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.services.mcp_registry import get_mcp_registry
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.utils.logger import logger


router = APIRouter(prefix="/mcp/tools")


# ============================================================
# Request/Response Models
# ============================================================

class ToolCallRequest(BaseModel):
    """Request model for calling an MCP tool."""
    
    server: str = Field(..., description="MCP server name")
    tool: str = Field(..., description="Tool name to execute")
    arguments: Dict[str, Any] = Field(default={}, description="Tool arguments")


class ToolCallResponse(BaseModel):
    """Response model for tool execution."""
    
    success: bool
    server: str
    tool: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ============================================================
# Endpoints
# ============================================================

@router.get("/list")
async def list_tools(
    server: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    List available tools from MCP servers.
    
    Args:
        server: Optional server name to filter by
        db: Database session
        
    Returns:
        Dict with tools grouped by server
    """
    try:
        logger.info("📋 Listing MCP tools", server_filter=server)
        
        mcp_registry = get_mcp_registry()
        tools = mcp_registry.get_tools(server)
        
        return {
            "success": True,
            "data": {"servers": tools},
        }
        
    except Exception as e:
        logger.error("❌ Failed to list tools", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to list tools: {str(e)}")


@router.post("/call")
async def call_tool(
    request: ToolCallRequest,
    db: AsyncSession = Depends(get_db),
) -> ToolCallResponse:
    """
    Execute an MCP tool.
    
    Args:
        request: Tool call request
        db: Database session
        
    Returns:
        Tool execution result
    """
    try:
        logger.info("🔧 Executing MCP tool", server=request.server, tool=request.tool)
        
        mcp_registry = get_mcp_registry()
        result = await mcp_registry.call_tool(request.server, request.tool, request.arguments)
        
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("error"))
        
        return ToolCallResponse(
            success=True,
            server=request.server,
            tool=request.tool,
            result=result.get("result"),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("❌ Failed to execute tool", server=request.server, tool=request.tool, error=str(e))
        raise HTTPException(status_code=500, detail=f"Tool execution failed: {str(e)}")


@router.get("/health/{server_name}")
async def check_server_health(
    server_name: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Check health status of an MCP server.
    
    Args:
        server_name: Name of the MCP server
        db: Database session
        
    Returns:
        Health status
    """
    try:
        logger.info("🏥 Checking MCP server health", server=server_name)
        
        mcp_registry = get_mcp_registry()
        health = await mcp_registry.health_check(server_name, db)
        
        return {
            "success": True,
            "server": server_name,
            "health": health,
        }
        
    except Exception as e:
        logger.error("❌ Health check failed", server=server_name, error=str(e))
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@router.post("/reload")
async def reload_mcps(
    mcp_name: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Manually trigger MCP reload from database.
    
    Args:
        mcp_name: Optional - reload specific MCP, or all if not provided
        db: Database session
        
    Returns:
        Reload status and loaded MCPs
    """
    try:
        if mcp_name:
            logger.info("🔄 Manual reload triggered", mcp=mcp_name)
            
            from sqlalchemy import select
            from app.models import MCPServer
            
            result = await db.execute(
                select(MCPServer).where(MCPServer.name == mcp_name)
            )
            mcp = result.scalar_one_or_none()
            
            if not mcp:
                raise HTTPException(status_code=404, detail=f"MCP '{mcp_name}' not found")
            
            mcp_registry = get_mcp_registry()
            
            # Unload if exists
            if mcp_name in mcp_registry.get_loaded_mcps():
                await mcp_registry.unload_mcp(mcp_name, db)
            
            # Reload
            if mcp.status == 'active':
                await mcp_registry.load_mcp(mcp, db)
            
            return {
                "success": True,
                "message": f"MCP '{mcp_name}' reloaded",
                "mcp": mcp_name,
                "status": mcp.health_status,
            }
        else:
            logger.info("🔄 Manual reload all MCPs triggered")
            
            mcp_registry = get_mcp_registry()
            await mcp_registry.reload_if_changed(db)
            
            loaded_mcps = mcp_registry.get_loaded_mcps()
            
            return {
                "success": True,
                "message": "All MCPs reloaded",
                "loaded_mcps": loaded_mcps,
                "count": len(loaded_mcps),
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("❌ Manual reload failed", mcp=mcp_name, error=str(e))
        raise HTTPException(status_code=500, detail=f"Reload failed: {str(e)}")


@router.get("/servers")
async def list_mcp_servers(
    enabled_only: bool = False,
    include_health: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """
    List all configured MCP servers from database.
    """
    try:
        from sqlalchemy import select
        from app.models import MCPServer
        
        logger.info("📋 Listing MCP servers from database", enabled_only=enabled_only)
        
        query = select(MCPServer)
        if enabled_only:
            query = query.where(MCPServer.status == 'active')
        
        result = await db.execute(query)
        mcps = result.scalars().all()
        
        mcp_registry = get_mcp_registry()
        servers = []
        
        for mcp in mcps:
            server_info = {
                "name": mcp.name,
                "url": mcp.url,
                "protocol": mcp.protocol,
                "enabled": mcp.status == 'active',
                "description": mcp.description,
                "timeout_seconds": mcp.timeout_seconds,
                "health_status": mcp.health_status,
                "last_health_check": mcp.last_health_check.isoformat() if mcp.last_health_check else None,
            }
            
            if include_health and mcp.status == 'active':
                try:
                    health = await mcp_registry.health_check(mcp.name, db)
                    server_info["health"] = health
                except:
                    pass
            
            servers.append(server_info)
        
        return {
            "success": True,
            "data": {
                "servers": servers,
                "summary": {
                    "total": len(servers),
                    "enabled": sum(1 for s in servers if s["enabled"]),
                    "disabled": sum(1 for s in servers if not s["enabled"]),
                }
            }
        }
        
    except Exception as e:
        logger.error("❌ Failed to list MCP servers", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to list servers: {str(e)}")


@router.get("/mcps/{mcp_name}/tools")
async def get_mcp_tools_for_user(
    mcp_name: str,
    user_email: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get tools available for a specific MCP server filtered by user permissions.
    
    Args:
        mcp_name: Name of the MCP server
        user_email: User's email address
        db: Database session
        
    Returns:
        Dict with MCP info and filtered tools list
    """
    try:
        from app.services.user_service import get_user_service
        
        logger.info("🔍 Getting MCP tools for user", mcp_name=mcp_name, user_email=user_email)
        
        mcp_registry = get_mcp_registry()
        all_tools = mcp_registry.get_tools(mcp_name)
        
        if mcp_name not in all_tools:
            raise HTTPException(status_code=404, detail=f"MCP server '{mcp_name}' not found")
        
        all_tool_names = [tool["name"] for tool in all_tools[mcp_name]]
        
        # Filter tools by user permissions
        user_service = get_user_service()
        allowed_tools = await user_service.get_user_allowed_tools(
            user_id=user_email,
            mcp_name=mcp_name,
            all_tools=all_tool_names,
        )
        
        # Filter the tool list
        filtered_tools = [
            tool for tool in all_tools[mcp_name]
            if tool["name"] in allowed_tools
        ]
        
        logger.info(
            "✅ Filtered tools for user",
            mcp_name=mcp_name,
            user_email=user_email,
            total_tools=len(all_tool_names),
            allowed_tools=len(filtered_tools),
        )
        
        return {
            "success": True,
            "mcp_name": mcp_name,
            "description": f"Tools from {mcp_name}",
            "tools": filtered_tools,
            "total_available": len(all_tool_names),
            "user_allowed": len(filtered_tools),
        }
        
    except HTTPException:
        raise
        
    except Exception as e:
        logger.error(
            "❌ Failed to get MCP tools for user",
            mcp_name=mcp_name,
            user_email=user_email,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=f"Failed to get tools: {str(e)}")
