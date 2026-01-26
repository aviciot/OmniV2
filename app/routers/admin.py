"""
Admin Router - Permission Management

Endpoints for managing MCP permissions:
- Role permissions (developer, qa, dba, etc.)
- Team roles (team to role mapping)
- User-specific overrides
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db
from app.models import RolePermission, TeamRole, UserMCPPermission
from app.services.user_service import get_user_service
from app.utils.logger import logger

router = APIRouter(prefix="/admin/permissions", tags=["admin", "permissions"])


# ============================================================================
# Pydantic Models
# ============================================================================

class PermissionBase(BaseModel):
    mode: str  # all, custom, none, inherit
    allowed_tools: Optional[List[str]] = None
    denied_tools: Optional[List[str]] = None
    description: Optional[str] = None


class RolePermissionCreate(PermissionBase):
    role_name: str
    mcp_name: str


class TeamRoleCreate(BaseModel):
    team_name: str
    default_role: str
    description: Optional[str] = None


class UserPermissionCreate(PermissionBase):
    user_id: int
    mcp_name: str


# ============================================================================
# Role Permission Endpoints
# ============================================================================

@router.get("/roles")
async def list_role_permissions(db: AsyncSession = Depends(get_db)):
    """List all role permissions"""
    result = await db.execute(select(RolePermission).where(RolePermission.is_active == True))
    permissions = result.scalars().all()
    return [
        {
            "id": p.id,
            "role_name": p.role_name,
            "mcp_name": p.mcp_name,
            "mode": p.mode,
            "allowed_tools": p.allowed_tools,
            "denied_tools": p.denied_tools,
            "description": p.description
        }
        for p in permissions
    ]


@router.get("/roles/{role_name}")
async def get_role_permissions(role_name: str, db: AsyncSession = Depends(get_db)):
    """Get permissions for specific role"""
    result = await db.execute(
        select(RolePermission).where(
            RolePermission.role_name == role_name,
            RolePermission.is_active == True
        )
    )
    permissions = result.scalars().all()
    return [
        {
            "id": p.id,
            "mcp_name": p.mcp_name,
            "mode": p.mode,
            "allowed_tools": p.allowed_tools,
            "denied_tools": p.denied_tools,
            "description": p.description
        }
        for p in permissions
    ]


@router.post("/roles")
async def create_role_permission(perm: RolePermissionCreate, db: AsyncSession = Depends(get_db)):
    """Create or update role permission"""
    # Check if exists
    result = await db.execute(
        select(RolePermission).where(
            RolePermission.role_name == perm.role_name,
            RolePermission.mcp_name == perm.mcp_name
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        # Update
        existing.mode = perm.mode
        existing.allowed_tools = perm.allowed_tools
        existing.denied_tools = perm.denied_tools
        existing.description = perm.description
        existing.is_active = True
        await db.commit()
        await db.refresh(existing)
        logger.info(f"Updated role permission: {perm.role_name}/{perm.mcp_name}")
        return {"status": "updated", "id": existing.id}
    else:
        # Create
        new_perm = RolePermission(
            role_name=perm.role_name,
            mcp_name=perm.mcp_name,
            mode=perm.mode,
            allowed_tools=perm.allowed_tools,
            denied_tools=perm.denied_tools,
            description=perm.description
        )
        db.add(new_perm)
        await db.commit()
        await db.refresh(new_perm)
        logger.info(f"Created role permission: {perm.role_name}/{perm.mcp_name}")
        return {"status": "created", "id": new_perm.id}


@router.delete("/roles/{role_name}/{mcp_name}")
async def delete_role_permission(role_name: str, mcp_name: str, db: AsyncSession = Depends(get_db)):
    """Delete role permission (soft delete)"""
    result = await db.execute(
        select(RolePermission).where(
            RolePermission.role_name == role_name,
            RolePermission.mcp_name == mcp_name
        )
    )
    perm = result.scalar_one_or_none()
    
    if not perm:
        raise HTTPException(status_code=404, detail="Permission not found")
    
    perm.is_active = False
    await db.commit()
    logger.info(f"Deleted role permission: {role_name}/{mcp_name}")
    return {"status": "deleted"}


# ============================================================================
# Team Role Endpoints
# ============================================================================

@router.get("/teams")
async def list_team_roles(db: AsyncSession = Depends(get_db)):
    """List all team roles"""
    result = await db.execute(select(TeamRole).where(TeamRole.is_active == True))
    teams = result.scalars().all()
    return [
        {
            "id": t.id,
            "team_name": t.team_name,
            "default_role": t.default_role,
            "description": t.description
        }
        for t in teams
    ]


@router.post("/teams")
async def create_team_role(team: TeamRoleCreate, db: AsyncSession = Depends(get_db)):
    """Create or update team role"""
    # Check if exists
    result = await db.execute(
        select(TeamRole).where(TeamRole.team_name == team.team_name)
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        # Update
        existing.default_role = team.default_role
        existing.description = team.description
        existing.is_active = True
        await db.commit()
        await db.refresh(existing)
        logger.info(f"Updated team role: {team.team_name} -> {team.default_role}")
        return {"status": "updated", "id": existing.id}
    else:
        # Create
        new_team = TeamRole(
            team_name=team.team_name,
            default_role=team.default_role,
            description=team.description
        )
        db.add(new_team)
        await db.commit()
        await db.refresh(new_team)
        logger.info(f"Created team role: {team.team_name} -> {team.default_role}")
        return {"status": "created", "id": new_team.id}


@router.delete("/teams/{team_name}")
async def delete_team_role(team_name: str, db: AsyncSession = Depends(get_db)):
    """Delete team role (soft delete)"""
    result = await db.execute(
        select(TeamRole).where(TeamRole.team_name == team_name)
    )
    team = result.scalar_one_or_none()
    
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    team.is_active = False
    await db.commit()
    logger.info(f"Deleted team role: {team_name}")
    return {"status": "deleted"}


# ============================================================================
# User Permission Endpoints
# ============================================================================

@router.get("/users/{user_id}")
async def get_user_permissions(user_id: int, db: AsyncSession = Depends(get_db)):
    """Get user-specific permission overrides"""
    result = await db.execute(
        select(UserMCPPermission).where(UserMCPPermission.user_id == user_id)
    )
    permissions = result.scalars().all()
    return [
        {
            "id": p.id,
            "mcp_name": p.mcp_name,
            "mode": p.mode,
            "allowed_tools": p.allowed_tools,
            "denied_tools": p.denied_tools
        }
        for p in permissions
    ]


@router.post("/users")
async def create_user_permission(perm: UserPermissionCreate, db: AsyncSession = Depends(get_db)):
    """Create or update user-specific permission override"""
    # Check if exists
    result = await db.execute(
        select(UserMCPPermission).where(
            UserMCPPermission.user_id == perm.user_id,
            UserMCPPermission.mcp_name == perm.mcp_name
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        # Update
        existing.mode = perm.mode
        existing.allowed_tools = perm.allowed_tools
        existing.denied_tools = perm.denied_tools
        await db.commit()
        await db.refresh(existing)
        logger.info(f"Updated user permission: user={perm.user_id}, mcp={perm.mcp_name}")
        
        # Invalidate cache
        user_service = get_user_service()
        user_service.invalidate_permission_cache(str(perm.user_id))
        
        return {"status": "updated", "id": existing.id}
    else:
        # Create
        new_perm = UserMCPPermission(
            user_id=perm.user_id,
            mcp_name=perm.mcp_name,
            mode=perm.mode,
            allowed_tools=perm.allowed_tools,
            denied_tools=perm.denied_tools
        )
        db.add(new_perm)
        await db.commit()
        await db.refresh(new_perm)
        logger.info(f"Created user permission: user={perm.user_id}, mcp={perm.mcp_name}")
        
        # Invalidate cache
        user_service = get_user_service()
        user_service.invalidate_permission_cache(str(perm.user_id))
        
        return {"status": "created", "id": new_perm.id}


@router.delete("/users/{user_id}/{mcp_name}")
async def delete_user_permission(user_id: int, mcp_name: str, db: AsyncSession = Depends(get_db)):
    """Delete user permission override"""
    result = await db.execute(
        delete(UserMCPPermission).where(
            UserMCPPermission.user_id == user_id,
            UserMCPPermission.mcp_name == mcp_name
        )
    )
    await db.commit()
    
    # Invalidate cache
    user_service = get_user_service()
    user_service.invalidate_permission_cache(str(user_id))
    
    logger.info(f"Deleted user permission: user={user_id}, mcp={mcp_name}")
    return {"status": "deleted"}


# ============================================================================
# Cache Management
# ============================================================================

@router.post("/cache/invalidate")
async def invalidate_permission_cache(user_id: Optional[int] = None):
    """Invalidate permission cache"""
    user_service = get_user_service()
    if user_id:
        user_service.invalidate_permission_cache(str(user_id))
        return {"status": "ok", "message": f"Cache invalidated for user {user_id}"}
    else:
        user_service.invalidate_permission_cache()
        return {"status": "ok", "message": "All permission caches invalidated"}
