// /app/context-preview/:previewId — shows exactly what an app would receive
// before you approve: who's asking, the fields included, the fields your rules
// block, and a preview of the bundle. Approve all, approve a narrowed subset,
// or deny.

import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, CheckCircle2, Eye, ShieldX } from "lucide-react";
import { LoadingState, OfflineBanner } from "../components/states";
import { Button, Pill, Switch } from "../components/ui";
import { useResource } from "../lib/useResource";
import { titleize } from "../lib/format";
import { type ContextPreview as Preview, decideContextPreview, getContextPreview } from "../api";

const PREVIEW_FALLBACK: Preview = {
  id: "demo",
  app_id: "demo_app",
  app_name: "Demo Assistant",
  requested_purpose: "Personalize your experience",
  allowed_fields: ["identity_role", "capability_signals", "active_context"],
  excluded_fields: ["explicit_preferences"],
  confidence_levels: { identity_role: 0.9, capability_signals: 0.8, active_context: 0.6 },
  plain_english_summary: "This app would learn your role, the tools you use, and what you’re working on. Your stated preferences are blocked by your rules.",
  status: "pending",
};

export default function ContextPreview() {
  const { previewId = "" } = useParams();
  const navigate = useNavigate();
  const res = useResource<Preview>(() => getContextPreview(previewId), PREVIEW_FALLBACK, [previewId]);
  const preview = res.data;

  const allowed = useMemo(() => preview.allowed_fields || [], [preview]);
  const excluded = preview.excluded_fields || [];
  const [included, setIncluded] = useState<Record<string, boolean> | null>(null);
  const [busy, setBusy] = useState<"approve" | "deny" | null>(null);
  const [error, setError] = useState("");

  const chosen = included ?? Object.fromEntries(allowed.map((f) => [f, true]));
  const approvedFields = allowed.filter((f) => chosen[f]);
  const decided = preview.status && preview.status !== "pending";

  const decide = async (decision: "approved" | "denied") => {
    setBusy(decision === "approved" ? "approve" : "deny");
    setError("");
    try {
      const narrowing = decision === "approved" && approvedFields.length < allowed.length;
      await decideContextPreview(previewId, narrowing ? "narrowed" : decision, narrowing ? approvedFields : []);
      navigate("/app/activity", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "We couldn’t save your decision.");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="min-h-dvh bg-surface text-on-surface">
      <header className="mx-auto flex max-w-2xl items-center justify-between px-5 py-5">
        <Link to="/app/apps" className="inline-flex items-center gap-1.5 text-sm font-semibold text-on-surface-variant hover:text-on-surface">
          <ArrowLeft size={15} /> Apps
        </Link>
        <span className="text-sm font-bold text-primary">PersonaLayer</span>
      </header>

      <main className="mx-auto w-full max-w-2xl px-5 pb-16">
        {res.isPreview && <OfflineBanner onRetry={res.reload} />}

        {res.loading ? (
          <LoadingState label="Loading preview…" />
        ) : (
          <div className="rounded-2xl border border-outline-variant bg-white p-6 shadow-ambient sm:p-8">
            <div className="flex items-center gap-3">
              <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-primary/10 text-primary">
                <Eye size={22} />
              </span>
              <div className="min-w-0">
                <h1 className="truncate text-xl font-bold">{preview.app_name || titleize(preview.app_id)}</h1>
                <div className="text-xs text-on-surface-variant">{preview.requested_purpose || "Requesting your context"}</div>
              </div>
              {decided && <Pill tone="neutral">{titleize(preview.status)}</Pill>}
            </div>

            {preview.plain_english_summary && (
              <p className="mt-4 rounded-xl border border-outline-variant bg-surface-container-low p-3 text-sm leading-6 text-on-surface-variant">
                {preview.plain_english_summary}
              </p>
            )}

            {/* Included fields, each toggleable for a narrowed approval */}
            <div className="mt-5">
              <div className="mb-2 text-xs font-bold uppercase tracking-wide text-outline">Would be shared</div>
              {allowed.length === 0 ? (
                <p className="text-sm text-on-surface-variant">Nothing would be shared with this app.</p>
              ) : (
                <ul className="flex flex-col gap-2">
                  {allowed.map((f) => (
                    <li key={f} className="flex items-center justify-between gap-3 rounded-xl border border-outline-variant p-3">
                      <div className="min-w-0">
                        <div className={`font-semibold ${chosen[f] ? "" : "text-on-surface-variant line-through"}`}>{titleize(f)}</div>
                        {typeof preview.confidence_levels?.[f] === "number" && (
                          <div className="text-xs text-on-surface-variant">Confidence {Math.round((preview.confidence_levels[f] as number) * 100)}%</div>
                        )}
                      </div>
                      <Switch checked={Boolean(chosen[f])} onChange={(v) => setIncluded({ ...chosen, [f]: v })} label={titleize(f)} />
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Blocked by rules */}
            {excluded.length > 0 && (
              <div className="mt-4">
                <div className="mb-2 text-xs font-bold uppercase tracking-wide text-outline">Blocked by your rules</div>
                <div className="flex flex-wrap gap-1.5">
                  {excluded.map((f) => (
                    <span key={f} className="inline-flex items-center gap-1 rounded-md border border-[#ba1a1a]/20 bg-[#ba1a1a]/5 px-2 py-0.5 text-xs font-semibold text-[#ba1a1a]">
                      <ShieldX size={11} /> {titleize(f)}
                    </span>
                  ))}
                </div>
                <p className="mt-1.5 text-xs text-on-surface-variant">
                  These are excluded by rules you set in <Link to="/app/privacy" className="text-primary hover:underline">Privacy rules</Link>.
                </p>
              </div>
            )}

            {error && <p className="mt-4 rounded-lg border border-[#ba1a1a]/20 bg-[#ba1a1a]/5 px-3 py-2 text-sm font-semibold text-[#ba1a1a]">{error}</p>}

            {!decided && (
              <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
                <Button variant="default" loading={busy === "deny"} onClick={() => decide("denied")}>
                  <ShieldX size={15} /> Deny
                </Button>
                <Button variant="primary" loading={busy === "approve"} disabled={approvedFields.length === 0} onClick={() => decide("approved")}>
                  <CheckCircle2 size={15} /> Approve {approvedFields.length < allowed.length ? `${approvedFields.length} of ${allowed.length}` : "all"}
                </Button>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
