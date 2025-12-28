# tools/analytics_tools.py
"""
OMNI2 Analytics Tools - Admin-only tools for monitoring system usage, costs, and performance.
All tools query the audit_logs table and related views.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from mcp_app import mcp
from db import db

logger = logging.getLogger(__name__)

# ============================================================================
# 💰 Cost & Budget Tracking
# ============================================================================

@mcp.tool(description="OMNI2 Analytics: Get total cost summary from audit logs by period (today/week/month/all)")
async def get_cost_summary(
    period: str = "week",
    user_id: Optional[int] = None,
    group_by: Optional[str] = None
) -> str:
    """
    Get cost summary for OMNI2 system usage.
    
    Args:
        period: Time period - 'today', 'week', 'month', or 'all'
        user_id: Optional filter by specific user ID
        group_by: Optional grouping - 'user', 'mcp', 'day'
    
    Returns:
        Formatted cost summary with total spend and breakdown
    """
    try:
        await db.connect()
        
        # Build date filter
        date_filter = ""
        if period == "today":
            date_filter = "AND created_at >= CURRENT_DATE"
        elif period == "week":
            date_filter = "AND created_at >= CURRENT_DATE - INTERVAL '7 days'"
        elif period == "month":
            date_filter = "AND created_at >= DATE_TRUNC('month', CURRENT_DATE)"
        
        # Build user filter
        user_filter = f"AND user_id = {user_id}" if user_id else ""
        
        # Build query based on grouping
        if group_by == "user":
            query = f"""
                SELECT 
                    u.email,
                    u.name,
                    COUNT(*) as query_count,
                    SUM(cost_estimate) as total_cost,
                    SUM(tokens_input) as total_input_tokens,
                    SUM(tokens_output) as total_output_tokens
                FROM audit_logs al
                LEFT JOIN users u ON al.user_id = u.id
                WHERE cost_estimate IS NOT NULL {date_filter} {user_filter}
                GROUP BY u.email, u.name
                ORDER BY total_cost DESC
                LIMIT 20
            """
        elif group_by == "mcp":
            query = f"""
                SELECT 
                    unnest(mcps_accessed) as mcp_name,
                    COUNT(*) as query_count,
                    SUM(cost_estimate) as total_cost
                FROM audit_logs
                WHERE mcps_accessed IS NOT NULL {date_filter} {user_filter}
                GROUP BY mcp_name
                ORDER BY total_cost DESC
            """
        elif group_by == "day":
            query = f"""
                SELECT 
                    DATE(created_at) as date,
                    COUNT(*) as query_count,
                    SUM(cost_estimate) as total_cost
                FROM audit_logs
                WHERE cost_estimate IS NOT NULL {date_filter} {user_filter}
                GROUP BY DATE(created_at)
                ORDER BY date DESC
                LIMIT 30
            """
        else:
            # Overall summary
            query = f"""
                SELECT 
                    COUNT(*) as total_queries,
                    SUM(cost_estimate) as total_cost,
                    AVG(cost_estimate) as avg_cost_per_query,
                    SUM(tokens_input) as total_input_tokens,
                    SUM(tokens_output) as total_output_tokens,
                    SUM(tokens_cached) as total_cached_tokens
                FROM audit_logs
                WHERE cost_estimate IS NOT NULL {date_filter} {user_filter}
            """
        
        rows = await db.fetch_all(query)
        
        if not rows:
            return f"No cost data found for period: {period}"
        
        # Format response
        if group_by:
            result = f"📊 **OMNI2 Cost Summary ({period})** - Grouped by {group_by}\n\n"
            for row in rows:
                if group_by == "user":
                    result += f"• {row['name']} ({row['email']}): ${row['total_cost']:.4f} ({row['query_count']} queries)\n"
                elif group_by == "mcp":
                    result += f"• {row['mcp_name']}: ${row['total_cost']:.4f} ({row['query_count']} queries)\n"
                elif group_by == "day":
                    result += f"• {row['date']}: ${row['total_cost']:.4f} ({row['query_count']} queries)\n"
        else:
            row = rows[0]
            result = f"""📊 **OMNI2 Cost Summary ({period})**

💰 Total Cost: ${row['total_cost']:.4f}
📊 Total Queries: {row['total_queries']}
📈 Avg Cost/Query: ${row['avg_cost_per_query']:.4f}

