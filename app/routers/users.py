"""
User Management Endpoints

Provides user information, roles, and permissions
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict

from app.services.user_service import UserService, get_user_service
from app.utils.logger import logger


router = APIRouter()


@router.get("/users/{email}")
async def get_user_info(email: str, user_service: UserService = Depends(get_user_service)) -> Dict:
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
        user_config = await user_service.get_user(email)
        
        # Get allowed MCPs
        allowed_mcps = await user_service.get_allowed_mcps(email)
        
        return {
            "email": email,
            "name": user_config.get("name", email.split("@")[0]),
            "role": user_config.get("role", "read_only"),
            "allowed_mcps": allowed_mcps,
            "allowed_domains": user_config.get("allowed_domains", []),
            "allowed_databases": user_config.get("allowed_databases", []),
            "teams": user_config.get("teams", []),
            "slack_user_id": user_config.get("slack_user_id"),
            "allow_all_mcps": user_config.get("allow_all_mcps", False),
            "is_default": user_config.get("is_default", False),
        }
        
    except Exception as e:
        logger.error("Failed to get user info", email=email, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve user info: {str(e)}"
        )


@router.get("/users")
async def list_users(user_service: UserService = Depends(get_user_service)) -> Dict:
    """
    List all configured users
    
    Returns:
        Dict with users list and statistics
    """
    try:
        users_list = await user_service.list_users()
        super_admins = [u for u in users_list if u.get("is_super_admin")]
        return {
            "total_users": len(users_list),
            "super_admins": len(super_admins),
            "regular_users": len(users_list) - len(super_admins),
            "users": users_list,
        }
        
    except Exception as e:
        logger.error("Failed to list users", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list users: {str(e)}"
        )
