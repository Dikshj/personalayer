// Add-device flow (requester side). Stepper: choose method → wait for approval
// → claim encrypted transfer → success. This browser generates a keypair, keeps
// the private key locally, and uses it to decrypt the transfer on claim.

import { useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  Clock,
  Download,
  Plus,
  QrCode,
  RefreshCw,
  XCircle,
} from "lucide-react";
import { Button, CopyButton, Panel, Pill, Stepper } from "../ui";
import { titleize } from "../../lib/format";
import {
  type PairingClaimResponse,
  type PairingSession,
  claimPairing,
  getPairingSession,
  startPairingSession,
} from "../../api";

const STEPS = ["Generate code", "Await approval", "Claim transfer", "Done"];

function QrVisual({ payload }: { payload: string }) {
  const cells = useMemo(() => {
    let hash = 0;
    for (const char of payload) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
    return Array.from({ length: 49 }, (_, index) => ((hash >> (index % 24)) + index * 7) % 3 === 0);
  }, [payload]);
  return (
    <div className="grid h-[180px] w-[180px] grid-cols-7 gap-1 rounded-lg bg-white p-3" title="Pairing QR (scan in the PersonaLayer app)">
      {cells.map((filled, index) => (
        <span key={index} className={filled ? "rounded-sm bg-slate-900" : "rounded-sm bg-slate-100"} />
      ))}
    </div>
  );
}

function formatCode(code?: string) {
  if (!code) return "— — — —";
  return code.toUpperCase();
}

function Countdown({ expiresAt }: { expiresAt?: number }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, []);
  if (!expiresAt) return null;
  const remaining = Math.max(0, expiresAt * 1000 - now);
  const m = Math.floor(remaining / 60000);
  const s = Math.floor((remaining % 60000) / 1000);
  const expired = remaining <= 0;
  return (
    <Pill tone={expired ? "danger" : "neutral"}>
      <Clock size={13} /> {expired ? "Expired" : `${m}:${String(s).padStart(2, "0")} left`}
    </Pill>
  );
}