**Token Usage:**
• Input: {row['total_input_tokens']:,}
• Output: {row['total_output_tokens']:,}
• Cached: {row['total_cached_tokens']:,} (90% discount)
"""
        
        return result
        
    except Exception as e:
        logger.error(f"Error in get_cost_summary: {e}")
        return f"❌ Error fetching cost data: {str(e)}"


@mcp.tool(description="OMNI2 Analytics: Get top N most expensive queries from audit logs")
async def get_top_expensive_queries(limit: int = 10, period: str = "week") -> str:
    """
    Find the most expensive queries by LLM cost.
    
    Args:
        limit: Number of queries to return (default 10)
        period: Time period - 'today', 'week', 'month', or 'all'
    
    Returns:
        List of most expensive queries with cost and details
    """
    try:
        await db.connect()
        
        date_filter = ""
        if period == "today":
            date_filter = "AND al.created_at >= CURRENT_DATE"
        elif period == "week":
            date_filter = "AND al.created_at >= CURRENT_DATE - INTERVAL '7 days'"
        elif period == "month":
            date_filter = "AND al.created_at >= DATE_TRUNC('month', CURRENT_DATE)"
        
        query = f"""
            SELECT 
                al.id,
                u.email as user_email,
                al.message_preview,
                al.cost_estimate,
                al.iterations,
                al.tool_calls_count,
                al.tokens_input,
                al.tokens_output,
                al.duration_ms,
                al.created_at
            FROM audit_logs al
            LEFT JOIN users u ON al.user_id = u.id
            WHERE al.cost_estimate IS NOT NULL {date_filter}
            ORDER BY al.cost_estimate DESC
            LIMIT {limit}
        """
        
        rows = await db.fetch_all(query)
        
        if not rows:
            return f"No expensive queries found for period: {period}"
        
        result = f"💸 **Top {len(rows)} Most Expensive Queries ({period})**\n\n"
        for i, row in enumerate(rows, 1):
            result += f"""**{i}. ${row['cost_estimate']:.4f}** - {row['user_email']}
   Query: "{row['message_preview']}"
   Details: {row['iterations']} iterations, {row['tool_calls_count']} tools, {row['duration_ms']}ms
   Tokens: {row['tokens_input']} in / {row['tokens_output']} out
   Time: {row['created_at'].strftime('%Y-%m-%d %H:%M')}

"""
        
        return result
        
    except Exception as e:
        logger.error(f"Error in get_top_expensive_queries: {e}")
        return f"❌ Error: {str(e)}"


# ============================================================================
# ⚡ Performance Metrics
# ============================================================================

@mcp.tool(description="OMNI2 Analytics: Get slow queries exceeding minimum duration threshold")
async def get_slow_queries(min_duration_ms: int = 5000, limit: int = 20, period: str = "week") -> str:
    """
    Find queries that took longer than specified duration.
    
    Args:
        min_duration_ms: Minimum duration in milliseconds (default 5000ms = 5s)
        limit: Number of results to return
        period: Time period filter
    
    Returns:
        List of slow queries with performance details
    """
    try:
        await db.connect()
        
        date_filter = ""
        if period == "today":
            date_filter = "AND created_at >= CURRENT_DATE"
        elif period == "week":
            date_filter = "AND created_at >= CURRENT_DATE - INTERVAL '7 days'"
        elif period == "month":
            date_filter = "AND created_at >= DATE_TRUNC('month', CURRENT_DATE)"
        
        query = f"""
            SELECT 
                al.id,
                u.email as user_email,
                al.message_preview,
                al.duration_ms,
                al.iterations,
                al.tool_calls_count,
                array_to_string(al.mcps_accessed, ', ') as mcps_used,
                array_to_string(al.tools_used, ', ') as tools_used,
                al.created_at
            FROM audit_logs al
            LEFT JOIN users u ON al.user_id = u.id
            WHERE al.duration_ms >= {min_duration_ms} {date_filter}
            ORDER BY al.duration_ms DESC
            LIMIT {limit}
        """
        
        rows = await db.fetch_all(query)
        
        if not rows:
            return f"✅ No slow queries found (>{min_duration_ms}ms) for period: {period}"
        
        result = f"🐌 **Slow Queries (>{min_duration_ms}ms) - {period}**\n\n"
        for row in rows:
            result += f"""• **{row['duration_ms']}ms** - {row['user_email']}
  Query: "{row['message_preview']}"
  Iterations: {row['iterations']}, Tools: {row['tool_calls_count']}
  MCPs: {row['mcps_used'] or 'none'}
  Time: {row['created_at'].strftime('%Y-%m-%d %H:%M')}

