"""
MCP Client Service

Handles communication with MCP servers using multiple protocols:
- HTTP: FastMCP servers with HTTP transport
- Stdio: Local MCP servers via subprocess
- SSE: FastMCP servers with SSE transport

Features:
- Auto-reconnect on connection failures
- Configurable retry per MCP
- Connection age validation
"""

from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime
import asyncio
import fnmatch
import time
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from app.config import settings
from app.utils.logger import logger


# Default retry settings (fallback if not configured)
DEFAULT_MAX_ATTEMPTS = 2
DEFAULT_DELAY_SECONDS = 1.0
DEFAULT_CONNECTION_MAX_AGE = 600  # 10 minutes


class MCPClient:
    """Multi-protocol MCP client supporting HTTP, Stdio, and SSE transports."""
    
    # Tool schema cache TTL (5 minutes)
    TOOL_CACHE_TTL = 300
    
    def __init__(self):
        """Initialize MCP client with configured servers."""
        # Convert list of MCPServerConfig to dict for easier lookup
        self.servers = {
            server.name: server.model_dump()
            for server in settings.mcps.mcps
        }
        self._client_cache: Dict[str, Client] = {}
        self._client_created_at: Dict[str, float] = {}  # Track connection age
        
        # Tool schema cache
        self._tool_cache: Dict[str, Dict[str, Any]] = {}
        self._tool_cache_timestamp: Dict[str, float] = {}
        
        # Load global retry settings
        self._global_retry = settings.mcps.global_settings.get("retry", {})
    
    def _get_retry_config(self, server_name: str) -> Tuple[int, float, int]:
        """
        Get retry configuration for a server (MCP-specific or global fallback).
        
        Returns:
            Tuple of (max_attempts, delay_seconds, connection_max_age_seconds)
        """
        server_config = self.servers.get(server_name, {})
        mcp_retry = server_config.get("retry", {}) or {}
        
        max_attempts = (
            mcp_retry.get("max_attempts") or 
            self._global_retry.get("max_attempts") or 
            DEFAULT_MAX_ATTEMPTS
        )
        delay_seconds = (
            mcp_retry.get("delay_seconds") or 
            self._global_retry.get("delay_seconds") or 
            DEFAULT_DELAY_SECONDS
        )
        connection_max_age = (
            mcp_retry.get("connection_max_age_seconds") or 
            self._global_retry.get("connection_max_age_seconds") or 
            DEFAULT_CONNECTION_MAX_AGE
        )
        
        return max_attempts, delay_seconds, connection_max_age
    
    def _is_connection_error(self, error: Exception) -> bool:
        """
        Check if an error is a connection-related error (worth retrying).
        
        Args:
            error: The exception to check
            
        Returns:
            True if this is a connection error, False otherwise
        """
        connection_error_types = (
            ConnectionError,
            ConnectionRefusedError,
            ConnectionResetError,
            TimeoutError,
            OSError,
        )
        
        # Check exception type
        if isinstance(error, connection_error_types):
            return True
        
        # Check error message for common connection issues
        error_msg = str(error).lower()
        connection_keywords = [
            "connection refused",
            "connection reset",
            "connection closed",
            "connect timeout",
            "timed out",
            "network unreachable",
            "host unreachable",
            "no route to host",
            "broken pipe",
            "eof",
            "stream",
            "transport",
        ]
        
        return any(keyword in error_msg for keyword in connection_keywords)
    
    async def _invalidate_client(self, server_name: str):
        """
        Safely close and remove a client from cache.
        
        Args:
            server_name: Name of the server to invalidate
        """
        if server_name in self._client_cache:
            try:
                client = self._client_cache[server_name]
                await client.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(
                    "⚠️ Error closing stale connection",
                    server=server_name,
                    error=str(e),
                )
            finally:
                self._client_cache.pop(server_name, None)
                self._client_created_at.pop(server_name, None)
                logger.info(
                    "🗑️ Invalidated client connection",
                    server=server_name,
                )
        
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
        # Check if cached client exists and is not too old
        if server_name in self._client_cache:
            _, _, max_age = self._get_retry_config(server_name)
            created_at = self._client_created_at.get(server_name, 0)
            age = time.time() - created_at
            
            if age > max_age:
                logger.info(
                    "🔄 Connection too old, refreshing",
                    server=server_name,
                    age_seconds=round(age, 1),
                    max_age_seconds=max_age,
                )
                await self._invalidate_client(server_name)
            else:
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
            self._client_created_at[server_name] = time.time()  # Track creation time
            
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
    
    async def _fetch_tools_native(self, server_name: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        Fetch tools from FastMCP server using native MCP protocol with caching.
        
        Includes automatic retry with reconnection on connection failures.
        
        Args:
            server_name: Name of the MCP server
            use_cache: Whether to use cached tools (default: True)
            
        Returns:
            Dict with tools and server info
        """
        # Check cache first
        if use_cache and server_name in self._tool_cache:
            age = time.time() - self._tool_cache_timestamp.get(server_name, 0)
            if age < self.TOOL_CACHE_TTL:
                logger.info(
                    "✅ Using cached tools",
                    server=server_name,
                    cache_age_seconds=round(age, 1),
                )
                return self._tool_cache[server_name]
        
        logger.info(
            "🔍 Fetching fresh tools from FastMCP server",
            server=server_name,
        )
        
        max_attempts, delay_seconds, _ = self._get_retry_config(server_name)
        last_error = None
        
        for attempt in range(1, max_attempts + 1):
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
                    attempt=attempt,
                )
                
                result = {
                    "tools": filtered_tools,
                    "server_info": {
                        "name": server_name,
                        "protocol": "mcp",
                    },
                    "status": "healthy",
                    "last_check": datetime.utcnow().isoformat(),
                }
                
                # Cache the result
                self._tool_cache[server_name] = result
                self._tool_cache_timestamp[server_name] = time.time()
                
                return result
                
            except Exception as e:
                last_error = e
                is_conn_error = self._is_connection_error(e)
                
                logger.warning(
                    f"⚠️ Fetch tools failed (attempt {attempt}/{max_attempts})",
                    server=server_name,
                    error=str(e),
                    is_connection_error=is_conn_error,
                )
                
                # Only retry on connection errors
                if not is_conn_error:
                    break
                
                # If we have more attempts, invalidate and wait
                if attempt < max_attempts:
                    logger.info(
                        f"🔄 Reconnecting to MCP server for tool discovery",
                        server=server_name,
                        delay_seconds=delay_seconds,
                    )
                    await self._invalidate_client(server_name)
                    await asyncio.sleep(delay_seconds)
        
        # All attempts failed
        logger.error(
            "❌ Error fetching tools after all retries",
            server=server_name,
            max_attempts=max_attempts,
            error=str(last_error),
        )
        raise last_error
    
    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute a tool on an MCP server using native MCP protocol.
        
        Includes automatic retry with reconnection on connection failures.
        
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
        display_name = server_config.get("display_name", server_name)
        max_attempts, delay_seconds, _ = self._get_retry_config(server_name)
        
        logger.info(
            "🛠️ Calling tool on MCP server",
            server=server_name,
            tool=tool_name,
            protocol=protocol,
            arguments=arguments,
        )
        
        last_error = None
        reconnected = False
        
        for attempt in range(1, max_attempts + 1):
            try:
                client = await self._get_client(server_name)
                
                # Use native FastMCP call_tool method
                result = await client.call_tool(tool_name, arguments)
                
                log_msg = "✅ Tool execution successful"
                if reconnected:
                    log_msg = "✅ Tool execution successful (after reconnect)"
                    
                logger.info(
                    log_msg,
                    server=server_name,
                    tool=tool_name,
                    attempt=attempt,
                )
                
                response = {
                    "result": result.content if hasattr(result, 'content') else result,
                    "status": "success",
                    "server": server_name,
                    "tool": tool_name,
                    "protocol": protocol,
                    "timestamp": datetime.utcnow().isoformat(),
                }
                
                # Add reconnect notice if we had to retry
                if reconnected:
                    response["notice"] = f"⚠️ Reconnected to {display_name} after connection issue"
                
                return response
                
            except Exception as e:
                last_error = e
                is_conn_error = self._is_connection_error(e)
                
                logger.warning(
                    f"⚠️ Tool call failed (attempt {attempt}/{max_attempts})",
                    server=server_name,
                    tool=tool_name,
                    error=str(e),
                    is_connection_error=is_conn_error,
                )
                
                # Only retry on connection errors
                if not is_conn_error:
                    logger.error(
                        "❌ Non-connection error, not retrying",
                        server=server_name,
                        tool=tool_name,
                        error=str(e),
                    )
                    break
                
                # If we have more attempts, invalidate and wait
                if attempt < max_attempts:
                    logger.info(
                        f"🔄 Reconnecting to MCP server (retry {attempt}/{max_attempts - 1})",
                        server=server_name,
                        delay_seconds=delay_seconds,
                    )
                    await self._invalidate_client(server_name)
                    await asyncio.sleep(delay_seconds)
                    reconnected = True
        
        # All attempts failed
        error_msg = f"❌ {display_name} is unavailable after {max_attempts} attempts. Error: {str(last_error)}"
        logger.error(
            "❌ Tool execution failed after all retries",
            server=server_name,
            tool=tool_name,
            max_attempts=max_attempts,
            error=str(last_error),
        )
        
        # Return user-friendly error instead of raising
        return {
            "result": None,
            "status": "error",
            "error": error_msg,
            "server": server_name,
            "tool": tool_name,
            "protocol": protocol,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
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
    
    def invalidate_cache(self, server_name: Optional[str] = None):
        """
        Invalidate tool schema cache.
        
        Args:
            server_name: Specific server to invalidate, or None for all
        """
        if server_name:
            self._tool_cache.pop(server_name, None)
            self._tool_cache_timestamp.pop(server_name, None)
            logger.info("🗑️  Invalidated cache", server=server_name)
        else:
            self._tool_cache.clear()
            self._tool_cache_timestamp.clear()
            logger.info("🗑️  Invalidated all caches")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        current_time = time.time()
        stats = {
            "cached_servers": len(self._tool_cache),
            "servers": {}
        }
        
        for server_name, timestamp in self._tool_cache_timestamp.items():
            age = current_time - timestamp
            stats["servers"][server_name] = {
                "age_seconds": round(age, 1),
                "ttl_remaining": round(self.TOOL_CACHE_TTL - age, 1),
                "tool_count": len(self._tool_cache[server_name].get("tools", [])),
            }
        
        return stats
    
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
        self._tool_cache.clear()
        self._tool_cache_timestamp.clear()


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
