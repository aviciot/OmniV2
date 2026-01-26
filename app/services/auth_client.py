"""
Auth Service Client

Communicates with auth_service microservice for user authentication and management.
Includes in-memory caching with TTL and manual invalidation.
"""

import httpx
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from app.utils.logger import logger

# Auth service URL (from environment or default)
AUTH_SERVICE_URL = "http://localhost:8001"

# Cache configuration
CACHE_TTL_SECONDS = 300  # 5 minutes

# In-memory cache: {user_id: {"data": {...}, "cached_at": datetime}}
_user_cache: Dict[int, Dict[str, Any]] = {}
_email_cache: Dict[str, Dict[str, Any]] = {}  # {email: {"data": {...}, "cached_at": datetime}}


async def get_user(user_id: int, bypass_cache: bool = False) -> Optional[Dict[str, Any]]:
    """
    Fetch user details from auth_service with caching.
    
    Args:
        user_id: User ID (integer) or email (string) to fetch
        bypass_cache: If True, skip cache and fetch fresh data
        
    Returns:
        User data dict or None if not found
    """
    try:
        # If user_id is a string (email), use by-email endpoint
        if isinstance(user_id, str):
            return await get_user_by_email(user_id, bypass_cache=bypass_cache)
        
        # Check cache first (unless bypassed)
        if not bypass_cache and user_id in _user_cache:
            cached = _user_cache[user_id]
            if datetime.now() - cached["cached_at"] < timedelta(seconds=CACHE_TTL_SECONDS):
                logger.debug(f"Cache HIT for user {user_id}")
                return cached["data"]
            else:
                # Cache expired
                logger.debug(f"Cache EXPIRED for user {user_id}")
                del _user_cache[user_id]
        
        # Cache miss - fetch from auth_service
        logger.debug(f"Cache MISS for user {user_id} - fetching from auth_service")
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{AUTH_SERVICE_URL}/auth/users/{user_id}")
            response.raise_for_status()
            user_data = response.json()
            
            # Store in cache
            _user_cache[user_id] = {
                "data": user_data,
                "cached_at": datetime.now()
            }
            
            # Also cache by email if present
            if "email" in user_data:
                _email_cache[user_data["email"]] = {
                    "data": user_data,
                    "cached_at": datetime.now()
                }
            
            return user_data
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            logger.warning(f"User {user_id} not found in auth_service")
            return None
        logger.error(f"Failed to fetch user {user_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error fetching user {user_id} from auth_service: {e}")
        return None


async def get_user_by_email(email: str, bypass_cache: bool = False) -> Optional[Dict[str, Any]]:
    """
    Fetch user by email from auth_service with caching.
    
    Args:
        email: User email
        bypass_cache: If True, skip cache and fetch fresh data
        
    Returns:
        User data dict or None if not found
    """
    try:
        # Check cache first (unless bypassed)
        if not bypass_cache and email in _email_cache:
            cached = _email_cache[email]
            if datetime.now() - cached["cached_at"] < timedelta(seconds=CACHE_TTL_SECONDS):
                logger.debug(f"Cache HIT for email {email}")
                return cached["data"]
            else:
                # Cache expired
                logger.debug(f"Cache EXPIRED for email {email}")
                del _email_cache[email]
        
        # Cache miss - fetch from auth_service
        logger.debug(f"Cache MISS for email {email} - fetching from auth_service")
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{AUTH_SERVICE_URL}/auth/users/by-email/{email}")
            response.raise_for_status()
            user_data = response.json()
            
            # Store in cache
            _email_cache[email] = {
                "data": user_data,
                "cached_at": datetime.now()
            }
            
            # Also cache by user_id if present
            if "id" in user_data:
                _user_cache[user_data["id"]] = {
                    "data": user_data,
                    "cached_at": datetime.now()
                }
            
            return user_data
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            logger.warning(f"User with email {email} not found in auth_service")
            return None
        logger.error(f"Failed to fetch user by email {email}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error fetching user by email from auth_service: {e}")
        return None


async def validate_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Validate JWT token with auth_service.
    
    Args:
        token: JWT token to validate
        
    Returns:
        User data if valid, None otherwise
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{AUTH_SERVICE_URL}/auth/validate",
                headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"Token validation failed: {e}")
        return None


