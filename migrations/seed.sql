-- ============================================================
-- OMNI2 Database Seed Data
-- ============================================================
-- Populates initial users, MCP servers, and sample data
-- ============================================================

-- ============================================================
-- Seed Users
-- ============================================================

-- Admin Users
INSERT INTO users (email, name, role, is_super_admin, is_active)
VALUES 
    ('avicoiot@gmail.com', 'Avi Cohen', 'admin', true, true),
    ('avi.cohen@shift4.com', 'Avi Cohen', 'admin', true, true)
ON CONFLICT (email) DO UPDATE SET
    is_super_admin = EXCLUDED.is_super_admin,
    is_active = EXCLUDED.is_active,
    updated_at = NOW();

-- Developer User
INSERT INTO users (email, name, role, is_super_admin, is_active)
VALUES ('alonab@shift4.com', 'Alon AB', 'developer', false, true)
ON CONFLICT (email) DO UPDATE SET
    role = EXCLUDED.role,
    is_active = EXCLUDED.is_active,
    updated_at = NOW();

-- DBA User
INSERT INTO users (email, name, role, is_super_admin, is_active)
VALUES ('dba1@shift4.com', 'DBA User', 'dba', false, true)
ON CONFLICT (email) DO UPDATE SET
    role = EXCLUDED.role,
    is_active = EXCLUDED.is_active,
    updated_at = NOW();

-- ============================================================
-- Seed MCP Servers
-- ============================================================

INSERT INTO mcp_servers (name, url, is_enabled, is_healthy)
VALUES 
    ('database_mcp', 'http://database-mcp:8001', true, true),
    ('github_mcp', 'http://github-mcp:8002', true, true),
    ('filesystem_mcp', 'http://filesystem-mcp:8003', false, true),
    ('smoketest_mcp', 'http://smoketest-mcp:8004', false, true)
ON CONFLICT (name) DO UPDATE SET
    url = EXCLUDED.url,
    is_enabled = EXCLUDED.is_enabled,
    updated_at = NOW();

-- ============================================================
-- Completion Message
-- ============================================================
DO $$
DECLARE
    user_count INTEGER;
    mcp_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO user_count FROM users;
    SELECT COUNT(*) INTO mcp_count FROM mcp_servers;
    
    RAISE NOTICE '============================================================';
    RAISE NOTICE '✅ OMNI2 Seed Data Loaded Successfully!';
    RAISE NOTICE '============================================================';
    RAISE NOTICE 'Users Created/Updated: %', user_count;
    RAISE NOTICE '  • Admins: avicoiot@gmail.com, avi.cohen@shift4.com';
    RAISE NOTICE '  • Developer: alonab@shift4.com';
    RAISE NOTICE '  • DBA: dba1@shift4.com';
    RAISE NOTICE '';
    RAISE NOTICE 'MCP Servers Registered: %', mcp_count;
    RAISE NOTICE '  • database_mcp (enabled)';
    RAISE NOTICE '  • github_mcp (enabled)';
    RAISE NOTICE '  • filesystem_mcp (disabled)';
    RAISE NOTICE '  • smoketest_mcp (disabled)';
    RAISE NOTICE '';
    RAISE NOTICE '🚀 Database ready for use!';
    RAISE NOTICE '============================================================';
END $$;
