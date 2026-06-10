// /app/devices — device pairing (QR + manual code) and paired devices.
// Relocated from the former default homepage into the app shell.

import { useEffect, useMemo, useState } from "react";
import { RefreshCw, Smartphone } from "lucide-react";
import { EmptyState, LoadingState, OfflineBanner, PageHeader } from "../components/states";
import { Button, ConfirmButton, Panel, Pill } from "../components/ui";
import { useResource } from "../lib/useResource";
import { useBackend } from "../lib/backend";
import { relativeTime, titleize } from "../lib/format";
import { previewDevices } from "../lib/preview";
import { type PairingSession, getPairingSession, getSyncDevices, revokeSyncDevice, startPairingSession } from "../api";

function QrVisual({ payload }: { payload: string }) {
  const cells = useMemo(() => {
    let hash = 0;
    for (const char of payload) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
    return Array.from({ length: 49 }, (_, index) => ((hash >> (index % 24)) + index * 7) % 3 === 0);
  }, [payload]);

  return (
    <div className="grid h-[200px] w-[200px] grid-cols-7 gap-1 rounded-lg bg-white p-3" title={payload}>
      {cells.map((filled, index) => (
        <span key={index} className={filled ? "rounded-sm bg-slate-900" : "rounded-sm bg-slate-100"} />
      ))}
    </div>
  );
}

function formatCode(code?: string) {
  const raw = (code || "A7B2X9").toUpperCase().replace(/[^A-Z0-9]/g, "").padEnd(6, "•").slice(0, 6);
  return `${raw.slice(0, 2)}-${raw.slice(2, 4)}-${raw.slice(4, 6)}`;
}

export default function Devices() {
  const { online } = useBackend();
  const devicesRes = useResource(async () => (await getSyncDevices()).devices || [], previewDevices);
  const [session, setSession] = useState<PairingSession | null>(null);
  const [pairing, setPairing] = useState(false);
  const [pairError, setPairError] = useState("");

  const beginPairing = async () => {
    setPairing(true);
    setPairError("");
    try {
      const data = await startPairingSession();
      if (data.session) setSession(data.session);
      else setPairError(data.status || "Unable to start pairing");
    } catch {
      setPairError("Backend offline — pairing is unavailable right now.");
    } finally {
      setPairing(false);
    }
  };

  // Poll the active pairing session for status changes.
  useEffect(() => {
    if (!session?.id) return;
    const timer = window.setInterval(() => {
      getPairingSession(session.id!)
        .then((next) => next.session && setSession(next.session))
        .catch(() => undefined);
    }, 5000);
    return () => window.clearInterval(timer);
  }, [session?.id]);

  const payload = session?.qr_payload ? JSON.stringify(session.qr_payload) : "PersonaLayer pairing — start to generate";
  const devices = devicesRes.data;

  return (
    <>
      <PageHeader
        title="Devices"
        subtitle="Pair a device to securely sync your account. Pairing never transmits behavioral data."
      />

      {devicesRes.isPreview && <OfflineBanner onRetry={devicesRes.reload} />}

      <div className="flex flex-col gap-4">
        <Panel title="Pair a new device">
          <div className="flex flex-col gap-6 md:flex-row md:items-start">
            <div className="mx-auto shrink-0 rounded-xl border border-outline-variant bg-white p-3 md:mx-0">
              <QrVisual payload={payload} />
            </div>
            <div className="flex flex-1 flex-col items-start gap-3">
              <p className="text-sm text-on-surface-variant">
                Start a pairing session, then scan the code with the PersonaLayer mobile app or enter the manual code.
              </p>
              <div className="flex items-center gap-3">
                <span className="rounded-lg border border-outline-variant bg-surface-container-low px-3 py-2 font-mono text-lg font-semibold tracking-widest text-primary">
                  {formatCode(session?.pairing_code)}
                </span>
                {session?.status && <Pill tone="info">{titleize(session.status)}</Pill>}
              </div>
              <Button variant="primary" onClick={beginPairing} loading={pairing} disabled={!online && !session}>
                <RefreshCw size={15} /> {session ? "Refresh code" : "Start pairing"}
              </Button>
              {pairError && <p className="text-sm font-semibold text-[#ba1a1a]">{pairError}</p>}
              {!online && <p className="text-xs text-outline">Backend offline — connect to start a live pairing session.</p>}
            </div>
          </div>
        </Panel>

        <Panel title="Paired devices" action={<span className="text-xs text-on-surface-variant">{devices.length} device(s)</span>}>
          {devicesRes.loading && devices.length === 0 ? (
            <LoadingState label="Loading devices…" />
          ) : devices.length === 0 ? (
            <EmptyState icon={<Smartphone size={22} />} title="No devices paired" hint="Start a pairing session above to add your first device." />
          ) : (
            <ul className="-my-1">
              {devices.map((d) => (
                <li key={d.device_id} className="flex items-center justify-between gap-4 border-b border-outline-variant py-3 last:border-none">
                  <div className="flex items-center gap-3">
                    <span className="grid h-9 w-9 place-items-center rounded-xl bg-surface-container text-on-surface-variant">
                      <Smartphone size={18} />
                    </span>
                    <div>
                      <div className="font-semibold">{d.device_name || titleize(d.device_id)}</div>
                      <div className="text-xs text-on-surface-variant">
                        {titleize(d.platform || "device")} · paired {relativeTime(d.created_at)}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <Pill tone={d.status === "trusted" ? "good" : "warn"}>{titleize(d.status || "pending")}</Pill>
                    <ConfirmButton
                      confirmLabel="Unpair"
                      onConfirm={async () => {
                        if (d.device_id) await revokeSyncDevice(d.device_id);
                        devicesRes.reload();
                      }}
                    >
                      Unpair
                    </ConfirmButton>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </>
  );
}
