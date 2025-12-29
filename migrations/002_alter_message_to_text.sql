-- ============================================================
-- Migration: Change message column from VARCHAR(200) to TEXT
-- ============================================================
-- Purpose: Allow unlimited message length for enhanced CSV comparison messages
-- Date: 2025-12-29
-- ============================================================

-- Alter the message column to TEXT type
ALTER TABLE audit_logs 
ALTER COLUMN message TYPE TEXT;

-- Add comment
COMMENT ON COLUMN audit_logs.message IS 'User message or enhanced query (unlimited length)';
