import {
  Briefcase,
  CalendarDays,
  ChevronDown,
  CircleUser,
  Code,
  Database,
  Eye,
  Mail,
  MapPin,
  MessageCircle,
  Search,
  ShieldCheck,
} from "lucide-react";
import { ReactNode, useEffect, useMemo, useState } from "react";
import {
  BackendStatus,
  PersonaSignal,
  PrivacyBoundary,
  PclIntegration,
  addPrivacyBoundary,
  connectIntegration,
  deletePrivacyBoundary,
  deleteSignal,
  disconnectIntegration,
  getApps,
  getControlCenterSummary,
  getIntegrations,
  getPrivacyProfile,
  searchSignals,
  updateSignalShareable,
} from "./api";

type AppScreen = "laptop" | "scan" | "manual" | "success" | "privacy-home" | "privacy-apps" | "privacy-controls";

type PrivacyManagerProps = {
  screen: AppScreen;
  setScreen: (screen: AppScreen) => void;
};

const facts = [
  {
    icon: <Code size={22} />,
    title: "You work in software",
    detail: "We noticed this from your GitHub activity.",
  },
  {
    icon: <Briefcase size={22} />,
    title: "You're building a side project",
    detail: "Based on recent repositories, docs, and product planning notes.",
  },
  {
    icon: <MessageCircle size={22} />,
    title: "You prefer direct communication",
    detail: "Learned from how you interact with AI assistants.",
  },
  {
    icon: <MapPin size={22} />,
    title: "You are based in India",
    detail: "Used only for local defaults such as timezone and region.",
  },
];

const apps = [
  {
    name: "GitHub",
    icon: <Code size={28} />,
    detail: "Helps us understand your work projects.",
    connected: true,
  },
  {
    name: "Calendar",
    icon: <CalendarDays size={28} />,
    detail: "Helps map your schedule and availability.",
    connected: true,
  },
  {
    name: "Notion",
    icon: <Database size={28} />,
    detail: "Turns notes and task pages into private context.",
    connected: true,
  },
  {
    name: "Browser History",
    icon: <Search size={28} />,
    detail: "Protected locally and never shared without consent.",
    connected: false,
  },
];

function PrivacyManager({ screen, setScreen }: PrivacyManagerProps) {
  const active = screen === "privacy-apps" ? "apps" : screen === "privacy-controls" ? "privacy" : "home";
  const [backendStatus, setBackendStatus] = useState<BackendStatus>("loading");
  const [signals, setSignals] = useState<PersonaSignal[]>([]);
  const [integrations, setIntegrations] = useState<PclIntegration[]>([]);
  const [boundaries, setBoundaries] = useState<PrivacyBoundary[]>([]);
  const [summary, setSummary] = useState<Record<string, unknown>>({});
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let activeRequest = true;
    Promise.allSettled([searchSignals(), getIntegrations(), getApps(), getPrivacyProfile(), getControlCenterSummary()])
      .then(([signalResult, integrationResult, appResult, profileResult, summaryResult]) => {
        if (!activeRequest) return;
        if (signalResult.status === "fulfilled") setSignals(signalResult.value.signals || []);
        if (integrationResult.status === "fulfilled") setIntegrations(integrationResult.value.integrations || []);
        if (appResult.status === "fulfilled") {
          const appIntegrations = (appResult.value.apps || []).map((app) => ({
            source: app.app_id,
            name: app.name,
            status: app.status || "registered",
            connected: app.status !== "revoked",
          }));
          setIntegrations((current) => mergeIntegrations(current, appIntegrations));
        }
        if (profileResult.status === "fulfilled") setBoundaries(profileResult.value.active_boundaries || []);
        if (summaryResult.status === "fulfilled") setSummary(summaryResult.value || {});
        const anyFulfilled = [signalResult, integrationResult, appResult, profileResult, summaryResult].some((item) => item.status === "fulfilled");
        setBackendStatus(anyFulfilled ? "online" : "offline");
      })
      .catch(() => setBackendStatus("offline"));
    return () => {
      activeRequest = false;
    };
  }, [refreshKey]);

  const refresh = () => setRefreshKey((current) => current + 1);

  return (
    <div className="privacy-shell min-h-[calc(100dvh-64px)] bg-[#f9f9f9] px-5 pb-28 pt-6 text-[#1a1c1c] md:px-8 md:pb-10">
      <div className="mx-auto max-w-[1100px]">
        <PrivacyTabs active={active} setScreen={setScreen} backendStatus={backendStatus} />

        {screen === "privacy-home" && <PrivacyHome signals={signals} summary={summary} refresh={refresh} />}
        {screen === "privacy-apps" && <PrivacyApps integrations={integrations} refresh={refresh} />}
        {screen === "privacy-controls" && <PrivacyControls integrations={integrations} boundaries={boundaries} refresh={refresh} />}
      </div>

      <PrivacyBottomNav active={active} setScreen={setScreen} />
    </div>
  );
}