async def create_user(username: str, email: str, password: str, role: str = "read_only") -> Optional[Dict[str, Any]]:
    """
    Create new user via auth_service.
    
    Args:
        username: Username
        email: Email address
        password: Password (will be hashed by auth_service)
        role: User role (default: read_only)
        
    Returns:
        Created user data or None if failed
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{AUTH_SERVICE_URL}/auth/register",
                json={
                    "username": username,
                    "email": email,
                    "password": password,
                    "role": role
                }
            )
            response.raise_for_status()
            logger.info(f"User created: {email}")
            return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"Failed to create user {email}: {e.response.text}")
        return None
    except Exception as e:
        logger.error(f"Error creating user via auth_service: {e}")
        return None


async def update_user(user_id: int, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Update user via auth_service.
    
    Args:
        user_id: User ID to update
        updates: Dict of fields to update
        
    Returns:
        Updated user data or None if failed
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.patch(
                f"{AUTH_SERVICE_URL}/auth/users/{user_id}",
                json=updates
            )
            response.raise_for_status()
            logger.info(f"User {user_id} updated")
            return response.json()
    except Exception as e:
        logger.error(f"Error updating user {user_id}: {e}")
        return None


async def list_users(skip: int = 0, limit: int = 100) -> list[Dict[str, Any]]:
    """
    List users from auth_service.
    
    Args:
        skip: Number of records to skip
        limit: Max records to return
        
    Returns:
        List of user dicts
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{AUTH_SERVICE_URL}/auth/users",
                params={"skip": skip, "limit": limit}
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"Error listing users from auth_service: {e}")
        return []


def invalidate_user_cache(user_id: Optional[int] = None, email: Optional[str] = None) -> Dict[str, Any]:
    """
    Invalidate cached user data.
    Called when user data changes in auth_service (e.g., user blocked, role changed).
    
    Args:
        user_id: User ID to invalidate (optional)
        email: Email to invalidate (optional)
        
    Returns:
        Dict with invalidation status
    """
    invalidated = {"user_id": [], "email": []}
    
    if user_id is not None:
        if user_id in _user_cache:
            # Get email before deleting
            user_data = _user_cache[user_id]["data"]
            del _user_cache[user_id]
            invalidated["user_id"].append(user_id)
            logger.info(f"Invalidated cache for user_id {user_id}")
            
            # Also invalidate email cache
            if "email" in user_data and user_data["email"] in _email_cache:
                del _email_cache[user_data["email"]]
                invalidated["email"].append(user_data["email"])
    
    if email is not None:
        if email in _email_cache:
            # Get user_id before deleting
            user_data = _email_cache[email]["data"]
            del _email_cache[email]
            invalidated["email"].append(email)
            logger.info(f"Invalidated cache for email {email}")
            
            # Also invalidate user_id cache
            if "id" in user_data and user_data["id"] in _user_cache:
                del _user_cache[user_data["id"]]
                invalidated["user_id"].append(user_data["id"])
    
    return invalidated


def clear_all_cache() -> Dict[str, int]:
    """
    Clear all cached user data.
    
    Returns:
        Dict with count of cleared entries
    """
    user_count = len(_user_cache)
    email_count = len(_email_cache)
    
    _user_cache.clear()
    _email_cache.clear()
    
    logger.info(f"Cleared all cache: {user_count} users, {email_count} emails")
    return {"users_cleared": user_count, "emails_cleared": email_count}


def get_cache_stats() -> Dict[str, Any]:
    """
    Get cache statistics.
    
    Returns:
        Dict with cache stats
    """
    now = datetime.now()
    
    user_cache_valid = sum(
        1 for cached in _user_cache.values()
        if now - cached["cached_at"] < timedelta(seconds=CACHE_TTL_SECONDS)
    )
    
    email_cache_valid = sum(
        1 for cached in _email_cache.values()
        if now - cached["cached_at"] < timedelta(seconds=CACHE_TTL_SECONDS)
    )
    
    return {
        "user_cache_size": len(_user_cache),
        "user_cache_valid": user_cache_valid,
        "email_cache_size": len(_email_cache),
        "email_cache_valid": email_cache_valid,
        "ttl_seconds": CACHE_TTL_SECONDS
    }
