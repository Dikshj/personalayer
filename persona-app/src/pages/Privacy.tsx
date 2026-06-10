// /app/privacy — always-private categories (wired to privacy boundaries),
// sharing defaults, per-app permissions, and an audit preview of blocked
// context.

import { useEffect, useMemo, useState } from "react";
import { Eye, Lock, Mail, MapPin, ShieldAlert, Wallet } from "lucide-react";
import { ErrorState, LoadingState, OfflineBanner, PageHeader } from "../components/states";
import { Chip, ConfirmButton, Panel, Pill, Switch } from "../components/ui";
import { useResource } from "../lib/useResource";
import { relativeTime, titleize } from "../lib/format";
import { previewBoundaries, previewPermissions } from "../lib/preview";
import {
  type PrivacyBoundary,
  addPrivacyBoundary,
  deletePrivacyBoundary,
  getControlCenterPermissions,
  getPrivacyDrops,
  getPrivacyProfile,
  revokeControlCenterPermission,
} from "../api";

const CATEGORIES = [
  { target: "emails", label: "My emails", icon: <Mail size={18} />, hint: "Keep inbox messages strictly for your eyes." },
  { target: "location", label: "My location", icon: <MapPin size={18} />, hint: "Prevent apps from knowing where you are." },
  { target: "browsing", label: "My browsing", icon: <Eye size={18} />, hint: "Hide sensitive sites from connected apps." },
  { target: "financial", label: "Financial", icon: <Wallet size={18} />, hint: "Never share financial details." },
];

const SHARING_OPTIONS = [
  { value: "minimal", label: "Minimal", hint: "Only what an app explicitly needs" },
  { value: "balanced", label: "Balanced", hint: "Relevant context with consent" },
  { value: "open", label: "Open", hint: "Share broadly with connected apps" },
] as const;

const SHARING_KEY = "personalayer_sharing_default";

function CategoryToggle({ target, label, icon, hint, boundaries, onChanged }: {
  target: string;
  label: string;
  icon: React.ReactNode;
  hint: string;
  boundaries: PrivacyBoundary[];
  onChanged: () => void;
}) {
  const existing = boundaries.find((b) => b.target === target || b.target === `private_${target}`);
  const [on, setOn] = useState(Boolean(existing));
  useEffect(() => setOn(Boolean(existing)), [existing]);

  const toggle = async (next: boolean) => {
    setOn(next);
    try {
      if (next) await addPrivacyBoundary("never_share_field", target, `User marked ${label} private`);
      else if (existing?.id) await deletePrivacyBoundary(existing.id);
      onChanged();
    } catch {
      setOn(!next);
    }
  };

  return (
    <li className="flex items-center justify-between gap-4 border-b border-outline-variant py-3 last:border-none">
      <div className="flex items-center gap-3">
        <span className="grid h-9 w-9 place-items-center rounded-full bg-surface-container text-on-surface-variant">{icon}</span>
        <div>
          <div className="font-semibold">{label}</div>
          <div className="text-xs text-on-surface-variant">{hint}</div>
        </div>
      </div>
      <Switch checked={on} onChange={toggle} amber label={`Keep ${label} private`} />
    </li>
  );
}

