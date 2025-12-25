-- ============================================================
-- OMNI2 Database Schema - Initial Migration
-- ============================================================
-- PostgreSQL 16+ required
-- Database: omni (existing PS_db database)
-- ============================================================

-- ============================================================
-- Users Table
-- ============================================================
-- Stores user information, roles, and authentication details
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'read_only',
    slack_user_id VARCHAR(50) UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT true,
    is_super_admin BOOLEAN NOT NULL DEFAULT false,
    
    -- Authentication (Phase 2)
    password_hash VARCHAR(255),
    last_login TIMESTAMP WITH TIME ZONE,
    login_count INTEGER DEFAULT 0,
    
    -- User preferences
    preferences JSONB DEFAULT '{}',
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by INTEGER REFERENCES users(id),
    updated_by INTEGER REFERENCES users(id)
);

-- Indexes for users table
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_slack_user_id ON users(slack_user_id);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_is_active ON users(is_active);

-- Comments
COMMENT ON TABLE users IS 'User accounts and authentication';
COMMENT ON COLUMN users.role IS 'User role: admin, dba, power_user, qa_tester, read_only';
COMMENT ON COLUMN users.preferences IS 'User-specific preferences (JSON)';

-- ============================================================
-- User Teams (Many-to-Many)
-- ============================================================
CREATE TABLE IF NOT EXISTS user_teams (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    team_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_user_teams_user_id ON user_teams(user_id);
CREATE INDEX idx_user_teams_team_name ON user_teams(team_name);
CREATE UNIQUE INDEX idx_user_teams_unique ON user_teams(user_id, team_name);

-- ============================================================
-- Audit Logs Table
-- ============================================================
-- Stores all user interactions and tool invocations
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    
    -- Request details
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    question TEXT NOT NULL,
    
    -- Routing & execution
    mcp_target VARCHAR(255),
    tool_called VARCHAR(255),
    tool_params JSONB,
    
    -- Response details
    success BOOLEAN NOT NULL,
    duration_ms INTEGER,
    result_summary TEXT,
    error_message TEXT,
    error_id VARCHAR(50),
    
    -- Slack context
    slack_channel VARCHAR(100),
    slack_user_id VARCHAR(50),
    slack_message_ts VARCHAR(50),
    slack_thread_ts VARCHAR(50),
    
    -- LLM routing details
    llm_confidence DECIMAL(3, 2),
    llm_reasoning TEXT,
    llm_tokens_used INTEGER,
    
    -- Security & compliance
    ip_address INET,
    user_agent TEXT,
    was_blocked BOOLEAN DEFAULT false,
    block_reason TEXT,
    
    -- Indexes for search
    search_vector tsvector
);

-- Indexes for audit_logs table
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_timestamp ON audit_logs(timestamp DESC);
CREATE INDEX idx_audit_logs_mcp_target ON audit_logs(mcp_target);
CREATE INDEX idx_audit_logs_tool_called ON audit_logs(tool_called);
CREATE INDEX idx_audit_logs_success ON audit_logs(success);
CREATE INDEX idx_audit_logs_slack_user_id ON audit_logs(slack_user_id);
CREATE INDEX idx_audit_logs_was_blocked ON audit_logs(was_blocked);

-- Full-text search index
CREATE INDEX idx_audit_logs_search ON audit_logs USING GIN(search_vector);

