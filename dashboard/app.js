const API_BASE = window.location.origin;

const state = {
  view: "overview",
  userId: "local_user",
  loading: false,
  data: {
    health: null,
    summary: null,
    profile: null,
    bundle: null,
    activity: null,
    featureSignals: [],
    integrations: [],
    consents: [],
    webPermissions: [],
    queryLogs: [],
    privacyDrops: [],
    refreshJobs: [],
    brief: null,
    apps: [],
    skills: [],
    memoryFiles: [],
    memoryDiffs: [],
    memorySources: [],
  },
};

const copy = {
  overview: ["Production Control Center", "Overview"],
  vault: ["Local Raw Vault", "Raw Vault"],
  egress: ["Boundary Simulator", "Egress Preview"],
  memory: ["Persona Memory", "Memory"],
  permissions: ["Access Control", "Permissions"],
  connectors: ["Data Sources", "Connectors"],
  audit: ["Traceability", "Audit"],
  developer: ["Integration Console", "Developer"],
};

const $ = (selector) => document.querySelector(selector);
const view = $("#view");
const notice = $("#notice");

function html(strings, ...values) {
  return strings.reduce((result, string, index) => {
    return result + string + escapeHtml(values[index] ?? "");
  }, "");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function rawJson(value) {
  return escapeHtml(JSON.stringify(value ?? {}, null, 2));
}

function formatDate(value) {
  if (!value) return "-";
  if (typeof value === "number") return new Date(value).toLocaleString();
  return value;
}

function setNotice(message, type = "") {
  notice.textContent = message || "";
  notice.className = message ? `notice show ${type}` : "notice";
}

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || response.statusText);
  return data;
}

async function loadAll() {
  state.loading = true;
  setNotice("Loading local context state...");
  const userId = encodeURIComponent(state.userId);
  const bundlePayload = {
    user_id: state.userId,
    app_id: "dashboard",
    intent: "full_profile",
    requested_scopes: ["dashboard"],
  };

  const [
    health,
    summary,
    profile,
    bundle,
    activity,
    featureSignals,
    integrations,
    consents,
    webPermissions,
    queryLogs,
    privacyDrops,
    refreshJobs,
    brief,
    apps,
    skills,
    memoryFiles,
    memoryDiffs,
    memorySources,
  ] = await Promise.all([
    api("/health").catch((error) => ({ error: error.message })),
    api("/activity/summary?days=30").catch((error) => ({ error: error.message })),
    api(`/pcl/profile?user_id=${userId}`).catch((error) => ({ error: error.message })),
    api("/v1/context/bundle", { method: "POST", body: JSON.stringify(bundlePayload) }).catch((error) => ({ error: error.message })),
    api(`/v1/context/activity?user_id=${userId}&limit=50`).catch((error) => ({ error: error.message, raw_events: [] })),
    api(`/v1/context/feature-signals?user_id=${userId}&active_only=false`).catch((error) => ({ error: error.message, features: [] })),
    api("/pcl/integrations").catch((error) => ({ error: error.message, integrations: [] })),
    api(`/v1/auth/consent?user_id=${userId}`).catch((error) => ({ error: error.message, permissions: [] })),
    api(`/v1/web/permissions?user_id=${userId}`).catch((error) => ({ error: error.message, permissions: [] })),
    api("/pcl/query-log?limit=100").catch((error) => ({ error: error.message, logs: [] })),
    api(`/v1/context/privacy-drops?user_id=${userId}&limit=50`).catch((error) => ({ error: error.message, drops: [] })),
    api(`/v1/jobs/daily-refresh?user_id=${userId}&limit=20`).catch((error) => ({ error: error.message, jobs: [] })),
    api(`/v1/context/brief?user_id=${userId}`).catch((error) => ({ error: error.message })),
    api("/pcl/apps?limit=100").catch((error) => ({ error: error.message, apps: [] })),
    api("/pcl/skills?active_only=false&limit=100").catch((error) => ({ error: error.message, skills: [] })),
    api(`/v1/memory/files?user_id=${userId}`).catch((error) => ({ error: error.message, files: [] })),
    api(`/v1/memory/diffs?user_id=${userId}&limit=100`).catch((error) => ({ error: error.message, diffs: [] })),
    api(`/v1/memory/sources?user_id=${userId}`).catch((error) => ({ error: error.message, sources: [] })),
  ]);

  state.data = {
    health,
    summary,
    profile,
    bundle,
    activity,
    featureSignals: featureSignals.features || [],
    integrations: integrations.integrations || [],
    consents: consents.permissions || [],
    webPermissions: webPermissions.permissions || [],
    queryLogs: queryLogs.logs || [],
    privacyDrops: privacyDrops.drops || [],
    refreshJobs: refreshJobs.jobs || [],
    brief,
    apps: apps.apps || [],
    skills: skills.skills || [],
    memoryFiles: memoryFiles.files || [],
    memoryDiffs: memoryDiffs.diffs || [],
    memorySources: memorySources.sources || [],
  };
  state.loading = false;
  updateDaemonStatus();
  setNotice("");
  render();
}

