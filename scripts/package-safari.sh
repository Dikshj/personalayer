#!/usr/bin/env bash
set -euo pipefail

MACOS_PROJECT="native/macos/PersonalLayer"
TEAM_ID="${TEAM_ID:-}"
SIGNING_IDENTITY="${SIGNING_IDENTITY:-}"

if [[ -z "$SIGNING_IDENTITY" ]]; then
  echo "Warning: SIGNING_IDENTITY not set — building unsigned"
fi

cd "$MACOS_PROJECT"

# Build the app (which embeds the Safari extension)
swift build -c release

# Sign the Safari extension target if identity available
if [[ -n "$SIGNING_IDENTITY" ]]; then
  codesign --force --options runtime --timestamp     --sign "$SIGNING_IDENTITY"     .build/release/PersonalLayerExtension.appex || true
fi

echo "Safari extension built:"
echo "  .build/release/PersonalLayerExtension.appex"
echo ""
echo "To distribute:"
echo "  1. Open the .app in Xcode"
echo "  2. Product > Archive"
echo "  3. Distribute App > Developer ID"
