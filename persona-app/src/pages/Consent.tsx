// /app/consent/:appId — a third-party app is requesting access. The user reviews
// each requested scope in plain language, toggles individual scopes on or off,
// and approves only what they choose (partial approval is allowed) or denies.

import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Check, ScrollText, ShieldCheck, ShieldX, X } from "lucide-react";
import { LoadingState, OfflineBanner } from "../components/states";
import { Button, Pill, Switch } from "../components/ui";
import { useResource } from "../lib/useResource";
import { titleize } from "../lib/format";
import { type PclApp, getApp, grantConsent, revokeConsent } from "../api";

// Plain-language explanation for each context layer / scope.
const SCOPE_INFO: Record<string, { label: string; desc: string }> = {
  identity_role: { label: "Your role", desc: "Your occupation and the domain you work in — e.g. “software engineer in AI”." },
  capability_signals: { label: "Tools & features", desc: "Which apps, tools, and features you use." },
  behavior_patterns: { label: "Work patterns", desc: "How you tend to work — session length, depth, and rhythm. No raw activity." },
  active_context: { label: "Current focus", desc: "What you’re working on right now, at a high level." },
  explicit_preferences: { label: "Your preferences", desc: "Things you’ve said apps should always or never do." },
  getFeatureUsage: { label: "Feature usage", desc: "Aggregate signals about which features you use." },
};

function infoFor(scope: string) {
  return SCOPE_INFO[scope] || { label: titleize(scope), desc: "Access to this part of your context." };
}

const PREVIEW_APP: PclApp = {
  app_id: "demo_app",
  name: "Demo Assistant",
  status: "active",
  allowed_layers: ["identity_role", "capability_signals", "active_context"],
};