-- Trigger to update search_vector
CREATE OR REPLACE FUNCTION audit_logs_search_trigger() RETURNS trigger AS $$
BEGIN
    NEW.search_vector := to_tsvector('english', 
        COALESCE(NEW.question, '') || ' ' || 
        COALESCE(NEW.tool_called, '') || ' ' ||
        COALESCE(NEW.result_summary, '')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_logs_search_update 
    BEFORE INSERT OR UPDATE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION audit_logs_search_trigger();

-- Comments
COMMENT ON TABLE audit_logs IS 'Complete audit trail of all OMNI2 interactions';
COMMENT ON COLUMN audit_logs.llm_confidence IS 'LLM routing confidence score (0.0 to 1.0)';
COMMENT ON COLUMN audit_logs.was_blocked IS 'Whether action was blocked by policy';

-- ============================================================
-- MCP Servers Table
-- ============================================================
-- Track registered MCP servers and their health
CREATE TABLE IF NOT EXISTS mcp_servers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    url VARCHAR(500) NOT NULL,
    is_enabled BOOLEAN NOT NULL DEFAULT true,
    
    -- Health tracking
    is_healthy BOOLEAN DEFAULT true,
    last_health_check TIMESTAMP WITH TIME ZONE,
    last_seen TIMESTAMP WITH TIME ZONE,
    consecutive_failures INTEGER DEFAULT 0,
    
    -- Metadata
    version VARCHAR(50),
    capabilities JSONB,
    
    -- Statistics
    total_requests INTEGER DEFAULT 0,
    successful_requests INTEGER DEFAULT 0,
    failed_requests INTEGER DEFAULT 0,
    avg_response_time_ms INTEGER,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_mcp_servers_name ON mcp_servers(name);
CREATE INDEX idx_mcp_servers_is_enabled ON mcp_servers(is_enabled);
CREATE INDEX idx_mcp_servers_is_healthy ON mcp_servers(is_healthy);

-- Comments
COMMENT ON TABLE mcp_servers IS 'Registry of connected MCP servers';

-- ============================================================
-- MCP Tools Table
-- ============================================================
-- Cache of available tools from each MCP
CREATE TABLE IF NOT EXISTS mcp_tools (
    id SERIAL PRIMARY KEY,
    mcp_server_id INTEGER NOT NULL REFERENCES mcp_servers(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    input_schema JSONB,
    
    -- Metadata
    category VARCHAR(100),
    tags TEXT[],
    is_dangerous BOOLEAN DEFAULT false,
    requires_admin BOOLEAN DEFAULT false,
    
    -- Usage tracking
    call_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    avg_duration_ms INTEGER,
    
    -- Timestamps
    discovered_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    last_called TIMESTAMP WITH TIME ZONE,
    
    UNIQUE(mcp_server_id, name)
);

-- Indexes
CREATE INDEX idx_mcp_tools_mcp_server_id ON mcp_tools(mcp_server_id);
CREATE INDEX idx_mcp_tools_name ON mcp_tools(name);
CREATE INDEX idx_mcp_tools_category ON mcp_tools(category);
CREATE INDEX idx_mcp_tools_is_dangerous ON mcp_tools(is_dangerous);

-- Comments
COMMENT ON TABLE mcp_tools IS 'Cache of available tools from MCPs';

-- ============================================================
-- Sessions Table (Phase 2)
-- ============================================================
-- Store user sessions (for stateful conversations)
CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id VARCHAR(100) UNIQUE NOT NULL,
    
    -- Session data
    context JSONB DEFAULT '{}',
    conversation_history JSONB DEFAULT '[]',
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    last_activity TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL
);

-- Indexes
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_session_id ON sessions(session_id);
CREATE INDEX idx_sessions_is_active ON sessions(is_active);
CREATE INDEX idx_sessions_expires_at ON sessions(expires_at);

-- Comments
COMMENT ON TABLE sessions IS 'User sessions for stateful conversations';

-- ============================================================
-- Notifications Table (Phase 2)
-- ============================================================
-- Store notifications to be sent to users
CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    
    -- Notification details
    type VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    severity VARCHAR(20) DEFAULT 'info',
    
    -- Delivery
    channels TEXT[] DEFAULT '{"slack"}',
    is_sent BOOLEAN DEFAULT false,
    sent_at TIMESTAMP WITH TIME ZONE,
    
    -- Status
    is_read BOOLEAN DEFAULT false,
    read_at TIMESTAMP WITH TIME ZONE,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_notifications_user_id ON notifications(user_id);
CREATE INDEX idx_notifications_is_sent ON notifications(is_sent);
CREATE INDEX idx_notifications_is_read ON notifications(is_read);
CREATE INDEX idx_notifications_created_at ON notifications(created_at DESC);

-- Comments
COMMENT ON TABLE notifications IS 'Notifications to be delivered to users';
COMMENT ON COLUMN notifications.severity IS 'Notification severity: info, warning, error, critical';

-- ============================================================
-- API Keys Table (Phase 2)
-- ============================================================
-- API keys for external integrations
CREATE TABLE IF NOT EXISTS api_keys (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Key details
    key_hash VARCHAR(255) UNIQUE NOT NULL,
    key_prefix VARCHAR(10) NOT NULL,
    name VARCHAR(255) NOT NULL,
    
    -- Permissions
    scopes TEXT[] DEFAULT '{"read"}',
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    is_revoked BOOLEAN DEFAULT false,
    revoked_at TIMESTAMP WITH TIME ZONE,
    revoked_by INTEGER REFERENCES users(id),
    
    -- Usage tracking
    last_used TIMESTAMP WITH TIME ZONE,
    usage_count INTEGER DEFAULT 0,
    
    -- Expiration
    expires_at TIMESTAMP WITH TIME ZONE,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX idx_api_keys_key_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_is_active ON api_keys(is_active);

-- Comments
COMMENT ON TABLE api_keys IS 'API keys for external integrations';

-- ============================================================
-- Triggers for updated_at
-- ============================================================
-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to relevant tables
CREATE TRIGGER update_users_updated_at 
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_mcp_servers_updated_at 
    BEFORE UPDATE ON mcp_servers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- Initial Data
-- ============================================================

-- Insert super admin user
INSERT INTO users (email, name, role, is_super_admin, is_active)
VALUES ('avicoiot@gmail.com', 'Avi Cohen', 'admin', true, true)
ON CONFLICT (email) DO NOTHING;

-- Insert initial MCP servers (from config)
INSERT INTO mcp_servers (name, url, is_enabled)
VALUES 
    ('oracle_mcp', 'http://localhost:8001', true),
    ('smoketest_mcp', 'http://localhost:8002', false),
    ('etl_mcp', 'http://localhost:8003', false)
ON CONFLICT (name) DO NOTHING;

-- ============================================================
-- Views for Analytics
-- ============================================================

-- User activity summary
CREATE OR REPLACE VIEW v_user_activity AS
SELECT 
    u.id,
    u.email,
    u.name,
    u.role,
    COUNT(al.id) as total_queries,
    SUM(CASE WHEN al.success THEN 1 ELSE 0 END) as successful_queries,
    SUM(CASE WHEN NOT al.success THEN 1 ELSE 0 END) as failed_queries,
    AVG(al.duration_ms) as avg_duration_ms,
    MAX(al.timestamp) as last_activity
FROM users u
LEFT JOIN audit_logs al ON u.id = al.user_id
GROUP BY u.id, u.email, u.name, u.role;

-- MCP health summary
CREATE OR REPLACE VIEW v_mcp_health AS
SELECT 
    ms.id,
    ms.name,
    ms.url,
    ms.is_enabled,
    ms.is_healthy,
    ms.last_health_check,
    ms.consecutive_failures,
    COUNT(mt.id) as tool_count,
    ms.total_requests,
    ms.successful_requests,
    ms.failed_requests,
    CASE 
        WHEN ms.total_requests > 0 
        THEN ROUND((ms.successful_requests::DECIMAL / ms.total_requests * 100), 2)
        ELSE 0 
    END as success_rate_pct
FROM mcp_servers ms
LEFT JOIN mcp_tools mt ON ms.id = mt.mcp_server_id
GROUP BY ms.id, ms.name, ms.url, ms.is_enabled, ms.is_healthy, 
         ms.last_health_check, ms.consecutive_failures, ms.total_requests,
         ms.successful_requests, ms.failed_requests;

-- Tool usage summary
CREATE OR REPLACE VIEW v_tool_usage AS
SELECT 
    mt.name,
    ms.name as mcp_name,
    mt.category,
    mt.call_count,
    mt.success_count,
    mt.failure_count,
    CASE 
        WHEN mt.call_count > 0 
        THEN ROUND((mt.success_count::DECIMAL / mt.call_count * 100), 2)
        ELSE 0 
    END as success_rate_pct,
    mt.avg_duration_ms,
    mt.last_called
FROM mcp_tools mt
JOIN mcp_servers ms ON mt.mcp_server_id = ms.id
WHERE mt.call_count > 0
ORDER BY mt.call_count DESC;

-- ============================================================
-- Partitioning for audit_logs (Phase 2 - for scale)
-- ============================================================
-- Partition audit_logs by month for better performance
-- Uncomment when ready to implement partitioning

-- CREATE TABLE audit_logs_template (LIKE audit_logs INCLUDING ALL);
-- 
-- ALTER TABLE audit_logs RENAME TO audit_logs_old;
-- ALTER TABLE audit_logs_template RENAME TO audit_logs;
-- 
-- CREATE TABLE audit_logs_2024_01 PARTITION OF audit_logs
--     FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
-- ...

-- ============================================================
-- Grants (adjust based on your security model)
-- ============================================================
-- Grant appropriate permissions to application user
-- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO omni_app;
-- GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO omni_app;

-- ============================================================
-- Completion
-- ============================================================
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    description TEXT,
    applied_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

INSERT INTO schema_version (version, description) 
VALUES (1, 'Initial OMNI2 schema - Phase 1');

-- Log migration completion
DO $$
BEGIN
    RAISE NOTICE 'OMNI2 database schema initialized successfully!';
    RAISE NOTICE 'Database: omni (PS_db)';
    RAISE NOTICE 'Tables created: users, user_teams, audit_logs, mcp_servers, mcp_tools, sessions, notifications, api_keys';
    RAISE NOTICE 'Views created: v_user_activity, v_mcp_health, v_tool_usage';
END $$;
