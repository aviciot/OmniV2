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
# User Models
# ============================================================

class User(Base):
    """User account model."""
    
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="read_only", index=True)
    slack_user_id = Column(String(50), unique=True, index=True)
    
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    is_super_admin = Column(Boolean, nullable=False, default=False)
    
    # Authentication (Phase 2)
    password_hash = Column(String(255))
    last_login = Column(DateTime(timezone=True))
    login_count = Column(Integer, default=0)
    
    # Preferences
    preferences = Column(JSONB, default={})
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))
    updated_by = Column(Integer, ForeignKey("users.id"))
    
    # Relationships
    audit_logs = relationship("AuditLog", back_populates="user", foreign_keys="AuditLog.user_id")
    teams = relationship("UserTeam", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    api_keys = relationship("APIKey", back_populates="user", foreign_keys="APIKey.user_id", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', role='{self.role}')>"


class UserTeam(Base):
    """User team membership (many-to-many)."""
    
    __tablename__ = "user_teams"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    team_name = Column(String(100), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="teams")
    
    __table_args__ = (
        UniqueConstraint("user_id", "team_name", name="uq_user_team"),
    )


# ============================================================
# Audit Log Model
# ============================================================

class AuditLog(Base):
    """Audit log for all user interactions."""
    
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    
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
    
    # Relationships
    user = relationship("User", back_populates="audit_logs", foreign_keys=[user_id])
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, user_id={self.user_id}, tool='{self.tool_called}', success={self.success})>"


# ============================================================
# MCP Server Models
# ============================================================

class MCPServer(Base):
    """MCP server registry."""
    
    __tablename__ = "mcp_servers"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    url = Column(String(500), nullable=False)
    is_enabled = Column(Boolean, nullable=False, default=True, index=True)
    
    # Health tracking
    is_healthy = Column(Boolean, default=True, index=True)
    last_health_check = Column(DateTime(timezone=True))
    last_seen = Column(DateTime(timezone=True))
    consecutive_failures = Column(Integer, default=0)
    
    # Metadata
    version = Column(String(50))
    capabilities = Column(JSONB)
    
    # Statistics
    total_requests = Column(Integer, default=0)
    successful_requests = Column(Integer, default=0)
    failed_requests = Column(Integer, default=0)
    avg_response_time_ms = Column(Integer)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    tools = relationship("MCPTool", back_populates="mcp_server", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<MCPServer(id={self.id}, name='{self.name}', healthy={self.is_healthy})>"


class MCPTool(Base):
    """MCP tool registry (cached from MCP discovery)."""
    
    __tablename__ = "mcp_tools"
    
    id = Column(Integer, primary_key=True, index=True)
    mcp_server_id = Column(Integer, ForeignKey("mcp_servers.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    input_schema = Column(JSONB)
    
    # Metadata
    category = Column(String(100), index=True)
    tags = Column(ARRAY(Text))
    is_dangerous = Column(Boolean, default=False, index=True)
    requires_admin = Column(Boolean, default=False)
    
    # Usage tracking
    call_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    avg_duration_ms = Column(Integer)
    
    # Timestamps
    discovered_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_called = Column(DateTime(timezone=True))
    
    # Relationships
    mcp_server = relationship("MCPServer", back_populates="tools")
    
    __table_args__ = (
        UniqueConstraint("mcp_server_id", "name", name="uq_mcp_tool"),
    )
    
    def __repr__(self):
        return f"<MCPTool(id={self.id}, name='{self.name}', mcp={self.mcp_server_id})>"


# ============================================================
# Session Model (Phase 2)
# ============================================================

class Session(Base):
    """User session for stateful conversations."""
    
    __tablename__ = "sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
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
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    
    def __repr__(self):
        return f"<Session(id={self.id}, user_id={self.user_id}, active={self.is_active})>"


# ============================================================
# Notification Model (Phase 2)
# ============================================================

class Notification(Base):
    """User notifications."""
    
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    
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
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
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
    revoked_by = Column(Integer, ForeignKey("users.id"))
    
    # Usage tracking
    last_used = Column(DateTime(timezone=True))
    usage_count = Column(Integer, default=0)
    
    # Expiration
    expires_at = Column(DateTime(timezone=True))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="api_keys", foreign_keys=[user_id])
    
    def __repr__(self):
        return f"<APIKey(id={self.id}, name='{self.name}', active={self.is_active})>"
