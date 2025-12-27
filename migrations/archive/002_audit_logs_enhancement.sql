-- ============================================================
-- OMNI2 Audit Logs Enhancement - Migration 002
-- ============================================================
-- Adds fields for agentic loop tracking, cost estimation, and better analytics
-- ============================================================

-- First, make the old 'question' column nullable for backward compatibility
ALTER TABLE audit_logs 
    ALTER COLUMN question DROP NOT NULL;

-- Add new columns for enhanced audit logging
ALTER TABLE audit_logs 
    ADD COLUMN IF NOT EXISTS request_type VARCHAR(50) DEFAULT 'chat',
    ADD COLUMN IF NOT EXISTS message TEXT,
    ADD COLUMN IF NOT EXISTS message_preview VARCHAR(200),
    ADD COLUMN IF NOT EXISTS iterations INTEGER DEFAULT 1,
    ADD COLUMN IF NOT EXISTS tool_calls_count INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS tools_used TEXT[],
    ADD COLUMN IF NOT EXISTS mcps_accessed TEXT[],
    ADD COLUMN IF NOT EXISTS databases_accessed TEXT[],
    ADD COLUMN IF NOT EXISTS tokens_input INTEGER,
    ADD COLUMN IF NOT EXISTS tokens_output INTEGER,
    ADD COLUMN IF NOT EXISTS tokens_cached INTEGER,
    ADD COLUMN IF NOT EXISTS cost_estimate DECIMAL(10, 6),
    ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'success',
    ADD COLUMN IF NOT EXISTS warning VARCHAR(255),
    ADD COLUMN IF NOT EXISTS response_preview TEXT,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- Add indexes for new columns
CREATE INDEX IF NOT EXISTS idx_audit_logs_request_type ON audit_logs(request_type);
CREATE INDEX IF NOT EXISTS idx_audit_logs_iterations ON audit_logs(iterations);
CREATE INDEX IF NOT EXISTS idx_audit_logs_status ON audit_logs(status);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_cost_estimate ON audit_logs(cost_estimate);
CREATE INDEX IF NOT EXISTS idx_audit_logs_mcps_accessed ON audit_logs USING GIN(mcps_accessed);
CREATE INDEX IF NOT EXISTS idx_audit_logs_tools_used ON audit_logs USING GIN(tools_used);

-- Update comments
COMMENT ON COLUMN audit_logs.message IS 'Full user message/question';
COMMENT ON COLUMN audit_logs.message_preview IS 'Truncated message for listings (first 200 chars)';
COMMENT ON COLUMN audit_logs.iterations IS 'Number of agentic loop iterations';
COMMENT ON COLUMN audit_logs.tool_calls_count IS 'Total number of MCP tool calls';
COMMENT ON COLUMN audit_logs.tools_used IS 'Array of tool names called (format: mcp_name.tool_name)';
COMMENT ON COLUMN audit_logs.mcps_accessed IS 'Array of MCP server names accessed';
COMMENT ON COLUMN audit_logs.databases_accessed IS 'Array of database names accessed';
COMMENT ON COLUMN audit_logs.tokens_input IS 'Claude input tokens (not including cached)';
COMMENT ON COLUMN audit_logs.tokens_output IS 'Claude output tokens';
COMMENT ON COLUMN audit_logs.tokens_cached IS 'Claude cached input tokens (90% discount)';
COMMENT ON COLUMN audit_logs.cost_estimate IS 'Estimated cost in USD for this request';
COMMENT ON COLUMN audit_logs.status IS 'Request status: success, error, warning';
COMMENT ON COLUMN audit_logs.warning IS 'Warning message if any (e.g., max_iterations_reached)';

-- Create view for easy analytics
CREATE OR REPLACE VIEW audit_logs_summary AS
SELECT 
    DATE_TRUNC('day', created_at) as date,
    user_id,
    request_type,
    COUNT(*) as total_requests,
    SUM(tool_calls_count) as total_tool_calls,
    AVG(iterations) as avg_iterations,
    AVG(duration_ms) as avg_duration_ms,
    SUM(tokens_input) as total_tokens_input,
    SUM(tokens_output) as total_tokens_output,
    SUM(tokens_cached) as total_tokens_cached,
    SUM(cost_estimate) as total_cost,
    COUNT(*) FILTER (WHERE status = 'error') as error_count,
    COUNT(*) FILTER (WHERE status = 'success') as success_count
FROM audit_logs
GROUP BY DATE_TRUNC('day', created_at), user_id, request_type;

COMMENT ON VIEW audit_logs_summary IS 'Daily summary of audit log metrics by user and request type';
