"""
Audit Router

API endpoints for querying audit logs and usage statistics.
"""

from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from app.services.audit_service import get_audit_service, AuditService
from app.services.user_service import get_user_service, UserService
from app.utils.logger import logger


router = APIRouter(prefix="/audit")


# ============================================================
# Response Models
# ============================================================

class AuditLogEntry(BaseModel):
    """Single audit log entry."""
    
    id: int
    user_email: Optional[str]
    request_type: str
    message_preview: str
    iterations: int
    tool_calls_count: int
    tools_used: list
    mcps_accessed: list
    duration_ms: int
    cost_estimate: float
    status: str
    warning: Optional[str]
    created_at: datetime


class AuditLogsResponse(BaseModel):
    """Response model for audit logs query."""
    
    logs: list[AuditLogEntry]
    total: int
    limit: int
    offset: int


class AuditStatsResponse(BaseModel):
    """Response model for audit statistics."""
    
    total_requests: int
    total_tool_calls: int
    avg_iterations: float
    avg_duration_ms: float
    total_cost: float
    error_count: int
    success_count: int
    warning_count: int
    period_days: int


# ============================================================
# Endpoints
# ============================================================

@router.get("/logs", response_model=AuditLogsResponse)
async def get_audit_logs(
    user_id: Optional[str] = Query(None, description="Filter by user email"),
    status: Optional[str] = Query(None, description="Filter by status (success, error, warning)"),
    mcp_name: Optional[str] = Query(None, description="Filter by MCP name"),
    days: int = Query(7, description="Number of days to include", ge=1, le=90),
    limit: int = Query(100, description="Maximum results", ge=1, le=1000),
    offset: int = Query(0, description="Pagination offset", ge=0),
    requesting_user: str = Query(..., description="User making the request"),
    audit_service: AuditService = Depends(get_audit_service),
    user_service: UserService = Depends(get_user_service),
):
    """
    Query audit logs with filters.
    
    **Admin-only endpoint:** Only super_admin users can access all logs.
    Regular users can only see their own logs.
    
    Args:
        user_id: Filter by specific user (admin only)
        status: Filter by status
        mcp_name: Filter by MCP name
        days: Number of days to include
        limit: Maximum results
        offset: Pagination offset
        requesting_user: Email of user making request
        
    Returns:
        Audit logs with pagination info
        
    Examples:
        ```
        GET /audit/logs?requesting_user=admin@company.com&limit=50
        GET /audit/logs?requesting_user=dba@company.com&status=error&days=30
        GET /audit/logs?requesting_user=admin@company.com&user_id=developer@company.com
        ```
    """
    try:
        # Check permissions
        requesting_user_data = await user_service.get_user(requesting_user)
        is_admin = bool(requesting_user_data.get("is_super_admin")) or requesting_user_data.get("role") == "admin"
        
        # Regular users can only see their own logs
        if not is_admin:
            if user_id and user_id != requesting_user:
                raise HTTPException(
                    status_code=403,
                    detail="You can only view your own audit logs"
                )
            user_id = requesting_user
        
        # Calculate date range
        start_date = datetime.now() - timedelta(days=days)
        
        # Query logs
        logs = await audit_service.get_logs(
            user_id=user_id,
            limit=limit,
            offset=offset,
            status=status,
            mcp_name=mcp_name,
            start_date=start_date,
        )
        
        logger.info(
            "📋 Audit logs queried",
            requesting_user=requesting_user,
            filter_user=user_id,
            results=len(logs),
        )
        
        return AuditLogsResponse(
            logs=logs,
            total=len(logs),  # Note: This is just current page count, not total
            limit=limit,
            offset=offset,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "❌ Failed to query audit logs",
            requesting_user=requesting_user,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to query audit logs: {str(e)}"
        )


