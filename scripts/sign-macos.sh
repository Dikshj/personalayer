#!/usr/bin/env bash
set -euo pipefail

APP_NAME="PersonalLayer"
BUNDLE_ID="com.personalayer.macos"
TEAM_ID="${TEAM_ID:-}"
SIGNING_IDENTITY="${SIGNING_IDENTITY:-}"
NOTARIZE_PASSWORD="${NOTARIZE_PASSWORD:-}"
NOTARIZE_KEYCHAIN_PROFILE="${NOTARIZE_KEYCHAIN_PROFILE:-}"

if [[ -z "$SIGNING_IDENTITY" || -z "$TEAM_ID" ]]; then
  echo "Error: Set SIGNING_IDENTITY and TEAM_ID environment variables"
  echo "Example:"
  echo "  export SIGNING_IDENTITY="Developer ID Application: Your Name (TEAMID)""
  echo "  export TEAM_ID=ABCD123456"
  exit 1
fi

echo "Building release binary..."
cd "$(dirname "$0")/../native/macos/PersonalLayer"
swift build -c release

BINARY=".build/release/$APP_NAME"
APP_DIR=".build/release/${APP_NAME}.app"
CONTENTS="$APP_DIR/Contents"

# Bundle as .app
echo "Bundling .app..."
mkdir -p "$CONTENTS/MacOS"
mkdir -p "$CONTENTS/Resources"
cp "$BINARY" "$CONTENTS/MacOS/"
cp Resources/Info.plist "$CONTENTS/"
cp Resources/PersonalLayer.entitlements "$CONTENTS/Resources/"

# Sign the binary and bundle
echo "Signing with identity: $SIGNING_IDENTITY"
codesign --force --options runtime --timestamp   --entitlements Resources/PersonalLayer.entitlements   --sign "$SIGNING_IDENTITY"   "$CONTENTS/MacOS/$APP_NAME"

codesign --force --options runtime --timestamp   --sign "$SIGNING_IDENTITY"   "$APP_DIR"

# Create DMG
echo "Creating DMG..."
DMG_NAME="${APP_NAME}-$(date +%Y%m%d).dmg"
hdiutil create -volname "$APP_NAME" -srcfolder "$APP_DIR" -ov -format UDZO "$DMG_NAME"

# Notarize if credentials available
if [[ -n "$NOTARIZE_KEYCHAIN_PROFILE" ]]; then
  echo "Notarizing..."
  xcrun notarytool submit "$DMG_NAME"     --keychain-profile "$NOTARIZE_KEYCHAIN_PROFILE"     --wait
  xcrun stapler staple "$DMG_NAME"
  echo "Notarized and stapled: $DMG_NAME"
else
  echo "Skipping notarization (set NOTARIZE_KEYCHAIN_PROFILE to enable)"
fi

echo "Done: $DMG_NAME"
