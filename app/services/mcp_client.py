"""
MCP Client Service

Handles communication with MCP servers using multiple protocols:
- HTTP: FastMCP servers with HTTP transport
- Stdio: Local MCP servers via subprocess
- SSE: FastMCP servers with SSE transport
"""

from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import asyncio
import fnmatch
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from app.config import settings
from app.utils.logger import logger


class MCPClient:
    """Multi-protocol MCP client supporting HTTP, Stdio, and SSE transports."""
    
    def __init__(self):
        """Initialize MCP client with configured servers."""
        # Convert list of MCPServerConfig to dict for easier lookup
        self.servers = {
            server.name: server.model_dump()
            for server in settings.mcps.mcps
        }
        self._client_cache: Dict[str, Client] = {}
        
    async def _get_client(self, server_name: str) -> Client:
        """
        Get or create a FastMCP client for a server with appropriate protocol.
        
        Supports:
        - HTTP: URL-based connection (http://...)
        - Stdio: Subprocess-based connection (command + args)
        - SSE: Server-Sent Events (http://... with SSE transport)
        
        Args:
            server_name: Name of the MCP server
            
        Returns:
            FastMCP Client instance
        """
        if server_name in self._client_cache:
            return self._client_cache[server_name]
        
        server_config = self.servers.get(server_name)
        if not server_config:
            raise ValueError(f"Unknown MCP server: {server_name}")
        
        protocol = server_config.get("protocol", "http").lower()
        
        logger.info(
            "🔌 Creating MCP client",
            server=server_name,
            protocol=protocol,
        )
        
        try:
            client = None
            
            if protocol == "stdio":
                # Stdio protocol - run as subprocess
                client = await self._create_stdio_client(server_name, server_config)
                
            elif protocol in ("http", "sse"):
                # HTTP/SSE protocol - URL-based
                client = await self._create_http_client(server_name, server_config)
                
            else:
                raise ValueError(f"Unsupported protocol: {protocol}")
            
            self._client_cache[server_name] = client
            
            logger.info(
                "✅ MCP client connected",
                server=server_name,
                protocol=protocol,
            )
            
            return client
            
        except Exception as e:
            logger.error(
                "❌ Failed to create MCP client",
                server=server_name,
                protocol=protocol,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise
    
    async def _create_http_client(
        self, 
        server_name: str, 
        config: Dict[str, Any]
    ) -> Client:
        """
        Create HTTP or SSE client.
        
        Args:
            server_name: Name of the server
            config: Server configuration
            
        Returns:
            FastMCP Client with HTTP/SSE transport
        """
        url = config.get("url", "")
        if not url:
            raise ValueError(f"No URL configured for server: {server_name}")

        # Ensure URL ends with /mcp
        if not url.rstrip("/").endswith("/mcp"):
            url = url.rstrip("/") + "/mcp"

        # Build authentication
        auth = None
        auth_config = config.get("authentication", {})
        if auth_config.get("enabled", False):
            api_key = auth_config.get("api_key", "")
            if api_key:
                # Use httpx.Auth class for Bearer token
                import httpx
                class BearerAuth(httpx.Auth):
                    def __init__(self, token: str):
                        self.token = token
                    def auth_flow(self, request):
                        request.headers["Authorization"] = f"Bearer {self.token}"
                        yield request
                auth = BearerAuth(api_key)

        # Create client
        client = Client(
            transport=url,
            auth=auth,
            timeout=config.get("timeout_seconds", 30),
        )

        # Initialize connection
        await client.__aenter__()

        return client
    
    async def _create_stdio_client(
        self, 
        server_name: str, 
        config: Dict[str, Any]
    ) -> Client:
        """
        Create stdio client for subprocess-based MCP servers.
        
        Args:
            server_name: Name of the server
            config: Server configuration with command and args
            
        Returns:
            FastMCP Client with Stdio transport
        """
        command = config.get("command")
        args = config.get("args", [])
        cwd = config.get("cwd")
        
        if not command:
            raise ValueError(f"No command configured for stdio server: {server_name}")
        
        logger.info(
            "📟 Starting stdio MCP subprocess",
            server=server_name,
            command=command,
            args=args,
        )
        
        # Create stdio transport
        transport = StdioTransport(
            command=command,
            args=args,
            env=None,  # Use current environment
        )
        
        # Create client with stdio transport
        client = Client(
            transport=transport,
            timeout=config.get("timeout_seconds", 30),
        )
        
        # Initialize connection
        await client.__aenter__()
        
        return client
        
    def _filter_tools_by_policy(
        self, 
        tools: List[Dict[str, Any]], 
        server_name: str
    ) -> List[Dict[str, Any]]:
        """
        Filter tools based on server's tool policy.
        
        Args:
            tools: List of tool dicts
            server_name: Name of the server
            
        Returns:
            Filtered list of tools
        """
        server_config = self.servers.get(server_name, {})
        tool_policy = server_config.get("tool_policy", {})
        
        if not tool_policy:
            return tools
        
        mode = tool_policy.get("mode", "allow_all")
        
        if mode == "allow_all":
            # No filtering
            return tools
            
        elif mode == "allow_only":
            # Only allow specified tools
            allowed = tool_policy.get("allow", [])
            filtered_tools = []
            
            for tool in tools:
                tool_name = tool.get("name", "")
                # Check exact match or pattern match
                if any(
                    tool_name == pattern or fnmatch.fnmatch(tool_name, pattern)
                    for pattern in allowed
                ):
                    filtered_tools.append(tool)
            
            logger.info(
                f"🔒 Filtered tools (allow_only)",
                server=server_name,
                original_count=len(tools),
                filtered_count=len(filtered_tools),
                allowed_patterns=allowed,
            )
            return filtered_tools
            
        elif mode == "allow_all_except":
            # Allow all except excluded tools
            excluded = tool_policy.get("exclude", [])
            filtered_tools = []
            
            for tool in tools:
                tool_name = tool.get("name", "")
                # Check if tool matches any exclude pattern
                is_excluded = any(
                    tool_name == pattern or fnmatch.fnmatch(tool_name, pattern)
                    for pattern in excluded
                )
                if not is_excluded:
                    filtered_tools.append(tool)
            
            logger.info(
                f"🔒 Filtered tools (allow_all_except)",
                server=server_name,
                original_count=len(tools),
                filtered_count=len(filtered_tools),
                excluded_patterns=excluded,
            )
            return filtered_tools
        
        return tools
        
    async def list_tools(self, server_name: Optional[str] = None) -> Dict[str, Any]:
        """
        List available tools from one or all MCP servers using native MCP protocol.
        
        Args:
            server_name: Specific server to query, or None for all servers
            
        Returns:
            Dict with tools grouped by server
        """
        if server_name:
            # Query specific server
            server_config = self.servers.get(server_name)
            if not server_config:
                raise ValueError(f"Unknown MCP server: {server_name}")
            
            tools = await self._fetch_tools_native(server_name)
            return {
                "servers": {server_name: tools},
                "total_tools": len(tools.get("tools", [])),
            }
        
        # Query all servers
        all_tools = {}
        total_count = 0
        
        for name, config in self.servers.items():
            if not config.get("enabled", True):
                logger.info(f"⏭️  Skipping disabled MCP server", server=name)
                continue
                
            try:
                tools = await self._fetch_tools_native(name)
                all_tools[name] = tools
                total_count += len(tools.get("tools", []))
            except Exception as e:
                logger.error(
                    "❌ Failed to list tools from MCP server",
                    server=name,
                    error=str(e),
                )
                all_tools[name] = {
                    "error": str(e),
                    "status": "unhealthy",
                }
        
        return {
            "servers": all_tools,
            "total_tools": total_count,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    async def _fetch_tools_native(self, server_name: str) -> Dict[str, Any]:
        """
        Fetch tools from FastMCP server using native MCP protocol.
        
        Args:
            server_name: Name of the MCP server
            
        Returns:
            Dict with tools and server info
        """
        logger.info(
            "🔍 Fetching tools from FastMCP server",
            server=server_name,
        )
        
        try:
            client = await self._get_client(server_name)
            
            # Use native FastMCP list_tools method
            tools_result = await client.list_tools()
            
            # tools_result is either a list of tools or an object with .tools attribute
            if isinstance(tools_result, list):
                tools_list = tools_result
            elif hasattr(tools_result, 'tools'):
                tools_list = tools_result.tools
            else:
                tools_list = []
            
            # Convert to our format
            tools = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.inputSchema.model_dump() if hasattr(tool.inputSchema, 'model_dump') else tool.inputSchema,
                }
                for tool in tools_list
            ]
            
            # Apply tool policy filtering
            filtered_tools = self._filter_tools_by_policy(tools, server_name)
            
            logger.info(
                "✅ Successfully fetched tools",
                server=server_name,
                tool_count=len(filtered_tools),
            )
            
            return {
                "tools": filtered_tools,
                "server_info": {
                    "name": server_name,
                    "protocol": "mcp",
                },
                "status": "healthy",
                "last_check": datetime.utcnow().isoformat(),
            }
            
        except Exception as e:
            logger.error(
                "❌ Error fetching tools",
                server=server_name,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise
    
    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute a tool on an MCP server using native MCP protocol.
        
        Args:
            server_name: Name of the MCP server
            tool_name: Name of the tool to call
            arguments: Tool arguments
            
        Returns:
            Dict with tool execution result
        """
        server_config = self.servers.get(server_name)
        if not server_config:
            raise ValueError(f"Unknown MCP server: {server_name}")
        
        protocol = server_config.get("protocol", "http")
        
        logger.info(
            "�️  Calling tool on MCP server",
            server=server_name,
            tool=tool_name,
            protocol=protocol,
            arguments=arguments,
        )
        
        try:
            client = await self._get_client(server_name)
            
            # Use native FastMCP call_tool method
            result = await client.call_tool(tool_name, arguments)
            
            logger.info(
                "✅ Tool execution successful",
                server=server_name,
                tool=tool_name,
            )
            
            return {
                "result": result.content if hasattr(result, 'content') else result,
                "status": "success",
                "server": server_name,
                "tool": tool_name,
                "protocol": protocol,
                "timestamp": datetime.utcnow().isoformat(),
            }
            
        except Exception as e:
            logger.error(
                "❌ Tool execution failed",
                server=server_name,
                tool=tool_name,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise
    
    async def health_check(self, server_name: str) -> Dict[str, Any]:
        """
        Check health of an MCP server by attempting to list tools.
        
        Args:
            server_name: Name of the MCP server
            
        Returns:
            Health status dict
        """
        server_config = self.servers.get(server_name)
        if not server_config:
            return {
                "healthy": False,
                "error": f"Unknown server: {server_name}",
            }
        
        protocol = server_config.get("protocol", "http")
        
        logger.info(
            "🏥 Health check for MCP server",
            server=server_name,
            protocol=protocol,
        )
        
        try:
            # Try to list tools as a health check
            client = await self._get_client(server_name)
            tools_result = await client.list_tools()
            
            tool_count = len(tools_result.tools) if hasattr(tools_result, 'tools') else 0
            
            return {
                "healthy": True,
                "protocol": protocol,
                "tool_count": tool_count,
                "last_check": datetime.utcnow().isoformat(),
            }
            
        except Exception as e:
            logger.error(
                "❌ Health check failed",
                server=server_name,
                error=str(e),
            )
            return {
                "healthy": False,
                "protocol": protocol,
                "error": str(e),
                "last_check": datetime.utcnow().isoformat(),
            }
    
    async def close(self):
        """Close all client connections."""
        logger.info("🔌 Closing MCP client connections")
        
        for server_name, client in self._client_cache.items():
            try:
                await client.__aexit__(None, None, None)
                logger.info("✅ Closed connection", server=server_name)
            except Exception as e:
                logger.error(
                    "❌ Error closing connection",
                    server=server_name,
                    error=str(e),
                )
        
        self._client_cache.clear()


# Global MCP client instance
_mcp_client: Optional[MCPClient] = None


def get_mcp_client() -> MCPClient:
    """
    Get or create the global MCP client instance.
    
    Returns:
        MCPClient instance
    """
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient()
    return _mcp_client
