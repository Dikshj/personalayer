#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p build/chrome

# Copy extension files
cp extension/manifest.json build/chrome/
cp extension/background.js build/chrome/
cp extension/content.js build/chrome/
cp extension/popup.html build/chrome/
cp extension/popup.js build/chrome/
cp extension/icons/icon128.png build/chrome/icons/

# Create ZIP for Chrome Web Store
cd build/chrome
zip -r ../personalayer-chrome.zip .
cd ../..

echo "Chrome extension packaged: build/personalayer-chrome.zip"
echo ""
echo "Upload to Chrome Web Store Developer Dashboard:"
echo "  https://chrome.google.com/webstore/devconsole"
