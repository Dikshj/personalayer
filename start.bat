@echo off
:: PersonaLayer — Start everything with one command
:: Starts: FastAPI backend (which auto-starts all collectors)
:: Auto-starts: Claude Code watcher, Ollama proxy (if Ollama running),
::              GitHub sync (every 6h if GITHUB_USERNAME set in .env)

setlocal enabledelayedexpansion
cd /d "%~dp0"

:: ── Check .env exists ──
if not exist "backend\.env" (
    if exist "backend\.env.example" (
        copy backend\.env.example backend\.env >nul
    )
    echo ACTION NEEDED: set ANTHROPIC_API_KEY in backend\.env
    echo Also set GITHUB_USERNAME in backend\.env for auto GitHub sync
    echo Opening .env now...
    notepad backend\.env
)

:: ── Load GITHUB_USERNAME from .env into environment ──
for /f "usebackq tokens=1,* delims==" %%A in ("backend\.env") do (
    set "%%A=%%B"
)

echo.
echo PersonaLayer starting...
echo   Backend:          http://localhost:7823
echo   Dashboard:        http://localhost:7823/dashboard
echo   Demo app:         http://localhost:3001
echo   Claude Code watcher: auto (daemon thread)
if defined GITHUB_USERNAME (
    echo   GitHub sync:      @%GITHUB_USERNAME% every 6h
) else (
    echo   GitHub sync:      SKIPPED (set GITHUB_USERNAME in .env^)
)
echo.

:: ── Start demo-app server in background ──
start "PersonaLayer Demo" /min python demo-app\serve.py

:: ── Start main backend (blocking — this window stays open) ──
python backend\main.py
