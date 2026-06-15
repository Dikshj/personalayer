// Devices overview — trusted / pending / revoked devices, the current browser
// device, fingerprints (never full keys), and per-device security actions.

import { useState } from "react";
import {
  KeyRound,
  Laptop,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  Smartphone,
} from "lucide-react";
import { EmptyState, ErrorState, LoadingState } from "../states";
import { Button, ConfirmButton, Pill } from "../ui";
import type { Resource } from "../../lib/useResource";
import { fingerprint, relativeTime, titleize } from "../../lib/format";
import {
  type SyncDevice,
  ensureWebKeypair,
  getStoredKeypair,
  getWebDeviceId,
  getWebDeviceName,
  recoveryRevokeSyncDevice,
  revokeSyncDevice,
  rotateSyncDeviceKey,
  trustSyncDevice,
} from "../../api";

function statusTone(status?: string): "good" | "warn" | "danger" | "neutral" {
  if (status === "trusted") return "good";
  if (status === "pending") return "warn";
  if (status === "revoked") return "danger";
  return "neutral";
}

function deviceIcon(device: SyncDevice) {
  const name = `${device.device_name || ""} ${device.device_id || ""}`.toLowerCase();
  if (/iphone|android|pixel|mobile|phone/.test(name)) return Smartphone;
  return Laptop;
}

function DeviceRow({
  device,
  isCurrent,
  disabled,
  onChange,
  onError,
}: {
  device: SyncDevice;
  isCurrent: boolean;
  disabled: boolean;
  onChange: () => void;
  onError: (message: string) => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const Icon = deviceIcon(device);
  const id = device.device_id || "";
  const revoked = device.trust_status === "revoked";

  const run = async (key: string, fn: () => Promise<{ error?: string }>) => {
    setBusy(key);
    onError("");
    try {
      const res = await fn();
      if (res?.error) onError(humanize(res.error));
    } catch (err) {
      onError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setBusy(null);
      onChange();
    }
  };

  const rotateOwnKey = async () => {
    const kp = await ensureWebKeypair(true);
    return rotateSyncDeviceKey(id, kp.public_key);
  };

  return (
    <li className="flex flex-col gap-3 rounded-xl border border-outline-variant p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-surface-container text-on-surface-variant">
            <Icon size={18} />
          </span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="truncate font-semibold">{device.device_name || titleize(id) || "Unknown device"}</span>
              {isCurrent && <Pill tone="info">This device</Pill>}
            </div>
            <div className="mt-0.5 truncate text-xs text-on-surface-variant">
              Last seen {relativeTime(device.last_seen_at)} · paired {relativeTime(device.created_at)}
            </div>
            <div className="mt-1 font-mono text-[11px] text-outline" title="Public key fingerprint">
              fp {fingerprint(device.public_key)}
            </div>
          </div>
        </div>
        <Pill tone={statusTone(device.trust_status)}>{titleize(device.trust_status || "unknown")}</Pill>
      </div>

      {!revoked && (
        <div className="flex flex-wrap items-center gap-2">
          {device.trust_status === "pending" && (
            <Button
              variant="primary"
              loading={busy === "trust"}
              disabled={disabled}
              onClick={() => run("trust", () => trustSyncDevice(id, { device_name: device.device_name, public_key: device.public_key }))}
            >
              <ShieldCheck size={15} /> Trust
            </Button>
          )}
          {isCurrent && device.trust_status === "trusted" && (
            <Button variant="default" loading={busy === "rotate"} disabled={disabled} onClick={() => run("rotate", rotateOwnKey)}>
              <RotateCcw size={15} /> Rotate key
            </Button>
          )}
          <ConfirmButton confirmLabel="Revoke device" disabled={disabled} onConfirm={() => run("revoke", () => revokeSyncDevice(id))}>
            <KeyRound size={15} /> Revoke
          </ConfirmButton>
          <ConfirmButton
            confirmLabel="Recovery revoke"
            disabled={disabled}
            onConfirm={() => run("recovery", () => recoveryRevokeSyncDevice(id, "Recovery revoke from web console"))}
          >
            <ShieldAlert size={15} /> Recovery revoke
          </ConfirmButton>
        </div>
      )}
      {revoked && (
        <p className="text-xs text-on-surface-variant">
          Revoked {relativeTime(device.revoked_at)} — this device can no longer sync.
        </p>
      )}
    </li>
  );
}

function humanize(code: string): string {
  return titleize(code).replace(/\bId\b/, "ID");
}

const GROUPS: { key: string; label: string; tone: "good" | "warn" | "danger" }[] = [
  { key: "trusted", label: "Trusted", tone: "good" },
  { key: "pending", label: "Pending", tone: "warn" },
  { key: "revoked", label: "Revoked", tone: "danger" },
];

export default function DevicesOverview({
  devicesRes,
  disabled,
}: {
  devicesRes: Resource<SyncDevice[]>;
  disabled: boolean;
}) {
  const [actionError, setActionError] = useState("");
  const devices = devicesRes.data;
  const currentId = getWebDeviceId();
  const storedKeypair = getStoredKeypair();

  const counts = {
    trusted: devices.filter((d) => d.trust_status === "trusted").length,
    pending: devices.filter((d) => d.trust_status === "pending").length,
    revoked: devices.filter((d) => d.trust_status === "revoked").length,
  };

  const registered = devices.some((d) => d.device_id === currentId);

  return (
    <section className="rounded-2xl border border-outline-variant bg-white shadow-ambient">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-outline-variant px-5 py-4">
        <h2 className="text-base font-bold">Devices</h2>
        <div className="flex flex-wrap items-center gap-2">
          {GROUPS.map((g) => (
            <Pill key={g.key} tone={g.tone}>
              {counts[g.key as keyof typeof counts]} {g.label}
            </Pill>
          ))}
        </div>
      </header>

      <div className="p-5">
        {/* Current browser device summary */}
        <div className="mb-4 flex flex-col gap-2 rounded-xl border border-primary/20 bg-primary/[0.04] p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Laptop size={16} className="text-primary" />
              <span className="font-semibold">{getWebDeviceName()}</span>
              <Pill tone="info">This browser</Pill>
              {!registered && <Pill tone="neutral">Not paired</Pill>}
            </div>
            <div className="mt-1 font-mono text-[11px] text-outline">
              fp {fingerprint(storedKeypair?.public_key)}
            </div>
          </div>
          <p className="text-xs text-on-surface-variant sm:max-w-[16rem] sm:text-right">
            Keys for this browser live in localStorage. Native clients should use the OS keychain.
          </p>
        </div>

        {actionError && (
          <p className="mb-3 rounded-lg border border-danger/20 bg-danger/5 px-3 py-2 text-sm font-semibold text-danger">
            {actionError}
          </p>
        )}

        {devicesRes.loading && devices.length === 0 ? (
          <LoadingState label="Loading devices…" />
        ) : devicesRes.error ? (
          <ErrorState message={devicesRes.error} onRetry={devicesRes.reload} />
        ) : devices.length === 0 ? (
          <EmptyState
            icon={<Smartphone size={22} />}
            title="No devices yet"
            hint="Pair a device below to start syncing securely across your devices."
          />
        ) : (
          <ul className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            {devices.map((d) => (
              <DeviceRow
                key={d.id || d.device_id}
                device={d}
                isCurrent={d.device_id === currentId}
                disabled={disabled}
                onChange={devicesRes.reload}
                onError={setActionError}
              />
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
