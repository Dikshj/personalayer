// /app/capture — local & on-device capture sources. Set up the browser
// extension, laptop agent, and iPhone app, then turn individual on-device
// sources on or off. OAuth/cloud apps live in /app/apps; device pairing and
// sync live in /app/devices — this page links into both.

import { useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  Chrome,
  ChevronDown,
  ChevronUp,
  Cpu,
  ExternalLink,
  Laptop,
  Megaphone,
  Radio,
  RefreshCw,
  Smartphone,
  type LucideIcon,
} from "lucide-react";
import { EmptyState, ErrorState, LoadingState, OfflineBanner, PageHeader } from "../components/states";
import { Button, Chip, CopyButton, Panel, Pill, Switch } from "../components/ui";
import { useResource } from "../lib/useResource";
import { useBackend } from "../lib/backend";
import { titleize } from "../lib/format";
import { previewCollectorSpecs, previewMemorySources } from "../lib/preview";
import {
  API_BASE,
  type CollectorSpec,
  type MemorySource,
  getDaemonStatus,
  getMemorySources,
  getPushTokens,
  getSyncDevices,
  setMemorySource,
} from "../api";

// Sources that connect via OAuth/cloud belong on /app/apps, not here.
const OAUTH_SOURCES = new Set(["gmail", "calendar", "google_drive", "youtube", "spotify", "github", "notion"]);

type Tone = "good" | "warn" | "danger" | "info" | "neutral";

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

function SourceRow({
  spec,
  enabled,
  live,
  onToggle,
}: {
  spec: CollectorSpec;
  enabled: boolean;
  live: boolean;
  onToggle: (next: boolean) => void;
}) {
  const name = spec.display_name || titleize(spec.source);
  return (
    <li className="flex items-center justify-between gap-3 border-b border-outline-variant py-3 last:border-none">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-semibold">{name}</span>
          <Pill tone={spec.raw_content_stored ? "warn" : "good"}>
            {spec.raw_content_stored ? "Stores content" : "Metadata only"}
          </Pill>
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-1.5">
          {(spec.permissions || []).map((p) => (
            <Chip key={p}>{p}</Chip>
          ))}
          {(spec.event_types || []).slice(0, 3).map((e) => (
            <span key={e} className="text-xs text-on-surface-variant">{titleize(e)}</span>
          ))}
        </div>
      </div>
      <Switch checked={enabled} onChange={onToggle} disabled={!live} label={`Capture ${name}`} />
    </li>
  );
}

export default function Capture() {
  const { online } = useBackend();
  const daemonRes = useResource(async () => (await getDaemonStatus()).collector_specs || [], previewCollectorSpecs);
  const sourcesRes = useResource(getMemorySources, previewMemorySources);
  const devicesRes = useResource(async () => (await getSyncDevices()).devices || [], []);
  const pushRes = useResource(async () => (await getPushTokens()).tokens || [], []);

  const [overrides, setOverrides] = useState<Record<string, boolean>>({});
  const [note, setNote] = useState<string | null>(null);

  const offline = daemonRes.isPreview;
  const enabledMap = useMemo(() => {
    const map = new Map<string, boolean>();
    for (const s of sourcesRes.data as MemorySource[]) if (s.source) map.set(s.source, Boolean(s.enabled));
    return map;
  }, [sourcesRes.data]);

  const specs = useMemo(
    () => daemonRes.data.filter((s) => s.source && !OAUTH_SOURCES.has(s.source)),
    [daemonRes.data],
  );

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

  const reload = () => {
    daemonRes.reload();
    sourcesRes.reload();
    devicesRes.reload();
    pushRes.reload();
  };

  const laptopConnected = devicesRes.data.some(
    (d) => d.trust_status === "trusted" && !(d.device_id || "").startsWith("web-"),
  );
  const phoneConnected = pushRes.data.length > 0;

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

      {note && (
        <div className="mb-4 rounded-lg border border-danger/20 bg-danger/5 px-3 py-2 text-sm font-semibold text-danger">{note}</div>
      )}

      <div className="flex flex-col gap-4">
        {/* Setup */}
        <Panel title="Set up capture">
          <ul className="grid gap-3 sm:grid-cols-2">
            <SetupCard
              icon={Chrome}
              title="Browser extension"
              body="Page and search metadata from your browser."
              status="Action needed"
              statusTone="neutral"
              action={<a className="inline-flex items-center gap-1.5 text-sm font-semibold text-primary hover:underline" href="#" onClick={(e) => e.preventDefault()}>Add extension <ExternalLink size={13} /></a>}
              steps={ol([
                "Install the PersonaLayer extension for your browser.",
                "Sign in with this account.",
                <>It streams page metadata (no content) to <code className="rounded bg-surface-container px-1">{new URL(API_BASE || "https://personalayer.onrender.com").host}</code>.</>,
              ])}
            />
            <SetupCard
              icon={Laptop}
              title="Laptop agent"
              body="Terminal, editor, and app activity from your computer."
              status={laptopConnected ? "Connected" : "Not set up"}
              statusTone={laptopConnected ? "good" : "neutral"}
              action={<Link to="/app/devices" className="inline-flex items-center gap-1.5 text-sm font-semibold text-primary hover:underline">Pair laptop <ArrowRight size={13} /></Link>}
              steps={ol([
                "Download the PersonaLayer desktop app for your OS.",
                "Open it and sign in with this account.",
                <span className="inline-flex flex-wrap items-center gap-2">Point it at your backend: <CopyButton value={API_BASE || ""} label="Copy URL" /></span>,
                <>Pair it from <Link to="/app/devices" className="text-primary hover:underline">Devices</Link>.</>,
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
              icon={Megaphone}
              title="Agent Reach"
              body="Optional outreach channels for your agents."
              status="Coming soon"
              statusTone="neutral"
              action={<span className="text-sm text-outline">Not available yet</span>}
              steps={ol(["Optional channels that let your agents reach out on your behalf. This isn’t available in the product yet — it’s on the roadmap."])}
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
                <SourceRow
                  key={spec.source}
                  spec={spec}
                  enabled={isEnabled(spec)}
                  live={online}
                  onToggle={(next) => toggle(spec, next)}
                />
              ))}
            </ul>
          )}
          <p className="mt-3 text-xs text-outline">
            Turning a source off stops it from feeding your persona. Cloud apps like Gmail or GitHub are managed in{" "}
            <Link to="/app/apps" className="text-primary hover:underline">Connected apps</Link>.
          </p>
        </Panel>
      </div>
    </>
  );
}
