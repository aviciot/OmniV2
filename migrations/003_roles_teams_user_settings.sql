-- ============================================================
-- OMNI2 Database Migration: Roles, Teams, and User Settings
-- ============================================================
-- Adds role/team metadata, per-user MCP permissions, and user settings.
-- Safe to run multiple times (uses IF NOT EXISTS).
-- ============================================================

-- Users table extensions
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS allow_all_mcps BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS allowed_domains TEXT[],
    ADD COLUMN IF NOT EXISTS allowed_databases TEXT[];

-- ============================================================
-- Roles Table
-- ============================================================
CREATE TABLE IF NOT EXISTS roles (
    name VARCHAR(50) PRIMARY KEY,
    display_name VARCHAR(255) NOT NULL,
    description TEXT,
    color VARCHAR(20),
    permissions JSONB DEFAULT '{}',
    rate_limit JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_roles_name ON roles(name);

-- ============================================================
-- Teams Table
-- ============================================================
CREATE TABLE IF NOT EXISTS teams (
    name VARCHAR(100) PRIMARY KEY,
    display_name VARCHAR(255) NOT NULL,
    description TEXT,
    slack_channel VARCHAR(100),
    notify_on_errors BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_teams_name ON teams(name);

-- ============================================================
-- User MCP Permissions
-- ============================================================
CREATE TABLE IF NOT EXISTS user_mcp_permissions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    mcp_name VARCHAR(255) NOT NULL,
    mode VARCHAR(20) NOT NULL DEFAULT 'inherit',
    allowed_tools TEXT[],
    denied_tools TEXT[],
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, mcp_name)
);

CREATE INDEX IF NOT EXISTS idx_user_mcp_permissions_user_id ON user_mcp_permissions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_mcp_permissions_mcp_name ON user_mcp_permissions(mcp_name);

-- ============================================================
-- User Settings (Singleton Config)
-- ============================================================
CREATE TABLE IF NOT EXISTS user_settings (
    id SERIAL PRIMARY KEY,
    default_user JSONB DEFAULT '{}',
    auto_provisioning JSONB DEFAULT '{}',
    session JSONB DEFAULT '{}',
    restrictions JSONB DEFAULT '{}',
    user_audit JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

