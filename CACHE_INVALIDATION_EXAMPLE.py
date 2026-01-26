"""
Example: How auth_service should invalidate omni2 cache

Add this code to auth_service when user data changes.
"""

import httpx
from typing import Optional

# Omni2 service URL
OMNI2_URL = "http://localhost:8000"


async def invalidate_omni2_cache(user_id: Optional[int] = None, email: Optional[str] = None):
    """
    Notify omni2 to invalidate user cache.
    
    Call this function after:
    - User blocked/unblocked
    - User role changed
    - User permissions changed
    - User deleted
    - Any user data modification
    
    Args:
        user_id: User ID that changed
        email: User email that changed
    """
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.post(
                f"{OMNI2_URL}/cache/invalidate",
                json={"user_id": user_id, "email": email}
            )
            response.raise_for_status()
            print(f"✅ Omni2 cache invalidated for user {user_id or email}")
    except Exception as e:
        # Don't fail the main operation if cache invalidation fails
        print(f"⚠️ Failed to invalidate omni2 cache: {e}")


# ============================================================
# EXAMPLE 1: Block User
# ============================================================

async def block_user(db, user_id: int):
    """Example: Block user and invalidate cache."""
    # Update user in database
    user = db.query(User).filter(User.id == user_id).first()
    user.is_active = False
    db.commit()
    
    # Invalidate omni2 cache
    await invalidate_omni2_cache(user_id=user_id, email=user.email)
    
    return {"status": "ok", "user_id": user_id, "is_active": False}


# ============================================================
# EXAMPLE 2: Change User Role
# ============================================================

async def change_user_role(db, user_id: int, new_role: str):
    """Example: Change user role and invalidate cache."""
    # Update user role in database
    user = db.query(User).filter(User.id == user_id).first()
    user.role = new_role
    db.commit()
    
    # Invalidate omni2 cache
    await invalidate_omni2_cache(user_id=user_id, email=user.email)
    
    return {"status": "ok", "user_id": user_id, "role": new_role}


# ============================================================
# EXAMPLE 3: Update User Endpoint (FastAPI)
# ============================================================

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

router = APIRouter()

@router.patch("/users/{user_id}")
async def update_user(user_id: int, updates: dict, db: Session = Depends(get_db)):
    """Update user and invalidate omni2 cache."""
    # Update user in database
    user = db.query(User).filter(User.id == user_id).first()
    
    for key, value in updates.items():
        setattr(user, key, value)
    
    db.commit()
    db.refresh(user)
    
    # Invalidate omni2 cache
    await invalidate_omni2_cache(user_id=user_id, email=user.email)
    
    return user


# ============================================================
# EXAMPLE 4: Delete User
# ============================================================

async def delete_user(db, user_id: int):
    """Example: Delete user and invalidate cache."""
    # Get user email before deleting
    user = db.query(User).filter(User.id == user_id).first()
    email = user.email
    
    # Delete user from database
    db.delete(user)
    db.commit()
    
    # Invalidate omni2 cache
    await invalidate_omni2_cache(user_id=user_id, email=email)
    
    return {"status": "ok", "user_id": user_id, "deleted": True}


# ============================================================
# INTEGRATION NOTES
# ============================================================

"""
1. Add this function to auth_service/app/services/cache_invalidation.py

2. Import and call after ANY user modification:
   
   from app.services.cache_invalidation import invalidate_omni2_cache
   
   # After blocking user
   await invalidate_omni2_cache(user_id=123)
   
   # After changing email
   await invalidate_omni2_cache(user_id=123, email="new@example.com")

3. The function is fire-and-forget with 2-second timeout:
   - Won't block the main operation
   - Logs errors but doesn't fail
   - Omni2 cache will expire after 5 minutes anyway (fallback)

4. Test the integration:
   
   # Block user in auth_service
   curl -X PATCH http://localhost:8001/auth/users/1 -d '{"is_active": false}'
   
   # Verify cache invalidated in omni2
   curl http://localhost:8000/cache/stats
   
   # Try to get user (should fetch fresh data)
   curl http://localhost:8000/users/1
"""
