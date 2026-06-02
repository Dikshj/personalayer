#!/bin/bash
set -euo pipefail

# Build and archive Personal Layer iOS app for TestFlight.
# Prerequisites:
#   - Xcode 15+
#   - Apple Developer account with Team ID
#   - Core ML model converted: python scripts/convert-coreml-model.py

PROJECT="native/ios/PersonalLayer"
BUILD_DIR="build/ios"
APP_NAME="PersonalLayer"
BUNDLE_ID="com.personalayer.ios"

cd "${PROJECT}"

echo "[build] Resolving packages..."
swift package resolve

echo "[build] Building for iOS..."
swift build -c release --sdk iphoneos

echo "[build] Archiving for TestFlight..."
xcodebuild archive \
  -scheme "PersonalLayer" \
  -destination "generic/platform=iOS" \
  -archivePath "../../${BUILD_DIR}/${APP_NAME}.xcarchive" \
  || true

echo "[build] Exporting IPA..."
mkdir -p "../../${BUILD_DIR}"
cat > "../../${BUILD_DIR}/ExportOptions.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>method</key>
  <string>app-store-connect</string>
  <key>teamID</key>
  <string>${APPLE_TEAM_ID}</string>
  <key>uploadSymbols</key>
  <true/>
</dict>
</plist>
EOF

xcodebuild -exportArchive \
  -archivePath "../../${BUILD_DIR}/${APP_NAME}.xcarchive" \
  -exportPath "../../${BUILD_DIR}/ipa" \
  -exportOptionsPlist "../../${BUILD_DIR}/ExportOptions.plist"

echo "[build] Done: ${BUILD_DIR}/ipa/${APP_NAME}.ipa"
