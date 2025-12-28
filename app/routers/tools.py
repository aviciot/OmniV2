"""
MCP Tools Router

Exposes MCP tool discovery and execution endpoints.
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.services.mcp_client import get_mcp_client, MCPClient
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
    mcp_client: MCPClient = Depends(get_mcp_client),
):
    """
    List available tools from MCP servers.
    
    Args:
        server: Optional server name to filter by
        mcp_client: MCP client instance (injected)
        
    Returns:
        Dict with tools grouped by server
    """
    try:
        logger.info(
            "📋 Listing MCP tools",
            server_filter=server,
        )
        
        tools = await mcp_client.list_tools(server_name=server)
        
        return {
            "success": True,
            "data": tools,
        }
        
    except ValueError as e:
        logger.warning("⚠️  Invalid request", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
        
    except Exception as e:
        logger.error(
            "❌ Failed to list tools",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list tools: {str(e)}",
        )


@router.post("/call")
async def call_tool(
    request: ToolCallRequest,
    mcp_client: MCPClient = Depends(get_mcp_client),
) -> ToolCallResponse:
    """
    Execute an MCP tool.
    
    Args:
        request: Tool call request
        mcp_client: MCP client instance (injected)
        
    Returns:
        Tool execution result
    """
    try:
        logger.info(
            "🔧 Executing MCP tool",
            server=request.server,
            tool=request.tool,
            args=request.arguments,
        )
        
        result = await mcp_client.call_tool(
            server_name=request.server,
            tool_name=request.tool,
            arguments=request.arguments,
        )
        
        return ToolCallResponse(
            success=True,
            server=request.server,
            tool=request.tool,
            result=result,
        )
        
    except ValueError as e:
        logger.warning("⚠️  Invalid request", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
        
    except Exception as e:
        logger.error(
            "❌ Failed to execute tool",
            server=request.server,
            tool=request.tool,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Tool execution failed: {str(e)}",
        )


@router.get("/health/{server_name}")
async def check_server_health(
    server_name: str,
    mcp_client: MCPClient = Depends(get_mcp_client),
):
    """
    Check health status of an MCP server.
    
    Args:
        server_name: Name of the MCP server
        mcp_client: MCP client instance (injected)
        
    Returns:
        Health status
    """
    try:
        logger.info(
            "🏥 Checking MCP server health",
            server=server_name,
        )
        
        health = await mcp_client.health_check(server_name)
        
        return {
            "success": True,
            "server": server_name,
            "health": health,
        }
        
    except Exception as e:
        logger.error(
            "❌ Health check failed",
            server=server_name,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Health check failed: {str(e)}",
        )


@router.get("/servers")
async def list_mcp_servers(
    enabled_only: bool = False,
    include_health: bool = False,
    mcp_client: MCPClient = Depends(get_mcp_client),
):
    """
    List all configured MCP servers with their status and capabilities.
    
    Args:
        enabled_only: If True, only return enabled MCP servers
        include_health: If True, perform live health check for each server
        mcp_client: MCP client instance (injected)
    
    Returns:
        List of MCP servers with configuration details
        
    Examples:
        - GET /mcp/servers - All MCPs
        - GET /mcp/servers?enabled_only=true - Only enabled MCPs
        - GET /mcp/servers?include_health=true - All MCPs with health status
    """
    try:
        logger.info(
            "📋 Listing configured MCP servers",
            enabled_only=enabled_only,
            include_health=include_health,
        )
        
        servers = []
        for server_name, server_config in mcp_client.servers.items():
            # Skip if config is None or invalid
            if not server_config or not isinstance(server_config, dict):
                continue
            
            is_enabled = server_config.get("enabled", True)
            
            # Filter by enabled status if requested
            if enabled_only and not is_enabled:
                continue
            
            # Get basic server info
            server_info = {
                "name": server_name,
                "display_name": server_config.get("display_name", server_name),
                "protocol": server_config.get("protocol", "http"),
                "enabled": is_enabled,
                "description": server_config.get("description", ""),
                "tags": server_config.get("tags", []),
                "timeout_seconds": server_config.get("timeout_seconds", 30),
            }
            
            # Add protocol-specific details
            if server_info["protocol"] == "http":
                server_info["url"] = server_config.get("url", "")
                auth_config = server_config.get("authentication", {})
                if auth_config:
                    server_info["authentication"] = {
                        "enabled": auth_config.get("enabled", False),
                        "type": auth_config.get("type", ""),
                    }
            elif server_info["protocol"] == "stdio":
                server_info["command"] = server_config.get("command", "")
                server_info["args"] = server_config.get("args", [])
            
            # Add tool policy info
            tool_policy = server_config.get("tool_policy", {})
            if isinstance(tool_policy, dict):
                server_info["tool_policy"] = {
                    "mode": tool_policy.get("mode", "allow_all"),
                    "excluded_count": len(tool_policy.get("exclude", [])),
                }
            
            # Add rate limit info if configured
            rate_limit = server_config.get("rate_limit", {})
            if isinstance(rate_limit, dict) and rate_limit:
                server_info["rate_limit"] = {
                    "requests_per_minute": rate_limit.get("requests_per_minute"),
                    "burst": rate_limit.get("burst"),
                }
            
            # Perform live health check if requested
            if include_health and is_enabled:
                try:
                    health = await mcp_client.health_check(server_name)
                    server_info["health"] = {
                        "status": "healthy" if health.get("healthy") else "unhealthy",
                        "tool_count": health.get("tool_count", 0),
                        "last_check": health.get("last_check"),
                        "error": health.get("error"),
                    }
                except Exception as e:
                    server_info["health"] = {
                        "status": "error",
                        "error": str(e),
                    }
            elif include_health and not is_enabled:
                server_info["health"] = {
                    "status": "disabled",
                }
            
            servers.append(server_info)
        
        # Count enabled vs disabled (from all servers, not filtered)
        all_servers_count = len(mcp_client.servers)
        enabled_count = sum(
            1 for cfg in mcp_client.servers.values() 
            if isinstance(cfg, dict) and cfg.get("enabled", True)
        )
        disabled_count = all_servers_count - enabled_count
        
        return {
            "success": True,
            "data": {
                "servers": servers,
                "summary": {
                    "total": len(servers),  # Filtered count
                    "total_configured": all_servers_count,  # All configured
                    "enabled": enabled_count,
                    "disabled": disabled_count,
                    "protocols": {
                        "http": sum(1 for s in servers if s["protocol"] == "http"),
                        "stdio": sum(1 for s in servers if s["protocol"] == "stdio"),
                        "sse": sum(1 for s in servers if s["protocol"] == "sse"),
                    }
                }
            }
        }
        
    except Exception as e:
        logger.error(
            "❌ Failed to list MCP servers",
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list servers: {str(e)}",
        )


@router.get("/mcps/{mcp_name}/tools")
async def get_mcp_tools_for_user(
    mcp_name: str,
    user_email: str,
    mcp_client: MCPClient = Depends(get_mcp_client),
):
    """
    Get tools available for a specific MCP server filtered by user permissions.
    
    Args:
        mcp_name: Name of the MCP server
        user_email: User's email address
        mcp_client: MCP client instance (injected)
        
    Returns:
        Dict with MCP info and filtered tools list
    """
    try:
        from app.services.user_service import get_user_service
        
        logger.info(
            "🔍 Getting MCP tools for user",
            mcp_name=mcp_name,
            user_email=user_email,
        )
        
        # Get all tools for this MCP
        all_tools_response = await mcp_client.list_tools(server_name=mcp_name)
        
        # Handle the response format: {"servers": {mcp_name: {...}}}
        all_tools = all_tools_response.get("servers", {})
        
        if mcp_name not in all_tools:
            raise HTTPException(
                status_code=404,
                detail=f"MCP server '{mcp_name}' not found"
            )
        
        mcp_data = all_tools[mcp_name]
        all_tool_names = [tool["name"] for tool in mcp_data.get("tools", [])]
        
        # Filter tools by user permissions
        user_service = get_user_service()
        allowed_tools = user_service.get_user_allowed_tools(
            user_id=user_email,
            mcp_name=mcp_name,
            all_tools=all_tool_names
        )
        
        # Filter the tool list
        filtered_tools = [
            tool for tool in mcp_data.get("tools", [])
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
            "description": mcp_data.get("description", f"Tools from {mcp_name}"),
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
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get tools: {str(e)}",
        )
