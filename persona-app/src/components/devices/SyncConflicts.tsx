// Sync conflicts — list open conflicts and resolve each by accepting the remote
// snapshot, keeping the local one, or ignoring the conflict.

import { useState } from "react";
import { GitMerge, ShieldCheck } from "lucide-react";
import { EmptyState, ErrorState, LoadingState } from "../states";
import { Button, Panel, Pill } from "../ui";
import type { Resource } from "../../lib/useResource";
import { relativeTime, shortHash, titleize } from "../../lib/format";
import { type SyncConflict, resolveSyncConflict } from "../../api";

type Action = "accept_remote" | "keep_local" | "ignore";

function ConflictRow({
  conflict,
  disabled,
  onResolved,
  onError,
}: {
  conflict: SyncConflict;
  disabled: boolean;
  onResolved: () => void;
  onError: (m: string) => void;
}) {
  const [busy, setBusy] = useState<Action | null>(null);
  const id = conflict.id || "";

  const act = async (action: Action) => {
    setBusy(action);
    onError("");
    try {
      const res = await resolveSyncConflict(id, action);
      if (res.error) onError(titleize(res.error));
    } catch (err) {
      onError(err instanceof Error ? err.message : "Could not resolve conflict.");
    } finally {
      setBusy(null);
      onResolved();
    }
  };

  return (
    <li className="flex flex-col gap-3 rounded-xl border border-outline-variant p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <GitMerge size={16} className="text-[#9a5b00]" />
          <span className="font-semibold">{titleize(conflict.reason || "Version conflict")}</span>
        </div>
        <Pill tone="warn">{titleize(conflict.status || "open")}</Pill>
      </div>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs sm:grid-cols-3">
        <div>
          <dt className="uppercase tracking-wide text-outline">Local</dt>
          <dd className="font-mono">{shortHash(conflict.local_version, 10)}</dd>
        </div>
        <div>
          <dt className="uppercase tracking-wide text-outline">Remote</dt>
          <dd className="font-mono">{shortHash(conflict.remote_version, 10)}</dd>
        </div>
        <div>
          <dt className="uppercase tracking-wide text-outline">Detected</dt>
          <dd>{relativeTime(conflict.created_at)}</dd>
        </div>
      </dl>
      <div className="flex flex-wrap gap-2">
        <Button variant="primary" loading={busy === "accept_remote"} disabled={disabled} onClick={() => act("accept_remote")}>
          Accept remote
        </Button>
        <Button variant="default" loading={busy === "keep_local"} disabled={disabled} onClick={() => act("keep_local")}>
          Keep local
        </Button>
        <Button variant="ghost" loading={busy === "ignore"} disabled={disabled} onClick={() => act("ignore")}>
          Ignore
        </Button>
      </div>
    </li>
  );
}

export default function SyncConflicts({
  conflictsRes,
  disabled,
}: {
  conflictsRes: Resource<SyncConflict[]>;
  disabled: boolean;
}) {
  const [error, setError] = useState("");
  const conflicts = conflictsRes.data;

  return (
    <Panel
      title={<span className="inline-flex items-center gap-2"><GitMerge size={16} /> Conflicts</span>}
      action={<Pill tone={conflicts.length ? "warn" : "good"}>{conflicts.length} open</Pill>}
    >
      {error && (
        <p className="mb-3 rounded-lg border border-[#ba1a1a]/20 bg-[#ba1a1a]/5 px-3 py-2 text-sm font-semibold text-[#ba1a1a]">
          {error}
        </p>
      )}
      {conflictsRes.loading && conflicts.length === 0 ? (
        <LoadingState label="Loading conflicts…" />
      ) : conflictsRes.error ? (
        <ErrorState message={conflictsRes.error} onRetry={conflictsRes.reload} />
      ) : conflicts.length === 0 ? (
        <EmptyState icon={<ShieldCheck size={22} />} title="No open conflicts" hint="Snapshots are merging cleanly across your devices." />
      ) : (
        <ul className="flex flex-col gap-3">
          {conflicts.map((c) => (
            <ConflictRow key={c.id} conflict={c} disabled={disabled} onResolved={conflictsRes.reload} onError={setError} />
          ))}
        </ul>
      )}
    </Panel>
  );
}
