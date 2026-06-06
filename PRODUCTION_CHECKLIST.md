# Production Checklist

## Immediate Coding Work

### 0. Legal, Privacy, And Security Docs
- [x] Privacy Policy: `docs/PRIVACY_POLICY.md`
- [x] Terms of Service: `docs/TERMS_OF_SERVICE.md`
- [x] Data retention schedule: `docs/DATA_RETENTION.md`
- [x] Security policy and vulnerability contact: `docs/SECURITY.md`
- [x] In-app Legal surface exposes privacy, terms, retention, and security contact.
- [ ] Counsel review before broad commercial launch or regulated use.
- [ ] Replace placeholder contact domains if production email routing uses a different domain.

### 1. Core ML Model Asset
- [ ] Run `python scripts/convert-coreml-model.py` with:
  ```bash
  pip install torch transformers sentence-transformers coremltools
  python scripts/convert-coreml-model.py
  ```
- [ ] Verify output: `native/ios/PersonalLayer/Resources/all-MiniLM-L6-v2.mlpackage`
- [ ] Verify vocab: `native/ios/PersonalLayer/Resources/vocab.json`
- [ ] Add `.mlpackage` to the iOS target membership before release builds.

### 2. OAuth Credentials
- [x] Info.plist uses build-time variables: `$(GOOGLE_OAUTH_CLIENT_ID)`, `$(SPOTIFY_OAUTH_CLIENT_ID)`, `$(NOTION_OAUTH_CLIENT_ID)`
- [ ] Keep provider-specific token exchange code wired to encrypted local token storage.
- [ ] Test OAuth callback handling with mocked provider responses.

### 3. APNs Configuration
- [x] Edge function `apns-router` is implemented and ready for deploy.
- [ ] Keep notification routes free of behavioral text.
- [ ] Add tests for token registration, revoke, and route creation.

### 4. Supabase Thin Cloud
- [x] Migrations defined in `supabase/migrations/`
- [x] Edge functions implemented: `verify-api-key`, `apns-router`, `observability`
- [ ] Add integration tests around RLS and API-key verification.

### 5. iOS Build Verification
- [ ] iOS package resolve/build checks.
- [x] GRDB schema parity with Python backend.
- [x] App Group shared database path implemented.

### 6. Extension Testing
- [x] Build script: `bash scripts/build-extensions.sh`
- [ ] Load unpacked in Chrome: `chrome://extensions` -> Developer Mode -> Load unpacked -> `build/extensions/`
- [ ] Test `CL_GET_BUNDLE` and `CL_TRACK` against the Python local runtime on `127.0.0.1:7823`.
- [x] Domain approval checks persisted database.
- [ ] Test domain approval/denial flow end-to-end.

### 7. App Store / TestFlight
- [ ] Update version in `native/ios/PersonalLayer/Resources/Info.plist`.
- [x] Build script: `bash scripts/build-ios.sh`

## Validation Commands

```bash
# Python tests
pytest tests/ -q -n 4

# JS SDK
npm run build && npm test

# Extension package
bash scripts/package-chrome.sh && unzip -l build/personalayer-chrome.zip

# Supabase integration
pytest tests/integration/ -v

# End-to-end extension against Python runtime
bash scripts/test-extension-bridge.sh
```