"""
        
        return result
        
    except Exception as e:
        logger.error(f"Error in get_slow_queries: {e}")
        return f"❌ Error: {str(e)}"


@mcp.tool(description="OMNI2 Analytics: Analyze queries with high iteration counts (agentic loop efficiency)")
async def get_iteration_analysis(min_iterations: int = 5, period: str = "week") -> str:
    """
    Find queries that required many agentic loop iterations.
    
    Args:
        min_iterations: Minimum iterations to flag (default 5)
        period: Time period filter
    
    Returns:
        Analysis of high-iteration queries
    """
    try:
        await db.connect()
        
        date_filter = ""
        if period == "today":
            date_filter = "AND created_at >= CURRENT_DATE"
        elif period == "week":
            date_filter = "AND created_at >= CURRENT_DATE - INTERVAL '7 days'"
        elif period == "month":
            date_filter = "AND created_at >= DATE_TRUNC('month', CURRENT_DATE)"
        
        query = f"""
            SELECT 
                al.id,
                u.email as user_email,
                al.message_preview,
                al.iterations,
                al.tool_calls_count,
                al.warning,
                array_to_string(al.tools_used, ', ') as tools_used,
                al.duration_ms,
                al.created_at
            FROM audit_logs al
            LEFT JOIN users u ON al.user_id = u.id
            WHERE al.iterations >= {min_iterations} {date_filter}
            ORDER BY al.iterations DESC, al.created_at DESC
            LIMIT 20
        """
        
        rows = await db.fetch_all(query)
        
        if not rows:
            return f"✅ No high-iteration queries found (>{min_iterations}) for period: {period}"
        
        result = f"🔄 **High Iteration Queries (>={min_iterations}) - {period}**\n\n"
        for row in rows:
            warning_text = f" ⚠️ {row['warning']}" if row['warning'] else ""
            result += f"""• **{row['iterations']} iterations** - {row['user_email']}{warning_text}
  Query: "{row['message_preview']}"
  Tools called: {row['tool_calls_count']} ({row['tools_used'] or 'none'})
  Duration: {row['duration_ms']}ms
  Time: {row['created_at'].strftime('%Y-%m-%d %H:%M')}

"""
        
        return result
        
    except Exception as e:
        logger.error(f"Error in get_iteration_analysis: {e}")
        return f"❌ Error: {str(e)}"


# ============================================================================
# 🐛 Error Analysis
# ============================================================================

@mcp.tool(description="OMNI2 Analytics: Get error summary and failure rates")
async def get_error_summary(period: str = "week", mcp_name: Optional[str] = None, tool_name: Optional[str] = None) -> str:
    """
    Analyze errors and failure rates.
    
    Args:
        period: Time period - 'today', 'week', 'month', or 'all'
        mcp_name: Optional filter by specific MCP
        tool_name: Optional filter by specific tool
    
    Returns:
        Error analysis with rates and common patterns
    """
    try:
        await db.connect()
        
        date_filter = ""
        if period == "today":
            date_filter = "AND created_at >= CURRENT_DATE"
        elif period == "week":
            date_filter = "AND created_at >= CURRENT_DATE - INTERVAL '7 days'"
        elif period == "month":
            date_filter = "AND created_at >= DATE_TRUNC('month', CURRENT_DATE)"
        
        mcp_filter = f"AND '{mcp_name}' = ANY(mcps_accessed)" if mcp_name else ""
        tool_filter = f"AND '{tool_name}' = ANY(tools_used)" if tool_name else ""
        
        # Overall error rate
        summary_query = f"""
            SELECT 
                COUNT(*) as total_requests,
                SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as error_count,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count,
                ROUND(100.0 * SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) / COUNT(*), 2) as error_rate
            FROM audit_logs
            WHERE 1=1 {date_filter} {mcp_filter} {tool_filter}
        """
        
        summary = await db.fetch_one(summary_query)
        
        # Top error messages
        errors_query = f"""
            SELECT 
                error_message,
                COUNT(*) as occurrences,
                array_agg(DISTINCT user_id) as affected_users
            FROM audit_logs
            WHERE status = 'error' 
                AND error_message IS NOT NULL 
                {date_filter} {mcp_filter} {tool_filter}
            GROUP BY error_message
            ORDER BY occurrences DESC
            LIMIT 10
        """
        
        errors = await db.fetch_all(errors_query)
        
        result = f"""🐛 **OMNI2 Error Analysis ({period})**

