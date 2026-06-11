// /app/persona — "What PersonaLayer knows about you". Full editing: rename,
// adjust confidence, mark private (kept out of every bundle), mark wrong
// (suppressed), delete, view the evidence behind a signal, and merge
// duplicates. Signals are grouped by category with inline, optimistic edits.

import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  ArrowRight,
  Check,
  ChevronDown,
  ChevronUp,
  Code,
  Database,
  Eye,
  EyeOff,
  GitMerge,
  Info,
  Pencil,
  RefreshCw,
  Sparkles,
  Trash2,
  Wand2,
  X,
} from "lucide-react";
import { EmptyState, ErrorState, LoadingState, OfflineBanner, PageHeader } from "../components/states";
import { Button, ConfidenceBar, Panel, Pill, Stat } from "../components/ui";
import { useResource } from "../lib/useResource";
import { useBackend } from "../lib/backend";
import { relativeTime, titleize } from "../lib/format";
import { previewSignals, previewSummary } from "../lib/preview";
import {
  type PersonaSignal,
  deleteSignal,
  editSignal,
  getControlCenterSummary,
  searchSignals,
  updateSignalShareable,
} from "../api";

// Map a signal_type to a user-facing category.
const TYPE_TO_CATEGORY: Record<string, string> = {
  work_domain: "identity",
  skill: "work",
  tool: "work",
  task_pattern: "work",
  behavior: "habits",
  preference: "preferences",
  interest: "interests",
};
const CATEGORY_ORDER = ["identity", "work", "habits", "preferences", "interests", "other"];
const CATEGORY_LABEL: Record<string, string> = {
  identity: "Identity",
  work: "Work & skills",
  habits: "Habits",
  preferences: "Preferences",
  interests: "Interests",
  other: "Other",
};
const categoryOf = (s: PersonaSignal) => TYPE_TO_CATEGORY[s.signal_type || ""] || "other";

function signalIcon(type?: string) {
  if (type === "skill" || type === "tool") return <Code size={18} />;
  if (type === "behavior" || type === "preference") return <Sparkles size={18} />;
  return <Database size={18} />;
}

