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

// Check if Personal Layer is available (extension or local runtime)
const available = await sdk.isAvailable();

// Get context bundle
const bundle = await sdk.getBundle();

// Track an event
await sdk.track({ event_type: 'page_view', url: window.location.href });
```

## Architecture

The SDK tries the browser extension first, then falls back to the local Python
runtime on `localhost:7823` only if `fallbackEnabled: true` is set.

```typescript
const sdk = new PersonalLayerSDK({ fallbackEnabled: true });
```
