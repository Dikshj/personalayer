// Sync activity timeline — pairing, snapshots, trust/revoke, key rotation, and
// conflict resolution events from the sync audit log.

import {
  Archive,
  type LucideIcon,
  GitMerge,
  KeyRound,
  Link2,
  RefreshCw,
  RotateCcw,
  ScrollText,
  ShieldCheck,
  ShieldX,
} from "lucide-react";
import { EmptyState, ErrorState, LoadingState } from "../states";
import { Button, Panel } from "../ui";
import type { Resource } from "../../lib/useResource";
import { relativeTime, titleize } from "../../lib/format";
import type { SyncAuditEvent } from "../../api";

function iconFor(action: string): { icon: LucideIcon; tone: string } {
  const a = action.toLowerCase();
  if (a.includes("pairing")) return { icon: Link2, tone: "text-primary" };
  if (a.includes("snapshot") || a.includes("compact")) return { icon: Archive, tone: "text-on-surface-variant" };
  if (a.includes("rotate") || a.includes("key")) return { icon: RotateCcw, tone: "text-primary" };
  if (a.includes("conflict")) return { icon: GitMerge, tone: "text-warn" };
  if (a.includes("revoke")) return { icon: ShieldX, tone: "text-danger" };
  if (a.includes("trust")) return { icon: ShieldCheck, tone: "text-ok" };
  return { icon: KeyRound, tone: "text-on-surface-variant" };
}

export default function SyncAuditLog({ auditRes }: { auditRes: Resource<SyncAuditEvent[]> }) {
  const events = auditRes.data;

  return (
    <Panel
      title={<span className="inline-flex items-center gap-2"><ScrollText size={16} /> Sync activity</span>}
      action={
        <Button variant="default" onClick={auditRes.reload}>
          <RefreshCw size={15} /> Refresh
        </Button>
      }
    >
      {auditRes.loading && events.length === 0 ? (
        <LoadingState label="Loading sync activity…" />
      ) : auditRes.error ? (
        <ErrorState message={auditRes.error} onRetry={auditRes.reload} />
      ) : events.length === 0 ? (
        <EmptyState icon={<ScrollText size={22} />} title="No sync activity yet" hint="Pairing, snapshots, and device changes will appear here." />
      ) : (
        <ul className="-my-1">
          {events.map((e, i) => {
            const { icon: Icon, tone } = iconFor(e.action || "");
            return (
              <li key={e.id ?? i} className="flex items-center gap-3 border-b border-outline-variant py-3 last:border-none">
                <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-surface-container-low ${tone}`}>
                  <Icon size={16} />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="font-semibold">{titleize(e.action) || "Event"}</div>
                  {e.device_id && <div className="truncate text-xs text-on-surface-variant">{e.device_id}</div>}
                </div>
                <span className="shrink-0 text-xs text-outline">{relativeTime(e.created_at)}</span>
              </li>
            );
          })}
        </ul>
      )}
    </Panel>
  );
}
