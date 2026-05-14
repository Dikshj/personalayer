# Personal Layer JavaScript SDK

## Installation

```bash
npm install @personalayer/sdk
```

## Build

```bash
cd sdk/javascript
npm install     # installs typescript
npm run build   # compiles src/index.ts -> dist/index.js + dist/index.d.ts
```

## Usage

```typescript
import { PersonalLayerSDK } from '@personalayer/sdk';

const sdk = new PersonalLayerSDK();

// Check if Personal Layer is available (extension or localhost daemon)
const available = await sdk.isAvailable();

// Get context bundle
const bundle = await sdk.getBundle();

// Track an event
await sdk.track({ event_type: 'page_view', url: window.location.href });
```

## Architecture

The SDK tries the browser extension first (via `chrome.runtime.sendMessage`),
then falls back to localhost:7432 only if `fallbackEnabled: true` is set.

```typescript
const sdk = new PersonalLayerSDK({ fallbackEnabled: true });
```
