// /app/capture — local & on-device capture sources. Set up the browser
// extension, laptop agent (with a one-time enrollment code), and iPhone app;
// turn individual on-device sources on/off with live status; manage Agent Reach
// channels and review native device permissions. OAuth/cloud apps live in
// /app/apps; pairing/sync lives in /app/devices.

import { useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  Chrome,
  ChevronDown,
  ChevronUp,
  Cpu,
  Download,
  ExternalLink,
  KeyRound,
  Laptop,
  Megaphone,
  Radio,
  RefreshCw,
  Server,
  ShieldCheck,
  Smartphone,
  type LucideIcon,
} from "lucide-react";
import { EmptyState, ErrorState, LoadingState, OfflineBanner, PageHeader } from "../components/states";
import { Button, Chip, CopyButton, Panel, Pill, Switch } from "../components/ui";
import { useResource } from "../lib/useResource";
import { useBackend } from "../lib/backend";
import { relativeTime, titleize } from "../lib/format";
import {
  previewAgentReachChannels,
  previewCollectorSpecs,
  previewDevicePermissions,
  previewMemorySources,
} from "../lib/preview";
import {
  API_BASE,
  type AgentReachChannel,
  type CaptureSourceStatus,
  type CollectorSpec,
  type DaemonStatus,
  type DevicePermission,
  type MemorySource,
  createEnrollToken,
  getAgentReachChannels,
  getCaptureStatus,
  getDaemonStatus,
  getDevicePermissions,
  getMemorySources,
  getPushTokens,
  getSyncDevices,
  setAgentReachChannel,
  setMemorySource,
} from "../api";

const OAUTH_SOURCES = new Set(["gmail", "calendar", "google_drive", "youtube", "spotify", "github", "notion"]);
const LOCAL_DAEMON_URL = "http://127.0.0.1:7823";
const DAEMON_INSTALLER_URL = "/downloads/install-personalayer-daemon-windows.ps1";
const DAEMON_SETUP_URL = "/downloads/PERSONALAYER_DAEMON_SETUP.md";
const EXTENSION_SETUP_URL = "/downloads/PERSONALAYER_EXTENSION_SETUP.md";

type Tone = "good" | "warn" | "danger" | "info" | "neutral";

function permTone(state?: string): Tone {
  if (state === "granted") return "good";
  if (state === "denied") return "danger";
  return "neutral";
}