function updateDaemonStatus() {
  const dot = $("#daemon-dot");
  const label = $("#daemon-label");
  const ok = state.data.health && !state.data.health.error;
  dot.className = `status-dot ${ok ? "ok" : "error"}`;
  label.textContent = ok ? "Local daemon online" : "Daemon unavailable";
}

function render() {
  const [eyebrow, title] = copy[state.view] || copy.overview;
  $("#view-eyebrow").textContent = eyebrow;
  $("#view-title").textContent = title;
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === state.view);
  });

  if (state.view === "overview") renderOverview();
  if (state.view === "vault") renderVault();
  if (state.view === "egress") renderEgress();
  if (state.view === "memory") renderMemory();
  if (state.view === "permissions") renderPermissions();
  if (state.view === "connectors") renderConnectors();
  if (state.view === "audit") renderAudit();
  if (state.view === "developer") renderDeveloper();
}

function metric(label, value, hint = "") {
  return html`
    <article class="card metric">
      <span>${label}</span>
      <strong>${value}</strong>
      <small>${hint}</small>
    </article>
  `;
}

function renderOverview() {
  const { activity, bundle, featureSignals, integrations, consents, queryLogs, privacyDrops, refreshJobs } = state.data;
  const rawEvents = activity?.raw_events?.length || 0;
  const connected = integrations.filter((item) => item.status === "connected").length;
  const activeConsents = consents.filter((item) => item.is_active).length;
  const stale = bundle?.stale ? "Stale" : "Fresh";

  view.innerHTML = `
    <section class="grid-4">
      ${metric("Raw vault events", rawEvents, "Local-only payloads")}
      ${metric("Feature signals", featureSignals.length, "Derived memory")}
      ${metric("Connected sources", connected, "First-party connectors")}
      ${metric("Active grants", activeConsents, "App consent records")}
    </section>

    <section class="card">
      <div class="card-header">
        <div>
          <h2>Production Data Flow</h2>
          <p class="muted">Sensitive source data stays inside the local vault. Egress filtering applies only when context leaves PersonaLayer.</p>
        </div>
        <span class="pill ${bundle?.privacy?.filter_applied === "egress" ? "ok" : "warn"}">${bundle?.privacy?.filter_applied || "unknown"} filter</span>
      </div>
      <div class="flow">
        <div class="flow-step"><strong>1. Connect</strong><p>Google, Spotify, Health, Notion, browser, SDK, and app events.</p></div>
        <div class="flow-step"><strong>2. Vault</strong><p>Raw source payloads are stored locally for full persona formation.</p></div>
        <div class="flow-step"><strong>3. Synthesize</strong><p>Signals become memory tiers, graph nodes, active context, and profile traits.</p></div>
        <div class="flow-step"><strong>4. Filter</strong><p>Bundles are redacted, scoped, and denied at the egress boundary.</p></div>
        <div class="flow-step"><strong>5. Audit</strong><p>Every query, permission grant, and filter drop is visible.</p></div>
      </div>
    </section>

    <section class="grid-3">
      <article class="card">
        <h3>Context Bundle</h3>
        <p class="muted">Current bundle for dashboard access.</p>
        <div class="pill-row">
          <span class="pill ${stale === "Fresh" ? "ok" : "warn"}">${stale}</span>
          <span class="pill private">raw payload excluded</span>
          <span class="pill private">apps cannot store copy</span>
        </div>
      </article>
      <article class="card">
        <h3>Refresh Pipeline</h3>
        <p class="muted">${refreshJobs[0] ? `Last job: ${refreshJobs[0].status}` : "No refresh jobs yet."}</p>
        <div class="pill-row">
          <span class="pill">3 AM synthesis</span>
          <span class="pill">memory decay</span>
          <span class="pill">shared bundle</span>
        </div>
      </article>
      <article class="card">
        <h3>Privacy Exceptions</h3>
        <p class="muted">${privacyDrops.length ? `${privacyDrops.length} blocked ingest events` : "No blocked secrets detected."}</p>
        <div class="pill-row">
          <span class="pill blocked">tokens blocked</span>
          <span class="pill blocked">cards blocked</span>
          <span class="pill ok">PII allowed locally</span>
        </div>
      </article>
    </section>

    ${tableCard("Recent Context Queries", ["App", "Purpose", "Status", "Returned"], queryLogs.slice(0, 6).map((log) => [
      log.app_id,
      log.purpose || "-",
      log.status,
      (log.returned_layers || []).join(", ") || "-",
    ]))}
  `;
}

