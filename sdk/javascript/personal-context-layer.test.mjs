import assert from "node:assert/strict";
import test from "node:test";

import {PersonalContextLayer} from "./personal-context-layer.js";

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
