// /app/persona — "What PersonaLayer knows about you".
// Persona summary, signals with confidence + sources, and per-signal actions
// to hide / edit / delete (wired to the control-center signal endpoints).

import { useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  Briefcase,
  Check,
  Code,
  Database,
  Eye,
  EyeOff,
  MessageCircle,
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

function signalIcon(type?: string) {
  if (type === "skill" || type === "tool") return <Code size={18} />;
  if (type === "work_domain") return <Briefcase size={18} />;
  if (type === "preference" || type === "behavior") return <MessageCircle size={18} />;
  return <Database size={18} />;
}

function SignalRow({ signal, onChanged }: { signal: PersonaSignal; onChanged: () => void }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(signal.name ?? "");
  const [busy, setBusy] = useState(false);
  const hidden = signal.shareable === false;

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

  return (
    <li className="flex items-center gap-3 border-b border-outline-variant py-3 last:border-none">
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-[#006e2f]/10 text-[#006e2f]">
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
                if (e.key === "Enter" && signal.id) act(() => editSignal(signal.id!, { name: draft.trim() || signal.name }));
                if (e.key === "Escape") setEditing(false);
              }}
            />
            <Button variant="primary" loading={busy} onClick={() => signal.id && act(() => editSignal(signal.id!, { name: draft.trim() || signal.name }))}>
              <Check size={14} />
            </Button>
            <Button variant="ghost" onClick={() => setEditing(false)}>
              <X size={14} />
            </Button>
          </div>
        ) : (
          <>
            <div className={`truncate font-semibold ${hidden ? "text-on-surface-variant" : ""}`}>
              {signal.name || signal.human_readable_type || "Persona signal"}
            </div>
            <div className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-on-surface-variant">
              <Pill tone="info">{signal.human_readable_source || titleize(signal.source) || "Activity"}</Pill>
              {typeof signal.confidence === "number" && <ConfidenceBar value={signal.confidence} />}
              {hidden && <Pill tone="warn">Hidden from apps</Pill>}
            </div>
          </>
        )}
      </div>

      {!editing && (
        <div className="flex shrink-0 items-center gap-1">
          <button className="grid h-8 w-8 place-items-center rounded-lg text-on-surface-variant hover:bg-surface-container-low" title="Edit name" onClick={() => { setDraft(signal.name ?? ""); setEditing(true); }} disabled={!signal.id || busy}>
            <Pencil size={15} />
          </button>
          <button className="grid h-8 w-8 place-items-center rounded-lg text-on-surface-variant hover:bg-surface-container-low" title={hidden ? "Reveal to apps" : "Hide from apps"} onClick={() => signal.id && act(() => updateSignalShareable(signal.id!, hidden))} disabled={!signal.id || busy}>
            {hidden ? <Eye size={15} /> : <EyeOff size={15} />}
          </button>
          <button className="grid h-8 w-8 place-items-center rounded-lg text-[#ba1a1a] hover:bg-[#ba1a1a]/10" title="Delete signal" onClick={() => signal.id && act(() => deleteSignal(signal.id!))} disabled={!signal.id || busy}>
            <Trash2 size={15} />
          </button>
        </div>
      )}
    </li>
  );
}

export default function Persona() {
  const signalsRes = useResource(async () => (await searchSignals()).signals || [], previewSignals);
  const summaryRes = useResource(async () => await getControlCenterSummary(), previewSummary);

  const signals = signalsRes.data;
  const summary = summaryRes.data;
  const offline = signalsRes.isPreview || summaryRes.isPreview;
  const visible = signals.filter((s) => s.shareable !== false).length;

  const reload = () => {
    signalsRes.reload();
    summaryRes.reload();
  };

  return (
    <>
      <PageHeader
        title="What PersonaLayer knows about you"
        subtitle="Your living context, built from your own activity. Every signal is yours to edit, hide, or delete."
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
          <Panel
            title={
              <span className="inline-flex items-center gap-2">
                <Sparkles size={16} /> Persona summary
              </span>
            }
          >
            <p className="text-base leading-7 text-on-surface-variant">
              You’re a software developer building a side project. You prefer short, direct answers, and your context
              stays on this device unless you explicitly share it.
            </p>
          </Panel>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat value={visible} label="Active signals" hint="Visible to apps" />
            <Stat value={signals.length} label="Total tracked" />
            <Stat value={String(summary.active_permissions ?? 0)} label="App permissions" />
            <Stat value={String(summary.privacy_boundaries ?? 0)} label="Privacy rules" />
          </div>

          <Panel title="Signals" action={<span className="text-xs text-on-surface-variant">{signals.length} signals</span>}>
            {signals.length === 0 ? (
              <EmptyState
                icon={<Wand2 size={22} />}
                title="No signals yet"
                hint="Seed your persona in a minute, or connect an app to start building it from your activity."
                action={
                  <div className="mt-2 flex flex-wrap justify-center gap-2">
                    <Link to="/app/onboarding" className="primary-button !px-4 !py-2 !text-sm">
                      Set up your persona <ArrowRight size={15} />
                    </Link>
                    <Link to="/app/apps" className="secondary-button !px-4 !py-2 !text-sm">
                      Connect an app
                    </Link>
                  </div>
                }
              />
            ) : (
              <ul className="-my-1">
                {signals.map((s, i) => (
                  <SignalRow key={s.id ?? i} signal={s} onChanged={reload} />
                ))}
              </ul>
            )}
          </Panel>
        </div>
      )}
    </>
  );
}