function renderVault() {
  const events = state.data.activity?.raw_events || [];
  view.innerHTML = `
    <section class="grid-2">
      <article class="card">
        <div class="card-header">
          <div>
            <h2>Local Raw Data Vault</h2>
            <p class="muted">This view is local-only. These payloads are for persona synthesis and are never included in outbound context bundles.</p>
          </div>
          <span class="pill private">inside system</span>
        </div>
        <div class="pill-row">
          <span class="pill ok">PII can be retained locally</span>
          <span class="pill blocked">credentials blocked</span>
          <span class="pill private">egress excludes raw payload</span>
        </div>
      </article>
      <article class="card">
        <h2>Vault Policy</h2>
        <p class="muted">Use full local content to build a richer persona. Filter only when data leaves via MCP, SDK, app APIs, extension bridge, cloud, or agent context injection.</p>
      </article>
    </section>
    <section class="event-list">
      ${events.length ? events.map(renderEvent).join("") : empty("No raw events found for this user.")}
    </section>
  `;
}

function renderEvent(event) {
  const raw = event.raw_payload || {};
  const hasSensitiveShape = JSON.stringify(raw).match(/email|content|note|body|message|health|calendar/i);
  return html`
    <article class="event-card">
      <header>
        <div>
          <strong>${event.app_id}:${event.feature_id}</strong>
          <span class="muted">${event.action} via ${event.source} at ${formatDate(event.timestamp)}</span>
        </div>
        <span class="pill ${hasSensitiveShape ? "private" : "ok"}">${hasSensitiveShape ? "sensitive local" : "behavioral"}</span>
      </header>
      <code>${JSON.stringify(raw, null, 2)}</code>
    </article>
  `;
}

function renderEgress() {
  const bundle = state.data.bundle || {};
  view.innerHTML = `
    <section class="split">
      <article class="card">
        <h2>Simulate an Agent Request</h2>
        <p class="muted">Generate the exact kind of scoped bundle an app or MCP agent would receive after egress filtering.</p>
        <form class="form-grid" id="egress-form">
          <label class="field">
            <span>App ID</span>
            <input name="app_id" value="dashboard" autocomplete="off">
          </label>
          <label class="field">
            <span>Intent</span>
            <select name="intent">
              <option value="full_profile">Full profile</option>
              <option value="adapt_ui">Adapt UI</option>
              <option value="suggest_features">Suggest features</option>
              <option value="constraints">Constraints only</option>
            </select>
          </label>
          <label class="field">
            <span>Requested scopes, comma separated</span>
            <input name="scopes" value="dashboard">
          </label>
          <button class="button primary" type="submit">Generate Egress Bundle</button>
        </form>
      </article>
      <article class="card">
        <div class="card-header">
          <div>
            <h2>Outbound Privacy Result</h2>
            <p class="muted">Raw events and raw payloads should remain absent here.</p>
          </div>
          <span class="pill ok">egress filtered</span>
        </div>
        <pre class="json-block" id="egress-output">${rawJson(bundle)}</pre>
      </article>
    </section>
  `;
  $("#egress-form").addEventListener("submit", generateEgressBundle);
}

