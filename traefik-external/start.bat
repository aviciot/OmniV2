@echo off
echo ========================================
echo Starting Traefik External Gateway
echo ========================================
echo.

echo [1/3] Checking if omni2 network exists...
docker network inspect omni2_omni2-network >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: omni2_omni2-network not found!
    echo Please start omni2 stack first: cd .. ^&^& docker-compose up -d
    pause
    exit /b 1
)
echo ✓ Network found

echo.
echo [2/3] Starting Traefik-External...
docker-compose up -d

echo.
echo [3/3] Verifying...
timeout /t 3 /nobreak >nul
docker ps | findstr traefik-external

echo.
echo ========================================
echo ✓ Traefik External Gateway Started
echo ========================================
echo.
echo Dashboard: http://localhost:8091/dashboard/
echo Gateway:   http://localhost:8090/
echo.
echo Test endpoints:
echo   curl http://localhost:8090/health
echo   curl -H "Authorization: Bearer <token>" http://localhost:8090/api/v1/chat
echo.
pause
