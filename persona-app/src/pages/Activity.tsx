// /app/activity — recent context accesses, app requests, privacy drops, sync
// activity, and refresh status, drawn from the control-center audit log.

import { useMemo, useState } from "react";
import {
  Activity as ActivityIcon,
  ArrowDownUp,
  type LucideIcon,
  RefreshCw,
  Search,
  ShieldX,
  SlidersHorizontal,
  Trash2,
} from "lucide-react";
import { EmptyState, ErrorState, LoadingState, OfflineBanner, PageHeader } from "../components/states";
import { Button, Panel, Pill, Stat } from "../components/ui";
import { useResource } from "../lib/useResource";
import { relativeTime, titleize } from "../lib/format";
import { previewAudit } from "../lib/preview";
import { type AuditEntry, getAuditLog } from "../api";

type Kind = "access" | "drop" | "sync" | "change" | "other";

function classify(action: string): { kind: Kind; icon: LucideIcon; tone: "good" | "warn" | "danger" | "info" | "neutral" } {
  const a = action.toLowerCase();
  if (a.includes("drop") || a.includes("privacy")) return { kind: "drop", icon: ShieldX, tone: "danger" };
  if (a.includes("sync") || a.includes("integration")) return { kind: "sync", icon: ArrowDownUp, tone: "info" };
  if (a.includes("access") || a.includes("bundle") || a.includes("query") || a.includes("search")) return { kind: "access", icon: Search, tone: "good" };
  if (a.includes("revoke") || a.includes("delete") || a.includes("remove")) return { kind: "change", icon: Trash2, tone: "warn" };
  if (a.includes("edit") || a.includes("hidden") || a.includes("update") || a.includes("boundary")) return { kind: "change", icon: SlidersHorizontal, tone: "neutral" };
  return { kind: "other", icon: ActivityIcon, tone: "neutral" };
}

const FILTERS: { value: Kind | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "access", label: "Access" },
  { value: "drop", label: "Privacy drops" },
  { value: "sync", label: "Sync" },
  { value: "change", label: "Changes" },
];

export default function Activity() {
  const auditRes = useResource(async () => (await getAuditLog(100)).logs || [], previewAudit);
  const [filter, setFilter] = useState<Kind | "all">("all");

  const logs = auditRes.data;

  const counts = useMemo(() => {
    const c = { access: 0, drop: 0, sync: 0, change: 0 };
    logs.forEach((l) => {
      const k = classify(l.action || "").kind;
      if (k === "access") c.access += 1;
      else if (k === "drop") c.drop += 1;
      else if (k === "sync") c.sync += 1;
      else if (k === "change") c.change += 1;
    });
    return c;
  }, [logs]);

  const filtered = logs.filter((l) => filter === "all" || classify(l.action || "").kind === filter);

  const detailText = (e: AuditEntry) => {
    const d = e.details || {};
    const intent = d.intent || d.reason || d.query || d.status;
    return [e.target_id, intent].filter(Boolean).map(String).map(titleize).join(" · ");
  };

  return (
    <>
      <PageHeader
        title="Activity & audit log"
        subtitle="Every context access, request, privacy drop, and change — in one timeline."
        action={
          <Button variant="default" onClick={auditRes.reload}>
            <RefreshCw size={15} /> Refresh
          </Button>
        }
      />

      {auditRes.isPreview && <OfflineBanner onRetry={auditRes.reload} />}

      <div className="flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat value={counts.access} label="Context accesses" />
          <Stat value={counts.drop} label="Privacy drops" hint="Blocked" />
          <Stat value={counts.sync} label="Syncs" />
          <Stat value={counts.change} label="Changes" />
        </div>

        <Panel
          title="Timeline"
          action={
            <div className="flex flex-wrap gap-1.5">
              {FILTERS.map((f) => (
                <button
                  key={f.value}
                  onClick={() => setFilter(f.value)}
                  className={`rounded-full border px-2.5 py-1 text-xs font-semibold transition ${
                    filter === f.value ? "border-primary bg-primary/10 text-primary" : "border-outline-variant text-on-surface-variant hover:bg-surface-container-low"
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>
          }
        >
          {auditRes.loading && logs.length === 0 ? (
            <LoadingState label="Loading activity…" />
          ) : auditRes.error ? (
            <ErrorState message={auditRes.error} onRetry={auditRes.reload} />
          ) : filtered.length === 0 ? (
            <EmptyState icon={<ActivityIcon size={22} />} title="No activity yet" hint="Activity appears as apps request context and you make changes." />
          ) : (
            <ul className="-my-1">
              {filtered.map((e, i) => {
                const meta = classify(e.action || "");
                const Icon = meta.icon;
                const detail = detailText(e);
                return (
                  <li key={e.id ?? i} className="flex items-center gap-3 border-b border-outline-variant py-3 last:border-none">
                    <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-surface-container-low text-on-surface-variant">
                      <Icon size={16} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-semibold">{titleize(e.action) || "Event"}</span>
                        {e.target_type && <Pill tone="neutral">{titleize(e.target_type)}</Pill>}
                      </div>
                      {detail && <div className="truncate text-xs text-on-surface-variant">{detail}</div>}
                    </div>
                    <span className="shrink-0 text-xs text-outline">{relativeTime(e.created_at)}</span>
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
