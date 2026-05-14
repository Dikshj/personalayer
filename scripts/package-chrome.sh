#!/usr/bin/env bash
set -euo pipefail
cd extension
zip -r ../build/personalayer-chrome.zip manifest.json background.js content.js popup.html popup.js icons/icon128.png
cd ..
echo "Chrome extension packaged: build/personalayer-chrome.zip"
