"""
Chat Router

LLM-powered chat interface for intelligent MCP routing.
"""

import time
import json
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.llm_service import get_llm_service, LLMService
from app.services.audit_service import get_audit_service, AuditService
from app.services.user_service import get_user_service, UserService
from app.services.rate_limiter import get_rate_limiter, RateLimiter
from app.utils.logger import logger


router = APIRouter(prefix="/chat")


# ============================================================
# Request/Response Models
# ============================================================

class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    
    user_id: str = Field(..., description="User email address")
    message: str = Field(..., description="User's question or request")
    slack_context: Optional[dict] = Field(None, description="Slack metadata (user_id, channel, message_ts, thread_ts, event_type)")


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    
    success: bool
    answer: str
    tool_calls: int = 0
    tools_used: list = []
    iterations: int = 1
    error: Optional[str] = None
    warning: Optional[str] = None


# ============================================================
# Endpoints
# ============================================================

@router.post("/ask", response_model=ChatResponse)
async def ask_question(
    request: ChatRequest,
    http_request: Request,
    llm_service: LLMService = Depends(get_llm_service),
    audit_service: AuditService = Depends(get_audit_service),
    user_service: UserService = Depends(get_user_service),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
) -> ChatResponse:
    """
    Ask a question with intelligent MCP routing.
    
    The LLM will:
    1. Determine if question needs MCP tools
    2. Call appropriate tools based on user permissions
    3. Synthesize a natural language answer
    
    Args:
        request: Chat request with user_id and message
        http_request: FastAPI request object (for IP, user agent)
        llm_service: LLM service instance (injected)
        audit_service: Audit service instance (injected)
        
    Returns:
        ChatResponse with answer and metadata
        
    Examples:
        ```json
        {
          "user_id": "developer@company.com",
          "message": "Show my Python repos"
        }
        ```
        
        ```json
        {
          "user_id": "dba@company.com",
          "message": "What's the database health?"
        }
        ```
    """
    start_time = time.time()
    
    try:
        logger.info(
            "📬 Chat request received",
            user=request.user_id,
            message_preview=request.message[:50],
        )
        
        # Get user info for rate limiting
        user_info = await user_service.get_user(request.user_id)
        user_role = user_info.get("role", "default")
        
        # Check rate limit
        allowed, current_count, limit = rate_limiter.check_rate_limit(
            user_id=request.user_id,
            role=user_role
        )
        
        if not allowed:
            # Get reset time
            reset_time = rate_limiter.get_window_reset_time(request.user_id)
            reset_in_seconds = int(reset_time - time.time()) if reset_time else 3600
            reset_in_minutes = reset_in_seconds // 60
            
            error_msg = (
                f"Rate limit exceeded. You've made {current_count}/{limit} requests in the last hour. "
                f"Please try again in {reset_in_minutes} minutes."
            )
            
            logger.warning(
                "🚫 Rate limit exceeded",
                user=request.user_id,
                role=user_role,
                count=current_count,
                limit=limit,
                reset_in_minutes=reset_in_minutes
            )
            
            # Log rate limit violation to audit
            await audit_service.log_error(
                user_id=request.user_id,
                message=request.message,
                error_message=f"Rate limit exceeded: {current_count}/{limit} requests",
                duration_ms=0,
                ip_address=http_request.client.host if http_request.client else None,
                user_agent=http_request.headers.get("user-agent"),
            )
            
            raise HTTPException(
                status_code=429,
                detail=error_msg
            )
        
        logger.debug(
            "✅ Rate limit check passed",
            user=request.user_id,
            role=user_role,
            count=current_count,
            limit=limit
        )
        
        # Check if request is from admin dashboard
        is_admin_dashboard = http_request.headers.get("x-source") == "omni2-admin-dashboard"
        
        # Process with LLM
        result = await llm_service.ask(
            user_id=request.user_id,
            message=request.message,
            is_admin_dashboard=is_admin_dashboard,
        )
        
        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Extract Slack context if provided
        slack_user_id = None
        slack_channel = None
        slack_message_ts = None
        slack_thread_ts = None
        
        if request.slack_context:
            slack_user_id = request.slack_context.get("slack_user_id")
            slack_channel = request.slack_context.get("slack_channel")
            slack_message_ts = request.slack_context.get("slack_message_ts")
            slack_thread_ts = request.slack_context.get("slack_thread_ts")
        
        # Determine source from headers
        source = http_request.headers.get("x-source", "web")  # "slack-bot" or "web"
        
        # Log to audit (async, non-blocking)
        await audit_service.log_chat_request(
            user_id=request.user_id,
            message=request.message,
            result=result,
            duration_ms=duration_ms,
            ip_address=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("user-agent"),
            slack_user_id=slack_user_id,
            slack_channel=slack_channel,
            slack_message_ts=slack_message_ts,
            slack_thread_ts=slack_thread_ts,
        )
        
        return ChatResponse(
            success=True,
            answer=result["answer"],
            tool_calls=result.get("tool_calls", 0),
            tools_used=result.get("tools_used", []),
            iterations=result.get("iterations", 1),
            warning=result.get("warning"),
        )
        
    except ValueError as e:
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Log error to audit
        await audit_service.log_error(
            user_id=request.user_id,
            message=request.message,
            error_message=str(e),
            duration_ms=duration_ms,
            ip_address=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("user-agent"),
        )
        
        logger.warning("⚠️  Invalid chat request", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Log error to audit
        await audit_service.log_error(
            user_id=request.user_id,
            message=request.message,
            error_message=str(e),
            duration_ms=duration_ms,
            ip_address=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("user-agent"),
        )
        
        logger.error(
            "❌ Chat request failed",
            user=request.user_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Chat request failed: {str(e)}",
        )


@router.post("/ask/stream")
async def ask_question_stream(
    request: ChatRequest,
    http_request: Request,
    llm_service: LLMService = Depends(get_llm_service),
    audit_service: AuditService = Depends(get_audit_service),
    user_service: UserService = Depends(get_user_service),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
):
    """
    Stream chat response tokens using Server-Sent Events (SSE).
    """
    start_time = time.time()

    user_info = await user_service.get_user(request.user_id)
    user_role = user_info.get("role", "default")

    allowed, current_count, limit = rate_limiter.check_rate_limit(
        user_id=request.user_id,
        role=user_role
    )

    if not allowed:
        reset_time = rate_limiter.get_window_reset_time(request.user_id)
        reset_in_seconds = int(reset_time - time.time()) if reset_time else 3600
        reset_in_minutes = reset_in_seconds // 60

        error_msg = (
            f"Rate limit exceeded. You've made {current_count}/{limit} requests in the last hour. "
            f"Please try again in {reset_in_minutes} minutes."
        )

        await audit_service.log_error(
            user_id=request.user_id,
            message=request.message,
            error_message=f"Rate limit exceeded: {current_count}/{limit} requests",
            duration_ms=0,
            ip_address=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("user-agent"),
        )

        async def error_stream():
            yield f"event: error\ndata: {json.dumps({'error': error_msg})}\n\n"

        return StreamingResponse(
            error_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    is_admin_dashboard = http_request.headers.get("x-source") == "omni2-admin-dashboard"

    slack_user_id = None
    slack_channel = None
    slack_message_ts = None
    slack_thread_ts = None

    if request.slack_context:
        slack_user_id = request.slack_context.get("slack_user_id")
        slack_channel = request.slack_context.get("slack_channel")
        slack_message_ts = request.slack_context.get("slack_message_ts")
        slack_thread_ts = request.slack_context.get("slack_thread_ts")

    async def event_stream():
        try:
            async for event in llm_service.ask_stream(
                user_id=request.user_id,
                message=request.message,
                is_admin_dashboard=is_admin_dashboard,
            ):
                if event.get("type") == "token":
                    payload = json.dumps({"text": event.get("text", "")})
                    yield f"event: token\ndata: {payload}\n\n"
                elif event.get("type") == "done":
                    result = event.get("result", {})
                    duration_ms = int((time.time() - start_time) * 1000)
                    await audit_service.log_chat_request(
                        user_id=request.user_id,
                        message=request.message,
                        result=result,
                        duration_ms=duration_ms,
                        ip_address=http_request.client.host if http_request.client else None,
                        user_agent=http_request.headers.get("user-agent"),
                        slack_user_id=slack_user_id,
                        slack_channel=slack_channel,
                        slack_message_ts=slack_message_ts,
                        slack_thread_ts=slack_thread_ts,
                    )
                    yield f"event: done\ndata: {json.dumps(result)}\n\n"
                elif event.get("type") == "error":
                    duration_ms = int((time.time() - start_time) * 1000)
                    await audit_service.log_error(
                        user_id=request.user_id,
                        message=request.message,
                        error_message=event.get("error", "Streaming error"),
                        duration_ms=duration_ms,
                        ip_address=http_request.client.host if http_request.client else None,
                        user_agent=http_request.headers.get("user-agent"),
                    )
                    yield f"event: error\ndata: {json.dumps({'error': event.get('error', 'Streaming error')})}\n\n"
                    return
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            await audit_service.log_error(
                user_id=request.user_id,
                message=request.message,
                error_message=str(e),
                duration_ms=duration_ms,
                ip_address=http_request.client.host if http_request.client else None,
                user_agent=http_request.headers.get("user-agent"),
            )
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
