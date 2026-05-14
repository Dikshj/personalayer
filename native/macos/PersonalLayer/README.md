# Personal Layer — macOS Daemon

Swift Package Manager project for the macOS menu-bar daemon.

## Stack
- **SwiftUI** `MenuBarExtra`
- **GRDB** for SQLite
- **Network.framework** `NWListener` on `127.0.0.1:7432`
- **CryptoKit** AES-256-GCM
- **Security.framework** Keychain
- **Core ML** all-MiniLM-L6-v2 embeddings
- **BackgroundTasks** BGTaskScheduler

## Endpoints
| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/context/bundle` | Return shared context bundle |
| POST | `/v1/ingest/extension` | Ingest event from browser extension |

## Build
```bash
cd native/macos/PersonalLayer
swift build
```

## Run
```bash
swift run PersonalLayer
```

The app launches as a menu-bar extra (LSUIElement). Look for the brain icon in the system tray.

## Project Structure
```
Sources/PersonalLayer/
  App/           — SwiftUI lifecycle, menu bar view, BGTaskScheduler refresh
  Server/        — NWListener, HTTP parsing, routing, bundle/ingest endpoints
  Storage/       — GRDB database, migrations, models, raw event CRUD
  CoreML/        — all-MiniLM-L6-v2 embedding model wrapper + fallback
  Crypto/        — AES-256-GCM helpers, bundle file encryption
  Keychain/      — Generic password storage
  OAuth/         — Typed OAuth token save/load/revoke via Keychain
  Approval/      — Per-domain CORS approval store
  AppGroup/      — Shared container read/write
  LaunchAgent/   — Run-on-login helper
  NativeMessaging/ — Chrome/Edge/Safari stdio host loop
```

## Features Implemented
1. ✅ Core ML `all-MiniLM-L6-v2` embeddings pipeline (with NLTagger fallback)
2. ✅ BGTaskScheduler 3 AM daily refresh (11-step pipeline)
3. ✅ Native Messaging stdio loop for Chrome/Edge (`CL_GET_BUNDLE`, `CL_TRACK`, `CL_IS_AVAILABLE`)
4. ✅ LaunchAgent plist + run-on-login toggle in menu bar
5. ✅ OAuth token Keychain storage with masked inspection and revoke
6. ✅ AES-256 bundle file encryption for `bundle_{userId}.json`
7. ✅ App Group shared container (`group.com.personalayer`)

## Next Steps
1. Convert the real `all-MiniLM-L6-v2` model via `coremltools` and drop it into `Resources/Models/`.
2. Implement real connector sync for Gmail, Calendar, Spotify, etc.
3. Add Hummingbird or Vapor if HTTP needs become complex.
4. Sign / notarize for distribution.
