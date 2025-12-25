# ============================================================
# OMNI2 Startup Script (Windows PowerShell)
# ============================================================

Write-Host "🚀 Starting OMNI2 Bridge..." -ForegroundColor Green
Write-Host ""

# Check if .env exists
if (-not (Test-Path .env)) {
    Write-Host "⚠️  .env file not found. Creating from template..." -ForegroundColor Yellow
    Copy-Item .env.example .env
    Write-Host "✅ Created .env file. Please edit it with your credentials." -ForegroundColor Green
    Write-Host ""
}

# Check if Docker is running
try {
    docker info | Out-Null
} catch {
    Write-Host "❌ Docker is not running. Please start Docker Desktop first." -ForegroundColor Red
    exit 1
}

# Build and start services
Write-Host "🔨 Building Docker images..." -ForegroundColor Cyan
docker-compose build

Write-Host ""
Write-Host "🚀 Starting services..." -ForegroundColor Cyan
docker-compose up -d

Write-Host ""
Write-Host "⏳ Waiting for services to be healthy..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Check health
Write-Host ""
Write-Host "🏥 Checking health..." -ForegroundColor Cyan
try {
    $response = Invoke-WebRequest -Uri http://localhost:8000/health -UseBasicParsing
    $response.Content | ConvertFrom-Json | ConvertTo-Json -Depth 10
} catch {
    Write-Host "Service not ready yet..." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "✅ OMNI2 is running!" -ForegroundColor Green
Write-Host ""
Write-Host "📚 Access points:" -ForegroundColor Cyan
Write-Host "   - API:    http://localhost:8000"
Write-Host "   - Docs:   http://localhost:8000/docs"
Write-Host "   - Health: http://localhost:8000/health"
Write-Host ""
Write-Host "📝 View logs:" -ForegroundColor Cyan
Write-Host "   docker-compose logs -f omni2"
Write-Host ""
Write-Host "🛑 Stop services:" -ForegroundColor Cyan
Write-Host "   docker-compose down"
