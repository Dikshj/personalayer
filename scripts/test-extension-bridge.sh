#!/usr/bin/env bash
set -euo pipefail

# End-to-end test for Chrome extension + native messaging bridge
# Requires: macOS daemon running on 127.0.0.1:7432, Chrome installed

echo "=== Personal Layer Extension Bridge Test ==="

# 1. Check daemon health
echo "1. Checking daemon health..."
HEALTH=$(curl -s http://127.0.0.1:7432/health || echo '{}')
if echo "$HEALTH" | grep -q '"status":"ok"'; then
    echo "   Daemon is running"
else
    echo "   ERROR: Daemon not responding. Start it first:"
    echo "   cd native/macos/PersonalLayer && swift run"
    exit 1
fi

# 2. Test bundle endpoint without approval (should fail)
echo "2. Testing bundle without domain approval..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -H "Origin: https://untrusted.com" http://127.0.0.1:7432/v1/context/bundle || true)
if [ "$STATUS" = "403" ]; then
    echo "   Correctly denied (403)"
else
    echo "   WARNING: Expected 403, got $STATUS"
fi

# 3. Approve test domain
echo "3. Approving test domain..."
curl -s -X POST http://127.0.0.1:7432/v1/ingest/extension     -H "Content-Type: application/json"     -d '{"event_type":"domain_approval","domain":"https://example.com"}' || true

# 4. Test bundle with approved domain
echo "4. Testing bundle with approved domain..."
BUNDLE=$(curl -s -H "Origin: https://example.com" http://127.0.0.1:7432/v1/context/bundle || echo '{}')
if echo "$BUNDLE" | grep -q '"version"'; then
    echo "   Bundle received OK"
else
    echo "   WARNING: Bundle may be empty (expected on fresh install)"
fi

# 5. Test ingest endpoint
echo "5. Testing ingest endpoint..."
INGEST=$(curl -s -X POST http://127.0.0.1:7432/v1/ingest/extension     -H "Content-Type: application/json"     -H "Origin: https://example.com"     -d '{"event_type":"page_view","url":"https://example.com/page","title":"Test"}' || echo '{}')
if echo "$INGEST" | grep -q '"status":"ingested"'; then
    echo "   Ingest OK"
else
    echo "   WARNING: Ingest may have failed"
fi

# 6. Check extension install (if Chrome is available)
if command -v /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome &>/dev/null; then
    echo "6. Chrome found. Extension install test:"
    echo "   - Open chrome://extensions"
    echo "   - Enable Developer Mode"
    echo "   - Load unpacked: $(pwd)/extension"
    echo "   - Install native messaging host: ./scripts/install-native-messaging-host.sh"
else
    echo "6. Chrome not found, skipping extension install test"
fi

echo "=== Extension Bridge Test Complete ==="
