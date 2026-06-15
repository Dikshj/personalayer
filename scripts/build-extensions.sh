#!/bin/bash
set -euo pipefail

# Package the Chrome extension for distribution.
# Outputs:
#   build/extensions/personalayer-chrome.zip

BUILD_DIR="build/extensions"
mkdir -p "${BUILD_DIR}"

echo "[build] Packaging Chrome extension..."
cd extension
zip -r "../${BUILD_DIR}/personalayer-chrome.zip" \
  manifest.json background.js content.js popup.html popup.js popup.css icons/
cd ..

echo "[build] Done: ${BUILD_DIR}/personalayer-chrome.zip"