async function generateEgressBundle(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const payload = {
    user_id: state.userId,
    app_id: form.get("app_id") || "dashboard",
    intent: form.get("intent") || "full_profile",
    requested_scopes: String(form.get("scopes") || "").split(",").map((item) => item.trim()).filter(Boolean),
  };
  const result = await api("/v1/context/bundle", { method: "POST", body: JSON.stringify(payload) });
  $("#egress-output").textContent = JSON.stringify(result, null, 2);
  setNotice("Generated filtered outbound bundle.");
}

function renderMemory() {
  const signals = state.data.featureSignals;
  const brief = state.data.brief || {};
  view.innerHTML = `
    <section class="grid-2">
      <article class="card">
        <h2>Context Brief</h2>
        <p class="muted">${brief.context_brief || "No synthesized context brief yet."}</p>
        <div class="pill-row">
          <span class="pill">last synthesized ${formatDate(brief.last_synthesized_at)}</span>
          <span class="pill">timezone ${brief.timezone || "UTC"}</span>
        </div>
      </article>
      <article class="card">
        <h2>Daily Insight</h2>
        <p class="muted">${brief.daily_insight || "Run daily refresh after collecting signals."}</p>
      </article>
    </section>
    ${tableCard("Feature Signals", ["App", "Feature", "Tier", "Usage", "Recency", "Synthetic"], signals.map((signal) => [
      signal.app_id,
      signal.feature_id,
      signal.tier,
      signal.usage_count,
      signal.recency_score,
      signal.is_synthetic ? "yes" : "no",
    ]))}
  `;
}

function renderPermissions() {
  const appPermissions = state.data.consents;
  const webPermissions = state.data.webPermissions;
  view.innerHTML = `
    <section class="split">
      <article class="card">
        <h2>Grant App Consent</h2>
        <form class="form-grid" id="grant-form">
          <label class="field"><span>App ID</span><input name="app_id" placeholder="research_copilot"></label>
          <label class="field"><span>Scopes</span><input name="scopes" value="getContextBundle,getFeatureUsage"></label>
          <button class="button primary" type="submit">Grant Consent</button>
        </form>
      </article>
      <article class="card">
        <h2>Grant Web Domain</h2>
        <form class="form-grid" id="web-grant-form">
          <label class="field"><span>Domain</span><input name="domain" placeholder="example.com"></label>
          <label class="field"><span>Scopes</span><input name="scopes" value="getFeatureUsage,track"></label>
          <button class="button primary" type="submit">Grant Domain</button>
        </form>
      </article>
    </section>
    <section class="grid-2">
      <article class="card permission-card">
        <h2>App Grants</h2>
        ${appPermissions.length ? appPermissions.map((item) => permissionRow(item.app_id, item.scopes, item.is_active, "app")).join("") : empty("No app consent grants.")}
      </article>
      <article class="card permission-card">
        <h2>Web Grants</h2>
        ${webPermissions.length ? webPermissions.map((item) => permissionRow(item.domain, item.scopes, item.is_active, "domain")).join("") : empty("No domain permissions.")}
      </article>
    </section>
  `;
  $("#grant-form").addEventListener("submit", grantConsent);
  $("#web-grant-form").addEventListener("submit", grantWebDomain);
}