export default function Privacy() {
  const profileRes = useResource(async () => (await getPrivacyProfile()).active_boundaries || [], previewBoundaries);
  const permsRes = useResource(async () => (await getControlCenterPermissions()).active || [], previewPermissions);
  const dropsRes = useResource(async () => (await getPrivacyDrops()).drops || [], [] as Array<Record<string, unknown>>);

  const boundaries = profileRes.data;
  const perms = permsRes.data;
  const drops = dropsRes.data;
  const offline = profileRes.isPreview || permsRes.isPreview;

  const [sharing, setSharing] = useState<string>(() => localStorage.getItem(SHARING_KEY) || "minimal");
  const setSharingDefault = (v: string) => {
    setSharing(v);
    localStorage.setItem(SHARING_KEY, v);
  };

  const reload = () => {
    profileRes.reload();
    permsRes.reload();
    dropsRes.reload();
  };

  const dropRows = useMemo(() => drops.slice(0, 8), [drops]);

  return (
    <>
      <PageHeader
        title="Privacy controls"
        subtitle="Set the boundaries of your context layer. These rules apply before anything reaches an app."
      />

      {offline && <OfflineBanner onRetry={reload} />}

      <div className="flex flex-col gap-4">
        <Panel title={<span className="inline-flex items-center gap-2"><Lock size={16} /> Always keep private</span>}>
          {profileRes.loading && boundaries.length === 0 ? (
            <LoadingState />
          ) : (
            <ul className="-my-1">
              {CATEGORIES.map((c) => (
                <CategoryToggle key={c.target} {...c} boundaries={boundaries} onChanged={reload} />
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Sharing default">
          <p className="mb-4 text-sm text-on-surface-variant">How much context apps receive by default when granted access.</p>
          <div className="grid gap-2 sm:grid-cols-3">
            {SHARING_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setSharingDefault(opt.value)}
                className={`flex flex-col gap-0.5 rounded-xl border p-3 text-left transition ${
                  sharing === opt.value ? "border-primary bg-primary/5" : "border-outline-variant bg-white hover:bg-surface-container-low"
                }`}
              >
                <span className="font-semibold">{opt.label}</span>
                <span className="text-xs text-on-surface-variant">{opt.hint}</span>
              </button>
            ))}
          </div>
        </Panel>

        <Panel title="Per-app permissions" action={<span className="text-xs text-on-surface-variant">{perms.length} active</span>}>
          {permsRes.loading && perms.length === 0 ? (
            <LoadingState />
          ) : permsRes.error ? (
            <ErrorState message={permsRes.error} onRetry={permsRes.reload} />
          ) : perms.length === 0 ? (
            <p className="text-sm text-on-surface-variant">No apps have been granted access.</p>
          ) : (
            <ul className="-my-1">
              {perms.map((p) => (
                <li key={p.id || p.app_id} className="flex items-center justify-between gap-4 border-b border-outline-variant py-3 last:border-none">
                  <div className="min-w-0">
                    <div className="font-semibold">{p.name || titleize(p.app_id)}</div>
                    <div className="mt-1 flex flex-wrap gap-1.5">
                      {(p.scopes || []).map((s) => (
                        <Chip key={s}>{titleize(s)}</Chip>
                      ))}
                    </div>
                  </div>
                  <ConfirmButton
                    confirmLabel="Revoke"
                    onConfirm={async () => {
                      await revokeControlCenterPermission(p.id || p.app_id || "", p.permission_type || p.type || "app");
                      permsRes.reload();
                    }}
                  >
                    Revoke
                  </ConfirmButton>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel
          title={<span className="inline-flex items-center gap-2"><ShieldAlert size={16} /> Audit preview — recently blocked</span>}
          action={<span className="text-xs text-on-surface-variant">{drops.length} drops</span>}
        >
          <p className="mb-3 text-sm text-on-surface-variant">Context dropped before reaching an app. See the full log in Activity.</p>
          {dropsRes.loading && drops.length === 0 ? (
            <LoadingState />
          ) : dropRows.length === 0 ? (
            <p className="text-sm text-on-surface-variant">Nothing has been blocked recently.</p>
          ) : (
            <ul className="-my-1">
              {dropRows.map((d, i) => (
                <li key={(d.id as string) ?? i} className="flex flex-wrap items-center gap-3 border-b border-outline-variant py-3 last:border-none">
                  <Pill tone="danger">{titleize(String(d.category || d.reason || "blocked"))}</Pill>
                  <span className="flex-1 text-sm text-on-surface-variant">{String(d.reason || "Filtered by privacy rule")}</span>
                  <span className="text-xs text-outline">{relativeTime(d.timestamp as number)}</span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </>
  );
}
