# ContextLayer JavaScript SDK

Minimal dependency-free SDK for web pages using the ContextLayer browser extension bridge, plus the older local prototype client for tests and local tooling.

## Web Extension Bridge

Websites do not call cloud APIs and do not read localhost directly. The SDK checks for the extension marker injected by the content script. If the extension is missing, `getBundle()` and `track()` return `null` and the site should render its default UI.

```js
import {getBundle, isAvailable, track} from "./personal-context-layer.js";

if (isAvailable()) {
  const bundle = await getBundle({
    appId: window.location.hostname,
    intent: "adapt_ui",
  });

  if (bundle) {
    // Personalize UI from bundle.features.
  }

  await track({
    appId: window.location.hostname,
    featureId: "smart_reply",
    action: "used",
    metadata: {hour_of_day: 9, day_of_week: 1, subject_category: "email"},
  });
}
```

Bridge contract:

- Extension content script injects `data-cl-ext="1"` on `<html>`.
- `getBundle()` sends `CL_GET_BUNDLE` with `window.postMessage`.
- `track()` sends `CL_TRACK`.
- The extension checks local permission and forwards to the local desktop app/runtime.
- No cloud fallback and no localStorage bundle copy.

For macOS app shells or trusted local tooling, the same exports can explicitly opt into the local daemon path. This is not enabled by default for websites.

```js
const bundle = await getBundle({
  appId: "desktop_app",
  allowLocalhostFallback: true,
  localhostBaseUrl: "http://127.0.0.1:7432",
});
```

## Local Prototype Client

The `PersonalContextLayer` class still targets the local Python prototype HTTP API and is useful for local demos, tests, and non-browser tooling.

```js
import {PersonalContextLayer} from "./personal-context-layer.js";

const pcl = new PersonalContextLayer({
  appId: "mail_app",
  apiKey: "cl_test_...",       // optional for local mode, required for developer auth
  userToken: "user:user_1",    // local prototype user token shape
});

await pcl.registerApp({
  name: "Mail App",
  allowedLayers: ["identity_role", "capability_signals", "active_context"],
});

await pcl.trackFeature({
  userId: "user_1",
  featureId: "smart_reply",
  featureName: "Smart Reply",
});

await pcl.track({
  userId: "user_1",
  featureId: "smart_reply",
  action: "used",
  sessionId: "session_1",
  metadata: {hour_of_day: 9, day_of_week: 1, subject_category: "email"},
});

await pcl.generateColdStart({
  userId: "user_1",
  appName: "Mail App",
  features: ["smart_reply", "newsletter_filter"],
  role: "founder",
  domain: "developer tools",
});

await pcl.heartbeat({
  userId: "user_1",
  project: "Inbox cleanup",
  inferredIntent: "adapt_ui",
  sessionDepth: "moderate",
});

const bundle = await pcl.personalize({
  userId: "user_1",
  features: [
    {feature_id: "smart_reply", name: "Smart Reply"},
    {feature_id: "newsletter_filter", name: "Newsletter Filter"},
  ],
});

const context = await pcl.getContextBundle({userId: "user_1", intent: "adapt_ui"});
await pcl.feedback({
  userId: "user_1",
  bundleId: context.bundle_id,
  outcome: "accepted",
  featuresActuallyUsed: ["smart_reply"],
});

await pcl.activity({userId: "user_1"});
await pcl.listIntegrationOAuthTokens({userId: "user_1"});
await pcl.registerPushToken({
  userId: "user_1",
  deviceId: "iphone_1",
  apnsToken: "apns_token_from_ios_app",
  environment: "development",
});
await pcl.listPushTokens({userId: "user_1"});
await pcl.listNotificationRoutes({userId: "user_1"});
await pcl.clearQueryLog({userId: "user_1"});
await pcl.revokeApp();
await pcl.deleteAppData();
await pcl.deleteUserData({userId: "user_1"});
await pcl.deleteAllContext({userId: "user_1"});
```

`trackFeature` and `personalize` keep compatibility with the older local prototype routes. New integrations should prefer `track`, `generateColdStart`, `heartbeat`, `getContextBundle`, and `feedback`, which use the `/v1` ContextLayer API. `track` accepts only whitelisted metadata: `hour_of_day`, `day_of_week`, and `subject_category`.

The local prototype also exposes `listIntegrationOAuthTokens` and `revokeIntegrationOAuthToken` for masked provider-token inspection. Token list responses never include raw OAuth tokens.

The prototype exposes `registerPushToken`, `listPushTokens`, `revokePushToken`, and `listNotificationRoutes` for testing the APNs routing boundary. Routes carry only delivery metadata and `payload_kind`; the daily insight text stays local.

Apps should call `getContextBundle` at runtime and avoid storing returned bundles. The daemon logs each query for the user's activity trail.

When `apiKey` is set, the SDK sends `Authorization: Bearer {apiKey}`. When `userToken` is set, it sends `x-user-token`. Authenticated bundle requests require an active user consent record for the app and all requested scopes.

Use `revokeApp` when the user disconnects an app. Use `deleteAppData` or `deleteUserData` when the user asks for stored records to be removed instead of only stopping future access.

See `examples/feature-ranking-demo.html` for a browser demo that ranks and dims UI features from a PCL decision bundle.