function permissionRow(target, scopes, active, type) {
  return html`
    <div class="permission-row">
      <div>
        <strong>${target}</strong>
        <div class="pill-row">${(scopes || []).map((scope) => `<span class="pill">${escapeHtml(scope)}</span>`).join("")}</div>
      </div>
      <span class="pill ${active ? "ok" : "blocked"}">${active ? "active" : "revoked"} ${type}</span>
    </div>
  `;
}

async function grantConsent(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  await api("/v1/auth/consent", {
    method: "POST",
    body: JSON.stringify({
      user_id: state.userId,
      app_id: form.get("app_id"),
      scopes: String(form.get("scopes") || "").split(",").map((item) => item.trim()).filter(Boolean),
      granted_via: "dashboard",
    }),
  });
  setNotice("App consent granted.");
  await loadAll();
}

async function grantWebDomain(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  await api("/v1/web/permissions", {
    method: "POST",
    body: JSON.stringify({
      user_id: state.userId,
      domain: form.get("domain"),
      scopes: String(form.get("scopes") || "").split(",").map((item) => item.trim()).filter(Boolean),
    }),
  });
  setNotice("Web domain permission granted.");
  await loadAll();
}

function renderConnectors() {
  const integrations = state.data.integrations;
  view.innerHTML = `
    <section class="grid-3">
      ${integrations.map((item) => html`
        <article class="card">
          <div class="card-header">
            <div>
              <h2>${item.name || item.source}</h2>
              <p class="muted">${item.description || "Connector source"}</p>
            </div>
            <span class="pill ${item.status === "connected" ? "ok" : "warn"}">${item.status || "available"}</span>
          </div>
          <div class="pill-row">
            <span class="pill">${item.auth_status || "not_connected"}</span>
            <span class="pill">${item.items_synced || 0} synced</span>
          </div>
          <div class="topbar-actions" style="justify-content:start;margin-top:14px">
            <button class="button primary" data-connect="${item.source}" type="button">${item.status === "connected" ? "Sync" : "Connect"}</button>
            <button class="button danger" data-delete-source="${item.source}" type="button">Delete Data</button>
          </div>
        </article>
      `).join("") || empty("No connector catalog returned.")}
    </section>
  `;
  document.querySelectorAll("[data-connect]").forEach((button) => {
    button.addEventListener("click", () => connectOrSync(button.dataset.connect));
  });
  document.querySelectorAll("[data-delete-source]").forEach((button) => {
    button.addEventListener("click", () => deleteIntegrationData(button.dataset.deleteSource));
  });
}

async function connectOrSync(source) {
  const integration = state.data.integrations.find((item) => item.source === source);
  if (integration?.status === "connected") {
    await api(`/pcl/integrations/${encodeURIComponent(source)}/sync`, { method: "POST" });
    setNotice(`${source} sync completed.`);
  } else {
    await api(`/pcl/integrations/${encodeURIComponent(source)}/connect`, {
      method: "POST",
      body: JSON.stringify({
        account_hint: "",
        auth_status: "local_metadata",
        metadata: integration?.metadata_example || {},
      }),
    });
    setNotice(`${source} connected with local metadata.`);
  }
  await loadAll();
}

async function deleteIntegrationData(source) {
  if (!window.confirm(`Delete local ${source} integration data?`)) return;
  await api(`/pcl/integrations/${encodeURIComponent(source)}/data`, { method: "DELETE" });
  setNotice(`${source} data deleted.`);
  await loadAll();
}

function renderAudit() {
  const logs = state.data.queryLogs;
  const drops = state.data.privacyDrops;
  view.innerHTML = `
    <section class="grid-2">
      ${tableCard("Context Query Log", ["App", "User", "Purpose", "Status", "Created"], logs.map((log) => [
        log.app_id,
        log.user_id,
        log.purpose || "-",
        log.status,
        log.created_at,
      ]))}
      ${tableCard("Blocked Ingest Secrets", ["App", "Feature", "Reason", "Source", "Created"], drops.map((drop) => [
        drop.app_id || "-",
        drop.feature_id || "-",
        drop.reason,
        drop.source || "-",
        drop.created_at,
      ]))}
    </section>
  `;
}