// One-time enrollment code for the laptop agent.
function EnrollCode({ live }: { live: boolean }) {
  const [code, setCode] = useState<{ code?: string; expires_at?: number } | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const generate = async () => {
    setBusy(true);
    setErr("");
    try {
      const res = await createEnrollToken();
      if (res.code) setCode(res);
      else setErr("Couldn’t generate a code.");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Couldn’t generate a code.");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="mt-1">
      {code?.code ? (
        <div className="flex flex-wrap items-center gap-2">
          <code className="rounded-lg border border-outline-variant bg-white px-3 py-1.5 font-mono text-base font-bold tracking-widest text-primary">{code.code}</code>
          <CopyButton value={code.code} label="Copy code" />
          {code.expires_at && <span className="text-xs text-outline">expires {relativeTime(code.expires_at * 1000)}</span>}
        </div>
      ) : (
        <Button variant="default" loading={busy} disabled={!live} onClick={generate}>
          <KeyRound size={15} /> Generate setup code
        </Button>
      )}
      {err && <p className="mt-1 text-xs font-semibold text-danger">{err}</p>}
    </div>
  );
}

function SetupCard({
  icon: Icon,
  title,
  body,
  status,
  statusTone,
  steps,
  action,
}: {
  icon: LucideIcon;
  title: string;
  body: string;
  status: string;
  statusTone: Tone;
  steps: ReactNode;
  action?: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <li className="flex flex-col gap-3 rounded-2xl border border-outline-variant bg-white p-4 shadow-ambient">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary">
            <Icon size={20} />
          </span>
          <div className="min-w-0">
            <div className="truncate font-semibold">{title}</div>
            <div className="truncate text-xs text-on-surface-variant">{body}</div>
          </div>
        </div>
        <Pill tone={statusTone}>{status}</Pill>
      </div>
      {open && <div className="rounded-xl border border-outline-variant bg-surface-container-low p-3 text-sm text-on-surface-variant">{steps}</div>}
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-outline-variant pt-3">
        <button className="inline-flex items-center gap-1 text-sm font-semibold text-on-surface-variant hover:text-on-surface" onClick={() => setOpen((v) => !v)}>
          {open ? <ChevronUp size={15} /> : <ChevronDown size={15} />} Setup steps
        </button>
        {action}
      </div>
    </li>
  );
}

function ol(items: ReactNode[]) {
  return (
    <ol className="flex list-decimal flex-col gap-1.5 pl-4">
      {items.map((it, i) => (
        <li key={i}>{it}</li>
      ))}
    </ol>
  );
}

function LocalDaemonProduct({
  status,
  live,
  loading,
  onRefresh,
}: {
  status?: DaemonStatus;
  live: boolean;
  loading: boolean;
  onRefresh: () => void;
}) {
  const isLocal = Boolean(status?.bind || status?.mode === "local_context_daemon");
  const healthy = live && status?.status === "ok";
  const collectors = status?.collector_specs?.length || status?.collectors?.length || 0;
  const policy = status?.policy || {};

  return (
    <Panel
      title={<span className="inline-flex items-center gap-2"><Server size={16} /> Local daemon</span>}
      action={<Pill tone={healthy ? "good" : "warn"}>{healthy ? "Running" : loading ? "Checking" : "Not detected"}</Pill>}
    >
      <div className="grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
        <div className="rounded-xl border border-outline-variant bg-surface-container-low p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="text-base font-bold">PersonaLayer local runtime</h3>
              <p className="mt-1 max-w-2xl text-sm text-on-surface-variant">
                Runs on the user's computer, receives browser and device events, stores local SQLite data, and exposes scoped context on localhost.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <a className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-outline-variant bg-white px-3.5 py-2 text-sm font-semibold text-on-surface transition hover:bg-surface-container-low" href={DAEMON_INSTALLER_URL} download>
                <Download size={15} /> Windows installer
              </a>
              <a className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-outline-variant bg-white px-3.5 py-2 text-sm font-semibold text-on-surface transition hover:bg-surface-container-low" href={DAEMON_SETUP_URL} target="_blank" rel="noreferrer">
                Setup guide <ExternalLink size={14} />
              </a>
            </div>
          </div>

          <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-lg border border-outline-variant bg-white p-3">
              <div className="text-xs font-semibold uppercase text-outline">Endpoint</div>
              <code className="mt-1 block truncate text-sm font-semibold">{status?.bind || "127.0.0.1:7823"}</code>
            </div>
            <div className="rounded-lg border border-outline-variant bg-white p-3">
              <div className="text-xs font-semibold uppercase text-outline">Storage</div>
              <div className="mt-1 text-sm font-semibold">{titleize(status?.storage || "local_sqlite")}</div>
            </div>
            <div className="rounded-lg border border-outline-variant bg-white p-3">
              <div className="text-xs font-semibold uppercase text-outline">Collectors</div>
              <div className="mt-1 text-sm font-semibold">{collectors}</div>
            </div>
            <div className="rounded-lg border border-outline-variant bg-white p-3">
              <div className="text-xs font-semibold uppercase text-outline">Raw data</div>
              <div className="mt-1 text-sm font-semibold">{status?.raw_data_leaves_device === false ? "Stays local" : "Policy gated"}</div>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-2 text-sm">
            <Pill tone={isLocal ? "good" : "neutral"}>Localhost runtime</Pill>
            <Pill tone={policy.scoped_context_contracts ? "good" : "neutral"}>Scoped context</Pill>
            <Pill tone={policy.audit_log ? "good" : "neutral"}>Audit log</Pill>
            <Pill tone={policy.revocation ? "good" : "neutral"}>Revocation</Pill>
          </div>
        </div>

        <div className="rounded-xl border border-outline-variant bg-white p-4">
          <h3 className="text-base font-bold">Install flow</h3>
          {ol([
            <span>Download and run the Windows installer script.</span>,
            <span>Open <a className="text-primary hover:underline" href={`${LOCAL_DAEMON_URL}/daemon/status`} target="_blank" rel="noreferrer">daemon status</a> and confirm it returns <code className="rounded bg-surface-container px-1">status: ok</code>.</span>,
            <span>Load the browser extension, then refresh this page.</span>,
            <span>Enable only the on-device sources you want below.</span>,
          ])}
          <div className="mt-4 flex flex-wrap gap-2">
            <Button variant="default" onClick={onRefresh} loading={loading}>
              <RefreshCw size={15} /> Check daemon
            </Button>
            <a className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-outline-variant bg-white px-3.5 py-2 text-sm font-semibold text-on-surface transition hover:bg-surface-container-low" href={`${LOCAL_DAEMON_URL}/dashboard/`} target="_blank" rel="noreferrer">
              Open local dashboard <ExternalLink size={14} />
            </a>
          </div>
        </div>
      </div>
    </Panel>
  );
}

function SourceRow({
  spec,
  enabled,
  live,
  status,
  onToggle,
}: {
  spec: CollectorSpec;
  enabled: boolean;
  live: boolean;
  status?: CaptureSourceStatus;
  onToggle: (next: boolean) => void;
}) {
  const name = spec.display_name || titleize(spec.source);
  return (
    <li className="flex items-center justify-between gap-3 border-b border-outline-variant py-3 last:border-none">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-semibold">{name}</span>
          {status?.state === "connected" ? (
            <Pill tone="good">Streaming</Pill>
          ) : status ? (
            <Pill tone="neutral">Idle</Pill>
          ) : null}
          <Pill tone={spec.raw_content_stored ? "warn" : "good"}>{spec.raw_content_stored ? "Stores content" : "Metadata only"}</Pill>
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-1.5">
          {(spec.permissions || []).map((p) => (
            <Chip key={p}>{p}</Chip>
          ))}
          {status?.last_sync_at && <span className="text-xs text-outline">synced {relativeTime(status.last_sync_at)}</span>}
        </div>
      </div>
      <Switch checked={enabled} onChange={onToggle} disabled={!live} label={`Capture ${name}`} />
    </li>
  );
}

export default function Capture() {
  const { online } = useBackend();
  const daemonStatusRes = useResource(getDaemonStatus, undefined as DaemonStatus | undefined);
  const daemonRes = useResource(async () => (await getDaemonStatus()).collector_specs || [], previewCollectorSpecs);
  const sourcesRes = useResource(getMemorySources, previewMemorySources);
  const statusRes = useResource(async () => (await getCaptureStatus()).sources || [], [] as CaptureSourceStatus[]);
  const devicesRes = useResource(async () => (await getSyncDevices()).devices || [], []);
  const pushRes = useResource(async () => (await getPushTokens()).tokens || [], []);
  const agentRes = useResource(async () => (await getAgentReachChannels()).channels || [], previewAgentReachChannels);
  const permsRes = useResource(async () => (await getDevicePermissions()).permissions || [], previewDevicePermissions);

  const [overrides, setOverrides] = useState<Record<string, boolean>>({});
  const [reachOverrides, setReachOverrides] = useState<Record<string, boolean>>({});
  const [note, setNote] = useState<string | null>(null);

  const offline = daemonRes.isPreview;

  const enabledMap = useMemo(() => {
    const map = new Map<string, boolean>();
    for (const s of sourcesRes.data as MemorySource[]) if (s.source) map.set(s.source, Boolean(s.enabled));
    return map;
  }, [sourcesRes.data]);

  const statusMap = useMemo(() => {
    const map = new Map<string, CaptureSourceStatus>();
    for (const s of statusRes.data) if (s.source) map.set(s.source, s);
    return map;
  }, [statusRes.data]);

  const specs = useMemo(() => daemonRes.data.filter((s) => s.source && !OAUTH_SOURCES.has(s.source)), [daemonRes.data]);

  const isEnabled = (spec: CollectorSpec) =>
    overrides[spec.source!] ?? enabledMap.get(spec.source!) ?? Boolean(spec.enabled_by_default);

  const toggle = async (spec: CollectorSpec, next: boolean) => {
    const source = spec.source!;
    setOverrides((o) => ({ ...o, [source]: next }));
    setNote(null);
    try {
      await setMemorySource(source, next);
    } catch (err) {
      setOverrides((o) => ({ ...o, [source]: !next }));
      setNote(err instanceof Error ? err.message : "Couldn’t update that source. Try again.");
    }
  };

  const toggleReach = async (channel: AgentReachChannel, next: boolean) => {
    setReachOverrides((o) => ({ ...o, [channel.channel]: next }));
    setNote(null);
    try {
      await setAgentReachChannel(channel.channel, next);
    } catch (err) {
      setReachOverrides((o) => ({ ...o, [channel.channel]: !next }));
      setNote(err instanceof Error ? err.message : "Couldn’t update that channel. Try again.");
    }
  };

  const reload = () => {
    daemonStatusRes.reload();
    daemonRes.reload();
    sourcesRes.reload();
    statusRes.reload();
    devicesRes.reload();
    pushRes.reload();
    agentRes.reload();
    permsRes.reload();
  };

  const laptopConnected = devicesRes.data.some((d) => d.trust_status === "trusted" && !(d.device_id || "").startsWith("web-"));
  const phoneConnected = pushRes.data.length > 0;

  // Group device permissions by device for display.
  const permsByDevice = useMemo(() => {
    const map = new Map<string, DevicePermission[]>();
    for (const p of permsRes.data) {
      const k = p.device_id || "device";
      if (!map.has(k)) map.set(k, []);
      map.get(k)!.push(p);
    }
    return [...map.entries()];
  }, [permsRes.data]);

  return (
    <>
      <PageHeader
        title="Capture & sources"
        subtitle="Stream signals from your own devices. PersonaLayer reads metadata, not content — and you turn each source on or off."
        action={
          <Button variant="default" onClick={reload}>
            <RefreshCw size={15} /> Refresh
          </Button>
        }
      />

      {offline && <OfflineBanner onRetry={reload} />}
      {note && <div className="mb-4 rounded-lg border border-danger/20 bg-danger/5 px-3 py-2 text-sm font-semibold text-danger">{note}</div>}

      <div className="flex flex-col gap-4">
        {/* Set up */}
        <LocalDaemonProduct
          status={daemonStatusRes.data}
          live={online && !daemonStatusRes.isPreview}
          loading={daemonStatusRes.loading}
          onRefresh={reload}
        />

        <Panel title="Set up capture">
          <ul className="grid gap-3 sm:grid-cols-2">
            <SetupCard
              icon={Chrome}
              title="Browser extension"
              body="Page and search metadata from your browser."
              status="Action needed"
              statusTone="neutral"
              action={<a className="inline-flex items-center gap-1.5 text-sm font-semibold text-primary hover:underline" href={EXTENSION_SETUP_URL} target="_blank" rel="noreferrer">Install extension <ExternalLink size={13} /></a>}
              steps={ol([
                "Install and start the local daemon first.",
                "Open Chrome or Edge extensions, enable Developer mode, and load the PersonaLayer extension folder.",
                <>It streams page metadata to the local daemon at <code className="rounded bg-surface-container px-1">{LOCAL_DAEMON_URL}</code>, then syncs allowed derived signals to <code className="rounded bg-surface-container px-1">{new URL(API_BASE || "https://personalayer.onrender.com").host}</code>.</>,
              ])}
            />
            <SetupCard
              icon={Laptop}
              title="Desktop daemon"
              body="Terminal, editor, and app activity from your computer."
              status={laptopConnected ? "Connected" : "Not set up"}
              statusTone={laptopConnected ? "good" : "neutral"}
              action={<a className="inline-flex items-center gap-1.5 text-sm font-semibold text-primary hover:underline" href={DAEMON_INSTALLER_URL} download>Download <Download size={13} /></a>}
              steps={ol([
                "Install the daemon and let it register as a Windows login task.",
                <>Open <a className="text-primary hover:underline" href={`${LOCAL_DAEMON_URL}/dashboard/`} target="_blank" rel="noreferrer">the local dashboard</a> to verify it is running.</>,
                <span className="inline-flex flex-wrap items-center gap-2">Point it at your backend: <CopyButton value={API_BASE || ""} label="Copy URL" /></span>,
                <>For a second computer, generate a one-time setup code:<EnrollCode live={online} /></>,
              ])}
            />
            <SetupCard
              icon={Smartphone}
              title="iPhone app"
              body="Health, calendar, and on-device signals — each optional."
              status={phoneConnected ? "Connected" : "Not set up"}
              statusTone={phoneConnected ? "good" : "neutral"}
              action={<Link to="/app/devices" className="inline-flex items-center gap-1.5 text-sm font-semibold text-primary hover:underline">Pair iPhone <ArrowRight size={13} /></Link>}
              steps={ol([
                "Install PersonaLayer from the App Store.",
                "Sign in, then grant only the permissions you want (Health, Calendar, Contacts).",
                <>Pair it from <Link to="/app/devices" className="text-primary hover:underline">Devices</Link> to start syncing.</>,
              ])}
            />
            <SetupCard
              icon={ShieldCheck}
              title="On-device permissions"
              body="What your phone/laptop apps are allowed to read."
              status={permsRes.data.length ? `${permsRes.data.filter((p) => p.state === "granted").length} granted` : "None reported"}
              statusTone={permsRes.data.length ? "good" : "neutral"}
              action={undefined}
              steps={ol(["Your native apps report which OS permissions you've granted. Grant or revoke them in your device's system settings; this view updates after the app next syncs."])}
            />
          </ul>
        </Panel>

        {/* On-device sources */}
        <Panel
          title={<span className="inline-flex items-center gap-2"><Cpu size={16} /> On-device sources</span>}
          action={<span className="text-xs text-on-surface-variant">{specs.length} sources</span>}
        >
          {daemonRes.loading && specs.length === 0 ? (
            <LoadingState label="Loading sources…" />
          ) : daemonRes.error ? (
            <ErrorState message={daemonRes.error} onRetry={daemonRes.reload} />
          ) : specs.length === 0 ? (
            <EmptyState icon={<Radio size={22} />} title="No capture sources" hint="Set up the browser extension or laptop agent above to start streaming signals." />
          ) : (
            <ul className="-my-1">
              {specs.map((spec) => (
                <SourceRow key={spec.source} spec={spec} enabled={isEnabled(spec)} live={online} status={statusMap.get(spec.source!)} onToggle={(next) => toggle(spec, next)} />
              ))}
            </ul>
          )}
          <p className="mt-3 text-xs text-outline">
            Turning a source off stops it from feeding your persona. Cloud apps like Gmail or GitHub are managed in{" "}
            <Link to="/app/apps" className="text-primary hover:underline">Connected apps</Link>.
          </p>
        </Panel>

        {/* Agent Reach */}
        <Panel
          title={<span className="inline-flex items-center gap-2"><Megaphone size={16} /> Agent Reach</span>}
          action={<span className="text-xs text-on-surface-variant">Optional channels</span>}
        >
          <p className="mb-3 text-sm text-on-surface-variant">Channels your agents may use to reach you. All off by default — turn on only what you want.</p>
          {agentRes.loading && agentRes.data.length === 0 ? (
            <LoadingState />
          ) : (
            <ul className="-my-1">
              {agentRes.data.map((ch) => {
                const on = reachOverrides[ch.channel] ?? Boolean(ch.enabled);
                return (
                  <li key={ch.channel} className="flex items-center justify-between gap-3 border-b border-outline-variant py-3 last:border-none">
                    <div className="min-w-0">
                      <div className="font-semibold">{ch.name || titleize(ch.channel)}</div>
                      {ch.description && <div className="text-xs text-on-surface-variant">{ch.description}</div>}
                    </div>
                    <Switch checked={on} onChange={(next) => toggleReach(ch, next)} disabled={!online} label={`Enable ${ch.name || ch.channel}`} />
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>

        {/* Native device permissions */}
        <Panel
          title={<span className="inline-flex items-center gap-2"><ShieldCheck size={16} /> Device permissions</span>}
          action={<span className="text-xs text-on-surface-variant">{permsRes.data.length} reported</span>}
        >
          {permsRes.loading && permsRes.data.length === 0 ? (
            <LoadingState />
          ) : permsByDevice.length === 0 ? (
            <EmptyState icon={<Smartphone size={22} />} title="No permissions reported" hint="Install the iPhone or macOS app and grant access — what you allow shows up here." />
          ) : (
            <div className="flex flex-col gap-4">
              {permsByDevice.map(([device, perms]) => (
                <div key={device}>
                  <div className="mb-1.5 text-xs font-bold uppercase tracking-wide text-outline">{titleize(device)}</div>
                  <div className="flex flex-wrap gap-1.5">
                    {perms.map((p) => (
                      <Pill key={p.permission} tone={permTone(p.state)}>
                        {titleize(p.permission)}: {titleize(p.state) || "Unknown"}
                      </Pill>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>
    </>
  );
}
