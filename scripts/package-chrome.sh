#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

BUILD_DIR="build/chrome"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

cp extension/manifest.json "$BUILD_DIR/"
cp extension/background.js "$BUILD_DIR/"
cp extension/content.js "$BUILD_DIR/"
cp extension/popup.html "$BUILD_DIR/"
cp extension/popup.js "$BUILD_DIR/"

mkdir -p "$BUILD_DIR/icons"
cp extension/icons/icon16.png "$BUILD_DIR/icons/"
cp extension/icons/icon48.png "$BUILD_DIR/icons/"
cp extension/icons/icon128.png "$BUILD_DIR/icons/"

# Validate manifest JSON
node -e "JSON.parse(require('fs').readFileSync('$BUILD_DIR/manifest.json'))"

# Validate icon sizes
for size in 16 48 128; do
    if [ ! -f "$BUILD_DIR/icons/icon${size}.png" ]; then
        echo "Error: Missing icon${size}.png"
        exit 1
    fi
done

mkdir -p build
zip -r "build/personalayer-chrome.zip" -j "$BUILD_DIR"/* "$BUILD_DIR/icons"/*

echo "Chrome extension packaged: build/personalayer-chrome.zip"
echo "Upload this to Chrome Web Store Developer Dashboard."
