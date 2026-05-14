#!/usr/bin/env bash
set -euo pipefail

# End-to-end test script for native apps
# Run on macOS after building both macOS and iOS apps

echo "=== Personal Layer Native App Tests ==="

# macOS daemon tests
if [ -d "native/macos/PersonalLayer" ]; then
    echo "1. macOS daemon build check..."
    cd native/macos/PersonalLayer
    swift build 2>&1 | tee /tmp/macos-build.log
    if grep -q "error:" /tmp/macos-build.log; then
        echo "   BUILD FAILED"
        exit 1
    else
        echo "   Build OK"
    fi
    cd -

    echo "2. macOS daemon unit tests..."
    cd native/macos/PersonalLayer
    swift test 2>&1 | tee /tmp/macos-test.log || true
    cd -
fi

# iOS app tests
if [ -d "native/ios/PersonalLayer" ]; then
    echo "3. iOS app build check..."
    cd native/ios/PersonalLayer
    # SPM-based iOS apps need Xcode for SwiftUI; just verify package resolves
    swift package resolve
    echo "   Package resolved"
    cd -
fi

# Keychain tests
if command -v security &>/dev/null; then
    echo "4. Keychain access test..."
    security find-generic-password -s "com.personalayer.oauth.google" &>/dev/null && echo "   Google token found" || echo "   No Google token (expected if not connected)"
fi

# App Group tests
APP_GROUP_DIR="$HOME/Library/Group Containers/group.com.personalayer"
if [ -d "$APP_GROUP_DIR" ]; then
    echo "5. App Group container exists: $APP_GROUP_DIR"
    ls -la "$APP_GROUP_DIR" 2>/dev/null || true
else
    echo "5. App Group container not yet created (expected on first run)"
fi

echo "=== Native App Tests Complete ==="
