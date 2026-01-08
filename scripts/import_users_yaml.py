"""
Import users.yaml into the Omni2 database.

Usage:
    python scripts/import_users_yaml.py
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Tuple

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from sqlalchemy import select, delete

from app.config import config_loader
from app import database
from app.models import User, UserTeam, UserMCPPermission, Role, Team, UserSettings


def _extract_role_fields(role_data: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    data = dict(role_data)
    display_name = data.pop("display_name", "")
    description = data.pop("description", "")
    color = data.pop("color", None)
    rate_limit = data.pop("rate_limit", {}) or {}
    permissions = data
    return (
        {
            "display_name": display_name or role_data.get("name", ""),
            "description": description,
            "color": color,
        },
        {
            "permissions": permissions,
            "rate_limit": rate_limit,
        },
    )


def _permission_rows(allowed_mcps: Any) -> Tuple[bool, List[Dict[str, Any]]]:
    if allowed_mcps == "*":
        return True, []
    rows: List[Dict[str, Any]] = []
    if isinstance(allowed_mcps, list):
        for mcp_name in allowed_mcps:
            rows.append({"mcp_name": mcp_name, "mode": "inherit", "allowed_tools": [], "denied_tools": []})
        return False, rows
    if isinstance(allowed_mcps, dict):
        for mcp_name, entry in allowed_mcps.items():
            if isinstance(entry, str):
                mode = "all" if entry == "*" else "none"
                rows.append({"mcp_name": mcp_name, "mode": mode, "allowed_tools": [], "denied_tools": []})
            elif isinstance(entry, dict):
                rows.append(
                    {
                        "mcp_name": mcp_name,
                        "mode": entry.get("mode", "inherit"),
                        "allowed_tools": entry.get("tools", []) or [],
                        "denied_tools": entry.get("deny", []) or [],
                    }
                )
    return False, rows


async def main() -> None:
    await database.init_db()

    users_yaml = config_loader.load_users_yaml()
    default_user = users_yaml.get("default_user", {})
    super_admins = users_yaml.get("super_admins", [])
    users = users_yaml.get("users", [])
    roles = users_yaml.get("roles", {})
    teams = users_yaml.get("teams", {})

    if database.AsyncSessionLocal is None:
        raise RuntimeError("Database session not initialized")

    async with database.AsyncSessionLocal() as session:
        # Upsert roles
        for role_name, role_data in roles.items():
            meta, config = _extract_role_fields(role_data)
            result = await session.execute(select(Role).where(Role.name == role_name))
            role = result.scalar_one_or_none()
            if role:
                role.display_name = meta["display_name"] or role.display_name
                role.description = meta["description"]
                role.color = meta["color"]
                role.permissions = config["permissions"]
                role.rate_limit = config["rate_limit"]
            else:
                session.add(
                    Role(
                        name=role_name,
                        display_name=meta["display_name"] or role_name,
                        description=meta["description"],
                        color=meta["color"],
                        permissions=config["permissions"],
                        rate_limit=config["rate_limit"],
                    )
                )

        # Upsert teams
        for team_key, team_data in teams.items():
            result = await session.execute(select(Team).where(Team.name == team_key))
            team = result.scalar_one_or_none()
            display_name = team_data.get("name") or team_key
            if team:
                team.display_name = display_name
                team.description = team_data.get("description")
                team.slack_channel = team_data.get("slack_channel")
                team.notify_on_errors = bool(team_data.get("notify_on_errors", False))
            else:
                session.add(
                    Team(
                        name=team_key,
                        display_name=display_name,
                        description=team_data.get("description"),
                        slack_channel=team_data.get("slack_channel"),
                        notify_on_errors=bool(team_data.get("notify_on_errors", False)),
                    )
                )

        # Upsert user settings singleton
        settings_payload = {
            "default_user": default_user or {},
            "auto_provisioning": users_yaml.get("auto_provisioning", {}) or {},
            "session": users_yaml.get("session", {}) or {},
            "restrictions": users_yaml.get("restrictions", {}) or {},
            "user_audit": users_yaml.get("user_audit", {}) or {},
        }
        result = await session.execute(select(UserSettings).order_by(UserSettings.id.desc()).limit(1))
        settings_row = result.scalar_one_or_none()
        if settings_row:
            settings_row.default_user = settings_payload["default_user"]
            settings_row.auto_provisioning = settings_payload["auto_provisioning"]
            settings_row.session = settings_payload["session"]
            settings_row.restrictions = settings_payload["restrictions"]
            settings_row.user_audit = settings_payload["user_audit"]
        else:
            session.add(UserSettings(**settings_payload))

        # Upsert users
        for user_entry in super_admins + users:
            email = user_entry.get("email")
            if not email:
                continue
            result = await session.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()

            allowed_mcps = user_entry.get("allowed_mcps", [])
            allow_all_mcps, permission_rows = _permission_rows(allowed_mcps)

            if user:
                user.name = user_entry.get("name") or user.name
                user.role = user_entry.get("role") or user.role
                user.slack_user_id = user_entry.get("slack_user_id")
                user.is_super_admin = user_entry in super_admins
                user.is_active = user_entry.get("is_active", True)
                user.allow_all_mcps = allow_all_mcps
                user.allowed_domains = user_entry.get("allowed_domains")
                user.allowed_databases = user_entry.get("allowed_databases")
            else:
                user = User(
                    email=email,
                    name=user_entry.get("name") or email.split("@")[0],
                    role=user_entry.get("role") or default_user.get("role", "read_only"),
                    slack_user_id=user_entry.get("slack_user_id"),
                    is_super_admin=user_entry in super_admins,
                    is_active=user_entry.get("is_active", True),
                    allow_all_mcps=allow_all_mcps,
                    allowed_domains=user_entry.get("allowed_domains"),
                    allowed_databases=user_entry.get("allowed_databases"),
                )
                session.add(user)
                await session.flush()

            # Update teams
            await session.execute(delete(UserTeam).where(UserTeam.user_id == user.id))
            for team_name in user_entry.get("teams", []) or []:
                session.add(UserTeam(user_id=user.id, team_name=team_name))

            # Update MCP permissions
            await session.execute(delete(UserMCPPermission).where(UserMCPPermission.user_id == user.id))
            for perm in permission_rows:
                session.add(
                    UserMCPPermission(
                        user_id=user.id,
                        mcp_name=perm["mcp_name"],
                        mode=perm["mode"],
                        allowed_tools=perm["allowed_tools"],
                        denied_tools=perm["denied_tools"],
                    )
                )

        await session.commit()

    await database.close_db()
    print("Import complete.")


if __name__ == "__main__":
    asyncio.run(main())