**Overall Statistics:**
• Total Requests: {summary['total_requests']}
• Errors: {summary['error_count']}
• Success: {summary['success_count']}
• Error Rate: {summary['error_rate']}%

"""
        
        if errors:
            result += "**Top Error Messages:**\n"
            for i, error in enumerate(errors, 1):
                result += f"{i}. {error['error_message'][:100]} (× {error['occurrences']})\n"
        else:
            result += "✅ No errors found!\n"
        
        return result
        
    except Exception as e:
        logger.error(f"Error in get_error_summary: {e}")
        return f"❌ Error: {str(e)}"


@mcp.tool(description="OMNI2 Analytics: Get recent failed queries with error details")
async def get_failed_queries(limit: int = 10, period: str = "week") -> str:
    """
    Get recent failed queries with full error details.
    
    Args:
        limit: Number of failed queries to return
        period: Time period filter
    
    Returns:
        List of failed queries with error messages
    """
    try:
        await db.connect()
        
        date_filter = ""
        if period == "today":
            date_filter = "AND created_at >= CURRENT_DATE"
        elif period == "week":
            date_filter = "AND created_at >= CURRENT_DATE - INTERVAL '7 days'"
        elif period == "month":
            date_filter = "AND created_at >= DATE_TRUNC('month', CURRENT_DATE)"
        
        query = f"""
            SELECT 
                al.id,
                u.email as user_email,
                al.message_preview,
                al.error_message,
                al.error_id,
                array_to_string(al.mcps_accessed, ', ') as mcps_used,
                array_to_string(al.tools_used, ', ') as tools_used,
                al.iterations,
                al.created_at
            FROM audit_logs al
            LEFT JOIN users u ON al.user_id = u.id
            WHERE al.status = 'error' {date_filter}
            ORDER BY al.created_at DESC
            LIMIT {limit}
        """
        
        rows = await db.fetch_all(query)
        
        if not rows:
            return f"✅ No failed queries found for period: {period}"
        
        result = f"❌ **Recent Failed Queries ({period})**\n\n"
        for i, row in enumerate(rows, 1):
            result += f"""**{i}. Audit ID: {row['id']}** - {row['user_email']}
   Query: "{row['message_preview']}"
   Error: {row['error_message']}
   Error ID: {row['error_id'] or 'N/A'}
   MCPs/Tools: {row['mcps_used'] or 'none'} / {row['tools_used'] or 'none'}
   Time: {row['created_at'].strftime('%Y-%m-%d %H:%M:%S')}

"""
        
        return result
        
    except Exception as e:
        logger.error(f"Error in get_failed_queries: {e}")
        return f"❌ Error: {str(e)}"


# ============================================================================
# 👥 User Activity
# ============================================================================

@mcp.tool(description="OMNI2 Analytics: Get active users and their query counts")
async def get_active_users(period: str = "week", role: Optional[str] = None, limit: int = 20) -> str:
    """
    Get most active users by query count.
    
    Args:
        period: Time period filter
        role: Optional role filter (admin/dba/developer/read_only)
        limit: Number of users to return
    
    Returns:
        List of active users with query statistics
    """
    try:
        await db.connect()
        
        date_filter = ""
        if period == "today":
            date_filter = "AND al.created_at >= CURRENT_DATE"
        elif period == "week":
            date_filter = "AND al.created_at >= CURRENT_DATE - INTERVAL '7 days'"
        elif period == "month":
            date_filter = "AND al.created_at >= DATE_TRUNC('month', CURRENT_DATE)"
        
        role_filter = f"AND u.role = '{role}'" if role else ""
        
        query = f"""
            SELECT 
                u.email,
                u.name,
                u.role,
                COUNT(*) as query_count,
                SUM(CASE WHEN al.status = 'error' THEN 1 ELSE 0 END) as error_count,
                AVG(al.duration_ms) as avg_duration_ms,
                SUM(al.cost_estimate) as total_cost,
                MAX(al.created_at) as last_activity
            FROM users u
            JOIN audit_logs al ON u.id = al.user_id
            WHERE 1=1 {date_filter} {role_filter}
            GROUP BY u.email, u.name, u.role
            ORDER BY query_count DESC
            LIMIT {limit}
        """
        
        rows = await db.fetch_all(query)
        
        if not rows:
            return f"No active users found for period: {period}"
        
        result = f"👥 **Active Users ({period})**\n\n"
        for i, row in enumerate(rows, 1):
            error_rate = round(100 * row['error_count'] / row['query_count'], 1) if row['query_count'] > 0 else 0
            result += f"""**{i}. {row['name']}** ({row['email']}) - {row['role']}
   Queries: {row['query_count']} | Errors: {row['error_count']} ({error_rate}%)
   Avg Duration: {int(row['avg_duration_ms'])}ms | Cost: ${row['total_cost']:.4f}
   Last Active: {row['last_activity'].strftime('%Y-%m-%d %H:%M')}

