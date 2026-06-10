// Approve-incoming-device flow (approver side). Enter a manual pairing code (or
// paste the QR payload JSON for desktop testing), review the requested scopes,
// confirm, then approve. The one-time recovery token is shown exactly once and
// cleared when leaving this screen.

import { useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Inbox,
  KeyRound,
  ShieldCheck,
} from "lucide-react";
import { Button, CopyButton, Panel, Pill } from "../ui";
import { titleize } from "../../lib/format";
import { type PairingApprovalResponse, approvePairing } from "../../api";

type Parsed = { sessionId?: string; pairingCode?: string; scopes?: string[] };

function parseQr(raw: string): Parsed | null {
  try {
    const obj = JSON.parse(raw) as Record<string, unknown>;
    return {
      sessionId: (obj.session_id || obj.id) as string | undefined,
      pairingCode: obj.pairing_code as string | undefined,
      scopes: Array.isArray(obj.requested_scopes) ? (obj.requested_scopes as string[]) : undefined,
    };
  } catch {
    return null;
  }
}

export default function ApproveDevice({ online, onChange }: { online: boolean; onChange: () => void }) {
  const [code, setCode] = useState("");
  const [qr, setQr] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [approving, setApproving] = useState(false);
  const [result, setResult] = useState<PairingApprovalResponse | null>(null);
  const [error, setError] = useState("");

  const parsed = qr.trim() ? parseQr(qr.trim()) : null;
  const qrInvalid = qr.trim().length > 0 && !parsed;
  const effectiveCode = (parsed?.pairingCode || code).trim();
  const effectiveSession = parsed?.sessionId?.trim() || "";
  const previewScopes = parsed?.scopes || result?.session?.requested_scopes || [];
  const canSubmit = (Boolean(effectiveCode) || Boolean(effectiveSession)) && online;

  const approve = async () => {
    setApproving(true);
    setError("");
    try {
      const res = await approvePairing({ pairingCode: effectiveCode, sessionId: effectiveSession });
      if (res.status === "approved") {
        setResult(res);
        onChange();
      } else {
        setError(res.error ? titleize(res.error) : res.status === "expired" ? "This pairing code has expired." : "Approval failed.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approval failed.");
    } finally {
      setApproving(false);
      setConfirming(false);
    }
  };

  const dismiss = () => {
    // Clear the recovery token from memory — it is never shown again.
    setResult(null);
    setCode("");
    setQr("");
    setError("");
  };

  // Success: show the recovery token once.
  if (result) {
    return (
      <Panel title={<span className="inline-flex items-center gap-2"><CheckCircle2 size={16} className="text-[#006e2f]" /> Device approved</span>}>
        <p className="mb-4 text-sm text-on-surface-variant">
          The requesting device can now claim its encrypted transfer.
          {result.session?.requester_device_name ? ` (${result.session.requester_device_name})` : ""}
        </p>
        <div className="rounded-xl border border-[#fea619]/40 bg-[#fff8ec] p-4">
          <div className="mb-2 flex items-center gap-2 text-sm font-bold text-[#9a5b00]">
            <AlertTriangle size={16} /> Recovery token — shown once
          </div>
          <p className="mb-3 text-xs text-[#9a5b00]">
            Store this somewhere safe. It can recover or re-key this pairing later. You will not be able to see it again
            after you leave this screen.
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <code className="min-w-0 flex-1 break-all rounded-lg border border-outline-variant bg-white px-3 py-2 font-mono text-xs">
              {result.recovery_token || "(no token returned)"}
            </code>
            {result.recovery_token && <CopyButton value={result.recovery_token} label="Copy token" />}
          </div>
        </div>
        <div className="mt-4">
          <Button variant="primary" onClick={dismiss}>
            <ShieldCheck size={15} /> I’ve saved it — done
          </Button>
        </div>
      </Panel>
    );
  }

  return (
    <Panel title={<span className="inline-flex items-center gap-2"><Inbox size={16} /> Approve an incoming device</span>}>
      <p className="mb-4 text-sm text-on-surface-variant">
        On this trusted device, approve a new device that is requesting to pair. Enter its pairing code, or paste the QR
        payload JSON.
      </p>

      {error && (
        <p className="mb-4 rounded-lg border border-[#ba1a1a]/20 bg-[#ba1a1a]/5 px-3 py-2 text-sm font-semibold text-[#ba1a1a]">
          {error}
        </p>
      )}

      <div className="flex flex-col gap-4">
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-semibold">Pairing code</span>
          <input
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="ABCD-1234"
            disabled={Boolean(parsed?.pairingCode)}
            className="w-full rounded-lg border border-outline-variant bg-white px-3 py-2 font-mono uppercase tracking-widest outline-none focus:border-primary disabled:opacity-50"
          />
        </label>

        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-semibold">
            QR payload JSON <span className="font-normal text-outline">(optional — for desktop testing)</span>
          </span>
          <textarea
            value={qr}
            onChange={(e) => setQr(e.target.value)}
            placeholder='{"session_id":"…","pairing_code":"ABCD-1234","requested_scopes":[…]}'
            rows={3}
            className={`w-full rounded-lg border bg-white px-3 py-2 font-mono text-xs outline-none focus:border-primary ${
              qrInvalid ? "border-[#ba1a1a]" : "border-outline-variant"
            }`}
          />
          {qrInvalid && <span className="text-xs font-semibold text-[#ba1a1a]">That doesn’t look like valid JSON.</span>}
        </label>

        {previewScopes.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 rounded-lg border border-outline-variant bg-surface-container-low p-3">
            <span className="text-xs font-semibold text-on-surface-variant">Requested scopes:</span>
            {previewScopes.map((s) => (
              <Pill key={s} tone="info">{titleize(s)}</Pill>
            ))}
          </div>
        )}

        {!confirming ? (
          <div>
            <Button variant="primary" disabled={!canSubmit} onClick={() => setConfirming(true)}>
              <ShieldCheck size={15} /> Review & approve
            </Button>
            {!online && <p className="mt-2 text-xs text-outline">Backend offline — approval is unavailable right now.</p>}
          </div>
        ) : (
          <div className="flex flex-col gap-3 rounded-lg border border-primary/20 bg-primary/[0.04] p-4">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <KeyRound size={16} className="text-primary" /> Approve this device and share an encrypted summary?
            </div>
            <p className="text-xs text-on-surface-variant">
              This grants the requesting device the scopes above. You can revoke it later from the device list.
            </p>
            <div className="flex flex-wrap gap-2">
              <Button variant="primary" loading={approving} onClick={approve}>
                Confirm approval
              </Button>
              <Button variant="ghost" onClick={() => setConfirming(false)} disabled={approving}>
                Cancel
              </Button>
            </div>
          </div>
        )}
      </div>
    </Panel>
  );
}
