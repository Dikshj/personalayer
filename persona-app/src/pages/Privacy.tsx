// /app/privacy — the privacy rule builder. PersonaLayer ships with NO default
// rules: every boundary here is one the user created. Build rules that block a
// field, an app, or a domain (or require a confidence floor), test a rule
// against a real bundle preview before saving, and manage the rules you've set.

import { useMemo, useState } from "react";
import {
  Check,
  FlaskConical,
  Lock,
  Pencil,
  Plus,
  Search,
  ShieldAlert,
  ShieldX,
  Trash2,
  X,
} from "lucide-react";
import { ErrorState, LoadingState, OfflineBanner, PageHeader } from "../components/states";
import { Button, Chip, ConfirmButton, Panel, Pill } from "../components/ui";
import { useResource } from "../lib/useResource";
import { relativeTime, titleize } from "../lib/format";
import { previewBoundaries, previewPermissions } from "../lib/preview";
import { useBackend } from "../lib/backend";
import {
  type PrivacyBoundary,
  addPrivacyBoundary,
  createContextPreview,
  deletePrivacyBoundary,
  getApps,
  getBoundaries,
  getControlCenterPermissions,
  getPrivacyDrops,
  revokeControlCenterPermission,
} from "../api";

const RULE_TYPES = [
  { value: "field", boundary_type: "never_share_field", label: "Block a field", hint: "Exclude part of your persona from every app." },
  { value: "app", boundary_type: "never_share_app", label: "Block an app", hint: "Stop one app from receiving any context." },
  { value: "domain", boundary_type: "never_share_domain", label: "Block a website", hint: "Never share with a web domain." },
  { value: "confidence", boundary_type: "minimum_confidence", label: "Require confidence", hint: "Only share signals above a confidence score." },
] as const;

type RuleKind = (typeof RULE_TYPES)[number]["value"];

const LAYER_FIELDS = [
  { value: "identity_role", label: "Role & identity", desc: "Your occupation and the domain you work in." },
  { value: "capability_signals", label: "Tools & features", desc: "Which apps, tools, and features you use." },
  { value: "behavior_patterns", label: "Work patterns", desc: "How you work — depth, rhythm, session length." },
  { value: "active_context", label: "Current focus", desc: "What you’re working on right now." },
  { value: "explicit_preferences", label: "Your preferences", desc: "Things you’ve said apps should or shouldn’t do." },
];

function fieldLabel(target?: string) {
  return LAYER_FIELDS.find((f) => f.value === target)?.label || titleize(target);
}

function boundaryTypeLabel(bt?: string) {
  return RULE_TYPES.find((r) => r.boundary_type === bt)?.label || titleize(bt);
}

const inputClass =
  "w-full rounded-lg border border-outline-variant bg-white px-3 py-2 text-sm outline-none focus:border-primary";

