"""
MCP Registry Service - Database-Driven MCP Management

Features:
- Database-driven configuration (no YAML)
- Hot reload every 30 seconds
- Protocol support: HTTP, HTTP Streamable, SSE
- Authentication: Bearer token, API key
- Configurable retry logic per MCP
- Health checking and logging
- Connection age tracking (auto-reconnect after 10 min)
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import asyncio
import time
import httpx
from fastmcp import Client
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MCPServer, MCPTool, MCPHealthLog
from app.utils.logger import logger
from app.services.circuit_breaker import get_circuit_breaker

# Debug logging enabled via LOG_LEVEL env var


# Connection max age (10 minutes)
CONNECTION_MAX_AGE_SECONDS = 600


class BearerAuth(httpx.Auth):
    """Bearer token authentication for httpx."""
    def __init__(self, token: str):
        self.token = token
    
    def auth_flow(self, request):
        request.headers["Authorization"] = f"Bearer {self.token}"
        yield request


class MCPRegistry:
    """Database-driven MCP registry with hot reload."""
    
    def __init__(self):
        self.mcps: Dict[str, Client] = {}
        self.tools_cache: Dict[str, List[Dict]] = {}
        self.client_created_at: Dict[str, float] = {}
        self.last_check: Optional[datetime] = None
        self.circuit_breaker = get_circuit_breaker()
    
    async def load_from_database(self, db: AsyncSession):
        """Load all active MCPs from database."""
        # Load circuit breaker config
        await self.circuit_breaker.load_config(db)
        
        logger.debug("🔍 Querying database for active MCPs...")
        result = await db.execute(
            select(MCPServer).where(MCPServer.status == 'active')
        )
        mcps = result.scalars().all()
        
        logger.info(f"📦 Loading {len(mcps)} active MCPs from database")
        for mcp in mcps:
            logger.debug(f"  - {mcp.name}: {mcp.url} ({mcp.protocol})")
        
        for mcp in mcps:
            await self.load_mcp(mcp, db)
    
    async def load_mcp(self, mcp: MCPServer, db: AsyncSession):
        """Connect to MCP with retry logic and cache tools."""
        max_retries = mcp.max_retries or 2
        retry_delay = float(mcp.retry_delay_seconds or 1.0)
        start_time = time.time()
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.debug(f"🔌 Attempt {attempt}/{max_retries}: Connecting to {mcp.name}")
                logger.debug(f"  URL: {mcp.url}")
                logger.debug(f"  Protocol: {mcp.protocol}")
                logger.debug(f"  Auth: {mcp.auth_type}")
                logger.debug(f"  Timeout: {mcp.timeout_seconds}s")
                
                # Build authentication
                auth = None
                if mcp.auth_type and mcp.auth_config:
                    logger.debug(f"  🔐 Setting up {mcp.auth_type} authentication")
                    if mcp.auth_type == 'bearer':
                        token = mcp.auth_config.get('token') or mcp.auth_config.get('api_key')
                        if token:
                            auth = BearerAuth(token)
                            logger.debug(f"  ✅ Bearer token configured (length: {len(token)})")
                        else:
                            logger.warning(f"  ⚠️ Bearer auth configured but no token found")
                
                # Normalize URL
                url = mcp.url.rstrip('/')
                if not url.endswith('/mcp'):
                    url = f"{url}/mcp"
                    logger.debug(f"  🔗 Normalized URL: {url}")
                
                # Create client based on protocol
                protocol = (mcp.protocol or 'http').lower()
                logger.debug(f"  🌐 Creating {protocol} client...")
                
                if protocol in ('http', 'http_streamable', 'sse'):
                    client = Client(
                        transport=url,
                        auth=auth,
                        timeout=mcp.timeout_seconds or 30
                    )
                    logger.debug(f"  ✅ Client created")
                else:
                    raise ValueError(f"Unsupported protocol: {protocol}")
                
                # Initialize connection
                logger.debug(f"  🔌 Initializing connection...")
                await client.__aenter__()
                logger.debug(f"  ✅ Connection established")
                
                # Fetch tools
                logger.debug(f"  📋 Fetching tools...")
                tools_result = await client.list_tools()
                logger.debug(f"  ✅ Tools fetched")
                tools_list = tools_result.tools if hasattr(tools_result, 'tools') else tools_result
                
                # Convert to dict format
                tools = [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": tool.inputSchema.model_dump() if hasattr(tool.inputSchema, 'model_dump') else tool.inputSchema
                    }
                    for tool in tools_list
                ]
                
                # Store in registry
                logger.debug(f"  💾 Caching {len(tools)} tools")
                self.mcps[mcp.name] = client
                self.tools_cache[mcp.name] = tools
                self.client_created_at[mcp.name] = time.time()
                logger.debug(f"  ✅ Cached in registry")
                
                # Calculate response time
                response_time_ms = int((time.time() - start_time) * 1000)
                
                # Update database
                mcp.health_status = 'healthy'
                mcp.last_health_check = datetime.utcnow()
                mcp.error_count = 0
                await db.commit()
                
                # Record success in circuit breaker
                self.circuit_breaker.record_success(mcp.name)
                
                # Save tools to database
                logger.debug(f"  💾 Saving tools to database...")
                await self._save_tools_to_db(mcp.id, tools, db)
                logger.debug(f"  ✅ Tools saved to database")
                
                # Log success
                await self._log_health(
                    db, mcp.id, 'healthy', 
                    response_time_ms=response_time_ms,
                    event_type='load', 
                    metadata={'tool_count': len(tools), 'attempt': attempt}
                )
                
                logger.info(
                    f"✅ MCP loaded successfully",
                    server=mcp.name,
                    tools=len(tools),
                    response_time_ms=response_time_ms,
                    attempt=attempt
                )
                
                return  # Success, exit retry loop
                
            except Exception as e:
                error_msg = str(e)
                is_connection_error = self._is_connection_error(e)
                
                logger.warning(
                    f"⚠️ MCP load failed (attempt {attempt}/{max_retries})",
                    server=mcp.name,
                    error=error_msg,
                    is_connection_error=is_connection_error
                )
                
                # If last attempt or not a connection error, fail
                if attempt >= max_retries or not is_connection_error:
                    # Update database
                    mcp.health_status = 'error'
                    mcp.error_count = (mcp.error_count or 0) + 1
                    mcp.last_health_check = datetime.utcnow()
                    await db.commit()
                    
                    # Record failure in circuit breaker
                    self.circuit_breaker.record_failure(mcp.name)
                    
                    # Log error
                    await self._log_health(
                        db, mcp.id, 'error', 
                        error_message=error_msg, 
                        event_type='load',
                        metadata={'attempts': attempt}
                    )
                    
                    logger.error(
                        f"❌ MCP load failed after {attempt} attempts",
                        server=mcp.name,
                        error=error_msg
                    )
                    return
                
                # Wait before retry
                await asyncio.sleep(retry_delay)
    
    async def unload_mcp(self, mcp_name: str, db: AsyncSession):
        """Disconnect and remove MCP from registry."""
        if mcp_name in self.mcps:
            try:
                client = self.mcps[mcp_name]
                await client.__aexit__(None, None, None)
                logger.info(f"🔌 Disconnected MCP", server=mcp_name)
            except Exception as e:
                logger.warning(f"⚠️ Error disconnecting MCP", server=mcp_name, error=str(e))
            finally:
                del self.mcps[mcp_name]
                self.tools_cache.pop(mcp_name, None)
                self.client_created_at.pop(mcp_name, None)
    
    async def reload_if_changed(self, db: AsyncSession):
        """Check database for changes and hot reload."""
        # Get active MCPs from database
        result = await db.execute(
            select(MCPServer).where(MCPServer.status == 'active')
        )
        db_mcps = result.scalars().all()
        
        current_names = set(self.mcps.keys())
        db_names = set(mcp.name for mcp in db_mcps)
        
        # Load new MCPs
        new_mcps = db_names - current_names
        for mcp in db_mcps:
            if mcp.name in new_mcps:
                logger.info(f"🆕 New MCP detected", server=mcp.name)
                await self.load_mcp(mcp, db)
        
        # Unload removed MCPs
        removed_mcps = current_names - db_names
        for name in removed_mcps:
            logger.info(f"🗑️ MCP removed", server=name)
            await self.unload_mcp(name, db)
        
        # Reload changed MCPs (check updated_at)
        if self.last_check:
            for mcp in db_mcps:
                if mcp.updated_at > self.last_check and mcp.name in current_names:
                    logger.info(f"🔄 MCP config changed", server=mcp.name)
                    await self.unload_mcp(mcp.name, db)
                    await self.load_mcp(mcp, db)
        
        # Check connection age and reconnect if stale
        current_time = time.time()
        for mcp in db_mcps:
            if mcp.name in self.client_created_at:
                age = current_time - self.client_created_at[mcp.name]
                if age > CONNECTION_MAX_AGE_SECONDS:
                    logger.info(
                        f"🔄 Connection too old, reconnecting",
                        server=mcp.name,
                        age_seconds=int(age)
                    )
                    await self.unload_mcp(mcp.name, db)
                    await self.load_mcp(mcp, db)
        
        self.last_check = datetime.utcnow()
    
    async def call_tool(self, mcp_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute tool on MCP."""
        # Check circuit breaker first
        if self.circuit_breaker.is_open(mcp_name):
            retry_after = self.circuit_breaker.get_retry_after(mcp_name)
            return {
                "status": "unavailable",
                "error": f"MCP '{mcp_name}' temporarily unavailable (circuit breaker open)",
                "circuit_state": self.circuit_breaker.get_state(mcp_name),
                "retry_after_seconds": retry_after
            }
        
        if mcp_name not in self.mcps:
            return {
                "status": "error",
                "error": f"MCP '{mcp_name}' not loaded"
            }
        
        try:
            client = self.mcps[mcp_name]
            result = await client.call_tool(tool_name, arguments)
            
            # Record success
            self.circuit_breaker.record_success(mcp_name)
            
            return {
                "status": "success",
                "result": result.content if hasattr(result, 'content') else result,
                "server": mcp_name,
                "tool": tool_name
            }
        except Exception as e:
            # Record failure
            self.circuit_breaker.record_failure(mcp_name)
            
            logger.error(f"❌ Tool call failed", server=mcp_name, tool=tool_name, error=str(e))
            return {
                "status": "error",
                "error": str(e),
                "server": mcp_name,
                "tool": tool_name,
                "circuit_state": self.circuit_breaker.get_state(mcp_name)
            }
    
    async def health_check(self, mcp_name: str, db: AsyncSession) -> Dict[str, Any]:
        """Check health of MCP by attempting to list tools."""
        if mcp_name not in self.mcps:
            return {
                "healthy": False,
                "error": f"MCP '{mcp_name}' not loaded"
            }
        
        try:
            start_time = time.time()
            client = self.mcps[mcp_name]
            tools_result = await client.list_tools()
            response_time_ms = int((time.time() - start_time) * 1000)
            
            tool_count = len(tools_result.tools) if hasattr(tools_result, 'tools') else 0
            
            # Get MCP from database
            result = await db.execute(
                select(MCPServer).where(MCPServer.name == mcp_name)
            )
            mcp = result.scalar_one_or_none()
            
            if mcp:
                # Log health check
                await self._log_health(
                    db, mcp.id, 'healthy',
                    response_time_ms=response_time_ms,
                    event_type='health_check',
                    metadata={'tool_count': tool_count}
                )
            
            return {
                "healthy": True,
                "tool_count": tool_count,
                "response_time_ms": response_time_ms,
                "last_check": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Health check failed", server=mcp_name, error=str(e))
            return {
                "healthy": False,
                "error": str(e),
                "last_check": datetime.utcnow().isoformat()
            }
    
    def get_tools(self, mcp_name: Optional[str] = None) -> Dict[str, List[Dict]]:
        """Get cached tools."""
        if mcp_name:
            return {mcp_name: self.tools_cache.get(mcp_name, [])}
        return self.tools_cache
    
    def get_loaded_mcps(self) -> List[str]:
        """Get list of loaded MCP names."""
        return list(self.mcps.keys())
    
    def _is_connection_error(self, error: Exception) -> bool:
        """Check if error is connection-related (worth retrying)."""
        connection_error_types = (
            ConnectionError,
            ConnectionRefusedError,
            ConnectionResetError,
            TimeoutError,
            OSError,
        )
        
        if isinstance(error, connection_error_types):
            return True
        
        error_msg = str(error).lower()
        connection_keywords = [
            "connection refused", "connection reset", "connection closed",
            "connect timeout", "timed out", "network unreachable",
            "host unreachable", "no route to host", "broken pipe"
        ]
        
        return any(keyword in error_msg for keyword in connection_keywords)
    
    async def _save_tools_to_db(self, mcp_id: int, tools: List[Dict], db: AsyncSession):
        """Save tools to database."""
        try:
            # Delete old tools
            await db.execute(
                delete(MCPTool).where(MCPTool.mcp_server_id == mcp_id)
            )
            
            # Insert new tools
            for tool in tools:
                db_tool = MCPTool(
                    mcp_server_id=mcp_id,
                    name=tool['name'],
                    description=tool.get('description'),
                    input_schema=tool.get('inputSchema')
                )
                db.add(db_tool)
            
            await db.commit()
        except Exception as e:
            logger.warning(f"Failed to save tools to database", mcp_id=mcp_id, error=str(e))
            try:
                await db.rollback()
            except:
                pass
    
    async def _log_health(
        self, 
        db: AsyncSession, 
        mcp_id: int, 
        status: str,
        response_time_ms: Optional[int] = None,
        error_message: Optional[str] = None,
        event_type: str = 'health_check',
        metadata: Optional[Dict] = None
    ):
        """Log health event."""
        try:
            log = MCPHealthLog(
                mcp_server_id=mcp_id,
                status=status,
                response_time_ms=response_time_ms,
                error_message=error_message,
                event_type=event_type,
                metadata=metadata
            )
            db.add(log)
            await db.commit()
        except Exception as e:
            logger.warning(f"Failed to log health event", mcp_id=mcp_id, error=str(e))
            try:
                await db.rollback()
            except:
                pass
    
    async def close_all(self):
        """Close all MCP connections."""
        logger.info("🔌 Closing all MCP connections")
        for name, client in self.mcps.items():
            try:
                await client.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"Error closing {name}", error=str(e))
        self.mcps.clear()
        self.tools_cache.clear()
        self.client_created_at.clear()


# Global instance
mcp_registry = MCPRegistry()


def get_mcp_registry() -> MCPRegistry:
    """Get global MCP registry instance."""
    return mcp_registry
