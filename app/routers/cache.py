"""
Cache Management Router

Endpoints for invalidating and managing auth_client cache.
Called by auth_service when user data changes.
"""

from fastapi import APIRouter, HTTPException
from typing import Optional
from pydantic import BaseModel

from app.services import auth_client
from app.utils.logger import logger

router = APIRouter(prefix="/cache", tags=["cache"])


class InvalidateRequest(BaseModel):
    user_id: Optional[int] = None
    email: Optional[str] = None


@router.post("/invalidate")
async def invalidate_cache(request: InvalidateRequest):
    """
    Invalidate user cache entries.
    
    Called by auth_service when user data changes (e.g., user blocked, role changed).
    
    Args:
        user_id: User ID to invalidate (optional)
        email: Email to invalidate (optional)
    
    Returns:
        Invalidation status
    """
    if not request.user_id and not request.email:
        raise HTTPException(status_code=400, detail="Must provide user_id or email")
    
    result = auth_client.invalidate_user_cache(
        user_id=request.user_id,
        email=request.email
    )
    
    logger.info(f"Cache invalidated: {result}")
    return {"status": "ok", "invalidated": result}


@router.post("/invalidate/user/{user_id}")
async def invalidate_user_by_id(user_id: int):
    """
    Invalidate cache for specific user ID.
    
    Args:
        user_id: User ID to invalidate
    
    Returns:
        Invalidation status
    """
    result = auth_client.invalidate_user_cache(user_id=user_id)
    logger.info(f"Cache invalidated for user {user_id}: {result}")
    return {"status": "ok", "user_id": user_id, "invalidated": result}


@router.post("/clear")
async def clear_all_cache():
    """
    Clear all cached user data.
    
    Use with caution - forces all subsequent requests to fetch from auth_service.
    
    Returns:
        Count of cleared entries
    """
    result = auth_client.clear_all_cache()
    logger.warning(f"All cache cleared: {result}")
    return {"status": "ok", "cleared": result}


@router.get("/stats")
async def get_cache_stats():
    """
    Get cache statistics.
    
    Returns:
        Cache size, valid entries, TTL
    """
    stats = auth_client.get_cache_stats()
    return {"status": "ok", "stats": stats}
