import assert from "node:assert/strict";
import test from "node:test";

import {PersonalContextLayer, getBundle, isAvailable, track} from "./personal-context-layer.js";

function mockFetch(calls) {
  return async (url, options) => {
    calls.push({
      url,
      options,
      body: options.body ? JSON.parse(options.body) : undefined,
    });
    return {
      ok: true,
      status: 200,
      json: async () => ({status: "ok"}),
    };
  };
}

test("registerApp posts app scopes", async () => {
  const calls = [];
  const pcl = new PersonalContextLayer({appId: "mail_app", fetchImpl: mockFetch(calls)});

  await pcl.registerApp({
    name: "Mail App",
    allowedLayers: ["identity_role", "active_context"],
  });

  assert.equal(calls[0].url, "http://127.0.0.1:7823/pcl/apps");
  assert.deepEqual(calls[0].body, {
    app_id: "mail_app",
    name: "Mail App",
    allowed_layers: ["identity_role", "active_context"],
  });
});

test("trackFeature posts behavioral feature event", async () => {
  const calls = [];
  const pcl = new PersonalContextLayer({appId: "mail_app", fetchImpl: mockFetch(calls)});

  await pcl.trackFeature({
    userId: "user_1",
    featureId: "smart_reply",
    featureName: "Smart Reply",
    timestamp: 123,
  });

  assert.equal(calls[0].url, "http://127.0.0.1:7823/pcl/events/feature");
  assert.deepEqual(calls[0].body, {
    app_id: "mail_app",
    user_id: "user_1",
    feature_id: "smart_reply",
    feature_name: "Smart Reply",
    event_type: "used",
    weight: 1,
    timestamp: 123,
  });
});

test("personalize posts runtime feature list", async () => {
  const calls = [];
  const pcl = new PersonalContextLayer({appId: "mail_app", fetchImpl: mockFetch(calls)});

  await pcl.personalize({
    userId: "user_1",
    requestedLayers: ["capability_signals"],
    features: [{feature_id: "smart_reply", name: "Smart Reply"}],
  });

  assert.equal(calls[0].url, "http://127.0.0.1:7823/pcl/query");
  assert.deepEqual(calls[0].body, {
    app_id: "mail_app",
    user_id: "user_1",
    purpose: "ui_personalization",
    requested_layers: ["capability_signals"],
    features: [{feature_id: "smart_reply", name: "Smart Reply"}],
  });
});

test("track posts strict ContextLayer event", async () => {
  const calls = [];
  const pcl = new PersonalContextLayer({appId: "mail_app", fetchImpl: mockFetch(calls)});

  await pcl.track({
    userId: "user_1",
    featureId: "Smart Reply",
    action: "used",
    sessionId: "s1",
    timestamp: 123,
    metadata: {hour_of_day: 9, day_of_week: 1, subject_category: "email"},
  });

  assert.equal(calls[0].url, "http://127.0.0.1:7823/v1/ingest/sdk");
  assert.deepEqual(calls[0].body, {
    app_id: "mail_app",
    user_id: "user_1",
    feature_id: "smart-reply",
    action: "used",
    session_id: "s1",
    timestamp: 123,
    is_synthetic: false,
    metadata: {hour_of_day: 9, day_of_week: 1, subject_category: "email"},
  });
});

test("generateColdStart posts role and feature priors", async () => {
  const calls = [];
  const pcl = new PersonalContextLayer({appId: "figma", fetchImpl: mockFetch(calls)});

  await pcl.generateColdStart({
    userId: "user_1",
    appName: "Figma",
    features: ["Auto layout"],
    role: "designer",
    domain: "product design",
  });

  assert.equal(calls[0].url, "http://127.0.0.1:7823/v1/context/cold-start");
  assert.deepEqual(calls[0].body, {
    app_id: "figma",
    app_name: "Figma",
    user_id: "user_1",
    features: ["Auto layout"],
    role: "designer",
    domain: "product design",
    skill_level: "intermediate",
  });
});

