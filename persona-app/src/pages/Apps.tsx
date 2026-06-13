// /app/apps — connect the sources that feed your persona (with real OAuth where
// the server supports it), manage connections, and review apps that can request
// your context.

import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  CheckCircle2,
  ExternalLink,
  Plug,
  RefreshCw,
  ShieldCheck,
  Trash2,
  TriangleAlert,
} from "lucide-react";
import { ErrorState, LoadingState, OfflineBanner, PageHeader } from "../components/states";
import { Button, Chip, ConfirmButton, Pill } from "../components/ui";
import { useResource } from "../lib/useResource";
import { useBackend } from "../lib/backend";
import { relativeTime, titleize } from "../lib/format";
import { previewIntegrations } from "../lib/preview";
import {
  type PclIntegration,
  connectIntegration,
  deleteIntegrationData,
  disconnectIntegration,
  getApps,
  getIntegrationCatalog,
  getIntegrations,
  startOAuth,
  completeOAuthCallback,
  syncIntegration,
} from "../api";

// The connectors we surface, in order. Source ids match the backend catalog.
const FEATURED = ["gmail", "calendar", "google_drive", "notion", "spotify", "youtube", "github"] as const;

const SCOPE_NOTE = "Metadata only — no message or file content is stored.";
const USERNAME_SOURCES = new Set(["github"]);

function isConnected(i: PclIntegration) {
  return Boolean(i.connected) || i.status === "connected" || i.status === "registered";
}

const OAUTH_PENDING_KEY = "pl_oauth_pending";

