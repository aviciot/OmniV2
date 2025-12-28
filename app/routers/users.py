"""
User Management Endpoints

Provides user information, roles, and permissions
"""

from fastapi import APIRouter, HTTPException
from typing import Dict

from app.config import settings
from app.services.user_service import UserService
from app.utils.logger import logger


router = APIRouter()
user_service = UserService()


@router.get("/users/{email}")
async def get_user_info(email: str) -> Dict:
    """
    Get user information including role and permissions
    
    Args:
        email: User's email address
        
    Returns:
        Dict with user info:
        - email: User's email
        - name: User's display name
        - role: User role (admin, dba, power_user, etc.)
        - allowed_mcps: List of allowed MCP servers or "*" for all
        - allowed_domains: List of allowed domains
        - permissions: Additional permissions
    """
    try:
        # Get user config from users.yaml
        user_config = user_service.get_user(email)
        
        # Get allowed MCPs
        allowed_mcps = user_service.get_allowed_mcps(email)
        
        return {
            "email": email,
            "name": user_config.get("name", email.split("@")[0]),
            "role": user_config.get("role", "read_only"),
            "allowed_mcps": allowed_mcps,
            "allowed_domains": user_config.get("allowed_domains", []),
            "teams": user_config.get("teams", []),
            "slack_user_id": user_config.get("slack_user_id"),
            "is_default": user_config.get("email") == email and email not in [u["email"] for u in settings.users_config.get("super_admins", [])]
        }
        
    except Exception as e:
        logger.error("Failed to get user info", email=email, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve user info: {str(e)}"
        )


@router.get("/users")
async def list_users() -> Dict:
    """
    List all configured users
    
    Returns:
        Dict with users list and statistics
    """
    try:
        users_config = settings.users_config
        
        # Extract users list
        users = users_config.get("users", [])
        super_admins = users_config.get("super_admins", [])
        
        return {
            "total_users": len(users) + len(super_admins),
            "super_admins": len(super_admins),
            "regular_users": len(users),
            "users": [
                {
                    "email": user.get("email"),
                    "name": user.get("name"),
                    "role": user.get("role"),
                    "teams": user.get("teams", [])
                }
                for user in users + super_admins
            ]
        }
        
    except Exception as e:
        logger.error("Failed to list users", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list users: {str(e)}"
        )
