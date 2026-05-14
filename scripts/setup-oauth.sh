#!/usr/bin/env bash
set -euo pipefail

# Interactive OAuth credential setup for iOS/macOS apps.
# Reads credentials from environment or prompts interactively.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

INFO_PLIST="$PROJECT_ROOT/native/ios/PersonalLayer/Resources/Info.plist"

if [ ! -f "$INFO_PLIST" ]; then
    echo "ERROR: Info.plist not found at $INFO_PLIST"
    exit 1
fi

echo "=== Personal Layer OAuth Setup ==="
echo ""
echo "This script configures OAuth client IDs in Info.plist."
echo "You can set them via environment variables or enter them interactively."
echo ""

# Google
GOOGLE_CLIENT_ID="${GOOGLE_CLIENT_ID:-}"
if [ -z "$GOOGLE_CLIENT_ID" ]; then
    read -p "Google Client ID (format: XXX.apps.googleusercontent.com): " GOOGLE_CLIENT_ID
fi

# Spotify
SPOTIFY_CLIENT_ID="${SPOTIFY_CLIENT_ID:-}"
if [ -z "$SPOTIFY_CLIENT_ID" ]; then
    read -p "Spotify Client ID: " SPOTIFY_CLIENT_ID
fi

# Notion
NOTION_CLIENT_ID="${NOTION_CLIENT_ID:-}"
if [ -z "$NOTION_CLIENT_ID" ]; then
    read -p "Notion Client ID: " NOTION_CLIENT_ID
fi

# Update Info.plist
if command -v /usr/libexec/PlistBuddy &>/dev/null; then
    /usr/libexec/PlistBuddy -c "Set :OAuthProviders:google $GOOGLE_CLIENT_ID" "$INFO_PLIST"
    /usr/libexec/PlistBuddy -c "Set :OAuthProviders:spotify $SPOTIFY_CLIENT_ID" "$INFO_PLIST"
    /usr/libexec/PlistBuddy -c "Set :OAuthProviders:notion $NOTION_CLIENT_ID" "$INFO_PLIST"
    echo "Updated Info.plist with OAuth credentials."
else
    echo "WARNING: PlistBuddy not found. Please manually update $INFO_PLIST:"
    echo "  OAuthProviders -> google: $GOOGLE_CLIENT_ID"
    echo "  OAuthProviders -> spotify: $SPOTIFY_CLIENT_ID"
    echo "  OAuthProviders -> notion: $NOTION_CLIENT_ID"
fi

echo ""
echo "Next steps:"
echo "1. Configure redirect URIs in each provider's developer console:"
echo "   Google: com.personalayer.ios:/oauth2redirect"
echo "   Spotify: personalayer://spotify-callback"
echo "   Notion: https://localhost/oauth/callback"
echo "2. Build and run the iOS app."