export default function Consent() {
  const { appId = "" } = useParams();
  const navigate = useNavigate();
  const appRes = useResource<PclApp | undefined>(() => getApp(appId), PREVIEW_APP, [appId]);
  const app = appRes.data;

  const scopes = useMemo(() => {
    const layers = app?.allowed_layers && app.allowed_layers.length ? app.allowed_layers : ["getFeatureUsage"];
    return layers;
  }, [app]);

  const [selected, setSelected] = useState<Record<string, boolean> | null>(null);
  const [remember, setRemember] = useState(true);
  const [busy, setBusy] = useState<"approve" | "deny" | null>(null);
  const [error, setError] = useState("");

  // Initialize all scopes to approved once the app's scopes are known.
  const chosen = selected ?? Object.fromEntries(scopes.map((s) => [s, true]));
  const approvedScopes = scopes.filter((s) => chosen[s]);

  const setScope = (scope: string, on: boolean) => setSelected({ ...chosen, [scope]: on });

  const approve = async () => {
    setBusy("approve");
    setError("");
    try {
      await grantConsent({
        app_id: appId,
        scopes: approvedScopes,
        granted_via: remember ? "explicit" : "session",
      });
      navigate("/app/apps", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "We couldn’t save your decision. Try again.");
    } finally {
      setBusy(null);
    }
  };

  const deny = async () => {
    setBusy("deny");
    setError("");
    try {
      await revokeConsent(appId).catch(() => undefined);
      navigate("/app/apps", { replace: true });
    } finally {
      setBusy(null);
    }
  };

  const notFound = !appRes.loading && !appRes.isPreview && !app;

  return (
    <div className="min-h-dvh bg-surface text-on-surface">
      <header className="mx-auto flex max-w-2xl items-center justify-between px-5 py-5">
        <Link to="/app/apps" className="inline-flex items-center gap-1.5 text-sm font-semibold text-on-surface-variant hover:text-on-surface">
          <ArrowLeft size={15} /> Apps
        </Link>
        <span className="text-sm font-bold text-primary">PersonaLayer</span>
      </header>

      <main className="mx-auto w-full max-w-2xl px-5 pb-16">
        {appRes.isPreview && <OfflineBanner onRetry={appRes.reload} />}

        {appRes.loading ? (
          <LoadingState label="Loading request…" />
        ) : notFound ? (
          <div className="rounded-2xl border border-outline-variant bg-white p-8 text-center shadow-ambient">
            <div className="font-semibold">App not found</div>
            <p className="mt-1 text-sm text-on-surface-variant">We couldn’t find an app with id “{appId}”.</p>
            <Link to="/app/apps" className="mt-3 inline-block text-sm font-semibold text-primary hover:underline">Back to apps</Link>
          </div>
        ) : (
          <div className="rounded-2xl border border-outline-variant bg-white p-6 shadow-ambient sm:p-8">
            {/* App identity */}
            <div className="flex items-center gap-3">
              <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-primary/10 text-lg font-bold uppercase text-primary">
                {(app?.name || appId).slice(0, 1)}
              </span>
              <div className="min-w-0">
                <h1 className="truncate text-xl font-bold">{app?.name || titleize(appId)}</h1>
                <div className="flex items-center gap-2 text-xs text-on-surface-variant">
                  <span className="font-mono">{app?.app_id || appId}</span>
                  <Pill tone={app?.status === "revoked" ? "warn" : "good"}>{titleize(app?.status || "active")}</Pill>
                </div>
              </div>
            </div>

            <p className="mt-4 text-sm leading-6 text-on-surface-variant">
              <strong className="text-on-surface">{app?.name || titleize(appId)}</strong> wants to read parts of your
              persona. Choose what it can see — it only gets the scopes you leave on.
            </p>

            {/* Per-scope toggles */}
            <ul className="mt-5 flex flex-col gap-2">
              {scopes.map((scope) => {
                const info = infoFor(scope);
                const on = chosen[scope];
                return (
                  <li key={scope} className="flex items-start justify-between gap-3 rounded-xl border border-outline-variant p-4">
                    <div className="min-w-0">
                      <div className={`font-semibold ${on ? "" : "text-on-surface-variant line-through"}`}>{info.label}</div>
                      <p className="mt-0.5 text-sm text-on-surface-variant">{info.desc}</p>
                    </div>
                    <Switch checked={on} onChange={(v) => setScope(scope, v)} label={info.label} />
                  </li>
                );
              })}
            </ul>

            {/* Remember + audit preview */}
            <label className="mt-5 flex cursor-pointer items-center gap-2.5">
              <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} className="h-4 w-4 accent-[#bd5d3f]" />
              <span className="text-sm font-semibold">Remember this choice for {app?.name || titleize(appId)}</span>
            </label>

            <div className="mt-4 flex items-start gap-2 rounded-xl border border-outline-variant bg-surface-container-low p-3 text-xs text-on-surface-variant">
              <ScrollText size={14} className="mt-0.5 shrink-0" />
              <span>
                This will be logged as: <strong className="text-on-surface">
                  {approvedScopes.length === 0 ? "denied" : "granted"} {app?.name || appId}
                </strong>
                {approvedScopes.length > 0 && <> · scopes [{approvedScopes.map((s) => infoFor(s).label).join(", ")}]</>}
                {" · via "}{remember ? "explicit (remembered)" : "session (one-time)"}.
              </span>
            </div>

            {error && (
              <p className="mt-4 rounded-lg border border-danger/20 bg-danger/5 px-3 py-2 text-sm font-semibold text-danger">{error}</p>
            )}

            {/* Actions */}
            <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
              <Button variant="default" loading={busy === "deny"} onClick={deny}>
                <ShieldX size={15} /> Deny
              </Button>
              <Button variant="primary" loading={busy === "approve"} onClick={approve}>
                {approvedScopes.length === 0 ? <><X size={15} /> Approve none</> : <><ShieldCheck size={15} /> Approve {approvedScopes.length} scope{approvedScopes.length === 1 ? "" : "s"}</>}
              </Button>
            </div>
            {approvedScopes.length > 0 && approvedScopes.length < scopes.length && (
              <p className="mt-2 flex items-center justify-end gap-1 text-xs text-on-surface-variant">
                <Check size={12} /> Partial approval — {scopes.length - approvedScopes.length} scope(s) excluded.
              </p>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