@router.get("/stats", response_model=AuditStatsResponse)
async def get_audit_stats(
    user_id: Optional[str] = Query(None, description="Filter by user (admin only)"),
    days: int = Query(7, description="Number of days to include", ge=1, le=90),
    requesting_user: str = Query(..., description="User making the request"),
    audit_service: AuditService = Depends(get_audit_service),
    user_service: UserService = Depends(get_user_service),
):
    """
    Get usage statistics.
    
    **Admin-only for all users:** Super admins can see stats for all users or specific user.
    Regular users can only see their own stats.
    
    Args:
        user_id: Filter by user (admin only)
        days: Number of days to include
        requesting_user: Email of user making request
        
    Returns:
        Usage statistics
        
    Examples:
        ```
        GET /audit/stats?requesting_user=admin@company.com&days=30
        GET /audit/stats?requesting_user=admin@company.com&user_id=developer@company.com&days=7
        GET /audit/stats?requesting_user=dba@company.com&days=14
        ```
    """
    try:
        # Check permissions
        requesting_user_data = await user_service.get_user(requesting_user)
        is_admin = bool(requesting_user_data.get("is_super_admin")) or requesting_user_data.get("role") == "admin"
        
        # Regular users can only see their own stats
        if not is_admin:
            if user_id and user_id != requesting_user:
                raise HTTPException(
                    status_code=403,
                    detail="You can only view your own statistics"
                )
            user_id = requesting_user
        
        # Get stats
        stats = await audit_service.get_stats(
            user_id=user_id,
            days=days,
        )
        
        logger.info(
            "📊 Audit stats retrieved",
            requesting_user=requesting_user,
            filter_user=user_id,
            days=days,
        )
        
        return AuditStatsResponse(
            total_requests=stats.get("total_requests", 0),
            total_tool_calls=stats.get("total_tool_calls", 0),
            avg_iterations=float(stats.get("avg_iterations", 0) or 0),
            avg_duration_ms=float(stats.get("avg_duration_ms", 0) or 0),
            total_cost=float(stats.get("total_cost", 0) or 0),
            error_count=stats.get("error_count", 0),
            success_count=stats.get("success_count", 0),
            warning_count=stats.get("warning_count", 0),
            period_days=days,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "❌ Failed to get audit stats",
            requesting_user=requesting_user,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get audit stats: {str(e)}"
        )


@router.get("/my-logs", response_model=AuditLogsResponse)
async def get_my_audit_logs(
    status: Optional[str] = Query(None, description="Filter by status"),
    days: int = Query(7, description="Number of days to include", ge=1, le=90),
    limit: int = Query(50, description="Maximum results", ge=1, le=500),
    offset: int = Query(0, description="Pagination offset", ge=0),
    user_id: str = Query(..., description="Your email address"),
    audit_service: AuditService = Depends(get_audit_service),
):
    """
    Get your own audit logs (convenience endpoint).
    
    No admin required - any user can query their own logs.
    
    Args:
        status: Filter by status
        days: Number of days to include
        limit: Maximum results
        offset: Pagination offset
        user_id: Your email address
        
    Returns:
        Your audit logs
        
    Examples:
        ```
        GET /audit/my-logs?user_id=developer@company.com&days=30
        GET /audit/my-logs?user_id=dba@company.com&status=error
        ```
    """
    try:
        start_date = datetime.now() - timedelta(days=days)
        
        logs = await audit_service.get_logs(
            user_id=user_id,
            limit=limit,
            offset=offset,
            status=status,
            start_date=start_date,
        )
        
        return AuditLogsResponse(
            logs=logs,
            total=len(logs),
            limit=limit,
            offset=offset,
        )
        
    except Exception as e:
        logger.error(
            "❌ Failed to get user logs",
            user=user_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get your logs: {str(e)}"
        )


@router.get("/my-stats", response_model=AuditStatsResponse)
async def get_my_audit_stats(
    days: int = Query(7, description="Number of days to include", ge=1, le=90),
    user_id: str = Query(..., description="Your email address"),
    audit_service: AuditService = Depends(get_audit_service),
):
    """
    Get your own usage statistics (convenience endpoint).
    
    No admin required - any user can see their own stats.
    
    Args:
        days: Number of days to include
        user_id: Your email address
        
    Returns:
        Your usage statistics
        
    Examples:
        ```
        GET /audit/my-stats?user_id=developer@company.com&days=30
        GET /audit/my-stats?user_id=dba@company.com&days=7
        ```
    """
    try:
        stats = await audit_service.get_stats(
            user_id=user_id,
            days=days,
        )
        
        return AuditStatsResponse(
            total_requests=stats.get("total_requests", 0),
            total_tool_calls=stats.get("total_tool_calls", 0),
            avg_iterations=float(stats.get("avg_iterations", 0) or 0),
            avg_duration_ms=float(stats.get("avg_duration_ms", 0) or 0),
            total_cost=float(stats.get("total_cost", 0) or 0),
            error_count=stats.get("error_count", 0),
            success_count=stats.get("success_count", 0),
            warning_count=stats.get("warning_count", 0),
            period_days=days,
        )
        
    except Exception as e:
        logger.error(
            "❌ Failed to get user stats",
            user=user_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get your stats: {str(e)}"
        )