test("getContextBundle posts intent-bounded request", async () => {
  const calls = [];
  const pcl = new PersonalContextLayer({
    appId: "mail_app",
    apiKey: "cl_test_key",
    userToken: "user:user_1",
    fetchImpl: mockFetch(calls),
  });

  await pcl.getContextBundle({
    userId: "user_1",
    intent: "adapt_ui",
    requestedScopes: ["getFeatureUsage"],
  });

  assert.equal(calls[0].url, "http://127.0.0.1:7823/v1/context/bundle");
  assert.deepEqual(calls[0].options.headers, {
    "Content-Type": "application/json",
    Authorization: "Bearer cl_test_key",
    "x-user-token": "user:user_1",
  });
  assert.deepEqual(calls[0].body, {
    app_id: "mail_app",
    user_id: "user_1",
    intent: "adapt_ui",
    requested_scopes: ["getFeatureUsage"],
  });
});

test("getSharedBundle reads local shared bundle route", async () => {
  const calls = [];
  const pcl = new PersonalContextLayer({appId: "mail_app", fetchImpl: mockFetch(calls)});

  await pcl.getSharedBundle({userId: "user_1"});

  assert.equal(calls[0].url, "http://127.0.0.1:7823/v1/context/shared-bundle?user_id=user_1");
  assert.equal(calls[0].options.method, "GET");
});

test("web domain helpers use local permission routes", async () => {
  const calls = [];
  const pcl = new PersonalContextLayer({appId: "mail_app", fetchImpl: mockFetch(calls)});

  await pcl.grantWebDomain({userId: "user_1", domain: "mail.example.com"});
  await pcl.checkWebDomain({userId: "user_1", domain: "mail.example.com", requestedScopes: ["getFeatureUsage"]});
  await pcl.revokeWebDomain({userId: "user_1", domain: "mail.example.com"});

  assert.equal(calls[0].url, "http://127.0.0.1:7823/v1/web/permissions");
  assert.deepEqual(calls[0].body, {
    user_id: "user_1",
    domain: "mail.example.com",
    scopes: ["getFeatureUsage", "track"],
  });
  assert.equal(calls[1].url, "http://127.0.0.1:7823/v1/web/permissions/check");
  assert.deepEqual(calls[1].body, {
    user_id: "user_1",
    domain: "mail.example.com",
    requested_scopes: ["getFeatureUsage"],
  });
  assert.equal(calls[2].url, "http://127.0.0.1:7823/v1/web/permissions/mail.example.com?user_id=user_1");
  assert.equal(calls[2].options.method, "DELETE");
});

test("integration OAuth token helpers use masked local routes", async () => {
  const calls = [];
  const pcl = new PersonalContextLayer({appId: "mail_app", fetchImpl: mockFetch(calls)});

  await pcl.listIntegrationOAuthTokens({userId: "user_1"});
  await pcl.revokeIntegrationOAuthToken({userId: "user_1", source: "gmail"});

  assert.equal(calls[0].url, "http://127.0.0.1:7823/pcl/integrations/oauth/tokens?user_id=user_1");
  assert.equal(calls[0].options.method, "GET");
  assert.equal(calls[1].url, "http://127.0.0.1:7823/pcl/integrations/gmail/oauth/token?user_id=user_1");
  assert.equal(calls[1].options.method, "DELETE");
});

test("device push helpers use local routing routes", async () => {
  const calls = [];
  const pcl = new PersonalContextLayer({appId: "mail_app", fetchImpl: mockFetch(calls)});

  await pcl.registerPushToken({
    userId: "user_1",
    deviceId: "iphone_1",
    apnsToken: "apns_token_123",
    environment: "production",
  });
  await pcl.listPushTokens({userId: "user_1", activeOnly: false});
  await pcl.listNotificationRoutes({userId: "user_1", limit: 25});
  await pcl.revokePushToken({userId: "user_1", deviceId: "iphone_1"});

  assert.equal(calls[0].url, "http://127.0.0.1:7823/v1/devices/push-token");
  assert.deepEqual(calls[0].body, {
    user_id: "user_1",
    device_id: "iphone_1",
    apns_token: "apns_token_123",
    platform: "ios",
    environment: "production",
  });
  assert.equal(calls[1].url, "http://127.0.0.1:7823/v1/devices/push-token?user_id=user_1&active_only=false");
  assert.equal(calls[1].options.method, "GET");
  assert.equal(calls[2].url, "http://127.0.0.1:7823/v1/notifications/routes?user_id=user_1&limit=25");
  assert.equal(calls[2].options.method, "GET");
  assert.equal(calls[3].url, "http://127.0.0.1:7823/v1/devices/push-token/iphone_1?user_id=user_1");
  assert.equal(calls[3].options.method, "DELETE");
});