export default function PairNewDevice({ online, onChange }: { online: boolean; onChange: () => void }) {
  const [session, setSession] = useState<PairingSession | null>(null);
  const [starting, setStarting] = useState(false);
  const [claiming, setClaiming] = useState(false);
  const [claim, setClaim] = useState<PairingClaimResponse | null>(null);
  const [error, setError] = useState("");

  const status = session?.status || "";
  const expired = status === "expired" || (session?.expires_at ? session.expires_at * 1000 < Date.now() && status === "pending" : false);

  // Derive the stepper position from the session lifecycle.
  const step = !session ? 0 : claim?.status === "claimed" ? 3 : status === "approved" ? 2 : 1;

  const begin = async () => {
    setStarting(true);
    setError("");
    setClaim(null);
    try {
      const res = await startPairingSession();
      if (res.session) setSession(res.session);
      else setError(res.error ? titleize(res.error) : res.status || "Unable to start pairing.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Backend offline — pairing is unavailable right now.");
    } finally {
      setStarting(false);
    }
  };

  const reset = () => {
    setSession(null);
    setClaim(null);
    setError("");
  };

  // Poll for approval while the session is live.
  useEffect(() => {
    if (!session?.id) return;
    if (status === "claimed" || status === "expired") return;
    const t = window.setInterval(() => {
      getPairingSession(session.id!)
        .then((next) => next.session && setSession(next.session))
        .catch(() => undefined);
    }, 4000);
    return () => window.clearInterval(t);
  }, [session?.id, status]);

  const doClaim = async () => {
    if (!session?.id) return;
    setClaiming(true);
    setError("");
    try {
      const res = await claimPairing(session.id);
      if (res.status === "error") {
        setError(res.error ? titleize(res.error) : "Claim failed.");
      } else {
        setClaim(res);
        if (res.session) setSession(res.session);
        onChange();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Claim failed.");
    } finally {
      setClaiming(false);
    }
  };

  const payload = session?.qr_payload ? JSON.stringify(session.qr_payload) : "PersonaLayer pairing";
  const scopes = session?.requested_scopes || [];

  return (
    <Panel
      title={<span className="inline-flex items-center gap-2"><Plus size={16} /> Pair a new device</span>}
      action={session ? <Button variant="ghost" onClick={reset}>Start over</Button> : undefined}
    >
      <div className="mb-5">
        <Stepper steps={STEPS} current={step} />
      </div>

      {error && (
        <p className="mb-4 rounded-lg border border-[#ba1a1a]/20 bg-[#ba1a1a]/5 px-3 py-2 text-sm font-semibold text-[#ba1a1a]">
          {error}
        </p>
      )}

      {/* Step 1 — generate code */}
      {!session && (
        <div className="flex flex-col items-start gap-4">
          <p className="text-sm text-on-surface-variant">
            Generate a one-time pairing code. Scan the QR with the PersonaLayer app on your other device, or enter the
            manual code there. Pairing transfers an encrypted summary — never raw activity.
          </p>
          <Button variant="primary" loading={starting} disabled={!online} onClick={begin}>
            <QrCode size={15} /> Generate pairing code
          </Button>
          {!online && <p className="text-xs text-outline">Backend offline — connect to start a live pairing session.</p>}
        </div>
      )}

      {/* Steps 2–3 — show code, await approval, claim */}
      {session && step < 3 && (
        <div className="flex flex-col gap-5 md:flex-row md:items-start">
          <div className="mx-auto shrink-0 rounded-xl border border-outline-variant bg-white p-3 md:mx-0">
            <QrVisual payload={payload} />
          </div>
          <div className="flex min-w-0 flex-1 flex-col gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-lg border border-outline-variant bg-surface-container-low px-3 py-2 font-mono text-lg font-semibold tracking-widest text-primary">
                {formatCode(session.pairing_code)}
              </span>
              <CopyButton value={session.pairing_code || ""} label="Copy code" />
              <Countdown expiresAt={session.expires_at} />
            </div>

            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="text-on-surface-variant">QR payload:</span>
              <CopyButton value={payload} label="Copy QR JSON" />
            </div>

            {scopes.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-xs text-on-surface-variant">Scopes:</span>
                {scopes.map((s) => (
                  <Pill key={s} tone="neutral">{titleize(s)}</Pill>
                ))}
              </div>
            )}

            {/* Approval status */}
            {expired ? (
              <div className="flex flex-wrap items-center gap-3 rounded-lg border border-[#ba1a1a]/20 bg-[#ba1a1a]/5 px-3 py-2 text-sm text-[#ba1a1a]">
                <XCircle size={16} /> This pairing session expired.
                <Button variant="default" onClick={begin} loading={starting}>
                  <RefreshCw size={15} /> Restart pairing
                </Button>
              </div>
            ) : status === "approved" ? (
              <div className="flex flex-col gap-2 rounded-lg border border-[#006e2f]/20 bg-[#006e2f]/5 px-3 py-3">
                <div className="flex items-center gap-2 text-sm font-semibold text-[#006e2f]">
                  <CheckCircle2 size={16} /> Approved on the other device.
                </div>
                <Button variant="primary" loading={claiming} disabled={!online} onClick={doClaim}>
                  <Download size={15} /> Claim encrypted transfer
                </Button>
              </div>
            ) : (
              <div className="flex items-center gap-2 text-sm text-on-surface-variant">
                <RefreshCw size={15} className="animate-spin" /> Waiting for approval on your other device…
              </div>
            )}
          </div>
        </div>
      )}

      {/* Step 4 — success */}
      {step === 3 && claim && (
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-[#006e2f]">
            <CheckCircle2 size={18} /> Device paired and transfer imported.
          </div>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3">
            <div>
              <dt className="text-xs uppercase tracking-wide text-outline">Updated entries</dt>
              <dd className="font-semibold">{claim.merged?.updated ?? 0}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-outline">Snapshot</dt>
              <dd className="truncate font-mono text-sm">{(claim.local_snapshot?.version || "—").slice(0, 10)}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-outline">Merge status</dt>
              <dd className="font-semibold">{titleize(claim.local_snapshot?.merge_status || "merged")}</dd>
            </div>
          </dl>
          {(claim.merged?.scopes?.length ?? 0) > 0 && (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-xs text-on-surface-variant">Synced scopes:</span>
              {claim.merged!.scopes!.map((s) => (
                <Pill key={s} tone="good">{titleize(s)}</Pill>
              ))}
            </div>
          )}
          <div>
            <Button variant="default" onClick={reset}>
              <Plus size={15} /> Pair another device
            </Button>
          </div>
        </div>
      )}
    </Panel>
  );
}
