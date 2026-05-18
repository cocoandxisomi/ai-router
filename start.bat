@echo off
chcp 65001 >nul
title AI Router + Public Tunnel

echo ============================================
echo   AI Router v2.0 + Public Tunnel
echo ============================================
echo.

REM ── Step 1: Start AI Router in background ──
echo [1/2] Starting AI Router on port 9876...
start "AI-Router" /MIN pythonw app.py >nul 2>&1
timeout /t 3 /nobreak >nul

REM ── Quick health check ──
curl -s http://localhost:9876/ >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] AI Router failed to start!
    pause
    exit /b 1
)
echo [OK] AI Router running on http://localhost:9876
echo.

REM ── Step 2: Start localtunnel ──
echo [2/2] Starting public tunnel...
echo.
echo    Your public URL will appear below.
echo    Give this URL to your customers!
echo    Press Ctrl+C to stop.
echo.
echo ============================================
npx localtunnel --port 9876