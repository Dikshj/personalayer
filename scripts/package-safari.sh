#!/usr/bin/env bash
set -euo pipefail

# Safari WebExtension packaging script
# Requirements: macOS, Xcode, Apple Developer account

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BUILD_DIR="$PROJECT_ROOT/build"
APP_NAME="PersonalLayer"
BUNDLE_ID="${SAFARI_BUNDLE_ID:-com.personalayer.safari}"
TEAM_ID="${DEVELOPER_TEAM_ID:-}"

if [ -z "$TEAM_ID" ]; then
    echo "ERROR: DEVELOPER_TEAM_ID not set"
    echo "Set your Apple Developer Team ID: export DEVELOPER_TEAM_ID=YOUR_TEAM_ID"
    exit 1
fi

echo "=== Safari Extension Packaging ==="
echo "App: $APP_NAME"
echo "Bundle ID: $BUNDLE_ID"
echo "Team ID: $TEAM_ID"

mkdir -p "$BUILD_DIR"

# 1. Build Safari app extension
# The Safari extension is embedded in the macOS app
EXTENSION_PROJECT="$PROJECT_ROOT/native/macos/PersonalLayer"

if [ ! -d "$EXTENSION_PROJECT" ]; then
    echo "ERROR: macOS project not found at $EXTENSION_PROJECT"
    exit 1
fi

cd "$EXTENSION_PROJECT"

# Build the extension target
xcodebuild \
    -scheme PersonalLayer \
    -configuration Release \
    -derivedDataPath "$BUILD_DIR/DerivedData" \
    CODE_SIGN_IDENTITY="Apple Development" \
    DEVELOPMENT_TEAM="$TEAM_ID" \
    PRODUCT_BUNDLE_IDENTIFIER="$BUNDLE_ID" \
    build

# Find the built .appex
APPEX_PATH=$(find "$BUILD_DIR/DerivedData" -name "*.appex" -type d | head -1)

if [ -z "$APPEX_PATH" ]; then
    echo "ERROR: Safari extension .appex not found in build output"
    exit 1
fi

echo "Found extension: $APPEX_PATH"

# 2. Create Safari extension app wrapper
# Safari extensions need to be distributed as part of a macOS app
APP_PATH="$BUILD_DIR/$APP_NAME.app"
mkdir -p "$APP_PATH/Contents/MacOS"
mkdir -p "$APP_PATH/Contents/PlugIns"

cp -R "$APPEX_PATH" "$APP_PATH/Contents/PlugIns/"

# Create Info.plist for the wrapper app
cat > "$APP_PATH/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleIdentifier</key>
    <string>$BUNDLE_ID</string>
    <key>CFBundleName</key>
    <string>$APP_NAME</string>
    <key>CFBundleVersion</key>
    <string>1.0.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>NSExtension</key>
    <dict>
        <key>NSExtensionPointIdentifier</key>
        <string>com.apple.Safari.web-extension</string>
    </dict>
</dict>
</plist>
EOF

# 3. Sign the extension
codesign --force --sign "Apple Development" --timestamp \
    "$APP_PATH/Contents/PlugIns/$(basename "$APPEX_PATH")"

# 4. Create ZIP for distribution
ZIP_PATH="$BUILD_DIR/personalayer-safari.zip"
ditto -c -k --keepParent "$APP_PATH" "$ZIP_PATH"

echo ""
echo "=== Safari Extension Packaged ==="
echo "Output: $ZIP_PATH"
echo ""
echo "Next steps:"
echo "1. Upload to App Store Connect:"
echo "   xcrun altool --upload-app -f $ZIP_PATH -t macos"
echo "2. Or distribute directly for testing"
echo ""
