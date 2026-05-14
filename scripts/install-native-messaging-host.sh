#!/usr/bin/env bash
set -euo pipefail

# Install Personal Layer native messaging host for Chrome/Edge
# Must run after building the macOS app

APP_PATH="${1:-$(cd "$(dirname "$0")/../native/macos/PersonalLayer/.build/debug/PersonalLayer" && pwd)/PersonalLayer}"
CHROME_EXT_ID="${CHROME_EXT_ID:-}"
EDGE_EXT_ID="${EDGE_EXT_ID:-}"

if [ ! -f "$APP_PATH" ]; then
    echo "Error: PersonalLayer executable not found at $APP_PATH"
    echo "Usage: $0 /path/to/PersonalLayer [CHROME_EXT_ID] [EDGE_EXT_ID]"
    exit 1
fi

MANIFEST_PATH="$HOME/Library/Application Support/PersonalLayer/com.personalayer.macos.json"
mkdir -p "$(dirname "$MANIFEST_PATH")"

cat > "$MANIFEST_PATH" <<EOF
{
  "name": "com.personalayer.macos",
  "description": "Personal Layer Native Messaging Host",
  "path": "$APP_PATH",
  "type": "stdio",
  "allowed_origins": [
EOF

if [ -n "$CHROME_EXT_ID" ]; then
    echo "    "chrome-extension://${CHROME_EXT_ID}/"" >> "$MANIFEST_PATH"
fi
if [ -n "$EDGE_EXT_ID" ]; then
    echo "    "chrome-extension://${EDGE_EXT_ID}/"" >> "$MANIFEST_PATH"
fi

cat >> "$MANIFEST_PATH" <<EOF
  ]
}
EOF

# Install for Chrome
CHROME_NMH="$HOME/Library/Application Support/Google/Chrome/NativeMessagingHosts"
mkdir -p "$CHROME_NMH"
ln -sf "$MANIFEST_PATH" "$CHROME_NMH/com.personalayer.macos.json"

# Install for Edge
EDGE_NMH="$HOME/Library/Application Support/Microsoft Edge/NativeMessagingHosts"
mkdir -p "$EDGE_NMH"
ln -sf "$MANIFEST_PATH" "$EDGE_NMH/com.personalayer.macos.json"

# Install for Chromium
CHROMIUM_NMH="$HOME/Library/Application Support/Chromium/NativeMessagingHosts"
mkdir -p "$CHROMIUM_NMH"
ln -sf "$MANIFEST_PATH" "$CHROMIUM_NMH/com.personalayer.macos.json"

echo "Native messaging host installed."
echo "  Manifest: $MANIFEST_PATH"
echo "  Chrome:   $CHROME_NMH"
echo "  Edge:     $EDGE_NMH"
echo "Restart browser after installing the extension."
