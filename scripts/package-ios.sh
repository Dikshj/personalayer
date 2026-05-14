#!/usr/bin/env bash
set -euo pipefail

# Build and archive iOS app for TestFlight
# Requires:
#   - macOS with Xcode
#   - Valid signing certificates and provisioning profiles
#   - APP_STORE_CONNECT_API_KEY environment variable

cd "$(dirname "$0")/.."

PROJECT="native/ios/PersonalLayer"
SCHEME="PersonalLayer"
BUNDLE_ID="${BUNDLE_ID:-com.personalayer.ios}"
TEAM_ID="${TEAM_ID:-}"
API_KEY="${APP_STORE_CONNECT_API_KEY:-}"
API_ISSUER="${APP_STORE_CONNECT_ISSUER_ID:-}"

if [ ! -d "$PROJECT" ]; then
    echo "Error: iOS project not found at $PROJECT"
    exit 1
fi

ARCHIVE_PATH="build/PersonalLayer.xcarchive"
EXPORT_PATH="build/PersonalLayer-export"

# Clean
rm -rf "$ARCHIVE_PATH" "$EXPORT_PATH"
mkdir -p build

# Archive
xcodebuild archive     -project "${PROJECT}/${SCHEME}.xcodeproj"     -scheme "$SCHEME"     -destination "generic/platform=iOS"     -archivePath "$ARCHIVE_PATH"     CODE_SIGN_STYLE=Automatic     DEVELOPMENT_TEAM="$TEAM_ID"

# Export
xcodebuild -exportArchive     -archivePath "$ARCHIVE_PATH"     -exportPath "$EXPORT_PATH"     -exportOptionsPlist scripts/export-options.plist

# Upload to TestFlight
if [ -n "$API_KEY" ] && [ -n "$API_ISSUER" ]; then
    xcrun altool --upload-app         -f "${EXPORT_PATH}/${SCHEME}.ipa"         -t ios         --apiKey "$API_KEY"         --apiIssuer "$API_ISSUER"
    echo "Uploaded to TestFlight."
else
    echo "IPA built at ${EXPORT_PATH}/${SCHEME}.ipa"
    echo "Set APP_STORE_CONNECT_API_KEY and APP_STORE_CONNECT_ISSUER_ID to upload."
fi
