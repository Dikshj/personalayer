#!/usr/bin/env bash
set -euo pipefail

SCHEME="PersonalLayer"
PROJECT_ROOT="$(dirname "$0")/../native/ios"
EXPORT_PLIST="$PROJECT_ROOT/exportOptions.plist"

# Required env vars
APP_STORE_CONNECT_KEY_ID="${APP_STORE_CONNECT_KEY_ID:-}"
APP_STORE_CONNECT_ISSUER="${APP_STORE_CONNECT_ISSUER:-}"
APP_STORE_CONNECT_KEY_PATH="${APP_STORE_CONNECT_KEY_PATH:-}"

if [[ -z "$APP_STORE_CONNECT_KEY_ID" || -z "$APP_STORE_CONNECT_ISSUER" ]]; then
  echo "Error: Set App Store Connect credentials"
  echo "  export APP_STORE_CONNECT_KEY_ID=ABC123"
  echo "  export APP_STORE_CONNECT_ISSUER=xyz-issuer-id"
  exit 1
fi

# Generate export options plist if not exists
if [[ ! -f "$EXPORT_PLIST" ]]; then
  cat > "$EXPORT_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>method</key>
    <string>app-store-connect</string>
    <key>teamID</key>
    <string>${TEAM_ID:-}</string>
    <key>provisioningProfiles</key>
    <dict>
        <key>com.personalayer.ios</key>
        <string>Personal Layer App Store</string>
    </dict>
    <key>uploadSymbols</key>
    <true/>
</dict>
</plist>
EOF
fi

echo "Archiving..."
cd "$PROJECT_ROOT"
xcodebuild archive   -scheme "$SCHEME"   -destination "generic/platform=iOS"   -archivePath "../../build/PersonalLayer.xcarchive"   -allowProvisioningUpdates   -authenticationKeyPath "$APP_STORE_CONNECT_KEY_PATH"   -authenticationKeyID "$APP_STORE_CONNECT_KEY_ID"   -authenticationKeyIssuerID "$APP_STORE_CONNECT_ISSUER"

echo "Exporting IPA..."
xcodebuild -exportArchive   -archivePath "../../build/PersonalLayer.xcarchive"   -exportOptionsPlist "$EXPORT_PLIST"   -exportPath "../../build/ipa"   -allowProvisioningUpdates   -authenticationKeyPath "$APP_STORE_CONNECT_KEY_PATH"   -authenticationKeyID "$APP_STORE_CONNECT_KEY_ID"   -authenticationKeyIssuerID "$APP_STORE_CONNECT_ISSUER"

echo "Uploading to TestFlight..."
xcrun altool --upload-app   -f "../../build/ipa/*.ipa"   -t ios   --apiKey "$APP_STORE_CONNECT_KEY_ID"   --apiIssuer "$APP_STORE_CONNECT_ISSUER"

echo "Uploaded to TestFlight successfully"
