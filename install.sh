#!/usr/bin/env bash
# install.sh
set -euo pipefail

echo ""
echo "PersonaLayer — Setup"
echo "===================="

# Check Python 3.10+
PYTHON=$(command -v python3 || command -v python || echo "")
if [ -z "$PYTHON" ]; then
  echo "ERROR: Python 3.10+ required. Install from https://python.org"
  exit 1
fi

PY_VERSION=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Python: $PY_VERSION"

# Create data dir
mkdir -p ~/.personalayer

# Install deps
echo ""
echo "Installing Python dependencies..."
cd "$(dirname "$0")/backend"
$PYTHON -m pip install -r requirements.txt --quiet

# Scaffold .env
if [ ! -f .env ]; then
  cp .env.example .env
  echo ""
  echo "ACTION NEEDED: Add your Anthropic API key to backend/.env"
  echo "   Get one at: https://console.anthropic.com"
fi

# Generate MCP config with absolute path
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MCP_CONFIG="$SCRIPT_DIR/claude_desktop_config_generated.json"

cat > "$MCP_CONFIG" << EOF
{
  "mcpServers": {
    "personalayer": {
      "command": "python3",
      "args": ["$SCRIPT_DIR/backend/mcp_server.py"]
    }
  }
}
EOF

echo ""
echo "Installation complete!"
echo ""
echo "Next steps:"
echo ""
echo "1. Add API key:  nano backend/.env"
echo "2. Load extension:"
echo "   Chrome -> chrome://extensions/ -> Developer mode ON -> Load unpacked -> select 'extension/'"
echo "3. Start server:"
echo "   python3 backend/main.py"
echo "4. Add MCP to Claude Desktop:"
echo "   Merge $MCP_CONFIG into:"
echo "   ~/Library/Application Support/Claude/claude_desktop_config.json"
echo "5. Restart Claude Desktop"
echo "6. View dashboard: http://localhost:7823/dashboard"