function ConnectorCard({
  i,
  live,
  onChanged,
  onToast,
}: {
  i: PclIntegration;
  live: boolean;
  onChanged: () => void;
  onToast: (msg: string, kind: "good" | "danger") => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [username, setUsername] = useState("");
  const [showUsername, setShowUsername] = useState(false);
  const [configNote, setConfigNote] = useState("");
  const source = i.source || (i.name || "").toLowerCase();
  const connected = isConnected(i);
  const isOAuth = Boolean(i.oauth) || i.auth_type === "oauth_or_local_metadata";
  const needsUsername = USERNAME_SOURCES.has(source);

  const run = async (key: string, fn: () => Promise<unknown>, okMsg?: string) => {
    setBusy(key);
    try {
      await fn();
      if (okMsg) onToast(okMsg, "good");
      onChanged();
    } catch (err) {
      onToast(err instanceof Error ? err.message : "That didn’t work — try again.", "danger");
    } finally {
      setBusy(null);
    }
  };

  const startConnect = async () => {
    setConfigNote("");
    if (needsUsername) {
      setShowUsername(true);
      return;
    }
    if (isOAuth) {
      setBusy("conn");
      try {
        const redirectUri = `${window.location.origin}/app/apps`;
        const res = await startOAuth(source, redirectUri);
        if (res.status === "ok" && res.auth_url && res.state) {
          sessionStorage.setItem(OAUTH_PENDING_KEY, JSON.stringify({ state: res.state, source }));
          window.location.assign(res.auth_url);
          return;
        }
        if (res.status === "configuration_required") {
          setConfigNote(
            `Connecting ${i.name || titleize(source)} needs OAuth set up on the server (${res.client_id_env || "client id"}). You can add metadata manually instead.`,
          );
        } else {
          setConfigNote(res.error ? titleize(res.error) : "Couldn’t start the connection.");
        }
      } catch (err) {
        onToast(err instanceof Error ? err.message : "Couldn’t start the connection.", "danger");
      } finally {
        setBusy(null);
      }
      return;
    }
    // Local-metadata connector.
    run("conn", () => connectIntegration(source), `${i.name || titleize(source)} connected.`);
  };

  return (
    <li className="flex flex-col gap-3 rounded-2xl border border-outline-variant bg-white p-4 shadow-ambient">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-primary/10 text-sm font-bold uppercase text-primary">
            {(i.name || source).slice(0, 1)}
          </span>
          <div className="min-w-0">
            <div className="truncate font-semibold">{i.name || titleize(source)}</div>
            <div className="truncate text-xs text-on-surface-variant">
              {connected
                ? `Synced ${relativeTime(i.last_sync_at) }${i.items_synced ? ` · ${i.items_synced} items` : ""}`
                : i.description || "Feeds signals into your persona."}
            </div>
          </div>
        </div>
        <Pill tone={connected ? "good" : "neutral"}>
          {connected ? <><CheckCircle2 size={12} /> Connected</> : "Available"}
        </Pill>
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        <Chip>{SCOPE_NOTE}</Chip>
        {(i.scopes || []).slice(0, 3).map((s) => (
          <Chip key={s}>{titleize(s)}</Chip>
        ))}
      </div>

      {i.error && connected && (
        <p className="flex items-center gap-1.5 text-xs font-semibold text-warn">
          <TriangleAlert size={13} /> {i.error}
        </p>
      )}

      {showUsername && !connected && (
        <div className="flex items-center gap-2">
          <input
            className="w-full rounded-lg border border-outline-variant px-3 py-2 text-sm outline-none focus:border-primary"
            placeholder={`${titleize(source)} username`}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && username.trim() && run("conn", () => connectIntegration(source, { username: username.trim() }), `${titleize(source)} connected.`)}
          />
          <Button variant="primary" loading={busy === "conn"} disabled={!username.trim() || !live} onClick={() => run("conn", () => connectIntegration(source, { username: username.trim() }), `${titleize(source)} connected.`)}>
            Connect
          </Button>
        </div>
      )}

      {configNote && (
        <div className="flex flex-col gap-2 rounded-lg border border-warn/30 bg-warn/10 p-3 text-xs text-warn">
          <span>{configNote}</span>
          <div>
            <Button variant="default" loading={busy === "meta"} disabled={!live} onClick={() => run("meta", () => connectIntegration(source), `${i.name || titleize(source)} connected (local metadata).`)}>
              Connect with metadata
            </Button>
          </div>
        </div>
      )}

      <div className="flex flex-wrap justify-end gap-2 border-t border-outline-variant pt-3">
        {connected ? (
          <>
            <Button variant="ghost" loading={busy === "sync"} disabled={!live} onClick={() => run("sync", () => syncIntegration(source), `Synced ${i.name || titleize(source)}.`)}>
              <RefreshCw size={14} /> Sync now
            </Button>
            <ConfirmButton confirmLabel="Disconnect" disabled={!live} onConfirm={() => run("disc", () => disconnectIntegration(source), `Disconnected ${i.name || titleize(source)}.`)}>
              Disconnect
            </ConfirmButton>
            <ConfirmButton confirmLabel="Delete metadata" disabled={!live} onConfirm={() => run("del", () => deleteIntegrationData(source), "Imported metadata deleted.")}>
              <Trash2 size={14} /> Delete data
            </ConfirmButton>
          </>
        ) : showUsername ? null : (
          <Button variant="primary" loading={busy === "conn"} disabled={!live} onClick={startConnect}>
            <Plug size={14} /> Connect
          </Button>
        )}
      </div>
    </li>
  );
}

