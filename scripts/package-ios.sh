#!/usr/bin/env bash
set -euo pipefail
SCHEME="PersonalLayer"
WORKSPACE="native/ios/PersonalLayer.xcworkspace"

echo "Archiving iOS app..."
xcodebuild archive   -workspace "$WORKSPACE"   -scheme "$SCHEME"   -destination "generic/platform=iOS"   -archivePath build/PersonalLayer.xcarchive

echo "Exporting IPA..."
xcodebuild -exportArchive   -archivePath build/PersonalLayer.xcarchive   -exportOptionsPlist native/ios/exportOptions.plist   -exportPath build/ipa

echo "Uploading to TestFlight..."
xcrun altool --upload-app -f build/ipa/*.ipa -t ios --apiKey "${APP_STORE_CONNECT_KEY_ID}" --apiIssuer "${APP_STORE_CONNECT_ISSUER}"
