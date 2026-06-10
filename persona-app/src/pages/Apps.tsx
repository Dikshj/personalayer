// /app/apps — connected apps and integrations: status, scopes, last sync,
// and connect / disconnect / sync controls.

import { useState } from "react";
import { Plug, RefreshCw } from "lucide-react";
import { ErrorState, LoadingState, OfflineBanner, PageHeader } from "../components/states";
import { Button, ConfirmButton, Chip, Pill } from "../components/ui";
import { useResource } from "../lib/useResource";
import { useBackend } from "../lib/backend";
import { titleize } from "../lib/format";
import { previewIntegrations } from "../lib/preview";
import {
  type PclIntegration,
  connectIntegration,
  disconnectIntegration,
  getApps,
  getIntegrations,
  syncIntegration,
} from "../api";

function isConnected(i: PclIntegration) {
  return Boolean(i.connected) || i.status === "connected" || i.status === "registered";
}

function IntegrationCard({ i, onChanged, live }: { i: PclIntegration; onChanged: () => void; live: boolean }) {
  const [busy, setBusy] = useState<string | null>(null);
  const source = i.source || (i.name || "").toLowerCase();
  const connected = isConnected(i);

  const run = async (key: string, fn: () => Promise<unknown>) => {
    setBusy(key);
    try {
      await fn();
      onChanged();
    } catch {
      /* offline / no-op */
    } finally {
      setBusy(null);
    }
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
                ? `${i.items_synced ? `${i.items_synced} items · ` : ""}${i.last_sync_status || "synced"}`
                : "Not connected"}
            </div>
          </div>
        </div>
        <Pill tone={connected ? "good" : "neutral"}>{connected ? "Connected" : "Available"}</Pill>
      </div>

      <div className="flex justify-end gap-2 border-t border-outline-variant pt-3">
        {connected ? (
          <>
            <Button variant="ghost" loading={busy === "sync"} disabled={!live} onClick={() => run("sync", () => syncIntegration(source))}>
              <RefreshCw size={14} /> Sync
            </Button>
            <ConfirmButton confirmLabel="Disconnect" onConfirm={() => run("disc", () => disconnectIntegration(source))}>
              Disconnect
            </ConfirmButton>
          </>
        ) : (
          <Button variant="primary" loading={busy === "conn"} disabled={!live} onClick={() => run("conn", () => connectIntegration(source))}>
            <Plug size={14} /> Connect
          </Button>
        )}
      </div>
    </li>
  );
}

export default function Apps() {
  const integrationsRes = useResource(async () => (await getIntegrations()).integrations || [], previewIntegrations);
  const appsRes = useResource(async () => (await getApps()).apps || [], []);
  const { online } = useBackend();

  const integrations = integrationsRes.data;
  const connected = integrations.filter(isConnected);
  const available = integrations.filter((i) => !isConnected(i));
  const apps = appsRes.data;

  const reload = () => {
    integrationsRes.reload();
    appsRes.reload();
  };

  return (
    <>
      <PageHeader
        title="Apps & integrations"
        subtitle="Connect sources that feed your persona, and review which apps can request your context."
        action={
          <Button variant="default" onClick={reload}>
            <RefreshCw size={15} /> Refresh
          </Button>
        }
      />

      {(integrationsRes.isPreview || appsRes.isPreview) && <OfflineBanner onRetry={reload} />}

      {integrationsRes.loading && integrations.length === 0 ? (
        <LoadingState label="Loading integrations…" />
      ) : integrationsRes.error ? (
        <ErrorState message={integrationsRes.error} onRetry={reload} />
      ) : (
        <div className="flex flex-col gap-8">
          <section>
            <h2 className="mb-3 text-xs font-bold uppercase tracking-wider text-on-surface-variant">Connected sources</h2>
            {connected.length === 0 ? (
              <p className="text-sm text-on-surface-variant">No sources connected yet. Connect one below to start building your persona.</p>
            ) : (
              <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {connected.map((i) => (
                  <IntegrationCard key={i.source || i.name} i={i} onChanged={reload} live={online} />
                ))}
              </ul>
            )}
          </section>

          <section>
            <h2 className="mb-3 text-xs font-bold uppercase tracking-wider text-on-surface-variant">Available sources</h2>
            <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {available.map((i) => (
                <IntegrationCard key={i.source || i.name} i={i} onChanged={reload} live={online} />
              ))}
            </ul>
          </section>

          {apps.length > 0 && (
            <section>
              <h2 className="mb-3 text-xs font-bold uppercase tracking-wider text-on-surface-variant">Apps with context access</h2>
              <ul className="grid gap-3 sm:grid-cols-2">
                {apps.map((app) => (
                  <li key={app.app_id} className="rounded-2xl border border-outline-variant bg-white p-4 shadow-ambient">
                    <div className="flex items-center justify-between gap-3">
                      <div className="font-semibold">{app.name || app.app_id}</div>
                      <Pill tone={app.status === "revoked" ? "warn" : "good"}>{titleize(app.status || "active")}</Pill>
                    </div>
                    {app.allowed_layers && app.allowed_layers.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {app.allowed_layers.map((l) => (
                          <Chip key={l}>{titleize(l)}</Chip>
                        ))}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      )}
    </>
  );
}
