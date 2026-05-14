#!/usr/bin/env bash
set -euo pipefail
APP_NAME="PersonalLayer"
BUNDLE_ID="com.personalayer.macos"
TEAM_ID="${TEAM_ID:-}"
IDENTITY="${SIGNING_IDENTITY:-}"

echo "Building macOS app..."
cd native/macos/PersonalLayer
swift build -c release

# In production:
# codesign --force --options runtime --deep --sign "$IDENTITY" .build/release/$APP_NAME
# xcrun notarytool submit ...
# xcrun stapler staple ...
echo "Sign/notarize placeholders ready (set SIGNING_IDENTITY and TEAM_ID)."
