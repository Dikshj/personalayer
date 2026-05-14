#!/usr/bin/env bash
set -euo pipefail

# Sign and notarize macOS app
# Requires:
#   - macOS Developer ID Application certificate in Keychain
#   - App Store Connect API key (for notarytool)
#   - TEAM_ID, BUNDLE_ID, APP_NAME environment variables

cd "$(dirname "$0")/.."

APP_NAME="${APP_NAME:-PersonalLayer}"
BUNDLE_ID="${BUNDLE_ID:-com.personalayer.macos}"
TEAM_ID="${TEAM_ID:-}"
SIGN_ID="${SIGN_ID:-Developer ID Application: ${TEAM_ID}}"
NOTARY_KEY="${NOTARY_KEY:-}"
NOTARY_ISSUER="${NOTARY_ISSUER:-}"

BUILD_DIR="native/macos/PersonalLayer/.build/release"
APP_PATH="${BUILD_DIR}/${APP_NAME}"
DMG_PATH="build/${APP_NAME}.dmg"
ZIP_PATH="build/${APP_NAME}.zip"

if [ ! -f "$APP_PATH" ]; then
    echo "Building release binary..."
    cd native/macos/PersonalLayer
    swift build -c release
    cd -
fi

# Create app bundle structure
APP_BUNDLE="build/${APP_NAME}.app"
rm -rf "$APP_BUNDLE"
mkdir -p "${APP_BUNDLE}/Contents/MacOS"
mkdir -p "${APP_BUNDLE}/Contents/Resources"

cp "$APP_PATH" "${APP_BUNDLE}/Contents/MacOS/"
cp native/macos/PersonalLayer/Resources/Info.plist "${APP_BUNDLE}/Contents/"
cp native/macos/PersonalLayer/Resources/PersonalLayer.entitlements "${APP_BUNDLE}/Contents/Resources/"

# Sign
codesign --force --options runtime --deep --sign "$SIGN_ID"     --entitlements "${APP_BUNDLE}/Contents/Resources/PersonalLayer.entitlements"     "$APP_BUNDLE"

# Package for notarization
rm -f "$ZIP_PATH"
ditto -c -k --keepParent "$APP_BUNDLE" "$ZIP_PATH"

# Notarize
if [ -n "$NOTARY_KEY" ] && [ -n "$NOTARY_ISSUER" ]; then
    xcrun notarytool submit "$ZIP_PATH"         --key-id "$NOTARY_KEY"         --issuer "$NOTARY_ISSUER"         --wait
    xcrun stapler staple "$APP_BUNDLE"
    echo "Notarization complete."
else
    echo "Skipping notarization (set NOTARY_KEY and NOTARY_ISSUER)."
fi

# Create DMG
hdiutil create -volname "$APP_NAME" -srcfolder "$APP_BUNDLE" -ov "$DMG_PATH"

echo "Signed app: $APP_BUNDLE"
echo "DMG: $DMG_PATH"
