// /app/activity — the access log. Every time an app requested your context,
// what it asked for, what it actually received, what your rules blocked, and
// whether it was allowed or denied. Filter by app, date, and result; open any
// row for detail; export the log as JSON or CSV.

import { useMemo, useState } from "react";
import {
  Ban,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Download,
  ScrollText,
  ShieldX,
} from "lucide-react";
import { EmptyState, ErrorState, LoadingState, OfflineBanner, PageHeader } from "../components/states";
import { Button, Chip, Panel, Pill, Stat } from "../components/ui";
import { useResource } from "../lib/useResource";
import { relativeTime, titleize, toMs } from "../lib/format";
import { previewQueryLog } from "../lib/preview";
import { type QueryLogEntry, getQueryLog } from "../api";

const DATE_RANGES = [
  { value: "1", label: "24h", ms: 86_400_000 },
  { value: "7", label: "7 days", ms: 7 * 86_400_000 },
  { value: "30", label: "30 days", ms: 30 * 86_400_000 },
  { value: "all", label: "All", ms: Infinity },
] as const;

const STATUS_FILTERS = [
  { value: "all", label: "All" },
  { value: "allowed", label: "Allowed" },
  { value: "blocked", label: "Blocked" },
] as const;

function isAllowed(e: QueryLogEntry) {
  return e.status === "returned";
}

function blockedLayers(e: QueryLogEntry) {
  const returned = new Set(e.returned_layers || []);
  return (e.requested_layers || []).filter((l) => !returned.has(l));
}

