"""
User Service

Handles user lookup, permissions, and MCP access control.
Supports both MCP-level and tool-level permissions.
"""

from typing import Dict, List, Optional, Any, Union
import time
import fnmatch
from app.config import settings
from app.utils.logger import logger


class UserService:
    """Service for managing user permissions and MCP access."""
    
    # Cache TTL for permission lookups (5 minutes)
    PERMISSION_CACHE_TTL = 300
    
    def __init__(self):
        """Initialize user service with config."""
        self.default_user = settings.users_config.get("default_user", {})
        self.super_admins = settings.users_config.get("super_admins", [])
        self.users = {user["email"]: user for user in settings.users_config.get("users", [])}
        
        # Permission cache: {user_id: {mcp_name: {allowed_tools: [...], timestamp: ...}}}
        self._permission_cache: Dict[str, Dict[str, Dict[str, Any]]] = {}
        
    def _get_mcp_config(self, mcp_name: str) -> Optional[Dict]:
        """Get MCP configuration from settings."""
        for mcp in settings.mcps.mcps:
            if mcp.name == mcp_name:
                return mcp
        return None
        
    def get_user(self, user_id: str) -> Dict[str, Any]:
        """
        Get user configuration by ID (email).
        
        Args:
            user_id: User email address
            
        Returns:
            User config dict
        """
        # Check super admins first
        for admin in self.super_admins:
            if admin["email"] == user_id:
                return admin
        
        # Check regular users
        if user_id in self.users:
            return self.users[user_id]
        
        # Return default user for unknown users
        logger.warning(
            "Unknown user, using default configuration",
            user_id=user_id,
            default_role=self.default_user["role"],
        )
        return {
            **self.default_user,
            "email": user_id,
            "name": "Guest User",
        }
    
    def get_allowed_mcps(self, user_id: str) -> Union[str, List[str]]:
        """
        Get list of MCPs user can access.
        
        Args:
            user_id: User email address
            
        Returns:
            List of MCP names or "*" for all
        """
        user = self.get_user(user_id)
        allowed = user.get("allowed_mcps", [])
        
        if allowed == "*":
            return "*"
        
        # Handle new dict format {mcp_name: {mode: "custom", tools: [...]}}
        if isinstance(allowed, dict):
            return list(allowed.keys())
        
        return allowed if isinstance(allowed, list) else []
    
    def can_access_mcp(self, user_id: str, mcp_name: str) -> bool:
        """
        Check if user can access specific MCP.
        
        Args:
            user_id: User email address
            mcp_name: Name of MCP server
            
        Returns:
            True if user has access
        """
        allowed_mcps = self.get_allowed_mcps(user_id)
        
        if allowed_mcps == "*":
            return True
        
        return mcp_name in allowed_mcps
    
    def get_allowed_domains(self, user_id: str) -> Union[str, List[str]]:
        """
        Get list of knowledge domains user can query.
        
        Args:
            user_id: User email address
            
        Returns:
            List of domain names or "*" for all
        """
        user = self.get_user(user_id)
        allowed = user.get("allowed_domains", [])
        
        if allowed == "*":
            return "*"
        
        return allowed if isinstance(allowed, list) else []
    
    def can_ask_domain(self, user_id: str, domain: str) -> bool:
        """
        Check if user can ask questions in specific domain.
        
        Args:
            user_id: User email address
            domain: Domain name (e.g., "python_help")
            
        Returns:
            True if user has access
        """
        allowed_domains = self.get_allowed_domains(user_id)
        
        if allowed_domains == "*":
            return True
        
        return domain in allowed_domains
    
    def get_user_allowed_tools(self, user_id: str, mcp_name: str, all_tools: List[str]) -> List[str]:
        """
        Get list of tools user can access within an MCP.
        Supports both old format (list) and new format (dict with tool restrictions).
        
        Args:
            user_id: User email address
            mcp_name: Name of MCP server
            all_tools: Complete list of tools available in the MCP
            
        Returns:
            List of tool names user can access
        """
        # Check cache first
        cache_key = f"{user_id}:{mcp_name}"
        if user_id in self._permission_cache and mcp_name in self._permission_cache[user_id]:
            cached = self._permission_cache[user_id][mcp_name]
            age = time.time() - cached.get("timestamp", 0)
            if age < self.PERMISSION_CACHE_TTL:
                logger.debug(
                    "Using cached tool permissions",
                    user=user_id,
                    mcp=mcp_name,
                    cache_age=round(age, 1)
                )
                return cached["allowed_tools"]
        
        user = self.get_user(user_id)
        role = user.get("role", "read_only")
        allowed_mcps = user.get("allowed_mcps", [])
        
        # Check if user has access to this MCP at all
        if not self.can_access_mcp(user_id, mcp_name):
            return []
        
        # Admins bypass all restrictions
        if role == "admin" or allowed_mcps == "*":
            result = all_tools
        else:
            # Determine permission mode
            if isinstance(allowed_mcps, list):
                # OLD FORMAT: Simple list means inherit role defaults
                if mcp_name in allowed_mcps:
                    result = self._get_role_tools(role, mcp_name, all_tools)
                else:
                    result = []
            elif isinstance(allowed_mcps, dict):
                # NEW FORMAT: Check if MCP has custom tool list
                mcp_config = allowed_mcps.get(mcp_name)
                
                if mcp_config is None:
                    result = []
                elif isinstance(mcp_config, str):
                    # allowed_mcps: {database_mcp: "*"}
                    result = all_tools if mcp_config == "*" else []
                elif isinstance(mcp_config, dict):
                    # NEW GRANULAR FORMAT
                    mode = mcp_config.get("mode", "inherit")
                    
                    if mode == "inherit":
                        # Use role defaults
                        result = self._get_role_tools(role, mcp_name, all_tools)
                    elif mode == "custom":
                        # User-specific tool list
                        allowed_tools = mcp_config.get("tools", [])
                        denied_tools = mcp_config.get("deny", [])
                        
                        # Start with allowed tools
                        result = [t for t in all_tools if self._matches_patterns(t, allowed_tools)]
                        
                        # Remove denied tools
                        result = [t for t in result if not self._matches_patterns(t, denied_tools)]
                    elif mode == "all":
                        result = all_tools
                    else:
                        result = []
                else:
                    result = []
            else:
                result = []
        
        # Cache the result
        if user_id not in self._permission_cache:
            self._permission_cache[user_id] = {}
        self._permission_cache[user_id][mcp_name] = {
            "allowed_tools": result,
            "timestamp": time.time()
        }
        
        logger.info(
            "Resolved tool permissions",
            user=user_id,
            role=role,
            mcp=mcp_name,
            total_tools=len(all_tools),
            allowed_tools=len(result)
        )
        
        return result
    
    def _get_role_tools(self, role: str, mcp_name: str, all_tools: List[str]) -> List[str]:
        """
        Get tools allowed for a role based on MCP role_restrictions.
        
        Args:
            role: User role (admin, dba, power_user, etc.)
            mcp_name: Name of MCP server
            all_tools: Complete list of tools available in the MCP
            
        Returns:
            List of tools allowed for this role
        """
        mcp_config = self._get_mcp_config(mcp_name)
        if not mcp_config:
            return all_tools
        
        role_restrictions = mcp_config.role_restrictions or {}
        role_config = role_restrictions.get(role, {})
        
        # Check allow_all
        if role_config.get("allow_all"):
            return all_tools
        
        # Check deny_all
        if role_config.get("deny_all"):
            return []
        
        # Check allow_only
        allow_only = role_config.get("allow_only", [])
        if allow_only:
            return [t for t in all_tools if self._matches_patterns(t, allow_only)]
        
        # Check allow_all_except / deny
        deny = role_config.get("deny", []) or role_config.get("allow_all_except", [])
        if deny:
            return [t for t in all_tools if not self._matches_patterns(t, deny)]
        
        # Default: allow all if no restrictions specified
        return all_tools
    
    def _matches_patterns(self, tool_name: str, patterns: List[str]) -> bool:
        """
        Check if tool name matches any pattern (supports wildcards).
        
        Args:
            tool_name: Name of the tool
            patterns: List of patterns (can include wildcards like "get_*")
            
        Returns:
            True if tool matches any pattern
        """
        for pattern in patterns:
            if fnmatch.fnmatch(tool_name, pattern) or pattern == "*":
                return True
        return False
    
    def can_use_tool(self, user_id: str, mcp_name: str, tool_name: str, all_tools: List[str]) -> bool:
        """
        Check if user can use a specific tool.
        
        Args:
            user_id: User email address
            mcp_name: Name of MCP server
            tool_name: Name of the tool
            all_tools: Complete list of tools available in the MCP
            
        Returns:
            True if user has permission
        """
        allowed_tools = self.get_user_allowed_tools(user_id, mcp_name, all_tools)
        return tool_name in allowed_tools
    
    def invalidate_permission_cache(self, user_id: Optional[str] = None):
        """
        Invalidate permission cache for specific user or all users.
        
        Args:
            user_id: Optional user to invalidate, None for all
        """
        if user_id:
            self._permission_cache.pop(user_id, None)
            logger.info("Invalidated permission cache", user=user_id)
        else:
            self._permission_cache.clear()
            logger.info("Invalidated all permission caches")


# Global user service instance
_user_service: Optional[UserService] = None


def get_user_service() -> UserService:
    """
    Get or create the global user service instance.
    
    Returns:
        UserService instance
    """
    global _user_service
    if _user_service is None:
        _user_service = UserService()
    return _user_service
