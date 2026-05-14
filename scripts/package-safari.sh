#!/usr/bin/env bash
set -euo pipefail
cd native/macos/PersonalLayer
xcodebuild -target PersonalLayerExtension -configuration Release
echo "Safari extension built."