function download(name: string, content: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

function toCsv(rows: QueryLogEntry[]) {
  const head = ["id", "app_id", "purpose", "status", "requested_layers", "returned_layers", "blocked_layers", "reason", "created_at"];
  const esc = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const lines = rows.map((r) =>
    [r.id, r.app_id, r.purpose, r.status, (r.requested_layers || []).join("|"), (r.returned_layers || []).join("|"), blockedLayers(r).join("|"), r.reason, r.created_at]
      .map(esc)
      .join(","),
  );
  return [head.join(","), ...lines].join("\n");
}

function Detail({ e }: { e: QueryLogEntry }) {
  const returned = new Set(e.returned_layers || []);
  const blocked = blockedLayers(e);
  return (
    <div className="ml-12 mt-3 flex flex-col gap-3 rounded-xl border border-outline-variant bg-surface-container-low p-4 text-sm">
      <div>
        <div className="mb-1.5 text-xs font-bold uppercase tracking-wide text-outline">Scopes requested vs served</div>
        <div className="flex flex-wrap gap-1.5">
          {(e.requested_layers || []).length === 0 && <span className="text-xs text-on-surface-variant">None</span>}
          {(e.requested_layers || []).map((l) => (
            <span
              key={l}
              className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-semibold ${
                returned.has(l) ? "border-ok/20 bg-ok/5 text-ok" : "border-danger/20 bg-danger/5 text-danger line-through"
              }`}
            >
              {returned.has(l) ? <CheckCircle2 size={11} /> : <ShieldX size={11} />} {titleize(l)}
            </span>
          ))}
        </div>
      </div>

      {blocked.length > 0 && (
        <div className="flex items-start gap-2 text-xs text-warn">
          <ShieldX size={13} className="mt-0.5 shrink-0" />
          <span><strong>{blocked.length}</strong> field(s) blocked by your rules: {blocked.map(titleize).join(", ")}.</span>
        </div>
      )}

      <dl className="grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-4">
        <div>
          <dt className="text-xs uppercase tracking-wide text-outline">Result</dt>
          <dd className="font-semibold">{isAllowed(e) ? "Allowed" : "Denied"}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-outline">Purpose</dt>
          <dd className="font-semibold">{titleize(e.purpose) || "—"}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-outline">Request id</dt>
          <dd className="truncate font-mono text-xs">{e.id || "—"}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-outline">When</dt>
          <dd className="font-semibold">{relativeTime(e.created_at)}</dd>
        </div>
      </dl>

      {e.reason && <div className="text-xs text-on-surface-variant">Reason: {e.reason}</div>}
      {(e.feature_ids || []).length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-xs text-on-surface-variant">Features served:</span>
          {e.feature_ids!.map((f) => <Chip key={f}>{titleize(f)}</Chip>)}
        </div>
      )}
    </div>
  );
}

export default function Activity() {
  const logRes = useResource(async () => (await getQueryLog({ limit: 200 })).logs || [], previewQueryLog);
  const logs = logRes.data;

  const [app, setApp] = useState("all");
  const [range, setRange] = useState<string>("7");
  const [status, setStatus] = useState<string>("all");
  const [open, setOpen] = useState<string | null>(null);

  const apps = useMemo(() => [...new Set(logs.map((l) => l.app_id).filter(Boolean))] as string[], [logs]);

  const filtered = useMemo(() => {
    const rangeMs = DATE_RANGES.find((r) => r.value === range)?.ms ?? Infinity;
    const cutoff = rangeMs === Infinity ? 0 : Date.now() - rangeMs;
    return logs.filter((l) => {
      if (app !== "all" && l.app_id !== app) return false;
      if (status === "allowed" && !isAllowed(l)) return false;
      if (status === "blocked" && isAllowed(l) && blockedLayers(l).length === 0) return false;
      const ms = toMs(l.created_at) ?? 0;
      if (ms < cutoff) return false;
      return true;
    });
  }, [logs, app, range, status]);

  const stats = useMemo(() => {
    const allowed = logs.filter(isAllowed).length;
    return { total: logs.length, allowed, denied: logs.length - allowed, apps: apps.length };
  }, [logs, apps]);

  const selectClass = "rounded-lg border border-outline-variant bg-white px-3 py-1.5 text-sm font-semibold outline-none focus:border-primary";

  return (
    <>
      <PageHeader
        title="Activity & access log"
        subtitle="Every context request from an app — what it asked for, what it received, and what your rules blocked."
        action={
          <div className="flex gap-2">
            <Button variant="default" onClick={() => download(`personalayer-activity-${Date.now()}.json`, JSON.stringify(filtered, null, 2), "application/json")} disabled={filtered.length === 0}>
              <Download size={15} /> JSON
            </Button>
            <Button variant="default" onClick={() => download(`personalayer-activity-${Date.now()}.csv`, toCsv(filtered), "text/csv")} disabled={filtered.length === 0}>
              <Download size={15} /> CSV
            </Button>
          </div>
        }
      />

      {logRes.isPreview && <OfflineBanner onRetry={logRes.reload} />}

      <div className="flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat value={stats.total} label="Requests" />
          <Stat value={stats.allowed} label="Allowed" />
          <Stat value={stats.denied} label="Denied" hint="Blocked outright" />
          <Stat value={stats.apps} label="Apps" />
        </div>

        <Panel
          title="Timeline"
          action={
            <div className="flex flex-wrap items-center gap-2">
              <select className={selectClass} value={app} onChange={(e) => setApp(e.target.value)}>
                <option value="all">All apps</option>
                {apps.map((a) => <option key={a} value={a}>{titleize(a)}</option>)}
              </select>
              <select className={selectClass} value={range} onChange={(e) => setRange(e.target.value)}>
                {DATE_RANGES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
              </select>
              <select className={selectClass} value={status} onChange={(e) => setStatus(e.target.value)}>
                {STATUS_FILTERS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </div>
          }
        >
          {logRes.loading && logs.length === 0 ? (
            <LoadingState label="Loading activity…" />
          ) : logRes.error ? (
            <ErrorState message={logRes.error} onRetry={logRes.reload} />
          ) : filtered.length === 0 ? (
            <EmptyState
              icon={<ScrollText size={22} />}
              title={logs.length === 0 ? "No activity yet" : "Nothing matches these filters"}
              hint={logs.length === 0 ? "When an app requests your context, every request shows up here." : "Try widening the date range or clearing filters."}
            />
          ) : (
            <ul className="-my-1">
              {filtered.map((e, i) => {
                const allowed = isAllowed(e);
                const blocked = blockedLayers(e);
                const isOpen = open === (e.id ?? String(i));
                return (
                  <li key={e.id ?? i} className="border-b border-outline-variant py-3 last:border-none">
                    <button className="flex w-full items-center gap-3 text-left" onClick={() => setOpen(isOpen ? null : (e.id ?? String(i)))}>
                      <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-lg ${allowed ? "bg-ok/10 text-ok" : "bg-danger/10 text-danger"}`}>
                        {allowed ? <CheckCircle2 size={16} /> : <Ban size={16} />}
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-semibold">{titleize(e.app_id) || "App"}</span>
                          {e.purpose && <Pill tone="neutral">{titleize(e.purpose)}</Pill>}
                          {!allowed && <Pill tone="danger">Denied</Pill>}
                          {allowed && blocked.length > 0 && <Pill tone="warn">{blocked.length} blocked</Pill>}
                        </div>
                        <div className="truncate text-xs text-on-surface-variant">
                          {(e.returned_layers || []).length} of {(e.requested_layers || []).length} scopes served
                          {e.reason ? ` · ${e.reason}` : ""}
                        </div>
                      </div>
                      <span className="shrink-0 text-xs text-outline">{relativeTime(e.created_at)}</span>
                      {isOpen ? <ChevronUp size={15} className="shrink-0 text-outline" /> : <ChevronDown size={15} className="shrink-0 text-outline" />}
                    </button>
                    {isOpen && <Detail e={e} />}
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>
      </div>
    </>
  );
}
