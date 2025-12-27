# Database Reset Script for OMNI2
# Drops and recreates the 'omni' database with fresh schema and seed data
#
# Usage:
#   .\scripts\db-reset.ps1              # Interactive (asks for confirmation)
#   .\scripts\db-reset.ps1 -Force       # No confirmation
#   .\scripts\db-reset.ps1 -NoSeed      # Skip seed data
#   .\scripts\db-reset.ps1 -Force -NoSeed

param(
    [switch]$Force,
    [switch]$NoSeed
)

Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  OMNI2 Database Reset" -ForegroundColor Cyan
Write-Host "============================================`n" -ForegroundColor Cyan

if (-not $Force) {
    Write-Host "[WARNING] This will DROP the entire 'omni' database and recreate it." -ForegroundColor Yellow
    Write-Host "          All existing data will be lost!`n" -ForegroundColor Yellow
    $confirmation = Read-Host "Type 'yes' to continue"
    if ($confirmation -ne 'yes') {
        Write-Host "`nAborted." -ForegroundColor Yellow
        exit 0
    }
}

# Step 1: Drop database
Write-Host "`n[1/4] Dropping database 'omni'..." -ForegroundColor Yellow
docker exec -i omni2-postgres psql -U postgres -c "DROP DATABASE IF EXISTS omni;" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAILED] Could not drop database" -ForegroundColor Red
    exit 1
}
Write-Host "  [OK] Database dropped" -ForegroundColor Green

# Step 2: Create database
Write-Host "`n[2/4] Creating fresh database 'omni'..." -ForegroundColor Yellow
docker exec -i omni2-postgres psql -U postgres -c "CREATE DATABASE omni;" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAILED] Could not create database" -ForegroundColor Red
    exit 1
}
Write-Host "  [OK] Database created" -ForegroundColor Green

# Step 3: Run init.sql
Write-Host "`n[3/4] Running init.sql (creating schema)..." -ForegroundColor Yellow
docker exec -i omni2-postgres psql -U postgres -d omni -f /docker-entrypoint-initdb.d/001_init.sql 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAILED] Schema creation failed" -ForegroundColor Red
    exit 1
}
Write-Host "  [OK] Schema created (8 tables, 4 views)" -ForegroundColor Green

# Step 4: Run seed.sql (optional)
if (-not $NoSeed) {
    Write-Host "`n[4/4] Running seed.sql (populating data)..." -ForegroundColor Yellow
    docker exec -i omni2-postgres psql -U postgres -d omni -f /docker-entrypoint-initdb.d/002_seed.sql 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAILED] Seed data insertion failed" -ForegroundColor Red
        exit 1
    }
    Write-Host "  [OK] Seed data loaded" -ForegroundColor Green
} else {
    Write-Host "`n[4/4] Skipped seed data (-NoSeed flag)" -ForegroundColor Gray
}

# Summary
Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  Database Reset Complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan

$userCount = (docker exec -i omni2-postgres psql -U postgres -d omni -t -c "SELECT COUNT(*) FROM users;" 2>$null).Trim()
$mcpCount = (docker exec -i omni2-postgres psql -U postgres -d omni -t -c "SELECT COUNT(*) FROM mcp_servers;" 2>$null).Trim()

Write-Host "`nDatabase: omni" -ForegroundColor White
Write-Host "Users: $userCount" -ForegroundColor White
Write-Host "MCP Servers: $mcpCount" -ForegroundColor White
Write-Host "`n[OK] Database ready for use!`n" -ForegroundColor Green