function RuleBuilder({
  apps,
  editing,
  live,
  onSaved,
  onCancelEdit,
}: {
  apps: { app_id?: string; name?: string }[];
  editing: PrivacyBoundary | null;
  live: boolean;
  onSaved: (oldId?: string) => Promise<void> | void;
  onCancelEdit: () => void;
}) {
  const initialKind = (RULE_TYPES.find((r) => r.boundary_type === editing?.boundary_type)?.value || "field") as RuleKind;
  const [kind, setKind] = useState<RuleKind>(initialKind);
  const [target, setTarget] = useState(editing?.target || "identity_role");
  const [reason, setReason] = useState(editing?.reason || "");
  const [fieldSearch, setFieldSearch] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [test, setTest] = useState<{ before: string[]; after: string[] } | null>(null);
  const [testing, setTesting] = useState(false);

  const cfg = RULE_TYPES.find((r) => r.value === kind)!;

  const pickKind = (k: RuleKind) => {
    setKind(k);
    setTest(null);
    setTarget(k === "field" ? "identity_role" : k === "confidence" ? "0.7" : "");
  };

  const filteredFields = LAYER_FIELDS.filter(
    (f) => !fieldSearch || `${f.label} ${f.desc}`.toLowerCase().includes(fieldSearch.toLowerCase()),
  );

  const targetValid =
    kind === "confidence" ? Number(target) > 0 && Number(target) <= 1 : Boolean(target.trim());

  const runTest = async () => {
    setTesting(true);
    setError("");
    try {
      const preview = await createContextPreview({
        app_id: "rule_preview",
        app_name: "Rule preview",
        requested_purpose: "Preview how this rule changes what apps receive",
      });
      const before = preview.allowed_fields || [];
      const after = kind === "field" ? before.filter((f) => f !== target) : before;
      setTest({ before, after });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn’t run the preview.");
    } finally {
      setTesting(false);
    }
  };

  const save = async () => {
    setSaving(true);
    setError("");
    try {
      await addPrivacyBoundary(cfg.boundary_type, target.trim(), reason.trim());
      await onSaved(editing?.id);
      setReason("");
      setTest(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn’t save the rule.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Panel
      title={<span className="inline-flex items-center gap-2"><Plus size={16} /> {editing ? "Edit rule" : "Create a rule"}</span>}
      action={editing ? <Button variant="ghost" onClick={onCancelEdit}>Cancel</Button> : undefined}
    >
      <div className="flex flex-col gap-4">
        {/* Rule type */}
        <div>
          <span className="mb-1.5 block text-sm font-semibold">Rule type</span>
          <div className="grid gap-2 sm:grid-cols-2">
            {RULE_TYPES.map((r) => (
              <button
                key={r.value}
                onClick={() => pickKind(r.value)}
                className={`flex flex-col gap-0.5 rounded-xl border p-3 text-left transition ${
                  kind === r.value ? "border-primary bg-primary/[0.06]" : "border-outline-variant hover:bg-surface-container-low"
                }`}
              >
                <span className="font-semibold">{r.label}</span>
                <span className="text-xs text-on-surface-variant">{r.hint}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Target */}
        {kind === "field" && (
          <div>
            <span className="mb-1.5 block text-sm font-semibold">Field to block</span>
            <div className="mb-2 flex items-center gap-2 rounded-lg border border-outline-variant px-3">
              <Search size={15} className="text-outline" />
              <input
                className="w-full bg-transparent py-2 text-sm outline-none"
                placeholder="Search fields…"
                value={fieldSearch}
                onChange={(e) => setFieldSearch(e.target.value)}
              />
            </div>
            <ul className="flex flex-col gap-1.5">
              {filteredFields.map((f) => (
                <li key={f.value}>
                  <button
                    onClick={() => setTarget(f.value)}
                    className={`flex w-full items-start justify-between gap-3 rounded-lg border p-3 text-left transition ${
                      target === f.value ? "border-primary bg-primary/[0.06]" : "border-outline-variant hover:bg-surface-container-low"
                    }`}
                  >
                    <span>
                      <span className="block font-semibold">{f.label}</span>
                      <span className="block text-xs text-on-surface-variant">{f.desc}</span>
                    </span>
                    {target === f.value && <Check size={16} className="mt-0.5 shrink-0 text-primary" />}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {kind === "app" && (
          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-semibold">App to block</span>
            <input className={inputClass} list="apps-list" placeholder="app id" value={target} onChange={(e) => setTarget(e.target.value)} />
            <datalist id="apps-list">
              {apps.map((a) => (
                <option key={a.app_id} value={a.app_id}>{a.name}</option>
              ))}
            </datalist>
          </label>
        )}

        {kind === "domain" && (
          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-semibold">Website domain</span>
            <input className={inputClass} placeholder="example.com" value={target} onChange={(e) => setTarget(e.target.value)} />
          </label>
        )}

        {kind === "confidence" && (
          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-semibold">Minimum confidence (0–1)</span>
            <input className={inputClass} type="number" min="0" max="1" step="0.05" value={target} onChange={(e) => setTarget(e.target.value)} />
            <span className="text-xs text-on-surface-variant">Signals below this score won’t be shared with any app.</span>
          </label>
        )}

        {/* Applies-to note */}
        <div className="flex items-center gap-2 rounded-lg bg-surface-container-low px-3 py-2 text-xs text-on-surface-variant">
          <Lock size={13} />
          {kind === "app"
            ? "Applies to: the selected app only."
            : kind === "domain"
              ? "Applies to: the selected website."
              : "Applies to: all apps. Blocked fields are excluded entirely (value masking isn’t available yet)."}
        </div>

        {/* Reason */}
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-semibold">Note <span className="font-normal text-outline">(optional)</span></span>
          <input className={inputClass} placeholder="Why you’re adding this rule" value={reason} onChange={(e) => setReason(e.target.value)} />
        </label>

        {/* Test against a real bundle */}
        {kind === "field" && (
          <div className="rounded-xl border border-outline-variant p-4">
            <div className="flex items-center justify-between gap-3">
              <span className="flex items-center gap-2 text-sm font-semibold"><FlaskConical size={15} /> Test against a sample bundle</span>
              <Button variant="default" loading={testing} disabled={!live} onClick={runTest}>Run test</Button>
            </div>
            {test && (
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <div>
                  <div className="mb-1.5 text-xs font-bold uppercase tracking-wide text-outline">Before</div>
                  <div className="flex flex-wrap gap-1.5">
                    {test.before.length ? test.before.map((f) => <Chip key={f}>{fieldLabel(f)}</Chip>) : <span className="text-xs text-on-surface-variant">No fields</span>}
                  </div>
                </div>
                <div>
                  <div className="mb-1.5 text-xs font-bold uppercase tracking-wide text-outline">After this rule</div>
                  <div className="flex flex-wrap gap-1.5">
                    {test.after.length ? test.after.map((f) => <Chip key={f}>{fieldLabel(f)}</Chip>) : <span className="text-xs text-on-surface-variant">No fields</span>}
                    {test.before.includes(target) && (
                      <span className="inline-flex items-center gap-1 rounded-md border border-[#ba1a1a]/20 bg-[#ba1a1a]/5 px-2 py-0.5 text-xs font-semibold text-[#ba1a1a] line-through">
                        {fieldLabel(target)}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {error && <p className="rounded-lg border border-[#ba1a1a]/20 bg-[#ba1a1a]/5 px-3 py-2 text-sm font-semibold text-[#ba1a1a]">{error}</p>}

        <div className="flex items-center gap-2">
          <Button variant="primary" loading={saving} disabled={!targetValid || !live} onClick={save}>
            <Check size={15} /> {editing ? "Save changes" : "Create rule"}
          </Button>
          {!live && <span className="text-xs text-outline">Reconnect to save rules.</span>}
        </div>
      </div>
    </Panel>
  );
}

export default function Privacy() {
  const { online } = useBackend();
  const rulesRes = useResource(async () => (await getBoundaries(true)).boundaries || [], previewBoundaries);
  const permsRes = useResource(async () => (await getControlCenterPermissions()).active || [], previewPermissions);
  const dropsRes = useResource(async () => (await getPrivacyDrops()).drops || [], [] as Array<Record<string, unknown>>);
  const appsRes = useResource(async () => (await getApps()).apps || [], []);

  const rules = rulesRes.data;
  const perms = permsRes.data;
  const drops = dropsRes.data;
  const offline = rulesRes.isPreview || permsRes.isPreview;
  const [editing, setEditing] = useState<PrivacyBoundary | null>(null);

  const reload = () => {
    rulesRes.reload();
    permsRes.reload();
    dropsRes.reload();
  };

  // After save: if we were editing, drop the old boundary (no PATCH on the API).
  const onSaved = async (oldId?: string) => {
    if (oldId) await deletePrivacyBoundary(oldId).catch(() => undefined);
    setEditing(null);
    rulesRes.reload();
  };

  const dropRows = useMemo(() => drops.slice(0, 8), [drops]);

  return (
    <>
      <PageHeader
        title="Privacy rules"
        subtitle="You build every rule here. PersonaLayer has no default rules — nothing is blocked until you say so, and nothing is shared without your consent."
      />

      {offline && <OfflineBanner onRetry={reload} />}

      <div className="flex flex-col gap-4">
        <RuleBuilder
          apps={appsRes.data}
          editing={editing}
          live={online}
          onSaved={onSaved}
          onCancelEdit={() => setEditing(null)}
        />

        <Panel
          title={<span className="inline-flex items-center gap-2"><ShieldX size={16} /> Your rules</span>}
          action={<span className="text-xs text-on-surface-variant">{rules.length} rule(s)</span>}
        >
          {rulesRes.loading && rules.length === 0 ? (
            <LoadingState label="Loading your rules…" />
          ) : rulesRes.error ? (
            <ErrorState message={rulesRes.error} onRetry={rulesRes.reload} />
          ) : rules.length === 0 ? (
            <p className="text-sm text-on-surface-variant">
              No rules yet. You haven’t restricted anything — every field is shareable until you add a rule above.
            </p>
          ) : (
            <ul className="-my-1">
              {rules.map((r) => (
                <li key={r.id} className="flex items-center justify-between gap-4 border-b border-outline-variant py-3 last:border-none">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <Pill tone="danger">{boundaryTypeLabel(r.boundary_type)}</Pill>
                      <span className="font-semibold">{fieldLabel(r.target)}</span>
                    </div>
                    {r.reason && <div className="mt-0.5 truncate text-xs text-on-surface-variant">{r.reason}</div>}
                  </div>
                  <div className="flex shrink-0 items-center gap-1">
                    <button
                      className="grid h-8 w-8 place-items-center rounded-lg text-on-surface-variant hover:bg-surface-container-low"
                      title="Edit rule"
                      onClick={() => { setEditing(r); window.scrollTo({ top: 0, behavior: "smooth" }); }}
                      disabled={!online}
                    >
                      <Pencil size={15} />
                    </button>
                    <ConfirmButton
                      confirmLabel="Delete"
                      disabled={!online}
                      onConfirm={async () => {
                        if (r.id) await deletePrivacyBoundary(r.id);
                        rulesRes.reload();
                      }}
                    >
                      <Trash2 size={15} />
                    </ConfirmButton>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Apps you've granted access" action={<span className="text-xs text-on-surface-variant">{perms.length} active</span>}>
          {permsRes.loading && perms.length === 0 ? (
            <LoadingState />
          ) : permsRes.error ? (
            <ErrorState message={permsRes.error} onRetry={permsRes.reload} />
          ) : perms.length === 0 ? (
            <p className="text-sm text-on-surface-variant">No apps have access. When you approve one, it shows up here.</p>
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
                    disabled={!online}
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
          title={<span className="inline-flex items-center gap-2"><ShieldAlert size={16} /> Recently blocked</span>}
          action={<span className="text-xs text-on-surface-variant">{drops.length} drops</span>}
        >
          <p className="mb-3 text-sm text-on-surface-variant">Context your rules kept from reaching an app. See the full log in Activity.</p>
          {dropsRes.loading && drops.length === 0 ? (
            <LoadingState />
          ) : dropRows.length === 0 ? (
            <p className="text-sm text-on-surface-variant">Nothing has been blocked yet.</p>
          ) : (
            <ul className="-my-1">
              {dropRows.map((d, i) => (
                <li key={(d.id as string) ?? i} className="flex flex-wrap items-center gap-3 border-b border-outline-variant py-3 last:border-none">
                  <Pill tone="danger">{titleize(String(d.feature_id || d.reason || "blocked"))}</Pill>
                  <span className="flex-1 text-sm text-on-surface-variant">{String(d.reason || "Filtered by a privacy rule")}</span>
                  <span className="text-xs text-outline">{relativeTime((d.created_at as string) || (d.timestamp as number))}</span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </>
  );
}
