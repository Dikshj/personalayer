# Production Checklist

## Immediate (Required Before Release)

### 1. Core ML Model Asset
- [ ] Run `python scripts/convert-coreml-model.py` on macOS with:
  ```bash
  pip install torch transformers sentence-transformers coremltools
  python scripts/convert-coreml-model.py
  ```
- [ ] Verify output: `native/*/PersonalLayer/Resources/all-MiniLM-L6-v2.mlpackage`
- [ ] Verify vocab: `native/*/PersonalLayer/Resources/vocab.json`
- [ ] Add `.mlpackage` to Xcode target membership (both macOS and iOS)

### 2. OAuth Credentials
- [ ] Replace placeholders in `native/ios/PersonalLayer/Resources/Info.plist`:
  - `YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com`
  - `YOUR_SPOTIFY_CLIENT_ID`
  - `YOUR_NOTION_CLIENT_ID`
- [ ] Add client secrets to Info.plist `OAuthSecrets` dict (if required by provider)
- [ ] Configure redirect URIs in each provider's developer console
- [ ] Test OAuth flow on real device: Google → token exchange → Keychain storage

### 3. APNs Configuration
- [ ] Generate APNs auth key at https://developer.apple.com/account/resources/authkeys/list
- [ ] Download `.p8` key file
- [ ] Set Supabase secrets:
  ```bash
  supabase secrets set APNS_KEY_ID=YOUR_KEY_ID
  supabase secrets set APNS_TEAM_ID=YOUR_TEAM_ID
  supabase secrets set APNS_BUNDLE_ID=com.personalayer.ios
  supabase secrets set APNS_PRIVATE_KEY="$(cat AuthKey_XXX.p8)"
  supabase secrets set APNS_ENV=production
  ```
- [ ] Deploy edge functions: `supabase functions deploy apns-router`
- [ ] Test with a real device token

### 4. Supabase Deployment
- [ ] Run migrations: `supabase db push`
- [ ] Verify `verify_api_key` RPC works
- [ ] Deploy edge functions:
  ```bash
  supabase functions deploy verify-api-key
  supabase functions deploy apns-router
  supabase functions deploy observability
  ```
- [ ] Run integration tests: `pytest tests/integration/ -v`

### 5. Swift Build Verification
- [ ] macOS daemon: `cd native/macos/PersonalLayer && swift build`
- [ ] macOS tests: `swift test`
- [ ] iOS app: `cd native/ios/PersonalLayer && swift package resolve`
- [ ] Swift SDK: `cd sdk/swift && swift build`

### 6. Extension Testing
- [ ] Build Chrome extension: `bash scripts/package-chrome.sh`
- [ ] Load unpacked in Chrome: `chrome://extensions` → Developer Mode → Load unpacked → `build/chrome/`
- [ ] Install native messaging host: `bash scripts/install-native-messaging-host.sh`
- [ ] Test CL_GET_BUNDLE and CL_TRACK
- [ ] Test domain approval/denial flow

### 7. App Store / TestFlight
- [ ] Update version in `native/ios/PersonalLayer/Resources/Info.plist`
- [ ] Set `DEVELOPER_TEAM_ID` and `BUNDLE_ID` in environment
- [ ] Run: `bash scripts/package-ios.sh`
- [ ] Upload to App Store Connect via `altool`

### 8. macOS Notarization
- [ ] Set `DEVELOPER_ID` and `KEYCHAIN_PROFILE` in environment
- [ ] Run: `bash scripts/sign-macos.sh`
- [ ] Verify stapled ticket: `spctl -a -vv MyApp.app`

## Validation Commands

```bash
# Python tests
pytest tests/ -q -n 4

# JS SDK
npm run build && npm test

# Extension package
bash scripts/package-chrome.sh && unzip -l build/personalayer-chrome.zip

# Swift (macOS)
cd native/macos/PersonalLayer && swift build && swift test

# Supabase integration
pytest tests/integration/ -v

# End-to-end extension
cd scripts && bash test-extension-bridge.sh
```
