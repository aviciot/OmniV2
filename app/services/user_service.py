"""
User Service

Handles user lookup, permissions, and MCP access control.
Supports both MCP-level and tool-level permissions.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any, Union
import time
import fnmatch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import User, UserTeam, UserMCPPermission, UserSettings
from app.utils.logger import logger


class UserService:
    """Service for managing user permissions and MCP access."""

    # Cache TTL for permission lookups (5 minutes)
    PERMISSION_CACHE_TTL = 300
    USER_CACHE_TTL = 300
    SETTINGS_CACHE_TTL = 300

    def __init__(self) -> None:
        self._permission_cache: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._user_cache: Dict[str, Dict[str, Any]] = {}
        self._settings_cache: Optional[Dict[str, Any]] = None

    def _get_session(self) -> AsyncSession:
        if AsyncSessionLocal is None:
            raise RuntimeError("Database not initialized. Call init_db() first.")
        return AsyncSessionLocal()

    async def _load_settings(self) -> Dict[str, Any]:
        cached = self._settings_cache
        if cached:
            age = time.time() - cached.get("timestamp", 0)
            if age < self.SETTINGS_CACHE_TTL:
                return cached["data"]

        data: Dict[str, Any] = {}
        if AsyncSessionLocal is None:
            data = settings.users_config
        else:
            async with self._get_session() as session:
                result = await session.execute(
                    select(UserSettings).order_by(UserSettings.id.desc()).limit(1)
                )
                row = result.scalar_one_or_none()
                if row:
                    data = {
                        "default_user": row.default_user or {},
                        "auto_provisioning": row.auto_provisioning or {},
                        "session": row.session or {},
                        "restrictions": row.restrictions or {},
                        "user_audit": row.user_audit or {},
                    }
                else:
                    data = settings.users_config

        self._settings_cache = {"data": data, "timestamp": time.time()}
        return data

    async def _get_default_user(self) -> Dict[str, Any]:
        settings_data = await self._load_settings()
        default_user = settings_data.get("default_user") or {}
        return default_user

    def _normalize_allowlist(self, value: Any) -> Union[str, List[str]]:
        if value == "*":
            return "*"
        if isinstance(value, list):
            if "*" in value:
                return "*"
            return value
        return []

    def _permissions_from_allowed_mcps(self, allowed_mcps: Any) -> Dict[str, Dict[str, Any]]:
        permissions: Dict[str, Dict[str, Any]] = {}
        if allowed_mcps == "*":
            return permissions
        if isinstance(allowed_mcps, list):
            for name in allowed_mcps:
                permissions[name] = {"mode": "inherit", "tools": [], "deny": []}
            return permissions
        if isinstance(allowed_mcps, dict):
            for name, entry in allowed_mcps.items():
                permissions[name] = self._normalize_permission_entry(entry)
            return permissions
        return permissions

    def _normalize_permission_entry(self, entry: Any) -> Dict[str, Any]:
        if entry is None:
            return {"mode": "none", "tools": [], "deny": []}
        if isinstance(entry, str):
            if entry == "*":
                return {"mode": "all", "tools": [], "deny": []}
            return {"mode": "none", "tools": [], "deny": []}
        if isinstance(entry, dict):
            mode = entry.get("mode", "inherit")
            tools = entry.get("tools") or entry.get("allowed_tools") or []
            deny = entry.get("deny") or entry.get("denied_tools") or []
            return {"mode": mode, "tools": tools, "deny": deny}
        return {"mode": "none", "tools": [], "deny": []}

    async def _load_user_from_db(self, user_id: str) -> Optional[Dict[str, Any]]:
        async with self._get_session() as session:
            result = await session.execute(select(User).where(User.email == user_id))
            user = result.scalar_one_or_none()
            if not user:
                return None

            team_result = await session.execute(
                select(UserTeam.team_name).where(UserTeam.user_id == user.id)
            )
            teams = [row[0] for row in team_result.all()]

            perm_result = await session.execute(
                select(UserMCPPermission).where(UserMCPPermission.user_id == user.id)
            )
            permissions: Dict[str, Dict[str, Any]] = {}
            for perm in perm_result.scalars().all():
                permissions[perm.mcp_name] = {
                    "mode": perm.mode or "inherit",
                    "tools": perm.allowed_tools or [],
                    "deny": perm.denied_tools or [],
                }

            return {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "role": user.role,
                "slack_user_id": user.slack_user_id,
                "is_active": user.is_active,
                "is_super_admin": user.is_super_admin,
                "allow_all_mcps": user.allow_all_mcps,
                "allowed_domains": user.allowed_domains,
                "allowed_databases": user.allowed_databases,
                "teams": teams,
                "mcp_permissions": permissions,
            }

    async def get_user(self, user_id: str) -> Dict[str, Any]:
        cached = self._user_cache.get(user_id)
        if cached:
            age = time.time() - cached.get("timestamp", 0)
            if age < self.USER_CACHE_TTL:
                return cached["data"]

        user_data = await self._load_user_from_db(user_id) if AsyncSessionLocal else None

        if not user_data:
            default_user = await self._get_default_user()
            guest = {
                **default_user,
                "email": user_id,
                "name": default_user.get("name") or "Guest User",
                "role": default_user.get("role") or "read_only",
                "teams": default_user.get("teams", []),
                "slack_user_id": default_user.get("slack_user_id"),
                "allow_all_mcps": default_user.get("allow_all_mcps", False),
                "is_default": True,
            }
            self._user_cache[user_id] = {
                "data": guest,
                "mcp_permissions": self._permissions_from_allowed_mcps(guest.get("allowed_mcps")),
                "timestamp": time.time(),
            }
            logger.warning(
                "Unknown user, using default configuration",
                user_id=user_id,
                default_role=guest.get("role"),
            )
            return guest

        default_user = await self._get_default_user()
        allowed_domains = user_data.get("allowed_domains")
        allowed_databases = user_data.get("allowed_databases")
        if not allowed_domains:
            allowed_domains = default_user.get("allowed_domains", [])
        if not allowed_databases:
            allowed_databases = default_user.get("allowed_databases", [])

        allow_all_mcps = bool(user_data.get("allow_all_mcps"))
        is_super_admin = bool(user_data.get("is_super_admin"))
        role = user_data.get("role") or "read_only"

        permissions = user_data.get("mcp_permissions", {})
        if not permissions:
            fallback_allowed = default_user.get("allowed_mcps", [])
            if fallback_allowed == "*":
                allow_all_mcps = True
            permissions = self._permissions_from_allowed_mcps(fallback_allowed)

        if allow_all_mcps or is_super_admin or role == "admin":
            allowed_mcps: Union[str, List[str]] = "*"
        else:
            allowed_mcps = sorted(permissions.keys())

        user_payload = {
            **user_data,
            "role": role,
            "allowed_mcps": allowed_mcps,
            "allowed_domains": self._normalize_allowlist(allowed_domains),
            "allowed_databases": self._normalize_allowlist(allowed_databases),
            "is_default": False,
        }

        self._user_cache[user_id] = {
            "data": user_payload,
            "mcp_permissions": permissions,
            "timestamp": time.time(),
        }

        return user_payload

    async def list_users(self) -> List[Dict[str, Any]]:
        if AsyncSessionLocal is None:
            users_config = settings.users_config
            combined = users_config.get("users", []) + users_config.get("super_admins", [])
            return [
                {
                    "email": entry.get("email"),
                    "name": entry.get("name"),
                    "role": entry.get("role"),
                    "teams": entry.get("teams", []),
                    "is_super_admin": entry.get("is_super_admin", False),
                }
                for entry in combined
            ]

        async with self._get_session() as session:
            result = await session.execute(select(User))
            users = result.scalars().all()

            user_ids = [user.id for user in users]
            team_map: Dict[int, List[str]] = {user_id: [] for user_id in user_ids}
            if user_ids:
                team_result = await session.execute(
                    select(UserTeam.user_id, UserTeam.team_name).where(UserTeam.user_id.in_(user_ids))
                )
                for user_id, team_name in team_result.all():
                    team_map.setdefault(user_id, []).append(team_name)

            return [
                {
                    "email": user.email,
                    "name": user.name,
                    "role": user.role,
                    "teams": team_map.get(user.id, []),
                    "is_super_admin": user.is_super_admin,
                    "is_active": user.is_active,
                }
                for user in users
            ]

    async def _get_user_permissions(self, user_id: str) -> Dict[str, Dict[str, Any]]:
        cached = self._user_cache.get(user_id)
        if cached:
            age = time.time() - cached.get("timestamp", 0)
            if age < self.USER_CACHE_TTL:
                return cached.get("mcp_permissions", {})
        await self.get_user(user_id)
        cached = self._user_cache.get(user_id)
        if cached:
            return cached.get("mcp_permissions", {})
        return {}

    async def get_allowed_mcps(self, user_id: str) -> Union[str, List[str]]:
        user = await self.get_user(user_id)
        allowed = user.get("allowed_mcps", [])
        if allowed == "*":
            return "*"
        if isinstance(allowed, dict):
            return list(allowed.keys())
        return allowed if isinstance(allowed, list) else []

    async def can_access_mcp(self, user_id: str, mcp_name: str) -> bool:
        allowed_mcps = await self.get_allowed_mcps(user_id)
        if allowed_mcps == "*":
            return True
        return mcp_name in allowed_mcps

    async def get_allowed_domains(self, user_id: str) -> Union[str, List[str]]:
        user = await self.get_user(user_id)
        allowed = user.get("allowed_domains", [])
        return self._normalize_allowlist(allowed)

    async def can_ask_domain(self, user_id: str, domain: str) -> bool:
        allowed_domains = await self.get_allowed_domains(user_id)
        if allowed_domains == "*":
            return True
        return domain in allowed_domains

    async def get_user_allowed_tools(self, user_id: str, mcp_name: str, all_tools: List[str]) -> List[str]:
        cache_key = f"{user_id}:{mcp_name}"
        if user_id in self._permission_cache and mcp_name in self._permission_cache[user_id]:
            cached = self._permission_cache[user_id][mcp_name]
            age = time.time() - cached.get("timestamp", 0)
            if age < self.PERMISSION_CACHE_TTL:
                logger.debug(
                    "Using cached tool permissions",
                    user=user_id,
                    mcp=mcp_name,
                    cache_age=round(age, 1),
                )
                return cached["allowed_tools"]

        user = await self.get_user(user_id)
        role = user.get("role", "read_only")
        allowed_mcps = user.get("allowed_mcps", [])

        if not await self.can_access_mcp(user_id, mcp_name):
            return []

        if role == "admin" or allowed_mcps == "*":
            result = all_tools
        else:
            permissions = await self._get_user_permissions(user_id)
            mcp_config = permissions.get(mcp_name)

            if mcp_config is None:
                result = []
            else:
                normalized = self._normalize_permission_entry(mcp_config)
                mode = normalized.get("mode", "inherit")

                if mode == "inherit":
                    result = self._get_role_tools(role, mcp_name, all_tools)
                elif mode == "custom":
                    allowed_tools = normalized.get("tools", [])
                    denied_tools = normalized.get("deny", [])
                    result = [t for t in all_tools if self._matches_patterns(t, allowed_tools)]
                    result = [t for t in result if not self._matches_patterns(t, denied_tools)]
                elif mode == "all":
                    result = all_tools
                else:
                    result = []

        if user_id not in self._permission_cache:
            self._permission_cache[user_id] = {}
        self._permission_cache[user_id][mcp_name] = {
            "allowed_tools": result,
            "timestamp": time.time(),
        }

        logger.info(
            "Resolved tool permissions",
            user=user_id,
            role=role,
            mcp=mcp_name,
            total_tools=len(all_tools),
            allowed_tools=len(result),
        )

        return result

    def _get_role_tools(self, role: str, mcp_name: str, all_tools: List[str]) -> List[str]:
        mcp_config = self._get_mcp_config(mcp_name)
        if not mcp_config:
            return all_tools

        role_restrictions = mcp_config.role_restrictions or {}
        role_config = role_restrictions.get(role, {})

        if role_config.get("allow_all"):
            return all_tools
        if role_config.get("deny_all"):
            return []

        allow_only = role_config.get("allow_only", [])
        if allow_only:
            return [t for t in all_tools if self._matches_patterns(t, allow_only)]

        deny = role_config.get("deny", []) or role_config.get("allow_all_except", [])
        if deny:
            return [t for t in all_tools if not self._matches_patterns(t, deny)]

        return all_tools

    def _matches_patterns(self, tool_name: str, patterns: List[str]) -> bool:
        for pattern in patterns:
            if fnmatch.fnmatch(tool_name, pattern) or pattern == "*":
                return True
        return False

    def _get_mcp_config(self, mcp_name: str) -> Optional[Dict]:
        for mcp in settings.mcps.mcps:
            if mcp.name == mcp_name:
                return mcp
        return None

    async def can_use_tool(self, user_id: str, mcp_name: str, tool_name: str, all_tools: List[str]) -> bool:
        allowed_tools = await self.get_user_allowed_tools(user_id, mcp_name, all_tools)
        return tool_name in allowed_tools

    def invalidate_permission_cache(self, user_id: Optional[str] = None) -> None:
        if user_id:
            self._permission_cache.pop(user_id, None)
            self._user_cache.pop(user_id, None)
            logger.info("Invalidated permission cache", user=user_id)
        else:
            self._permission_cache.clear()
            self._user_cache.clear()
            logger.info("Invalidated all permission caches")


_user_service: Optional[UserService] = None


def get_user_service() -> UserService:
    """Get or create the global user service instance."""
    global _user_service
    if _user_service is None:
        _user_service = UserService()
    return _user_service