test("heartbeat posts active context", async () => {
  const calls = [];
  const pcl = new PersonalContextLayer({appId: "mail_app", fetchImpl: mockFetch(calls)});

  await pcl.heartbeat({
    userId: "user_1",
    project: "ContextLayer",
    inferredIntent: "adapt_ui",
    sessionDepth: "deep-work",
  });

  assert.equal(calls[0].url, "http://127.0.0.1:7823/v1/context/heartbeat");
  assert.deepEqual(calls[0].body, {
    user_id: "user_1",
    project: "ContextLayer",
    active_apps: ["mail_app"],
    inferred_intent: "adapt_ui",
    session_depth: "deep-work",
  });
});

test("feedback posts bandit outcome", async () => {
  const calls = [];
  const pcl = new PersonalContextLayer({appId: "mail_app", fetchImpl: mockFetch(calls)});

  await pcl.feedback({
    userId: "user_1",
    bundleId: "bundle_1",
    outcome: "accepted",
    featuresActuallyUsed: ["Smart Reply"],
  });

  assert.equal(calls[0].url, "http://127.0.0.1:7823/v1/context/feedback");
  assert.deepEqual(calls[0].body, {
    app_id: "mail_app",
    user_id: "user_1",
    bundle_id: "bundle_1",
    outcome: "accepted",
    features_actually_used: ["smart-reply"],
  });
});

test("revokeApp posts revocation request", async () => {
  const calls = [];
  const pcl = new PersonalContextLayer({appId: "mail_app", fetchImpl: mockFetch(calls)});

  await pcl.revokeApp();

  assert.equal(calls[0].url, "http://127.0.0.1:7823/pcl/apps/mail_app/revoke");
  assert.equal(calls[0].options.method, "POST");
});

test("deleteAppData sends app delete request", async () => {
  const calls = [];
  const pcl = new PersonalContextLayer({appId: "mail_app", fetchImpl: mockFetch(calls)});

  await pcl.deleteAppData();

  assert.equal(calls[0].url, "http://127.0.0.1:7823/pcl/apps/mail_app/data");
  assert.equal(calls[0].options.method, "DELETE");
});

test("clearQueryLog scopes by app and optional user", async () => {
  const calls = [];
  const pcl = new PersonalContextLayer({appId: "mail_app", fetchImpl: mockFetch(calls)});

  await pcl.clearQueryLog({userId: "user_1"});

  assert.equal(calls[0].url, "http://127.0.0.1:7823/pcl/query-log?app_id=mail_app&user_id=user_1");
  assert.equal(calls[0].options.method, "DELETE");
});

test("deleteUserData sends user delete request", async () => {
  const calls = [];
  const pcl = new PersonalContextLayer({appId: "mail_app", fetchImpl: mockFetch(calls)});

  await pcl.deleteUserData({userId: "user 1"});

  assert.equal(calls[0].url, "http://127.0.0.1:7823/pcl/users/user%201/data");
  assert.equal(calls[0].options.method, "DELETE");
});

test("activity and deleteAllContext use v1 routes", async () => {
  const calls = [];
  const pcl = new PersonalContextLayer({appId: "mail_app", fetchImpl: mockFetch(calls)});

  await pcl.activity({userId: "user_1", limit: 10});
  await pcl.deleteAllContext({userId: "user_1"});

  assert.equal(calls[0].url, "http://127.0.0.1:7823/v1/context/activity?user_id=user_1&limit=10");
  assert.equal(calls[0].options.method, "GET");
  assert.equal(calls[1].url, "http://127.0.0.1:7823/v1/context/all?user_id=user_1");
  assert.equal(calls[1].options.method, "DELETE");
});

test("deleteUserData requires userId", () => {
  const pcl = new PersonalContextLayer({appId: "mail_app", fetchImpl: mockFetch([])});

  assert.throws(() => pcl.deleteUserData({}), /userId is required/);
});

test("constructor requires appId", () => {
  assert.throws(() => new PersonalContextLayer({fetchImpl: mockFetch([])}), /appId is required/);
});

test("web bridge availability checks extension marker", () => {
  const documentRef = {documentElement: {getAttribute: (name) => name === "data-cl-ext" ? "1" : null}};
  const missingDocument = {documentElement: {getAttribute: () => null}};

  assert.equal(isAvailable({documentRef}), true);
  assert.equal(isAvailable({documentRef: missingDocument}), false);
});

