# Database Initialization Script for OMNI2
# Runs init.sql and seed.sql on an existing database
#
# Usage:
#   .\scripts\db-init.ps1         # Full initialization with seed data
#   .\scripts\db-init.ps1 -NoSeed # Skip seed data

param(
    [switch]$NoSeed
)

Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  OMNI2 Database Initialization" -ForegroundColor Cyan
Write-Host "============================================`n" -ForegroundColor Cyan

# Step 1: Run init.sql
Write-Host "[1/2] Running init.sql (creating schema)..." -ForegroundColor Yellow
docker exec -i omni2-postgres psql -U postgres -d omni -f /docker-entrypoint-initdb.d/001_init.sql 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAILED] Schema creation failed" -ForegroundColor Red
    exit 1
}
Write-Host "  [OK] Schema created" -ForegroundColor Green

# Step 2: Run seed.sql (optional)
if (-not $NoSeed) {
    Write-Host "`n[2/2] Running seed.sql (populating data)..." -ForegroundColor Yellow
    docker exec -i omni2-postgres psql -U postgres -d omni -f /docker-entrypoint-initdb.d/002_seed.sql 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAILED] Seed data insertion failed" -ForegroundColor Red
        exit 1
    }
    Write-Host "  [OK] Seed data loaded" -ForegroundColor Green
} else {
    Write-Host "`n[2/2] Skipped seed data (-NoSeed flag)" -ForegroundColor Gray
}

Write-Host "`n[OK] Database initialization complete!`n" -ForegroundColor Green
