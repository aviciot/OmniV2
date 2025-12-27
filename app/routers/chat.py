"""
Chat Router

LLM-powered chat interface for intelligent MCP routing.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.services.llm_service import get_llm_service, LLMService
from app.utils.logger import logger


router = APIRouter(prefix="/chat")


# ============================================================
# Request/Response Models
# ============================================================

class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    
    user_id: str = Field(..., description="User email address")
    message: str = Field(..., description="User's question or request")


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
    llm_service: LLMService = Depends(get_llm_service),
) -> ChatResponse:
    """
    Ask a question with intelligent MCP routing.
    
    The LLM will:
    1. Determine if question needs MCP tools
    2. Call appropriate tools based on user permissions
    3. Synthesize a natural language answer
    
    Args:
        request: Chat request with user_id and message
        llm_service: LLM service instance (injected)
        
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
    try:
        logger.info(
            "📬 Chat request received",
            user=request.user_id,
            message_preview=request.message[:50],
        )
        
        # Process with LLM
        result = await llm_service.ask(
            user_id=request.user_id,
            message=request.message,
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
        logger.warning("⚠️  Invalid chat request", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
        
    except Exception as e:
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
