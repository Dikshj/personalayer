#!/usr/bin/env bash
set -euo pipefail

# Package Safari WebExtension
# Requires Xcode and a valid Developer ID

cd "$(dirname "$0")/.."

XCODE_PROJECT="native/macos/PersonalLayerApp/PersonalLayerApp.xcodeproj"
EXT_TARGET="PersonalLayer Safari Extension"

if [ ! -d "$XCODE_PROJECT" ]; then
    echo "Error: Xcode project not found at $XCODE_PROJECT"
    echo "This script requires the full Xcode app wrapper project."
    echo "Run 'swift package generate-xcodeproj' or create manually."
    exit 1
fi

# Build the extension
xcodebuild -project "$XCODE_PROJECT"     -target "$EXT_TARGET"     -configuration Release     -derivedDataPath build/DerivedData     CODE_SIGN_IDENTITY="${CODE_SIGN_IDENTITY:--}"

# Find the .appex
APPEX=$(find build/DerivedData -name "*.appex" -type d | head -1)
if [ -z "$APPEX" ]; then
    echo "Error: .appex not found in build output"
    exit 1
fi

echo "Safari extension built: $APPEX"
echo "Package this with the main app for App Store submission."