test("getBundle returns null when extension bridge is unavailable", async () => {
  const result = await getBundle({
    documentRef: {documentElement: {getAttribute: () => null}},
    windowRef: {},
  });

  assert.equal(result, null);
});

test("getBundle can explicitly use localhost fallback", async () => {
  const calls = [];
  const fetchImpl = async (url, options) => {
    calls.push({url, options, body: JSON.parse(options.body)});
    return {
      ok: true,
      json: async () => ({features: ["smart-reply"]}),
    };
  };

  const result = await getBundle({
    appId: "mail.example",
    userId: "user_1",
    intent: "adapt_ui",
    requestedScopes: ["getFeatureUsage"],
    allowLocalhostFallback: true,
    localhostBaseUrl: "http://127.0.0.1:7432/",
    fetchImpl,
    documentRef: {documentElement: {getAttribute: () => null}},
    windowRef: {},
  });

  assert.equal(calls[0].url, "http://127.0.0.1:7432/v1/context/bundle");
  assert.deepEqual(calls[0].body, {
    app_id: "mail.example",
    user_id: "user_1",
    intent: "adapt_ui",
    requested_scopes: ["getFeatureUsage"],
  });
  assert.deepEqual(result, {features: ["smart-reply"]});
});

test("getBundle posts CL_GET_BUNDLE and resolves bridge response", async () => {
  const listeners = new Map();
  const posted = [];
  const windowRef = {
    addEventListener: (type, handler) => listeners.set(type, handler),
    removeEventListener: (type) => listeners.delete(type),
    postMessage: (message) => {
      posted.push(message);
      queueMicrotask(() => {
        listeners.get("message")?.({
          source: windowRef,
          data: {
            type: "CL_BUNDLE_RESPONSE",
            requestId: message.requestId,
            bundle: {features: ["smart-reply"]},
          },
        });
      });
    },
  };
  const documentRef = {documentElement: {getAttribute: () => "1"}};

  const bundle = await getBundle({appId: "mail.example", windowRef, documentRef});

  assert.equal(posted[0].type, "CL_GET_BUNDLE");
  assert.equal(posted[0].appId, "mail.example");
  assert.deepEqual(bundle, {features: ["smart-reply"]});
});

test("track can explicitly use localhost fallback", async () => {
  const calls = [];
  const fetchImpl = async (url, options) => {
    calls.push({url, options, body: JSON.parse(options.body)});
    return {
      ok: true,
      json: async () => ({status: "accepted"}),
    };
  };

  const result = await track({
    appId: "mail.example",
    userId: "user_1",
    featureId: "Smart Reply",
    action: "used",
    sessionId: "session_1",
    timestamp: 1700000000000,
    metadata: {subject_category: "email"},
    allowLocalhostFallback: true,
    localhostBaseUrl: "http://127.0.0.1:7432",
    fetchImpl,
    documentRef: {documentElement: {getAttribute: () => null}},
    windowRef: {},
  });

  assert.equal(calls[0].url, "http://127.0.0.1:7432/v1/ingest/extension");
  assert.deepEqual(calls[0].body, {
    app_id: "mail.example",
    user_id: "user_1",
    feature_id: "smart-reply",
    action: "used",
    session_id: "session_1",
    timestamp: 1700000000000,
    metadata: {subject_category: "email"},
  });
  assert.deepEqual(result, {status: "accepted"});
});

test("track posts CL_TRACK and resolves result", async () => {
  const listeners = new Map();
  const posted = [];
  const windowRef = {
    addEventListener: (type, handler) => listeners.set(type, handler),
    removeEventListener: (type) => listeners.delete(type),
    postMessage: (message) => {
      posted.push(message);
      queueMicrotask(() => {
        listeners.get("message")?.({
          source: windowRef,
          data: {
            type: "CL_TRACK_RESPONSE",
            requestId: message.requestId,
            result: {status: "ok"},
          },
        });
      });
    },
  };
  const documentRef = {documentElement: {getAttribute: () => "1"}};

  const result = await track({
    appId: "mail.example",
    featureId: "Smart Reply",
    action: "used",
    windowRef,
    documentRef,
  });

  assert.equal(posted[0].type, "CL_TRACK");
  assert.equal(posted[0].featureId, "smart-reply");
  assert.deepEqual(result, {status: "ok"});
});