function renderDeveloper() {
  const apps = state.data.apps;
  const skills = state.data.skills;
  const memoryFiles = state.data.memoryFiles;
  const memoryDiffs = state.data.memoryDiffs;
  const memorySources = state.data.memorySources;
  const personalizationModules = [
    {
      name: "Markdown Memory",
      source: "pi-mem pattern",
      status: "Core",
      detail: "Stores profile, preferences, people, projects, daily logs, and scratchpads as user-readable local files.",
    },
    {
      name: "Reflection Loop",
      source: "pi-reflect pattern",
      status: "Core",
      detail: "Reviews corrections and session outcomes, then proposes persona updates for approval.",
    },
    {
      name: "Skill Registry",
      source: "skills pattern",
      status: "Core",
      detail: "Defines task-specific abilities such as email summaries, calendar planning, code review, research, and writing style.",
    },
    {
      name: "Semantic Search",
      source: "safe-skill-search pattern",
      status: "Core",
      detail: "Retrieves relevant memories, notes, conversations, and skills before an app receives context.",
    },
    {
      name: "Messaging Bridge",
      source: "wa_meow pattern",
      status: "Later",
      detail: "Delivers briefings, reminders, chat summaries, and reply drafts through channels like WhatsApp or Telegram.",
    },
    {
      name: "Nightly Profile Update",
      source: "daily refresh",
      status: "Core",
      detail: "Summarizes what changed, active projects, unresolved tasks, people mentioned, and assistant mistakes.",
    },
    {
      name: "Approved Ingestion",
      source: "connectors",
      status: "Core",
      detail: "Imports Gmail, Calendar, notes, browser, GitHub, files, and resumes only through explicit remember or forget flows.",
    },
    {
      name: "Persona Diff",
      source: "audit UI",
      status: "Core",
      detail: "Shows new inferred preferences as approve, edit, or delete changes before they become trusted context.",
    },
    {
      name: "Behavior Files",
      source: "editable persona",
      status: "Core",
      detail: "Keeps voice, priorities, boundaries, decision style, work style, and disliked behaviors visible to the user.",
    },
  ];

  view.innerHTML = `
    <section class="split">
      <article class="card">
        <h2>Register PCL App</h2>
        <form class="form-grid" id="app-form">
          <label class="field"><span>App ID</span><input name="app_id" placeholder="research_copilot"></label>
          <label class="field"><span>Name</span><input name="name" placeholder="Research Copilot"></label>
          <label class="field"><span>Allowed layers</span><input name="layers" value="identity_role,capability_signals,active_context,explicit_preferences"></label>
          <button class="button primary" type="submit">Register App</button>
        </form>
      </article>
      <article class="card">
        <h2>SDK Contract</h2>
        <pre class="json-block">${rawJson({
          ingest: "POST /v1/ingest/sdk",
          query: "POST /v1/context/bundle",
          consent: "POST /v1/auth/consent",
          rule: "Raw payloads remain local. Agents receive egress-filtered bundles only.",
          personalization: {
            memory: "Markdown files plus indexed feature signals",
            reflection: "Session review proposes persona diffs",
            skills: "Registry-selected capabilities run with scoped context",
            audit: "Every inferred update and outbound bundle is reviewable",
          },
        })}</pre>
      </article>
    </section>
    <section class="card">
      <div class="card-header">
        <div>
          <h2>Personalization Modules</h2>
          <p class="muted">Product ideas adapted from open agent infrastructure into user-owned PersonaLayer features.</p>
        </div>
        <span class="pill ok">memory + reflection first</span>
      </div>
      <div class="module-grid">
        ${personalizationModules.map((item) => `
          <article class="module-card">
            <div class="module-card-head">
              <strong>${escapeHtml(item.name)}</strong>
              <span class="pill ${item.status === "Later" ? "warn" : "private"}">${escapeHtml(item.status)}</span>
            </div>
            <p>${escapeHtml(item.detail)}</p>
            <small>${escapeHtml(item.source)}</small>
          </article>
        `).join("")}
      </div>
    </section>
    <section class="card">
      <div class="card-header">
        <div>
          <h2>Local Persona File Layout</h2>
          <p class="muted">The control center should expose these files as editable user-owned context, not hidden prompts.</p>
        </div>
      </div>
      <pre class="json-block">persona/
  memory/
    profile.md
    preferences.md
    people.md
    projects.md
    daily-log.md
    scratchpad.md
  behavior/
    voice.md
    priorities.md
    boundaries.md
    decision-style.md
    work-style.md
    disliked-behaviors.md
  skills/
    email-summary/
    calendar-planning/
    code-review/
    research/
    habit-tracking/
    travel-planning/
    personal-writing-style/
  audits/
    persona-diffs.md
    outbound-context-log.md</pre>
    </section>
    ${tableCard("Registered PCL Skills", ["Skill", "Category", "Memory", "Status"], skills.map((skill) => [
      skill.skill_id,
      skill.category,
      (skill.memory_scopes || []).join(", ") || "-",
      skill.status,
    ]))}
    ${tableCard("Markdown Memory Files", ["Scope", "Bytes", "Updated"], memoryFiles.map((file) => [
      file.scope,
      file.bytes,
      file.updated_at,
    ]))}
    ${tableCard("Persona Memory Diffs", ["Scope", "Source", "Status", "Reason"], memoryDiffs.map((diff) => [
      diff.scope,
      diff.source,
      diff.status,
      diff.reason || "-",
    ]))}
    ${tableCard("Memory Source Toggles", ["Source", "Enabled", "Reason"], memorySources.map((source) => [
      source.source,
      source.enabled ? "enabled" : "disabled",
      source.reason || "-",
    ]))}
    ${tableCard("Registered PCL Apps", ["App", "Name", "Layers", "Status"], apps.map((app) => [
      app.id || app.app_id,
      app.name,
      (app.allowed_layers || []).join(", "),
      app.status,
    ]))}
  `;
  $("#app-form").addEventListener("submit", registerApp);
}

