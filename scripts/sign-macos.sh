#!/usr/bin/env bash
set -euo pipefail

# macOS app signing and notarization script
# Requirements: macOS, Xcode, Apple Developer ID certificate, app-specific password

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BUILD_DIR="$PROJECT_ROOT/build"
APP_NAME="${MACOS_APP_NAME:-PersonalLayer}"
BUNDLE_ID="${MACOS_BUNDLE_ID:-com.personalayer.macos}"
DEVELOPER_ID="${DEVELOPER_ID:-}"
KEYCHAIN_PROFILE="${KEYCHAIN_PROFILE:-notarytool-profile}"

if [ -z "$DEVELOPER_ID" ]; then
    echo "ERROR: DEVELOPER_ID not set"
    echo "Set your Apple Developer ID: export DEVELOPER_ID='Developer ID Application: Your Name (TEAM_ID)'"
    exit 1
fi

echo "=== macOS Signing & Notarization ==="
echo "App: $APP_NAME"
echo "Bundle ID: $BUNDLE_ID"
echo "Developer ID: $DEVELOPER_ID"

mkdir -p "$BUILD_DIR"

# 1. Build Release
PROJECT_DIR="$PROJECT_ROOT/native/macos/PersonalLayer"
cd "$PROJECT_DIR"

swift build -c release 2>&1 | tee "$BUILD_DIR/macos-build.log"

APP_PATH="$BUILD_DIR/Release/$APP_NAME.app"

if [ ! -d "$APP_PATH" ]; then
    echo "ERROR: Built app not found at $APP_PATH"
    echo "Checking for alternative paths..."
    find "$PROJECT_DIR/.build" -name "*.app" -type d 2>/dev/null || true
    exit 1
fi

echo "Built app: $APP_PATH"

# 2. Sign with entitlements
ENTITLEMENTS_FILE="$PROJECT_DIR/Resources/$APP_NAME.entitlements"

if [ -f "$ENTITLEMENTS_FILE" ]; then
    codesign --force --options runtime --sign "$DEVELOPER_ID" \
        --entitlements "$ENTITLEMENTS_FILE" \
        --timestamp \
        "$APP_PATH"
else
    echo "WARNING: No entitlements file found at $ENTITLEMENTS_FILE"
    echo "Creating minimal entitlements..."
    cat > "/tmp/$APP_NAME.entitlements" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.security.app-sandbox</key>
    <true/>
    <key>com.apple.security.network.server</key>
    <true/>
    <key>com.apple.security.network.client</key>
    <true/>
    <key>com.apple.security.files.user-selected.read-write</key>
    <true/>
    <key>com.apple.security.keychain</key>
    <true/>
</dict>
</plist>
EOF
    codesign --force --options runtime --sign "$DEVELOPER_ID" \
        --entitlements "/tmp/$APP_NAME.entitlements" \
        --timestamp \
        "$APP_PATH"
fi

echo "Signed app"

# 3. Create DMG
DMG_PATH="$BUILD_DIR/$APP_NAME.dmg"
if command -v create-dmg &>/dev/null; then
    create-dmg \
        --volname "$APP_NAME" \
        --window-pos 200 120 \
        --window-size 600 400 \
        --icon-size 100 \
        --app-drop-link 450 185 \
        "$DMG_PATH" \
        "$APP_PATH"
else
    echo "create-dmg not installed, using hdiutil..."
    TEMP_DMG="/tmp/$APP_NAME-temp.dmg"
    hdiutil create -srcfolder "$APP_PATH" -volname "$APP_NAME" -fs HFS+ \
        -format UD RW -o "$TEMP_DMG"
    hdiutil convert "$TEMP_DMG" -format UDZO -o "$DMG_PATH"
    rm -f "$TEMP_DMG"
fi

echo "Created DMG: $DMG_PATH"

# 4. Notarize
if command -v xcrun &>/dev/null; then
    echo "Submitting for notarization..."
    xcrun notarytool submit "$DMG_PATH" \
        --keychain-profile "$KEYCHAIN_PROFILE" \
        --wait

    echo "Stapling ticket..."
    xcrun stapler staple "$DMG_PATH"

    echo "Verifying..."
    spctl -a -vv "$DMG_PATH" || true
else
    echo "WARNING: xcrun not available. Notarization skipped."
fi

echo ""
echo "=== macOS Signing Complete ==="
echo "App: $APP_PATH"
echo "DMG: $DMG_PATH"
echo ""
