// /app/devices — cross-device sync control center. Device management, pairing
// (requester + approver flows), snapshots, conflict resolution, and a sync
// audit timeline. Not the default homepage; reached from the app shell.

import { RefreshCw } from "lucide-react";
import { OfflineBanner, PageHeader } from "../components/states";
import { Button } from "../components/ui";
import { useBackend } from "../lib/backend";
import { useResource } from "../lib/useResource";
import { previewConflicts, previewDevices, previewSyncAudit } from "../lib/preview";
import { getSyncAudit, getSyncConflicts, getSyncDevices } from "../api";
import DevicesOverview from "../components/devices/DevicesOverview";
import PairNewDevice from "../components/devices/PairNewDevice";
import ApproveDevice from "../components/devices/ApproveDevice";
import SyncSnapshots from "../components/devices/SyncSnapshots";
import SyncConflicts from "../components/devices/SyncConflicts";
import SyncAuditLog from "../components/devices/SyncAuditLog";

export default function Devices() {
  const { online } = useBackend();
  const devicesRes = useResource(async () => (await getSyncDevices()).devices || [], previewDevices);
  const conflictsRes = useResource(async () => (await getSyncConflicts()).conflicts || [], previewConflicts);
  const auditRes = useResource(async () => (await getSyncAudit(100)).audit || [], previewSyncAudit);

  // Preview/offline: show mock data but disable destructive/sync actions.
  const offline = !online || devicesRes.isPreview;
  const disabled = offline;

  const reloadAll = () => {
    devicesRes.reload();
    conflictsRes.reload();
    auditRes.reload();
  };

  return (
    <>
      <PageHeader
        title="Devices & sync"
        subtitle="A security console for cross-device sync — pair devices, review trust, resolve conflicts, and audit every action. Sync transfers encrypted summaries, never raw activity."
        action={
          <Button variant="default" onClick={reloadAll}>
            <RefreshCw size={15} /> Refresh
          </Button>
        }
      />

      {offline && <OfflineBanner onRetry={reloadAll} />}

      <div className="flex flex-col gap-4">
        <DevicesOverview devicesRes={devicesRes} disabled={disabled} />

        {/* Pairing: requester + approver side by side on desktop. */}
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <PairNewDevice online={online} onChange={reloadAll} />
          <ApproveDevice online={online} onChange={reloadAll} />
        </div>

        <SyncSnapshots online={online} onChange={reloadAll} />

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <SyncConflicts conflictsRes={conflictsRes} disabled={disabled} />
          <SyncAuditLog auditRes={auditRes} />
        </div>
      </div>
    </>
  );
}