async function registerApp(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  await api("/pcl/apps", {
    method: "POST",
    body: JSON.stringify({
      app_id: form.get("app_id"),
      name: form.get("name"),
      allowed_layers: String(form.get("layers") || "").split(",").map((item) => item.trim()).filter(Boolean),
    }),
  });
  setNotice("App registered.");
  await loadAll();
}

function tableCard(title, headings, rows) {
  if (!rows.length) {
    return html`
      <article class="table-card">
        <div class="table-head"><h2>${title}</h2></div>
        ${empty("No rows yet.")}
      </article>
    `;
  }
  return `
    <article class="table-card">
      <div class="table-head"><h2>${escapeHtml(title)}</h2></div>
      <table class="table">
        <thead><tr>${headings.map((heading) => `<th>${escapeHtml(heading)}</th>`).join("")}</tr></thead>
        <tbody>
          ${rows.map((row) => `<tr>${row.map((cell) => `<td>${escapeHtml(cell ?? "-")}</td>`).join("")}</tr>`).join("")}
        </tbody>
      </table>
    </article>
  `;
}

function empty(message) {
  return html`
    <div class="empty-state">
      <strong>No data yet</strong>
      <p>${message}</p>
    </div>
  `;
}

async function runDailyRefresh() {
  setNotice("Running daily refresh...");
  await api("/v1/jobs/daily-refresh", {
    method: "POST",
    body: JSON.stringify({ user_id: state.userId, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC" }),
  });
  setNotice("Daily refresh completed.");
  await loadAll();
}

document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", () => {
    state.view = button.dataset.view;
    render();
  });
});

$("#refresh-button").addEventListener("click", loadAll);
$("#daily-refresh-button").addEventListener("click", runDailyRefresh);
$("#user-id").addEventListener("change", async (event) => {
  state.userId = event.target.value.trim() || "local_user";
  await loadAll();
});

loadAll().catch((error) => {
  updateDaemonStatus();
  setNotice(error.message || "Unable to load dashboard.", "error");
  render();
});
