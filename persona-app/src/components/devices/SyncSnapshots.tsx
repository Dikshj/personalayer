// Sync snapshots — create an encrypted snapshot of this device's summary,
// import an encrypted snapshot from another device, and compact old snapshots.

import { useState } from "react";
import { Archive, Camera, Download, Layers, Upload } from "lucide-react";
import { Button, CopyButton, Panel, Pill } from "../ui";
import { relativeTime, titleize } from "../../lib/format";
import {
  type SyncSnapshot,
  compactSnapshots,
  createSyncSnapshot,
  importSyncSnapshot,
} from "../../api";

export default function SyncSnapshots({ online, onChange }: { online: boolean; onChange: () => void }) {
  const [creating, setCreating] = useState(false);
  const [importing, setImporting] = useState(false);
  const [compacting, setCompacting] = useState(false);
  const [latest, setLatest] = useState<SyncSnapshot | null>(null);
  const [encryptedBlob, setEncryptedBlob] = useState<string>("");
  const [note, setNote] = useState<{ tone: "good" | "warn" | "danger"; text: string } | null>(null);

  const [remoteDeviceId, setRemoteDeviceId] = useState("");
  const [importBlob, setImportBlob] = useState("");

  const create = async () => {
    setCreating(true);
    setNote(null);
    try {
      const res = await createSyncSnapshot();
      if (res.status === "created" && res.snapshot) {
        setLatest(res.snapshot);
        setEncryptedBlob(res.encrypted_blob || "");
        setNote({ tone: "good", text: `Snapshot ${res.snapshot.version?.slice(0, 10)} created.` });
      } else {
        setNote({ tone: "danger", text: res.error ? titleize(res.error) : "Could not create snapshot." });
      }
    } catch (err) {
      setNote({ tone: "danger", text: err instanceof Error ? err.message : "Could not create snapshot." });
    } finally {
      setCreating(false);
    }
  };

  const doImport = async () => {
    setImporting(true);
    setNote(null);
    try {
      const res = await importSyncSnapshot({ remote_device_id: remoteDeviceId.trim(), encrypted_blob: importBlob.trim() });
      if (res.status === "merged") {
        setNote({ tone: "good", text: `Merged ${res.merged?.updated ?? 0} entries from ${remoteDeviceId.trim() || "remote"}.` });
        setImportBlob("");
        onChange();
      } else if (res.status === "conflict") {
        setNote({ tone: "warn", text: "Import created a conflict — resolve it in Conflicts below." });
        onChange();
      } else {
        setNote({ tone: "danger", text: res.error ? titleize(res.error) : "Import failed." });
      }
    } catch (err) {
      setNote({ tone: "danger", text: err instanceof Error ? err.message : "Import failed." });
    } finally {
      setImporting(false);
    }
  };

  const compact = async () => {
    setCompacting(true);
    setNote(null);
    try {
      const res = await compactSnapshots(5);
      setNote({ tone: "good", text: `Compacted — removed ${res.deleted ?? 0} old snapshot(s).` });
    } catch (err) {
      setNote({ tone: "danger", text: err instanceof Error ? err.message : "Compaction failed." });
    } finally {
      setCompacting(false);
    }
  };

  const canImport = remoteDeviceId.trim().length > 0 && importBlob.trim().length > 0 && online;

  return (
    <Panel title={<span className="inline-flex items-center gap-2"><Layers size={16} /> Sync snapshots</span>}>
      {note && (
        <p
          className={`mb-4 rounded-lg border px-3 py-2 text-sm font-semibold ${
            note.tone === "good"
              ? "border-[#006e2f]/20 bg-[#006e2f]/5 text-[#006e2f]"
              : note.tone === "warn"
                ? "border-[#fea619]/30 bg-[#fff8ec] text-[#9a5b00]"
                : "border-[#ba1a1a]/20 bg-[#ba1a1a]/5 text-[#ba1a1a]"
          }`}
        >
          {note.text}
        </p>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Create + compact */}
        <div className="flex flex-col gap-3 rounded-xl border border-outline-variant p-4">
          <div className="font-semibold">This device</div>
          {latest ? (
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
              <div>
                <dt className="text-xs uppercase tracking-wide text-outline">Latest version</dt>
                <dd className="font-mono">{latest.version?.slice(0, 12) || "—"}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-outline">Created</dt>
                <dd>{relativeTime(latest.created_at)}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-outline">Merge status</dt>
                <dd>{titleize(latest.merge_status || "local")}</dd>
              </div>
            </dl>
          ) : (
            <p className="text-sm text-on-surface-variant">No snapshot created in this session yet.</p>
          )}
          <div className="flex flex-wrap gap-2">
            <Button variant="primary" loading={creating} disabled={!online} onClick={create}>
              <Camera size={15} /> Create snapshot
            </Button>
            {encryptedBlob && <CopyButton value={encryptedBlob} label="Copy encrypted blob" />}
            <Button variant="default" loading={compacting} disabled={!online} onClick={compact}>
              <Archive size={15} /> Compact old
            </Button>
          </div>
          {encryptedBlob && (
            <p className="text-xs text-outline">
              Copy the encrypted blob to import it on another device. It stays end-to-end encrypted.
            </p>
          )}
        </div>

        {/* Import */}
        <div className="flex flex-col gap-3 rounded-xl border border-outline-variant p-4">
          <div className="flex items-center justify-between">
            <div className="font-semibold">Import encrypted snapshot</div>
            <Pill tone="neutral"><Download size={13} /> Receive</Pill>
          </div>
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-semibold text-on-surface-variant">Remote device ID</span>
            <input
              value={remoteDeviceId}
              onChange={(e) => setRemoteDeviceId(e.target.value)}
              placeholder="web-… / iphone-…"
              className="w-full rounded-lg border border-outline-variant bg-white px-3 py-2 text-sm outline-none focus:border-primary"
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-semibold text-on-surface-variant">Encrypted blob</span>
            <textarea
              value={importBlob}
              onChange={(e) => setImportBlob(e.target.value)}
              placeholder="Paste the encrypted snapshot blob"
              rows={3}
              className="w-full rounded-lg border border-outline-variant bg-white px-3 py-2 font-mono text-xs outline-none focus:border-primary"
            />
          </label>
          <div>
            <Button variant="default" loading={importing} disabled={!canImport} onClick={doImport}>
              <Upload size={15} /> Import &amp; merge
            </Button>
          </div>
        </div>
      </div>
    </Panel>
  );
}
