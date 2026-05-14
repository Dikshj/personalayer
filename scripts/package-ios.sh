#!/usr/bin/env bash
set -euo pipefail

# iOS archive, export, and TestFlight upload script
# Requirements: macOS, Xcode, Apple Developer account, App Store Connect API key

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BUILD_DIR="$PROJECT_ROOT/build"
APP_NAME="${IOS_APP_NAME:-PersonalLayer}"
BUNDLE_ID="${IOS_BUNDLE_ID:-com.personalayer.ios}"
TEAM_ID="${DEVELOPER_TEAM_ID:-}"

if [ -z "$TEAM_ID" ]; then
    echo "ERROR: DEVELOPER_TEAM_ID not set"
    echo "Set your Apple Developer Team ID: export DEVELOPER_TEAM_ID=YOUR_TEAM_ID"
    exit 1
fi

echo "=== iOS Packaging & TestFlight ==="
echo "App: $APP_NAME"
echo "Bundle ID: $BUNDLE_ID"
echo "Team ID: $TEAM_ID"

mkdir -p "$BUILD_DIR"

# 1. Update version from git
VERSION=$(cd "$PROJECT_ROOT" && git describe --tags --always 2>/dev/null || echo "0.1.0")
BUILD_NUMBER=$(cd "$PROJECT_ROOT" && git rev-list --count HEAD 2>/dev/null || echo "1")
echo "Version: $VERSION ($BUILD_NUMBER)"

# Update Info.plist
INFO_PLIST="$PROJECT_ROOT/native/ios/PersonalLayer/Resources/Info.plist"
if [ -f "$INFO_PLIST" ]; then
    /usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $VERSION" "$INFO_PLIST" 2>/dev/null || true
    /usr/libexec/PlistBuddy -c "Set :CFBundleVersion $BUILD_NUMBER" "$INFO_PLIST" 2>/dev/null || true
fi

# 2. Archive
ARCHIVE_PATH="$BUILD_DIR/$APP_NAME.xcarchive"
PROJECT_DIR="$PROJECT_ROOT/native/ios/PersonalLayer"

# For SPM projects, we need an Xcode project or workspace
# If using pure SPM, create one dynamically
if [ ! -f "$PROJECT_DIR/$APP_NAME.xcodeproj/project.pbxproj" ]; then
    echo "Generating Xcode project from Package.swift..."
    cd "$PROJECT_DIR"
    swift package generate-xcodeproj 2>/dev/null || {
        echo "WARNING: generate-xcodeproj may be deprecated. Using xcodebuild -scheme directly."
    }
fi

cd "$PROJECT_ROOT"

xcodebuild archive \
    -scheme "$APP_NAME" \
    -destination 'generic/platform=iOS' \
    -archivePath "$ARCHIVE_PATH" \
    -configuration Release \
    CODE_SIGN_IDENTITY="iPhone Distribution" \
    DEVELOPMENT_TEAM="$TEAM_ID" \
    PRODUCT_BUNDLE_IDENTIFIER="$BUNDLE_ID" \
    CURRENT_PROJECT_VERSION="$BUILD_NUMBER" \
    MARKETING_VERSION="$VERSION" \
    | tee "$BUILD_DIR/ios-archive.log"

if [ ! -d "$ARCHIVE_PATH" ]; then
    echo "ERROR: Archive failed"
    cat "$BUILD_DIR/ios-archive.log"
    exit 1
fi

echo "Archive created: $ARCHIVE_PATH"

# 3. Export IPA
EXPORT_PATH="$BUILD_DIR/Export"
EXPORT_OPTIONS="$SCRIPT_DIR/export-options.plist"

if [ ! -f "$EXPORT_OPTIONS" ]; then
    echo "ERROR: export-options.plist not found at $EXPORT_OPTIONS"
    exit 1
fi

# Update export options with team ID
sed -i.bak "s/YOUR_TEAM_ID/$TEAM_ID/g" "$EXPORT_OPTIONS"

xcodebuild -exportArchive \
    -archivePath "$ARCHIVE_PATH" \
    -exportPath "$EXPORT_PATH" \
    -exportOptionsPlist "$EXPORT_OPTIONS" \
    | tee "$BUILD_DIR/ios-export.log"

# Restore export options
mv "$EXPORT_OPTIONS.bak" "$EXPORT_OPTIONS"

IPA_PATH="$EXPORT_PATH/$APP_NAME.ipa"

if [ ! -f "$IPA_PATH" ]; then
    echo "ERROR: IPA not found at $IPA_PATH"
    find "$EXPORT_PATH" -name "*.ipa" 2>/dev/null || true
    exit 1
fi

echo "IPA created: $IPA_PATH"

# 4. Upload to TestFlight
API_KEY_PATH="${APP_STORE_CONNECT_API_KEY:-}"
API_KEY_ID="${APP_STORE_CONNECT_KEY_ID:-}"
API_ISSUER_ID="${APP_STORE_CONNECT_ISSUER_ID:-}"

if [ -n "$API_KEY_PATH" ] && [ -n "$API_KEY_ID" ] && [ -n "$API_ISSUER_ID" ]; then
    echo "Uploading to TestFlight..."
    xcrun altool --upload-app \
        --type ios \
        --file "$IPA_PATH" \
        --apiKey "$API_KEY_ID" \
        --apiIssuer "$API_ISSUER_ID" \
        | tee "$BUILD_DIR/ios-upload.log"
    echo "Upload complete!"
else
    echo ""
    echo "App Store Connect API key not configured."
    echo "To upload automatically, set these environment variables:"
    echo "  export APP_STORE_CONNECT_API_KEY=/path/to/AuthKey.p8"
    echo "  export APP_STORE_CONNECT_KEY_ID=YOUR_KEY_ID"
    echo "  export APP_STORE_CONNECT_ISSUER_ID=YOUR_ISSUER_ID"
    echo ""
    echo "Manual upload:"
    echo "  xcrun altool --upload-app --type ios --file $IPA_PATH"
    echo "  Or use Transporter app"
fi

echo ""
echo "=== iOS Packaging Complete ==="
echo "Archive: $ARCHIVE_PATH"
echo "IPA: $IPA_PATH"
echo ""