function PrivacyTabs({
  active,
  setScreen,
  backendStatus,
}: {
  active: "home" | "apps" | "privacy";
  setScreen: (screen: AppScreen) => void;
  backendStatus: BackendStatus;
}) {
  const tabs = [
    { id: "home" as const, label: "Home", screen: "privacy-home" as AppScreen },
    { id: "apps" as const, label: "Apps", screen: "privacy-apps" as AppScreen },
    { id: "privacy" as const, label: "Privacy", screen: "privacy-controls" as AppScreen },
  ];

  return (
    <div className="mb-8 hidden items-center justify-between md:flex">
      <OnDeviceBadge backendStatus={backendStatus} />
      <nav className="flex items-center gap-2 rounded-full bg-white p-1 shadow-soft">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={`rounded-full px-5 py-2 text-sm font-bold transition ${
              active === tab.id ? "bg-[#006e2f] text-white" : "text-[#3d4a3d] hover:bg-[#f3f3f3]"
            }`}
            onClick={() => setScreen(tab.screen)}
          >
            {tab.label}
          </button>
        ))}
      </nav>
    </div>
  );
}

function PrivacyHome({
  signals,
  summary,
  refresh,
}: {
  signals: PersonaSignal[];
  summary: Record<string, unknown>;
  refresh: () => void;
}) {
  const visibleFacts = signals.length ? signals.slice(0, 8) : facts;

  return (
    <div className="space-y-12">
      <section>
        <OnDeviceBadge backendStatus={signals.length ? "online" : "offline"} />
        <h1 className="mt-6 text-4xl font-bold leading-tight tracking-normal">Hi there.</h1>
        <div className="mt-4 rounded-[24px] bg-[#f3f3f3] p-6 md:p-8">
          <p className="max-w-3xl text-lg leading-8 text-[#3d4a3d]">
            You're a software developer working on a side project. You like short, direct answers and your context stays
            on this device unless you explicitly share it.
          </p>
        </div>
      </section>

      <section>
        <h2 className="mb-4 text-sm font-bold uppercase tracking-[0.14em] text-[#3d4a3d]">What we've noticed</h2>
        <div className="space-y-4">
          {visibleFacts.map((fact, index) => (
            <FactCard key={"id" in fact && fact.id ? fact.id : "title" in fact ? fact.title : index} fact={fact} refresh={refresh} />
          ))}
        </div>
      </section>

      <section className="grid gap-5 md:grid-cols-3">
        <SummaryCard value={String(signals.length || 4)} label="Known signals" detail="Stored locally and editable anytime." />
        <SummaryCard value={String(summary.active_permissions ?? 0)} label="Active permissions" detail="Only active after your consent." />
        <SummaryCard value={String(summary.privacy_boundaries ?? 0)} label="Privacy rules" detail="Fields blocked from app sharing." />
      </section>
    </div>
  );
}

function PrivacyApps({ integrations, refresh }: { integrations: PclIntegration[]; refresh: () => void }) {
  const visibleApps = integrations.length ? integrations : apps;

  return (
    <div className="space-y-10">
      <section>
        <h1 className="text-4xl font-bold tracking-normal">Your apps</h1>
        <p className="mt-3 max-w-2xl text-lg leading-8 text-[#3d4a3d]">
          Control which parts of your digital life PersonaLayer protects and understands.
        </p>
      </section>

      <section>
        <h2 className="mb-4 text-sm font-bold uppercase tracking-[0.14em] text-[#3d4a3d]">Connected</h2>
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {visibleApps.map((app) => (
            <AppCard key={"source" in app ? app.source || app.name : app.name} app={app} refresh={refresh} />
          ))}
        </div>
      </section>

      <section className="rounded-[32px] bg-[#f3f3f3] p-6 md:p-10">
        <h2 className="text-2xl font-semibold">Protection coverage</h2>
        <div className="mt-6 space-y-5">
          <ProgressRow label="Work context" value={84} />
          <ProgressRow label="Schedule context" value={68} />
          <ProgressRow label="Browsing context" value={32} />
        </div>
      </section>
    </div>
  );
}

