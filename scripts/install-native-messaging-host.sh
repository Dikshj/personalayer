#!/usr/bin/env bash
set -euo pipefail

# Install Personal Layer native messaging host for Chrome/Edge on macOS
# Must be run after the macOS app is built

APP_NAME="PersonalLayer"
HOST_NAME="com.personalayer.macos"
BUNDLE_ID="com.personalayer.macos"

# Determine Chrome/Edge extension IDs (set these before running)
CHROME_EXT_ID="${CHROME_EXT_ID:-}"
EDGE_EXT_ID="${EDGE_EXT_ID:-}"

if [[ -z "$CHROME_EXT_ID" && -z "$EDGE_EXT_ID" ]]; then
  echo "Error: Set CHROME_EXT_ID or EDGE_EXT_ID environment variable"
  exit 1
fi

# Find the built executable
EXECUTABLE_PATH=""
for path in   "$HOME/personalayer/native/macos/PersonalLayer/.build/release/$APP_NAME"   "/Applications/PersonalLayer.app/Contents/MacOS/$APP_NAME"   "$(dirname "$0")/../native/macos/PersonalLayer/.build/release/$APP_NAME"; do
  if [[ -f "$path" ]]; then
    EXECUTABLE_PATH="$(cd "$(dirname "$path")" && pwd)/$(basename "$path")"
    break
  fi
done

if [[ -z "$EXECUTABLE_PATH" ]]; then
  echo "Error: Could not find $APP_NAME executable"
  echo "Build it first: cd native/macos/PersonalLayer && swift build -c release"
  exit 1
fi

# Build allowed_origins array
ALLOWED_ORIGINS=""
if [[ -n "$CHROME_EXT_ID" ]]; then
  ALLOWED_ORIGINS="\"chrome-extension://$CHROME_EXT_ID/\""
fi
if [[ -n "$EDGE_EXT_ID" ]]; then
  if [[ -n "$ALLOWED_ORIGINS" ]]; then
    ALLOWED_ORIGINS="$ALLOWED_ORIGINS, \"chrome-extension://$EDGE_EXT_ID/\""
  else
    ALLOWED_ORIGINS="\"chrome-extension://$EDGE_EXT_ID/\""
  fi
fi

# Write manifest for Chrome
CHROME_DIR="$HOME/Library/Application Support/Google/Chrome/NativeMessagingHosts"
mkdir -p "$CHROME_DIR"
cat > "$CHROME_DIR/$HOST_NAME.json" <<EOF
{
  "name": "$HOST_NAME",
  "description": "Personal Layer Native Messaging Host",
  "path": "$EXECUTABLE_PATH",
  "type": "stdio",
  "allowed_origins": [
    $ALLOWED_ORIGINS
  ]
}
EOF

# Write manifest for Edge
EDGE_DIR="$HOME/Library/Application Support/Microsoft Edge/NativeMessagingHosts"
mkdir -p "$EDGE_DIR"
cp "$CHROME_DIR/$HOST_NAME.json" "$EDGE_DIR/$HOST_NAME.json"

# Write manifest for Chromium (if installed)
CHROMIUM_DIR="$HOME/Library/Application Support/Chromium/NativeMessagingHosts"
if [[ -d "$CHROMIUM_DIR" ]]; then
  mkdir -p "$CHROMIUM_DIR"
  cp "$CHROME_DIR/$HOST_NAME.json" "$CHROMIUM_DIR/$HOST_NAME.json"
fi

echo "Native messaging host installed:"
echo "  Chrome:  $CHROME_DIR/$HOST_NAME.json"
echo "  Edge:    $EDGE_DIR/$HOST_NAME.json"
echo ""
echo "Executable: $EXECUTABLE_PATH"
echo "Allowed origins: $ALLOWED_ORIGINS"
