@echo off
setlocal enabledelayedexpansion
echo.
echo PersonaLayer -- Setup
echo ====================

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo ERROR: Python 3.10+ required. Install from https://python.org
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo Python: %PY_VER%

if not exist "%USERPROFILE%\.personalayer" mkdir "%USERPROFILE%\.personalayer"

echo.
echo Installing Python dependencies...
cd /d "%~dp0backend"
python -m pip install -r requirements.txt --quiet

if not exist ".env" (
    copy .env.example .env >nul
    echo.
    echo ACTION NEEDED: Add your Anthropic API key to backend\.env
    echo Get one at: https://console.anthropic.com
)

set SCRIPT_DIR=%~dp0
set SCRIPT_DIR=%SCRIPT_DIR:~0,-1%

set MCP_CONFIG=%SCRIPT_DIR%\claude_desktop_config_generated.json

(
echo {
echo   "mcpServers": {
echo     "personalayer": {
echo       "command": "python",
echo       "args": ["%SCRIPT_DIR:\=/%/backend/mcp_server.py"]
echo     }
echo   }
echo }
) > "%MCP_CONFIG%"

echo.
echo Installation complete!
echo.
echo Next steps:
echo 1. Add API key: notepad backend\.env
echo 2. Install daemon startup:
echo    powershell -ExecutionPolicy Bypass -File scripts\install_windows_startup.ps1
echo 3. Load optional browser collector: Chrome - chrome://extensions/ - Developer mode ON - Load unpacked - select 'extension\'
echo 4. Merge %MCP_CONFIG% into %%APPDATA%%\Claude\claude_desktop_config.json
echo 5. Restart Claude Desktop
echo 6. View dashboard: http://localhost:7823/dashboard