function PrivacyControls({
  integrations,
  boundaries,
  refresh,
}: {
  integrations: PclIntegration[];
  boundaries: PrivacyBoundary[];
  refresh: () => void;
}) {
  const visibleApps = integrations.filter((item) => item.connected || item.status === "connected").slice(0, 2);
  const privacyTargets = [
    { target: "emails", icon: <Mail size={22} />, title: "My emails", detail: "Keep inbox messages strictly for your eyes." },
    { target: "location", icon: <MapPin size={22} />, title: "My location", detail: "Prevent apps from knowing where you are right now." },
    { target: "browsing", icon: <Eye size={22} />, title: "My browsing", detail: "Hide sensitive sites from all connected apps." },
  ];

  return (
    <div className="space-y-10">
      <section className="max-w-2xl">
        <h1 className="text-4xl font-bold tracking-normal">Who can see you</h1>
        <p className="mt-3 text-lg leading-8 text-[#3d4a3d]">
          Control which apps have access to your digital life and lock down your most sensitive details with a single tap.
        </p>
      </section>

      <section>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-2xl font-semibold">Apps that can see you</h2>
          <span className="rounded-full bg-[#22c55e]/10 px-3 py-1 text-sm font-bold text-[#006e2f]">
            2 Active Connections
          </span>
        </div>
        <div className="grid gap-6 md:grid-cols-2">
          {(visibleApps.length ? visibleApps : [{ name: "Notion" }, { name: "Calendar" }]).map((app) => (
            <AccessCard
              key={app.source || app.name}
              name={app.name || app.source || "Connected app"}
              icon={(app.name || app.source || "").toLowerCase().includes("calendar") ? <CalendarDays size={26} /> : <Database size={26} />}
              detail={`This app can see context allowed by its active PersonaLayer permission.`}
              source={app.source}
              refresh={refresh}
            />
          ))}
        </div>
      </section>

      <section className="rounded-[32px] bg-[#f3f3f3] p-6 md:p-10">
        <h2 className="mb-6 text-2xl font-semibold">Always keep private</h2>
        <div className="space-y-6">
          {privacyTargets.map((item, index) => (
            <div key={item.target}>
              <PrivacyToggle
                {...item}
                checked={boundaries.some((boundary) => boundary.target === item.target || boundary.target === `private_${item.target}`)}
                boundary={boundaries.find((boundary) => boundary.target === item.target || boundary.target === `private_${item.target}`)}
                refresh={refresh}
              />
              {index < privacyTargets.length - 1 && <div className="mt-6"><Divider /></div>}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function FactCard({
  fact,
  refresh,
}: {
  fact: PersonaSignal | { icon: ReactNode; title: string; detail: string };
  refresh: () => void;
}) {
  const [open, setOpen] = useState(false);
  const isSignal = "signal_type" in fact || "name" in fact;
  const icon = isSignal ? iconForSignal((fact as PersonaSignal).signal_type) : (fact as { icon: ReactNode }).icon;
  const title = isSignal ? (fact as PersonaSignal).name || (fact as PersonaSignal).human_readable_type || "Persona signal" : (fact as { title: string }).title;
  const detail = isSignal ? (fact as PersonaSignal).why_it_exists || (fact as PersonaSignal).evidence || "Stored by PersonaLayer." : (fact as { detail: string }).detail;

  async function hideFact() {
    const id = (fact as PersonaSignal).id;
    if (!id) return;
    await updateSignalShareable(id, false);
    refresh();
  }

  async function removeFact() {
    const id = (fact as PersonaSignal).id;
    if (!id) return;
    await deleteSignal(id);
    refresh();
  }

  return (
    <button className="privacy-card w-full text-left" onClick={() => setOpen((current) => !current)}>
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <span className="privacy-icon">{icon}</span>
          <span className="text-base font-semibold">{title}</span>
        </div>
        <ChevronDown className={`text-[#3d4a3d] transition ${open ? "rotate-180" : ""}`} size={20} />
      </div>
      {open && (
        <div className="ml-14 mt-3">
          <p className="text-sm text-[#3d4a3d]">{detail}</p>
          {isSignal && (
            <span className="mt-2 flex gap-4">
              <span className="text-sm font-bold text-[#006e2f]" onClick={(event) => { event.stopPropagation(); void hideFact(); }}>
                Hide from apps
              </span>
              <span className="text-sm font-bold text-[#ba1a1a]" onClick={(event) => { event.stopPropagation(); void removeFact(); }}>
                Remove this
              </span>
            </span>
          )}
        </div>
      )}
    </button>
  );
}

function AppCard({ app, refresh }: { app: PclIntegration | (typeof apps)[number]; refresh: () => void }) {
  const name = app.name || ("source" in app ? app.source : "") || "Connected app";
  const source = "source" in app ? app.source || name.toLowerCase() : name.toLowerCase();
  const icon = "icon" in app ? app.icon : iconForApp(name);
  const detail = "detail" in app ? app.detail : app.items_synced ? `${app.items_synced} items synced.` : `${name} is managed by PersonaLayer.`;
  const connected = "connected" in app ? Boolean(app.connected) : app.status === "connected" || app.status === "registered";
  const [enabled, setEnabled] = useState(connected);
  const [open, setOpen] = useState(false);

  async function toggle(next: boolean) {
    setEnabled(next);
    try {
      if (next) await connectIntegration(source);
      else await disconnectIntegration(source);
      refresh();
    } catch {
      setEnabled(!next);
    }
  }

  return (
    <article className="privacy-card app-lift">
      <div className="mb-5 flex items-start justify-between">
        <span className="privacy-square-icon">{icon}</span>
        <Switch checked={enabled} onChange={toggle} />
      </div>
      <h3 className="text-2xl font-semibold">{name}</h3>
      <button className="mt-2 text-sm font-bold text-[#006e2f]" onClick={() => setOpen((current) => !current)}>
        Details
      </button>
      {open && <p className="mt-3 text-base leading-6 text-[#3d4a3d]">{detail}</p>}
    </article>
  );
}

function AccessCard({
  icon,
  name,
  detail,
  source,
  refresh,
}: {
  icon: ReactNode;
  name: string;
  detail: string;
  source?: string;
  refresh: () => void;
}) {
  async function removeAccess() {
    if (!source) return;
    await disconnectIntegration(source);
    refresh();
  }

  return (
    <article className="privacy-card flex flex-col justify-between gap-6">
      <div className="flex gap-4">
        <span className="privacy-square-icon">{icon}</span>
        <div>
          <h3 className="text-2xl font-semibold">{name}</h3>
          <p className="mt-1 leading-6 text-[#3d4a3d]">{detail}</p>
        </div>
      </div>
      <button className="w-full rounded-full bg-[#f3f3f3] px-6 py-3 text-sm font-bold text-[#3d4a3d] transition hover:bg-[#ffdad6] hover:text-[#93000a] md:w-fit" onClick={removeAccess}>
        Remove access
      </button>
    </article>
  );
}

function PrivacyToggle({
  icon,
  title,
  detail,
  checked = false,
  target,
  boundary,
  refresh,
}: {
  icon: ReactNode;
  title: string;
  detail: string;
  checked?: boolean;
  target: string;
  boundary?: PrivacyBoundary;
  refresh: () => void;
}) {
  const [enabled, setEnabled] = useState(checked);

  useEffect(() => setEnabled(checked), [checked]);

  async function toggle(next: boolean) {
    setEnabled(next);
    try {
      if (next) await addPrivacyBoundary("never_share_field", target, `User marked ${title} private from UI`);
      else if (boundary?.id) await deletePrivacyBoundary(boundary.id);
      refresh();
    } catch {
      setEnabled(!next);
    }
  }

  return (
    <div className="flex items-center justify-between gap-4">
      <div className="flex items-center gap-4">
        <span className="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-[#e2e2e2] text-[#3d4a3d]">{icon}</span>
        <div>
          <p className="text-xl font-semibold">{title}</p>
          <p className="text-sm leading-5 text-[#3d4a3d] md:text-base">{detail}</p>
        </div>
      </div>
      <Switch checked={enabled} onChange={toggle} amber />
    </div>
  );
}

function Switch({
  checked,
  onChange,
  amber = false,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  amber?: boolean;
}) {
  return (
    <button
      className={`relative h-10 w-16 shrink-0 rounded-full transition ${
        checked ? (amber ? "bg-[#fea619] shadow-[0_0_16px_rgba(254,166,25,0.35)]" : "bg-[#006e2f]") : "bg-[#e2e2e2]"
      }`}
      onClick={() => onChange(!checked)}
      aria-pressed={checked}
    >
      <span
        className={`absolute top-1 h-8 w-8 rounded-full bg-white shadow transition ${
          checked ? "left-7" : "left-1"
        }`}
      />
    </button>
  );
}

function SummaryCard({ value, label, detail }: { value: string; label: string; detail: string }) {
  return (
    <article className="privacy-card">
      <p className="text-4xl font-bold text-[#006e2f]">{value}</p>
      <h3 className="mt-3 text-xl font-semibold">{label}</h3>
      <p className="mt-2 text-sm leading-6 text-[#3d4a3d]">{detail}</p>
    </article>
  );
}

function ProgressRow({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="mb-2 flex items-center justify-between text-sm font-bold text-[#3d4a3d]">
        <span>{label}</span>
        <span>{value}%</span>
      </div>
      <div className="h-4 overflow-hidden rounded-full bg-[#e2e2e2]">
        <div className="h-full rounded-full bg-[#006e2f]" style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}

function OnDeviceBadge({ backendStatus }: { backendStatus?: BackendStatus }) {
  return (
    <div className="inline-flex items-center gap-2 rounded-full bg-[#006e2f]/10 px-4 py-2 text-sm font-bold text-[#006e2f]">
      <span className="privacy-pulse h-2.5 w-2.5 rounded-full bg-[#006e2f]" />
      {backendStatus === "offline" ? "Backend offline: showing local preview" : "Running on your device"}
    </div>
  );
}

function PrivacyBottomNav({
  active,
  setScreen,
}: {
  active: "home" | "apps" | "privacy";
  setScreen: (screen: AppScreen) => void;
}) {
  const items = [
    { id: "home" as const, label: "Home", icon: <CircleUser size={20} />, screen: "privacy-home" as AppScreen },
    { id: "apps" as const, label: "Apps", icon: <Database size={20} />, screen: "privacy-apps" as AppScreen },
    { id: "privacy" as const, label: "Privacy", icon: <ShieldCheck size={20} />, screen: "privacy-controls" as AppScreen },
  ];

  return (
    <nav className="fixed bottom-0 left-0 z-30 flex h-20 w-full items-center justify-around bg-white px-4 shadow-soft md:hidden">
      {items.map((item) => (
        <button
          key={item.id}
          className={`flex min-w-20 flex-col items-center justify-center gap-1 rounded-full px-4 py-1 text-sm font-bold transition ${
            active === item.id ? "bg-[#22c55e]/20 text-[#006e2f]" : "text-[#3d4a3d]"
          }`}
          onClick={() => setScreen(item.screen)}
        >
          {item.icon}
          {item.label}
        </button>
      ))}
    </nav>
  );
}

function Divider() {
  return <div className="h-px w-full bg-[#bccbb9]/40" />;
}

export default PrivacyManager;

function mergeIntegrations(base: PclIntegration[], extras: PclIntegration[]) {
  const bySource = new Map<string, PclIntegration>();
  for (const item of [...base, ...extras]) {
    bySource.set(item.source || item.name || String(bySource.size), { ...bySource.get(item.source || item.name || ""), ...item });
  }
  return Array.from(bySource.values());
}

function iconForSignal(signalType?: string) {
  if (signalType === "skill" || signalType === "tool") return <Code size={22} />;
  if (signalType === "work_domain") return <Briefcase size={22} />;
  if (signalType === "preference" || signalType === "behavior") return <MessageCircle size={22} />;
  return <Database size={22} />;
}

function iconForApp(name: string) {
  const lower = name.toLowerCase();
  if (lower.includes("calendar")) return <CalendarDays size={28} />;
  if (lower.includes("github") || lower.includes("code")) return <Code size={28} />;
  if (lower.includes("browser") || lower.includes("search")) return <Search size={28} />;
  return <Database size={28} />;
}
