"""
Audit Service

Handles logging of all user interactions, tool calls, and system events.
"""

import time
from typing import Dict, List, Optional, Any
from datetime import datetime

from app.utils.logger import logger


class AuditService:
    """Service for audit logging to PostgreSQL."""
    
    def __init__(self):
        """Initialize audit service."""
        pass
    
    def _get_engine(self):
        """Get the database engine, checking if it's initialized."""
        from app.database import engine
        return engine
    
    async def log_chat_request(
        self,
        user_id: str,
        message: str,
        result: Dict[str, Any],
        duration_ms: int,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        slack_user_id: Optional[str] = None,
        slack_channel: Optional[str] = None,
        slack_message_ts: Optional[str] = None,
        slack_thread_ts: Optional[str] = None,
    ) -> int:
        """
        Log a chat request with full details.
        
        Args:
            user_id: User email address
            message: User's question/message
            result: Result from LLM service (answer, tool_calls, etc.)
            duration_ms: Request duration in milliseconds
            ip_address: Client IP address
            user_agent: Client user agent
            slack_user_id: Slack user ID (if from Slack)
            slack_channel: Slack channel ID (if from Slack)
            slack_message_ts: Slack message timestamp
            slack_thread_ts: Slack thread timestamp
            
        Returns:
            Audit log ID
        """
        try:
            # Extract data from result
            answer = result.get("answer", "")
            tool_calls_count = result.get("tool_calls", 0)
            tools_used = result.get("tools_used", [])
            iterations = result.get("iterations", 1)
            warning = result.get("warning")
            status = "success"
            
            if warning:
                status = "warning"
            
            # Extract MCPs accessed from tools_used
            mcps_accessed = list(set([
                tool.split(".")[0] for tool in tools_used if "." in tool
            ]))
            
            # Create message preview (first 197 chars + "..." = 200 total)
            message_preview = message[:197] + "..." if len(message) > 197 else message
            
            # Create response preview (first 500 chars)
            response_preview = answer[:500] + "..." if len(answer) > 500 else answer
            
            # Estimate cost (rough estimation)
            # Note: Real cost comes from Anthropic API response headers
            tokens_input = result.get("tokens_input", 0)
            tokens_output = result.get("tokens_output", 0)
            tokens_cached = result.get("tokens_cached", 0)
            cost_estimate = self._estimate_cost(tokens_input, tokens_output, tokens_cached)
            
            # Check if database is initialized
            engine = self._get_engine()
            if engine is None:
                logger.warning("⚠️ Database not initialized, skipping audit log")
                return -1
            
            # Use SQLAlchemy engine for raw SQL
            from sqlalchemy import text
            async with engine.begin() as conn:
                # Auto-create user if doesn't exist (upsert pattern)
                # Extract name from email (before @)
                await conn.execute(
                    text("""
                        INSERT INTO users (email, name, is_super_admin, created_at)
                        VALUES (:email, SPLIT_PART(:email_for_name, '@', 1), false, NOW())
                        ON CONFLICT (email) DO NOTHING
                    """),
                    {"email": user_id, "email_for_name": user_id}
                )
                
                # Now insert audit log
                result_row = await conn.execute(
                    text("""
                        INSERT INTO audit_logs (
                            user_id,
                            request_type,
                            message,
                            message_preview,
                            iterations,
                            tool_calls_count,
                            tools_used,
                            mcps_accessed,
                            duration_ms,
                            tokens_input,
                            tokens_output,
                            tokens_cached,
                            cost_estimate,
                            status,
                            warning,
                            response_preview,
                            ip_address,
                            user_agent,
                            slack_user_id,
                            slack_channel,
                            slack_message_ts,
                            slack_thread_ts,
                            success,
                            created_at
                        ) VALUES (
                            (SELECT id FROM users WHERE email = :user_id),
                            :request_type, :message, :message_preview, :iterations,
                            :tool_calls_count, :tools_used, :mcps_accessed, :duration_ms,
                            :tokens_input, :tokens_output, :tokens_cached, :cost_estimate,
                            :status, :warning, :response_preview, :ip_address, :user_agent,
                            :slack_user_id, :slack_channel, :slack_message_ts, :slack_thread_ts,
                            :success, NOW()
                        ) RETURNING id
                    """),
                    {
                        "user_id": user_id,
                        "request_type": "chat",
                        "message": message,
                        "message_preview": message_preview,
                        "iterations": iterations,
                        "tool_calls_count": tool_calls_count,
                        "tools_used": tools_used,
                        "mcps_accessed": mcps_accessed,
                        "duration_ms": duration_ms,
                        "tokens_input": tokens_input,
                        "tokens_output": tokens_output,
                        "tokens_cached": tokens_cached,
                        "cost_estimate": cost_estimate,
                        "status": status,
                        "warning": warning,
                        "response_preview": response_preview,
                        "ip_address": ip_address,
                        "user_agent": user_agent,
                        "slack_user_id": slack_user_id,
                        "slack_channel": slack_channel,
                        "slack_message_ts": slack_message_ts,
                        "slack_thread_ts": slack_thread_ts,
                        "success": True
                    }
                )
                audit_id = result_row.fetchone()[0]
            
            logger.info(
                "📝 Audit log created",
                audit_id=audit_id,
                user=user_id,
                tools=tool_calls_count,
                iterations=iterations,
                cost=f"${cost_estimate:.4f}",
            )
            
            return audit_id
            
        except Exception as e:
            # Don't fail the request if audit logging fails
            logger.error(
                "❌ Failed to create audit log",
                user=user_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            return -1
    
    async def log_error(
        self,
        user_id: str,
        message: str,
        error_message: str,
        duration_ms: int,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> int:
        """
        Log an error/failed request.
        
        Args:
            user_id: User email address
            message: User's question/message
            error_message: Error message
            duration_ms: Request duration in milliseconds
            ip_address: Client IP address
            user_agent: Client user agent
            
        Returns:
            Audit log ID
        """
        try:
            # Create message preview (first 197 chars + "..." = 200 total)
            message_preview = message[:197] + "..." if len(message) > 197 else message
            
            # Check if database is initialized
            engine = self._get_engine()
            if engine is None:
                logger.warning("⚠️ Database not initialized, skipping error audit log")
                return -1
            
            # Use SQLAlchemy engine for raw SQL
            from sqlalchemy import text
            async with engine.begin() as conn:
                # Auto-create user if doesn't exist
                await conn.execute(
                    text("""
                        INSERT INTO users (email, name, is_super_admin, created_at)
                        VALUES (:email, SPLIT_PART(:email_for_name, '@', 1), false, NOW())
                        ON CONFLICT (email) DO NOTHING
                    """),
                    {"email": user_id, "email_for_name": user_id}
                )
                
                # Insert error audit log
                result_row = await conn.execute(
                    text("""
                        INSERT INTO audit_logs (
                            user_id,
                            request_type,
                            message,
                            message_preview,
                            iterations,
                            tool_calls_count,
                            duration_ms,
                            status,
                            error_message,
                            response_preview,
                            ip_address,
                            user_agent,
                            success,
                            created_at
                        ) VALUES (
                            (SELECT id FROM users WHERE email = :user_id),
                            :request_type, :message, :message_preview, :iterations,
                            :tool_calls_count, :duration_ms, :status, :error_message,
                            :response_preview, :ip_address, :user_agent, :success, NOW()
                        ) RETURNING id
                    """),
                    {
                        "user_id": user_id,
                        "request_type": "chat",
                        "message": message,
                        "message_preview": message_preview,
                        "iterations": 0,
                        "tool_calls_count": 0,
                        "duration_ms": duration_ms,
                        "status": "error",
                        "error_message": error_message,
                        "response_preview": error_message[:500],
                        "ip_address": ip_address,
                        "user_agent": user_agent,
                        "success": False
                    }
                )
                audit_id = result_row.fetchone()[0]
            
            logger.info(
                "📝 Error audit log created",
                audit_id=audit_id,
                user=user_id,
                error_preview=error_message[:50],
            )
            
            return audit_id
            
        except Exception as e:
            logger.error(
                "❌ Failed to create error audit log",
                user=user_id,
                error=str(e),
            )
            return -1
    
    def _estimate_cost(
        self,
        tokens_input: int,
        tokens_output: int,
        tokens_cached: int
    ) -> float:
        """
        Estimate cost based on token usage.
        
        Claude 3.5 Haiku pricing (as of Dec 2024):
        - Input: $0.80 per million tokens
        - Output: $4.00 per million tokens
        - Cached input: $0.08 per million tokens (90% discount)
        
        Args:
            tokens_input: Input tokens (not cached)
            tokens_output: Output tokens
            tokens_cached: Cached input tokens
            
        Returns:
            Estimated cost in USD
        """
        # Pricing per million tokens
        PRICE_INPUT = 0.80
        PRICE_OUTPUT = 4.00
        PRICE_CACHED = 0.08
        
        cost_input = (tokens_input / 1_000_000) * PRICE_INPUT
        cost_output = (tokens_output / 1_000_000) * PRICE_OUTPUT
        cost_cached = (tokens_cached / 1_000_000) * PRICE_CACHED
        
        total_cost = cost_input + cost_output + cost_cached
        
        return round(total_cost, 6)
    
    async def get_logs(
        self,
        user_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None,
        mcp_name: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query audit logs with filters.
        
        Args:
            user_id: Filter by user email (optional)
            limit: Maximum number of results
            offset: Pagination offset
            status: Filter by status (success, error, warning)
            mcp_name: Filter by MCP name
            start_date: Filter by start date
            end_date: Filter by end date
            
        Returns:
            List of audit log records
        """
        try:
            # Check if database is initialized
            engine = self._get_engine()
            if engine is None:
                logger.warning("⚠️ Database not initialized, returning empty audit logs")
                return []
            
            from sqlalchemy import text
            
            # Build dynamic query
            query_str = """
                SELECT 
                    a.id,
                    u.email as user_email,
                    a.request_type,
                    a.message_preview,
                    a.iterations,
                    a.tool_calls_count,
                    a.tools_used,
                    a.mcps_accessed,
                    a.duration_ms,
                    a.cost_estimate,
                    a.status,
                    a.warning,
                    a.created_at
                FROM audit_logs a
                LEFT JOIN users u ON a.user_id = u.id
                WHERE 1=1
            """
            
            params = {}
            
            if user_id:
                query_str += " AND u.email = :user_id"
                params["user_id"] = user_id
            
            if status:
                query_str += " AND a.status = :status"
                params["status"] = status
            
            if mcp_name:
                query_str += " AND :mcp_name = ANY(a.mcps_accessed)"
                params["mcp_name"] = mcp_name
            
            if start_date:
                query_str += " AND a.created_at >= :start_date"
                params["start_date"] = start_date
            
            if end_date:
                query_str += " AND a.created_at <= :end_date"
                params["end_date"] = end_date
            
            query_str += " ORDER BY a.created_at DESC LIMIT :limit OFFSET :offset"
            params["limit"] = limit
            params["offset"] = offset
            
            async with engine.connect() as conn:
                result = await conn.execute(text(query_str), params)
                rows = result.fetchall()
            
            return [dict(row._mapping) for row in rows]
            
        except Exception as e:
            logger.error("❌ Failed to query audit logs", error=str(e))
            return []
    
    async def get_stats(
        self,
        user_id: Optional[str] = None,
        days: int = 7,
    ) -> Dict[str, Any]:
        """
        Get usage statistics.
        
        Args:
            user_id: Filter by user (optional, None = all users)
            days: Number of days to include
            
        Returns:
            Statistics dict
        """
        try:
            # Check if database is initialized
            engine = self._get_engine()
            if engine is None:
                logger.warning("⚠️ Database not initialized, returning empty audit stats")
                return {}
            
            from sqlalchemy import text
            
            # Build query with days as integer (can't bind in INTERVAL)
            query_str = f"""
                SELECT 
                    COUNT(*) as total_requests,
                    COALESCE(SUM(tool_calls_count), 0) as total_tool_calls,
                    COALESCE(AVG(iterations), 0) as avg_iterations,
                    COALESCE(AVG(duration_ms), 0) as avg_duration_ms,
                    COALESCE(SUM(cost_estimate), 0) as total_cost,
                    COUNT(*) FILTER (WHERE status = 'error') as error_count,
                    COUNT(*) FILTER (WHERE status = 'success') as success_count,
                    COUNT(*) FILTER (WHERE status = 'warning') as warning_count
                FROM audit_logs a
                LEFT JOIN users u ON a.user_id = u.id
                WHERE a.created_at >= NOW() - INTERVAL '{days} day'
            """
            
            params = {}
            
            if user_id:
                query_str += " AND u.email = :user_id"
                params["user_id"] = user_id
            
            async with engine.connect() as conn:
                result = await conn.execute(text(query_str), params)
                row = result.fetchone()
            
            return dict(row._mapping) if row else {}
            
        except Exception as e:
            logger.error("❌ Failed to get audit stats", error=str(e))
            return {}


# Global audit service instance
_audit_service: Optional[AuditService] = None


def get_audit_service() -> AuditService:
    """
    Get or create the global audit service instance.
    
    Returns:
        AuditService instance
    """
    global _audit_service
    if _audit_service is None:
        _audit_service = AuditService()
    return _audit_service