function SignalRow({ signal, live, onChanged }: { signal: PersonaSignal; live: boolean; onChanged: () => void }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(signal.name ?? "");
  const [conf, setConf] = useState(Math.round((signal.confidence ?? 0.5) * 100));
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const hidden = signal.shareable === false;
  const wrong = hidden && (signal.confidence ?? 1) === 0;

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await fn();
      onChanged();
    } catch {
      /* surfaced via offline notice */
    } finally {
      setBusy(false);
      setEditing(false);
    }
  };

  const commitConfidence = () => {
    const value = conf / 100;
    if (signal.id && value !== signal.confidence) act(() => editSignal(signal.id!, { confidence: value, reason: "Adjusted confidence" }));
  };

  return (
    <li className="border-b border-outline-variant py-3 last:border-none">
      <div className="flex items-center gap-3">
        <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-full ${wrong ? "bg-[#ba1a1a]/10 text-[#ba1a1a]" : "bg-[#006e2f]/10 text-[#006e2f]"}`}>
          {signalIcon(signal.signal_type)}
        </span>

        <div className="min-w-0 flex-1">
          {editing ? (
            <div className="flex items-center gap-2">
              <input
                value={draft}
                autoFocus
                onChange={(e) => setDraft(e.target.value)}
                className="h-9 min-w-0 flex-1 rounded-lg border border-outline-variant px-3 text-sm outline-none focus:border-primary"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && signal.id) act(() => editSignal(signal.id!, { name: draft.trim() || signal.name, reason: "Renamed signal" }));
                  if (e.key === "Escape") setEditing(false);
                }}
              />
              <Button variant="primary" loading={busy} onClick={() => signal.id && act(() => editSignal(signal.id!, { name: draft.trim() || signal.name, reason: "Renamed signal" }))}>
                <Check size={14} />
              </Button>
              <Button variant="ghost" onClick={() => setEditing(false)}><X size={14} /></Button>
            </div>
          ) : (
            <>
              <div className={`truncate font-semibold ${hidden ? "text-on-surface-variant" : ""}`}>
                {signal.name || signal.human_readable_type || "Persona signal"}
              </div>
              <div className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-on-surface-variant">
                <Pill tone="info">{signal.human_readable_source || titleize(signal.source) || "Activity"}</Pill>
                <ConfidenceBar value={(signal.confidence ?? 0.5)} />
                {wrong ? <Pill tone="danger">Marked wrong</Pill> : hidden && <Pill tone="warn">Private</Pill>}
              </div>
            </>
          )}
        </div>

        {!editing && (
          <div className="flex shrink-0 items-center gap-1">
            <button className="grid h-8 w-8 place-items-center rounded-lg text-on-surface-variant hover:bg-surface-container-low" title="Details & evidence" onClick={() => setExpanded((v) => !v)}>
              {expanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
            </button>
            <button className="grid h-8 w-8 place-items-center rounded-lg text-on-surface-variant hover:bg-surface-container-low disabled:opacity-40" title="Edit name" onClick={() => { setDraft(signal.name ?? ""); setEditing(true); }} disabled={!signal.id || busy || !live}>
              <Pencil size={15} />
            </button>
            <button className="grid h-8 w-8 place-items-center rounded-lg text-on-surface-variant hover:bg-surface-container-low disabled:opacity-40" title={hidden ? "Make shareable" : "Mark private (never shared)"} onClick={() => signal.id && act(() => updateSignalShareable(signal.id!, hidden))} disabled={!signal.id || busy || !live}>
              {hidden ? <Eye size={15} /> : <EyeOff size={15} />}
            </button>
            <button className="grid h-8 w-8 place-items-center rounded-lg text-[#ba1a1a] hover:bg-[#ba1a1a]/10 disabled:opacity-40" title="Delete signal" onClick={() => signal.id && act(() => deleteSignal(signal.id!))} disabled={!signal.id || busy || !live}>
              <Trash2 size={15} />
            </button>
          </div>
        )}
      </div>

      {expanded && !editing && (
        <div className="ml-12 mt-3 flex flex-col gap-3 rounded-xl border border-outline-variant bg-surface-container-low p-3">
          {/* Confidence slider */}
          <div>
            <div className="mb-1 flex items-center justify-between text-xs font-semibold text-on-surface-variant">
              <span>Confidence</span>
              <span>{conf}%</span>
            </div>
            <input
              type="range"
              min={0}
              max={100}
              value={conf}
              disabled={!live || busy}
              onChange={(e) => setConf(Number(e.target.value))}
              onPointerUp={commitConfidence}
              onKeyUp={commitConfidence}
              className="w-full accent-[#004ac6]"
            />
          </div>

          {/* Evidence / source */}
          <div className="flex items-start gap-2 text-xs text-on-surface-variant">
            <Info size={13} className="mt-0.5 shrink-0" />
            <span>
              {signal.why_it_exists || signal.evidence || "No evidence recorded for this signal."}
              {signal.created_at && <> · first seen {relativeTime(signal.created_at as string)}</>}
            </span>
          </div>

          {/* Mark wrong */}
          {!wrong && (
            <div>
              <Button variant="danger" loading={busy} disabled={!live} onClick={() => signal.id && act(() => editSignal(signal.id!, { confidence: 0, shareable: false, reason: "Marked as incorrect" }))}>
                <AlertTriangle size={14} /> Mark as wrong
              </Button>
              <p className="mt-1 text-xs text-outline">Suppresses it from every bundle. Delete to remove it entirely.</p>
            </div>
          )}
        </div>
      )}
    </li>
  );
}

export default function Persona() {
  const { online } = useBackend();
  const signalsRes = useResource(async () => (await searchSignals()).signals || [], previewSignals);
  const summaryRes = useResource(async () => await getControlCenterSummary(), previewSummary);
  const [merging, setMerging] = useState<string | null>(null);

  const signals = signalsRes.data;
  const summary = summaryRes.data;
  const offline = signalsRes.isPreview || summaryRes.isPreview;
  const visible = signals.filter((s) => s.shareable !== false).length;

  const reload = () => {
    signalsRes.reload();
    summaryRes.reload();
  };

  // Group signals by category, preserving the defined order.
  const groups = useMemo(() => {
    const map = new Map<string, PersonaSignal[]>();
    for (const s of signals) {
      const c = categoryOf(s);
      if (!map.has(c)) map.set(c, []);
      map.get(c)!.push(s);
    }
    return CATEGORY_ORDER.filter((c) => map.has(c)).map((c) => ({ category: c, items: map.get(c)! }));
  }, [signals]);

  // Detect duplicate-name clusters within a category for merging.
  const duplicateClusters = (items: PersonaSignal[]) => {
    const byName = new Map<string, PersonaSignal[]>();
    for (const s of items) {
      const key = (s.name || "").trim().toLowerCase();
      if (!key) continue;
      if (!byName.has(key)) byName.set(key, []);
      byName.get(key)!.push(s);
    }
    return [...byName.values()].filter((c) => c.length > 1);
  };

  // Merge: keep the highest-confidence signal, fold in evidence, delete the rest.
  const mergeCategory = async (category: string, items: PersonaSignal[]) => {
    setMerging(category);
    try {
      for (const cluster of duplicateClusters(items)) {
        const sorted = [...cluster].sort((a, b) => (b.confidence ?? 0) - (a.confidence ?? 0));
        const keep = sorted[0];
        const rest = sorted.slice(1);
        if (keep.id) {
          const evidence = [keep.evidence, ...rest.map((r) => r.evidence)].filter(Boolean).join(" · ").slice(0, 500);
          await editSignal(keep.id, { confidence: Math.max(...cluster.map((c) => c.confidence ?? 0)), evidence, reason: "Merged duplicates" }).catch(() => undefined);
        }
        for (const r of rest) if (r.id) await deleteSignal(r.id).catch(() => undefined);
      }
      reload();
    } finally {
      setMerging(null);
    }
  };

  return (
    <>
      <PageHeader
        title="What PersonaLayer knows about you"
        subtitle="Your living context, built from your own activity. Every signal is yours to edit, suppress, hide, or delete."
        action={
          <Button variant="default" onClick={reload}>
            <RefreshCw size={15} /> Refresh
          </Button>
        }
      />

      {offline && <OfflineBanner onRetry={reload} />}

      {signalsRes.loading && signals.length === 0 ? (
        <LoadingState label="Loading your persona…" />
      ) : signalsRes.error ? (
        <ErrorState message={signalsRes.error} onRetry={reload} />
      ) : (
        <div className="flex flex-col gap-4">
          <Panel title={<span className="inline-flex items-center gap-2"><Sparkles size={16} /> Persona summary</span>}>
            <p className="text-base leading-7 text-on-surface-variant">
              {typeof summary.summary === "string" && summary.summary
                ? (summary.summary as string)
                : "Your persona is built from the signals below. Connect more apps or seed it in onboarding to enrich it — and remember, nothing here is shared until you allow it."}
            </p>
          </Panel>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat value={visible} label="Active signals" hint="Visible to apps" />
            <Stat value={signals.length} label="Total tracked" />
            <Stat value={String(summary.active_permissions ?? 0)} label="App permissions" />
            <Stat value={String(summary.privacy_boundaries ?? 0)} label="Privacy rules" />
          </div>

          {signals.length === 0 ? (
            <Panel title="Signals">
              <EmptyState
                icon={<Wand2 size={22} />}
                title="No signals yet"
                hint="Seed your persona in a minute, or connect an app to start building it from your activity."
                action={
                  <div className="mt-2 flex flex-wrap justify-center gap-2">
                    <Link to="/app/onboarding" className="primary-button !px-4 !py-2 !text-sm">Set up your persona <ArrowRight size={15} /></Link>
                    <Link to="/app/apps" className="secondary-button !px-4 !py-2 !text-sm">Connect an app</Link>
                  </div>
                }
              />
            </Panel>
          ) : (
            groups.map(({ category, items }) => {
              const dupes = duplicateClusters(items);
              return (
                <Panel
                  key={category}
                  title={CATEGORY_LABEL[category]}
                  action={
                    dupes.length > 0 ? (
                      <Button variant="default" loading={merging === category} disabled={!online} onClick={() => mergeCategory(category, items)}>
                        <GitMerge size={14} /> Merge {dupes.reduce((n, c) => n + c.length - 1, 0)} duplicate(s)
                      </Button>
                    ) : (
                      <span className="text-xs text-on-surface-variant">{items.length}</span>
                    )
                  }
                >
                  <ul className="-my-1">
                    {items.map((s, i) => (
                      <SignalRow key={s.id ?? i} signal={s} live={online} onChanged={reload} />
                    ))}
                  </ul>
                </Panel>
              );
            })
          )}
        </div>
      )}
    </>
  );
}