"""
        
        return result
        
    except Exception as e:
        logger.error(f"Error in get_active_users: {e}")
        return f"❌ Error: {str(e)}"


# ============================================================================
# 🔧 Tool & MCP Usage
# ============================================================================

@mcp.tool(description="OMNI2 Analytics: Get tool popularity and usage statistics")
async def get_tool_popularity(limit: int = 20, period: str = "week") -> str:
    """
    Get most/least used tools.
    
    Args:
        limit: Number of tools to return
        period: Time period filter
    
    Returns:
        Tool usage statistics
    """
    try:
        await db.connect()
        
        date_filter = ""
        if period == "today":
            date_filter = "AND created_at >= CURRENT_DATE"
        elif period == "week":
            date_filter = "AND created_at >= CURRENT_DATE - INTERVAL '7 days'"
        elif period == "month":
            date_filter = "AND created_at >= DATE_TRUNC('month', CURRENT_DATE)"
        
        query = f"""
            SELECT 
                unnest(tools_used) as tool_name,
                COUNT(*) as usage_count,
                SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as error_count,
                AVG(duration_ms) as avg_duration_ms
            FROM audit_logs
            WHERE tools_used IS NOT NULL {date_filter}
            GROUP BY tool_name
            ORDER BY usage_count DESC
            LIMIT {limit}
        """
        
        rows = await db.fetch_all(query)
        
        if not rows:
            return f"No tool usage data for period: {period}"
        
        result = f"🔧 **Tool Popularity ({period})**\n\n"
        for i, row in enumerate(rows, 1):
            error_rate = round(100 * row['error_count'] / row['usage_count'], 1) if row['usage_count'] > 0 else 0
            result += f"{i}. **{row['tool_name']}**: {row['usage_count']} calls | {error_rate}% errors | {int(row['avg_duration_ms'])}ms avg\n"
        
        return result
        
    except Exception as e:
        logger.error(f"Error in get_tool_popularity: {e}")
        return f"❌ Error: {str(e)}"


@mcp.tool(description="OMNI2 Analytics: Get MCP server health and performance statistics")
async def get_mcp_health_summary() -> str:
    """
    Get health summary for all MCP servers.
    
    Returns:
        MCP health statistics with success rates and response times
    """
    try:
        await db.connect()
        
        # Query the v_mcp_health view
        query = """
            SELECT 
                name,
                url,
                is_enabled,
                is_healthy,
                tool_count,
                total_requests,
                successful_requests,
                failed_requests,
                success_rate_pct,
                last_health_check
            FROM v_mcp_health
            ORDER BY total_requests DESC
        """
        
        rows = await db.fetch_all(query)
        
        if not rows:
            return "No MCP server data found"
        
        result = "🏥 **MCP Server Health Summary**\n\n"
        for row in rows:
            status = "✅" if row['is_healthy'] else "❌"
            enabled = "ON" if row['is_enabled'] else "OFF"
            result += f"""**{row['name']}** [{enabled}] {status}
   URL: {row['url']}
   Tools: {row['tool_count']} | Requests: {row['total_requests']}
   Success Rate: {row['success_rate_pct']}%
   Last Check: {row['last_health_check'].strftime('%Y-%m-%d %H:%M') if row['last_health_check'] else 'Never'}

"""
        
        return result
        
    except Exception as e:
        logger.error(f"Error in get_mcp_health_summary: {e}")
        return f"❌ Error: {str(e)}"


logger.info("✅ Analytics tools loaded successfully")
