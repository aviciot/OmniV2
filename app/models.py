"""
SQLAlchemy ORM Models

Defines database tables as Python classes for:
- users
- user_teams
- audit_logs
- mcp_servers
- mcp_tools
- sessions
- notifications
- api_keys
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    DECIMAL,
    Index,
    UniqueConstraint,
    ARRAY,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


# ============================================================
# User-Related Models (Users table is in auth_service schema)
# ============================================================

# NOTE: User, Role, Team models are managed by auth_service microservice
# We only store user_id references here and fetch user data via auth_client


class UserUsageLimit(Base):
    """Per-user usage limits with reset windows."""

    __tablename__ = "user_usage_limits"
    __table_args__ = {"schema": "omni2"}

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, unique=True, index=True)  # References auth_service.users.id

    period_days = Column(Integer, nullable=False, default=30)
    max_requests = Column(Integer)
    max_tokens = Column(Integer)
    max_cost = Column(DECIMAL(12, 4))
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    last_reset_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<UserUsageLimit(user_id={self.user_id}, active={self.is_active})>"


class UserTeam(Base):
    """User team membership (many-to-many)."""
    
    __tablename__ = "user_teams"
    __table_args__ = (
        UniqueConstraint("user_id", "team_name", name="uq_user_team"),
        {"schema": "omni2"}
    )
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)  # References auth_service.users.id
    team_name = Column(String(100), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    



class UserMCPPermission(Base):
    """Per-user MCP permission overrides."""

    __tablename__ = "user_mcp_permissions"
    __table_args__ = (
        UniqueConstraint("user_id", "mcp_name", name="uq_user_mcp_permission"),
        {"schema": "omni2"}
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)  # References auth_service.users.id
    mcp_name = Column(String(255), nullable=False, index=True)
    mode = Column(String(20), nullable=False, default="inherit")
    allowed_tools = Column(ARRAY(Text))
    denied_tools = Column(ARRAY(Text))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())




class UserSettings(Base):
    """Singleton user settings (default user config, provisioning rules)."""

    __tablename__ = "user_settings"
    __table_args__ = {"schema": "omni2"}

    id = Column(Integer, primary_key=True, index=True)
    default_user = Column(JSONB, default={})
    auto_provisioning = Column(JSONB, default={})
    session = Column(JSONB, default={})
    restrictions = Column(JSONB, default={})
    user_audit = Column(JSONB, default={})
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


# ============================================================
# Audit Log Model
# ============================================================

class AuditLog(Base):
    """Audit log for all user interactions."""
    
    __tablename__ = "audit_logs"
    __table_args__ = {"schema": "omni2"}
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)  # References auth_service.users.id
    
    # Request details
    timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    question = Column(Text, nullable=False)
    
    # Routing & execution
    mcp_target = Column(String(255), index=True)
    tool_called = Column(String(255), index=True)
    tool_params = Column(JSONB)
    
    # Response details
    success = Column(Boolean, nullable=False, index=True)
    duration_ms = Column(Integer)
    result_summary = Column(Text)
    error_message = Column(Text)
    error_id = Column(String(50))
    
    # Slack context
    slack_channel = Column(String(100))
    slack_user_id = Column(String(50), index=True)
    slack_message_ts = Column(String(50))
    slack_thread_ts = Column(String(50))
    
    # LLM routing details
    llm_confidence = Column(DECIMAL(3, 2))
    llm_reasoning = Column(Text)
    llm_tokens_used = Column(Integer)
    
    # Security & compliance
    ip_address = Column(INET)
    user_agent = Column(Text)
    was_blocked = Column(Boolean, default=False, index=True)
    block_reason = Column(Text)
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, user_id={self.user_id}, tool='{self.tool_called}', success={self.success})>"


# ============================================================
# MCP Server Models
# ============================================================

class MCPServer(Base):
    """MCP server registry."""
    
    __tablename__ = "mcp_servers"
    __table_args__ = {"schema": "omni2"}
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    url = Column(String(500), nullable=False)
    description = Column(Text)
    
    # Status & config
    status = Column(String(20), default='active', index=True)
    protocol = Column(String(20), default='http')
    timeout_seconds = Column(Integer, default=30)
    
    # Retry configuration
    max_retries = Column(Integer, default=2)
    retry_delay_seconds = Column(DECIMAL(4, 2), default=1.0)
    
    # Authentication
    auth_type = Column(String(20))
    auth_config = Column(JSONB)
    
    # Health tracking
    last_health_check = Column(DateTime(timezone=True))
    health_status = Column(String(20), default='unknown', index=True)
    error_count = Column(Integer, default=0)
    
    # Metadata
    meta_data = Column(JSONB)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    tools = relationship("MCPTool", back_populates="mcp_server", cascade="all, delete-orphan")
    health_logs = relationship("MCPHealthLog", back_populates="mcp_server", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<MCPServer(id={self.id}, name='{self.name}', status='{self.status}')>"


class MCPTool(Base):
    """MCP tool registry (cached from MCP discovery)."""
    
    __tablename__ = "mcp_tools"
    __table_args__ = (
        UniqueConstraint("mcp_server_id", "name", name="uq_mcp_tool"),
        {"schema": "omni2"}
    )
    
    id = Column(Integer, primary_key=True, index=True)
    mcp_server_id = Column(Integer, ForeignKey("omni2.mcp_servers.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    input_schema = Column(JSONB)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    mcp_server = relationship("MCPServer", back_populates="tools")
    
    def __repr__(self):
        return f"<MCPTool(id={self.id}, name='{self.name}', mcp={self.mcp_server_id})>"


# ============================================================
# Session Model (Phase 2)
# ============================================================

class ChatSession(Base):
    """User session for stateful conversations."""
    
    __tablename__ = "chat_sessions"
    __table_args__ = {"schema": "omni2"}
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)  # References auth_service.users.id
    session_id = Column(String(100), unique=True, nullable=False, index=True)
    
    # Session data
    context = Column(JSONB, default={})
    conversation_history = Column(JSONB, default=[])
    
    # Status
    is_active = Column(Boolean, default=True, index=True)
    last_activity = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    
    def __repr__(self):
        return f"<Session(id={self.id}, user_id={self.user_id}, active={self.is_active})>"


# ============================================================
# Notification Model (Phase 2)
# ============================================================

class Notification(Base):
    """User notifications."""
    
    __tablename__ = "notifications"
    __table_args__ = {"schema": "omni2"}
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)  # References auth_service.users.id
    
    # Notification details
    type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    severity = Column(String(20), default="info")
    
    # Delivery
    channels = Column(ARRAY(Text), default=["slack"])
    is_sent = Column(Boolean, default=False, index=True)
    sent_at = Column(DateTime(timezone=True))
    
    # Status
    is_read = Column(Boolean, default=False, index=True)
    read_at = Column(DateTime(timezone=True))
    
    # Metadata (renamed to avoid SQLAlchemy reserved word)
    meta_data = Column(JSONB, default={})
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)


# ============================================================
# API Key Model (Phase 2)
# ============================================================

class APIKey(Base):
    """API keys for external integrations."""
    
    __tablename__ = "api_keys"
    __table_args__ = {"schema": "omni2"}
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)  # References auth_service.users.id
    
    # Key details
    key_hash = Column(String(255), unique=True, nullable=False, index=True)
    key_prefix = Column(String(10), nullable=False)
    name = Column(String(255), nullable=False)
    
    # Permissions
    scopes = Column(ARRAY(Text), default=["read"])
    
    # Status
    is_active = Column(Boolean, default=True, index=True)
    is_revoked = Column(Boolean, default=False)
    revoked_at = Column(DateTime(timezone=True))
    revoked_by = Column(Integer)  # References auth_service.users.id
    
    # Usage tracking
    last_used = Column(DateTime(timezone=True))
    usage_count = Column(Integer, default=0)
    
    # Expiration
    expires_at = Column(DateTime(timezone=True))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    def __repr__(self):
        return f"<APIKey(id={self.id}, name='{self.name}', active={self.is_active})>"


# ============================================================
# MCP Health Log Model
# ============================================================

class MCPHealthLog(Base):
    """Health and event log for MCP servers."""
    
    __tablename__ = "mcp_health_log"
    __table_args__ = {"schema": "omni2"}
    
    id = Column(Integer, primary_key=True, index=True)
    mcp_server_id = Column(Integer, ForeignKey("omni2.mcp_servers.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    status = Column(String(20), nullable=False)
    response_time_ms = Column(Integer)
    error_message = Column(Text)
    meta_data = Column(JSONB)
    event_type = Column(String(50), index=True)
    
    # Relationships
    mcp_server = relationship("MCPServer", back_populates="health_logs")
    
    def __repr__(self):
        return f"<MCPHealthLog(id={self.id}, mcp={self.mcp_server_id}, status='{self.status}', event='{self.event_type}')>"


# ============================================================
# Omni2 Configuration Model
# ============================================================

class Omni2Config(Base):
    """Configuration settings for omni2 behavior."""
    
    __tablename__ = "omni2_config"
    __table_args__ = {"schema": "omni2"}
    
    id = Column(Integer, primary_key=True, index=True)
    config_key = Column(String(100), unique=True, nullable=False, index=True)
    config_value = Column(JSONB, nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<Omni2Config(key='{self.config_key}', active={self.is_active})>"



# ============================================================================
# Permission Management Models
# ============================================================================

class RolePermission(Base):
    """Role-based MCP permissions (developer, qa, dba, etc.)."""
    
    __tablename__ = "role_permissions"
    __table_args__ = (
        UniqueConstraint("role_name", "mcp_name", name="uq_role_mcp"),
        {"schema": "omni2"}
    )
    
    id = Column(Integer, primary_key=True, index=True)
    role_name = Column(String(50), nullable=False, index=True)
    mcp_name = Column(String(255), nullable=False, index=True)
    mode = Column(String(20), nullable=False, default="inherit")
    allowed_tools = Column(ARRAY(Text))
    denied_tools = Column(ARRAY(Text))
    description = Column(Text)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<RolePermission(role='{self.role_name}', mcp='{self.mcp_name}', mode='{self.mode}')>"


class TeamRole(Base):
    """Team to role mapping (team inherits role permissions)."""
    
    __tablename__ = "team_roles"
    __table_args__ = {"schema": "omni2"}
    
    id = Column(Integer, primary_key=True, index=True)
    team_name = Column(String(100), unique=True, nullable=False, index=True)
    default_role = Column(String(50), nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<TeamRole(team='{self.team_name}', role='{self.default_role}')>"