export default function Apps() {
  const { online } = useBackend();
  const integrationsRes = useResource(async () => (await getIntegrations()).integrations || [], previewIntegrations);
  const catalogRes = useResource(async () => (await getIntegrationCatalog()).integrations || [], previewIntegrations);
  const appsRes = useResource(async () => (await getApps()).apps || [], []);
  const [toast, setToast] = useState<{ msg: string; kind: "good" | "danger" } | null>(null);

  const reload = () => {
    integrationsRes.reload();
    appsRes.reload();
  };
  const showToast = (msg: string, kind: "good" | "danger") => {
    setToast({ msg, kind });
    window.setTimeout(() => setToast(null), 4000);
  };

  // Complete an OAuth round-trip when the provider redirects back with ?code&state.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    const state = params.get("state");
    if (!code || !state) return;
    let pendingSource = "";
    try {
      const pending = JSON.parse(sessionStorage.getItem(OAUTH_PENDING_KEY) || "{}");
      if (pending.state === state) pendingSource = pending.source;
    } catch {
      /* ignore */
    }
    sessionStorage.removeItem(OAUTH_PENDING_KEY);
    window.history.replaceState({}, "", "/app/apps");
    completeOAuthCallback({ state, code })
      .then((res) => {
        if (res.status === "connected") showToast(`${titleize(pendingSource || res.source || "App")} connected.`, "good");
        else showToast(res.error ? titleize(res.error) : "We couldn’t finish connecting.", "danger");
        reload();
      })
      .catch((err) => showToast(err instanceof Error ? err.message : "We couldn’t finish connecting.", "danger"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Merge catalog (descriptions, scopes, oauth) with live connection status.
  const connectors = useMemo(() => {
    const bySource = new Map<string, PclIntegration>();
    for (const c of catalogRes.data) if (c.source) bySource.set(c.source, { ...c });
    for (const i of integrationsRes.data) if (i.source) bySource.set(i.source, { ...bySource.get(i.source), ...i });
    return FEATURED.map((s) => bySource.get(s) || { source: s, name: titleize(s) });
  }, [catalogRes.data, integrationsRes.data]);

  const connected = connectors.filter(isConnected);
  const available = connectors.filter((i) => !isConnected(i));
  const apps = appsRes.data;
  const offline = integrationsRes.isPreview || catalogRes.isPreview;

  return (
    <>
      <PageHeader
        title="Connected apps"
        subtitle="Connect the sources that feed your persona. PersonaLayer reads metadata only — never your messages or files."
        action={
          <Button variant="default" onClick={reload}>
            <RefreshCw size={15} /> Refresh
          </Button>
        }
      />

      {offline && <OfflineBanner onRetry={reload} />}

      {toast && (
        <div className={`mb-4 rounded-lg border px-3 py-2 text-sm font-semibold ${toast.kind === "good" ? "border-ok/20 bg-ok/5 text-ok" : "border-danger/20 bg-danger/5 text-danger"}`}>
          {toast.msg}
        </div>
      )}

      {integrationsRes.loading && integrationsRes.data.length === 0 && !offline ? (
        <LoadingState label="Loading connectors…" />
      ) : integrationsRes.error ? (
        <ErrorState message={integrationsRes.error} onRetry={reload} />
      ) : (
        <div className="flex flex-col gap-8">
          <section>
            <h2 className="mb-3 text-xs font-bold uppercase tracking-wider text-on-surface-variant">
              Connected ({connected.length})
            </h2>
            {connected.length === 0 ? (
              <p className="text-sm text-on-surface-variant">Nothing connected yet. Connect a source below to start building your persona.</p>
            ) : (
              <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {connected.map((i) => (
                  <ConnectorCard key={i.source} i={i} live={online} onChanged={reload} onToast={showToast} />
                ))}
              </ul>
            )}
          </section>

          <section>
            <h2 className="mb-3 text-xs font-bold uppercase tracking-wider text-on-surface-variant">Available</h2>
            <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {available.map((i) => (
                <ConnectorCard key={i.source} i={i} live={online} onChanged={reload} onToast={showToast} />
              ))}
            </ul>
          </section>

          <section>
            <h2 className="mb-3 text-xs font-bold uppercase tracking-wider text-on-surface-variant">Apps that can request your context</h2>
            {apps.length === 0 ? (
              <p className="text-sm text-on-surface-variant">No apps have requested access yet. When one does, you’ll approve exactly what it can see.</p>
            ) : (
              <ul className="grid gap-3 sm:grid-cols-2">
                {apps.map((app) => (
                  <li key={app.app_id} className="flex flex-col gap-2 rounded-2xl border border-outline-variant bg-white p-4 shadow-ambient">
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2 font-semibold">
                        <ShieldCheck size={16} className="text-primary" /> {app.name || app.app_id}
                      </div>
                      <Pill tone={app.status === "revoked" ? "warn" : "good"}>{titleize(app.status || "active")}</Pill>
                    </div>
                    {app.allowed_layers && app.allowed_layers.length > 0 && (
                      <div className="flex flex-wrap gap-1.5">
                        {app.allowed_layers.map((l) => (
                          <Chip key={l}>{titleize(l)}</Chip>
                        ))}
                      </div>
                    )}
                    <Link to={`/app/consent/${encodeURIComponent(app.app_id || "")}`} className="inline-flex items-center gap-1.5 text-sm font-semibold text-primary hover:underline">
                      Review access <ExternalLink size={13} />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </>
  );
}
