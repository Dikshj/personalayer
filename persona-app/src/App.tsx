import {
  ArrowLeft,
  ArrowRight,
  CircleHelp,
  Delete,
  FileText,
  History,
  KeyRound,
  LockKeyhole,
  Mail,
  QrCode,
  RefreshCw,
  ScanLine,
  Settings,
  ShieldCheck,
  Smartphone,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  API_CONFIG,
  BackendStatus,
  PairingSession,
  getHealth,
  getPairingSession,
  getStoredSessionToken,
  startPairingSession,
  storeSessionToken,
} from "./api";
import PrivacyManager from "./PrivacyManager";

type Screen = "laptop" | "scan" | "manual" | "success" | "privacy-home" | "privacy-apps" | "privacy-controls" | "legal";

const manualCode = ["A", "7", "-", "B", "2", "-", "X", "9"];
const keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "A", "0"];

function App() {
  const [screen, setScreen] = useState<Screen>("privacy-home");
  const [pairingCode, setPairingCode] = useState("");
  const [backendStatus, setBackendStatus] = useState<BackendStatus>("loading");
  const [pairingSession, setPairingSession] = useState<PairingSession | null>(null);
  const [pairingError, setPairingError] = useState("");
  const [sessionToken, setSessionToken] = useState(() => getStoredSessionToken());

  const addCodeChar = (value: string) => {
    setPairingCode((current) => `${current}${value}`.slice(0, 6));
  };

  const removeCodeChar = () => {
    setPairingCode((current) => current.slice(0, -1));
  };

  const completeManualEntry = pairingCode.length === 6;
  const privacyScreen = screen === "privacy-home" || screen === "privacy-apps" || screen === "privacy-controls";
  const legalScreen = screen === "legal";

  useEffect(() => {
    let active = true;
    getHealth()
      .then(() => active && setBackendStatus("online"))
      .catch(() => active && setBackendStatus("offline"));
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    let timer: number | undefined;

    if (screen !== "laptop" || backendStatus !== "online") return undefined;

    setPairingError("");
    startPairingSession()
      .then((data) => {
        if (!active) return;
        if (data.session) {
          setPairingSession(data.session);
          if (data.session.id) {
            timer = window.setInterval(() => {
              getPairingSession(data.session?.id || "")
                .then((next) => next.session && setPairingSession(next.session))
                .catch(() => undefined);
            }, 5000);
          }
        } else {
          setPairingError(data.status || "Unable to start pairing");
        }
      })
      .catch((error: Error) => {
        if (active) {
          setPairingError(error.message);
          setBackendStatus("offline");
        }
      });

    return () => {
      active = false;
      if (timer) window.clearInterval(timer);
    };
  }, [backendStatus, screen]);

  return (
    <div className="min-h-dvh bg-surface text-on-surface">
      <TopBar screen={screen} setScreen={setScreen} />

      <main className={`${privacyScreen || legalScreen ? "" : "mx-auto flex min-h-[calc(100dvh-64px)] w-full max-w-6xl flex-col px-5 py-6 md:px-8 md:py-10"}`}>
        {legalScreen && <LegalDocuments />}
        {!legalScreen && !API_CONFIG.hasApiBase && <DeploymentConfigScreen />}
        {!legalScreen && API_CONFIG.hasApiBase && API_CONFIG.requiresSession && !sessionToken && (
          <SessionSetupScreen
            onSave={(token) => {
              storeSessionToken(token);
              setSessionToken(token.trim());
            }}
          />
        )}
        {!legalScreen && API_CONFIG.hasApiBase && (!API_CONFIG.requiresSession || sessionToken) && (
          <>
        {screen === "laptop" && (
          <LaptopPairingScreen
            setScreen={setScreen}
            backendStatus={backendStatus}
            pairingSession={pairingSession}
            pairingError={pairingError}
          />
        )}
        {screen === "scan" && <ScanQrScreen setScreen={setScreen} />}
        {screen === "manual" && (
          <ManualEntryScreen
            code={pairingCode}
            complete={completeManualEntry}
            addCodeChar={addCodeChar}
            removeCodeChar={removeCodeChar}
            setScreen={setScreen}
          />
        )}
        {screen === "success" && <SuccessScreen setScreen={setScreen} />}
        {privacyScreen && <PrivacyManager screen={screen} setScreen={setScreen} />}
          </>
        )}
      </main>
    </div>
  );
}

function DeploymentConfigScreen() {
  return (
    <section className="mx-auto flex min-h-[calc(100dvh-64px)] w-full max-w-2xl items-center px-5">
      <div className="w-full rounded-lg border border-outline-variant bg-white p-8 shadow-ambient">
        <p className="mb-2 text-sm font-semibold uppercase tracking-[0.18em] text-outline">Deployment setup</p>
        <h1 className="text-3xl font-bold tracking-normal">Production API is not configured.</h1>
        <p className="mt-4 leading-7 text-on-surface-variant">
          Set <code className="rounded bg-surface-container-low px-1.5 py-1">VITE_PERSONALAYER_API_BASE</code> on the hosting provider to the production PersonaLayer API origin, then rebuild this app.
        </p>
      </div>
    </section>
  );
}

function SessionSetupScreen({ onSave }: { onSave: (token: string) => void }) {
  const [token, setToken] = useState("");

  return (
    <section className="mx-auto flex min-h-[calc(100dvh-64px)] w-full max-w-2xl items-center px-5">
      <div className="w-full rounded-lg border border-outline-variant bg-white p-8 shadow-ambient">
        <p className="mb-2 text-sm font-semibold uppercase tracking-[0.18em] text-outline">Session required</p>
        <h1 className="text-3xl font-bold tracking-normal">Connect your local session.</h1>
        <p className="mt-4 leading-7 text-on-surface-variant">
          Paste a PersonaLayer session token for the deployed frontend. The token is stored in this browser and sent as a bearer token to the configured API.
        </p>
        <label className="mt-6 block text-sm font-semibold text-on-surface-variant" htmlFor="session-token">
          Session token
        </label>
        <input
          id="session-token"
          className="mt-2 h-12 w-full rounded-lg border border-outline-variant px-4 font-mono text-sm outline-none focus:border-primary"
          value={token}
          onChange={(event) => setToken(event.target.value)}
          placeholder="pl_session token"
        />
        <button
          className="primary-button mt-5 justify-center disabled:cursor-not-allowed disabled:opacity-50"
          disabled={!token.trim()}
          onClick={() => onSave(token)}
        >
          Save session
        </button>
      </div>
    </section>
  );
}

function LegalDocuments() {
  const docs = [
    {
      title: "Privacy Policy",
      effective: "Effective June 6, 2026",
      body: [
        "PersonaLayer is local-first. Raw app, browser, connector, email, note, and local file content stays on the user's device unless the user explicitly exports it, syncs it to a trusted paired device, or authorizes sharing with an app.",
        "The cloud service stores only thin metadata for account routing, developer registry, API key hashes, app permissions, device pairing, push routing, redacted telemetry, and optional encrypted sync blobs.",
        "PersonaLayer does not sell personal context, train foundation models on user context, or expose raw local events through standard app APIs.",
      ],
    },
    {
      title: "Terms of Service",
      effective: "Effective June 6, 2026",
      body: [
        "Users own their personal data and context. Developers must request only minimum scopes, disclose context access, respect revocation immediately, and treat context bundles as confidential user data.",
        "Apps may not use PersonaLayer for spyware, unauthorized monitoring, credential harvesting, consent bypass, or high-stakes decisions without appropriate disclosure, human review, and legal compliance.",
        "The service is provided as available and should receive counsel review before broad commercial launch or regulated use.",
      ],
    },
    {
      title: "Data Retention",
      effective: "Production default schedule",
      body: [
        "Raw local events are retained for 90 days by default. Local query logs are retained for 30 days by default. Derived persona signals remain until deletion, replacement, or profile reset.",
        "Context bundles are session-only unless a user grants a longer-lived, purpose-specific permission. Receiving apps must not keep session-only bundles beyond the active session.",
        "Operational telemetry is retained for up to 30 days. Cloud permission, account, push, and device metadata is deleted when no longer needed for the account, security, or legal obligations.",
      ],
    },
    {
      title: "Security Contact",
      effective: "Vulnerability disclosure",
      body: [
        "Report suspected vulnerabilities to security@personallayer.dev with affected component, reproduction steps, impact, and any proof-of-concept using synthetic data.",
        "Production deployments must use HTTPS, explicit CORS origins, row-level security, OS secure storage for keys and tokens, redacted telemetry, and silent push payloads without behavioral text.",
        "Privacy requests go to privacy@personallayer.dev. Legal notices go to legal@personallayer.dev.",
      ],
    },
  ];

  return (
    <section className="min-h-[calc(100dvh-64px)] bg-[#f7f9fb] px-5 py-8 md:px-8 md:py-12">
      <div className="mx-auto max-w-5xl">
        <div className="mb-8 flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="mb-2 text-sm font-semibold uppercase tracking-[0.18em] text-outline">Production legal</p>
            <h1 className="text-3xl font-bold tracking-normal md:text-4xl">Legal and security readiness</h1>
            <p className="mt-3 max-w-2xl leading-7 text-on-surface-variant">
              Public-facing operating language for PersonaLayer before real users or real data enter production.
            </p>
          </div>
          <a className="primary-button w-fit" href="mailto:security@personallayer.dev">
            <Mail size={18} />
            Security contact
          </a>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          {docs.map((doc) => (
            <article key={doc.title} className="rounded-lg border border-outline-variant bg-white p-6 shadow-ambient">
              <div className="mb-4 flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-xl font-bold tracking-normal">{doc.title}</h2>
                  <p className="mt-1 text-sm font-semibold text-primary">{doc.effective}</p>
                </div>
                <div className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-surface-container-low text-primary">
                  <FileText size={20} />
                </div>
              </div>
              <div className="space-y-3 text-sm leading-6 text-on-surface-variant">
                {doc.body.map((paragraph) => (
                  <p key={paragraph}>{paragraph}</p>
                ))}
              </div>
            </article>
          ))}
        </div>

        <div className="mt-6 rounded-lg border border-outline-variant bg-white p-5 text-sm leading-6 text-on-surface-variant shadow-ambient">
          Source documents live in <code className="rounded bg-surface-container-low px-1.5 py-1">docs/PRIVACY_POLICY.md</code>,{" "}
          <code className="rounded bg-surface-container-low px-1.5 py-1">docs/TERMS_OF_SERVICE.md</code>,{" "}
          <code className="rounded bg-surface-container-low px-1.5 py-1">docs/DATA_RETENTION.md</code>, and{" "}
          <code className="rounded bg-surface-container-low px-1.5 py-1">docs/SECURITY.md</code>.
        </div>
      </div>
    </section>
  );
}

function TopBar({
  screen,
  setScreen,
}: {
  screen: Screen;
  setScreen: (screen: Screen) => void;
}) {
  const privacyScreen = screen === "privacy-home" || screen === "privacy-apps" || screen === "privacy-controls";
  const legalScreen = screen === "legal";
  const compact = screen !== "laptop" && !privacyScreen && !legalScreen;

  return (
    <header
      className={`sticky top-0 z-40 flex h-16 items-center justify-between border-b px-5 md:px-8 ${
        screen === "scan"
          ? "border-white/10 bg-black/30 text-white backdrop-blur"
          : "border-outline-variant bg-surface"
      }`}
    >
      <div className="flex items-center gap-3">
        {compact && (
          <button
            className="icon-button"
            onClick={() => setScreen("laptop")}
            aria-label="Back to pairing"
            title="Back"
          >
            <ArrowLeft size={20} />
          </button>
        )}
        <div className="flex items-center gap-2">
          <ShieldCheck className={screen === "scan" ? "text-white" : "text-primary-container"} size={24} />
          <span className={`text-lg font-bold ${screen === "scan" ? "text-white" : "text-primary"}`}>
            {privacyScreen || legalScreen ? "PersonaLayer" : "Fortress Logic"}
          </span>
        </div>
      </div>

      <div className="flex min-w-0 items-center gap-2">
        <div className="flex max-w-[calc(100vw-160px)] items-center overflow-x-auto rounded-full bg-surface-container-low p-1 sm:max-w-none">
          <button
            className={`shrink-0 rounded-full px-3 py-2 text-sm font-semibold transition sm:px-4 ${!privacyScreen && !legalScreen ? "bg-white text-primary shadow-sm" : "text-on-surface-variant"}`}
            onClick={() => setScreen("laptop")}
          >
            Pairing
          </button>
          <button
            className={`shrink-0 rounded-full px-3 py-2 text-sm font-semibold transition sm:px-4 ${privacyScreen ? "bg-white text-primary shadow-sm" : "text-on-surface-variant"}`}
            onClick={() => setScreen("privacy-home")}
          >
            Privacy
          </button>
          <button
            className={`shrink-0 rounded-full px-3 py-2 text-sm font-semibold transition sm:px-4 ${legalScreen ? "bg-white text-primary shadow-sm" : "text-on-surface-variant"}`}
            onClick={() => setScreen("legal")}
          >
            Legal
          </button>
        </div>
        <button className="icon-button" aria-label="Settings" title="Settings">
          <Settings size={20} />
        </button>
      </div>
    </header>
  );
}

function LaptopPairingScreen({
  setScreen,
  backendStatus,
  pairingSession,
  pairingError,
}: {
  setScreen: (screen: Screen) => void;
  backendStatus: BackendStatus;
  pairingSession: PairingSession | null;
  pairingError: string;
}) {
  const code = formatPairingCode(pairingSession?.pairing_code);
  const qrPayload = pairingSession?.qr_payload ? JSON.stringify(pairingSession.qr_payload) : "PersonaLayer pairing pending";

  return (
    <section className="grid flex-1 items-center gap-8 md:grid-cols-[1fr_380px]">
      <div className="mx-auto w-full max-w-[540px] rounded-lg border border-outline-variant bg-white p-8 shadow-ambient md:p-12">
        <div className="mb-8 text-center">
          <p className="mb-2 text-sm font-semibold uppercase tracking-[0.18em] text-outline">Secure device pairing</p>
          <h1 className="text-3xl font-bold leading-tight tracking-normal md:text-4xl">Pair Your Device</h1>
          <p className="mx-auto mt-3 max-w-[340px] text-base leading-6 text-on-surface-variant">
            Scan the QR code with the mobile app to securely sync your account.
          </p>
        </div>

        <div className="flex flex-col items-center gap-8">
          <div className="relative rounded-lg border border-outline-variant bg-white p-6">
            <QrVisual payload={qrPayload} />
            <div className="absolute -right-4 -top-4 grid h-14 w-14 place-items-center rounded-full border border-outline-variant bg-white shadow-ambient">
              <span className="text-xs font-bold text-primary">{pairingSession?.status || "ready"}</span>
            </div>
          </div>

          <div className="w-full text-center">
            <p className="mb-3 text-sm font-semibold uppercase tracking-[0.18em] text-outline">Manual Pairing Code</p>
            <div className="flex flex-wrap justify-center gap-2">
              {code.map((char, index) =>
                char === "-" ? (
                  <span key={`${char}-${index}`} className="grid h-14 w-4 place-items-center text-outline-variant">
                    -
                  </span>
                ) : (
                  <span
                    key={`${char}-${index}`}
                    className="grid h-14 w-12 rounded border border-outline-variant bg-surface-container-low font-mono text-xl font-semibold text-primary"
                  >
                    {char}
                  </span>
                ),
              )}
            </div>
            <p className="mt-4 text-sm text-on-surface-variant">
              {backendStatus === "online" && pairingSession
                ? `Session ${pairingSession.id?.slice(0, 8) || "active"} is ${pairingSession.status || "pending"}.`
                : backendStatus === "loading"
                  ? "Connecting to the local PersonaLayer backend..."
                  : "Backend is offline. Showing the Stitch demo flow until the API is running."}
            </p>
            {pairingError && <p className="mt-2 text-sm font-semibold text-[#ba1a1a]">{pairingError}</p>}
          </div>

          <div className="grid w-full gap-3 sm:grid-cols-2">
            <button className="secondary-button" type="button">
              <RefreshCw size={18} />
              Refresh Code
            </button>
            <button className="primary-button" type="button" onClick={() => setScreen("scan")}>
              <Smartphone size={18} />
              Open Mobile Flow
            </button>
          </div>
        </div>
      </div>

      <aside className="hidden rounded-lg border border-outline-variant bg-surface-container-low p-5 md:block">
        <p className="mb-4 text-sm font-semibold uppercase tracking-[0.18em] text-outline">Flow Preview</p>
        <div className="space-y-3">
          <PreviewStep active icon={<QrCode size={18} />} label="Display QR and fallback code" />
          <PreviewStep icon={<ScanLine size={18} />} label="Scan from mobile device" />
          <PreviewStep icon={<KeyRound size={18} />} label="Enter code manually when needed" />
          <PreviewStep icon={<ShieldCheck size={18} />} label="Store keys in Secure Enclave" />
        </div>
      </aside>
    </section>
  );
}

function ScanQrScreen({ setScreen }: { setScreen: (screen: Screen) => void }) {
  return (
    <section className="-mx-5 -my-6 flex min-h-[calc(100dvh-64px)] flex-1 flex-col overflow-hidden bg-black md:-mx-8 md:-my-10">
      <div className="camera-field relative flex flex-1 flex-col items-center justify-center px-5 pb-28 pt-20 text-white">
        <div className="absolute top-8 z-10 max-w-sm px-4 text-center">
          <h1 className="text-2xl font-bold">Scan QR Code</h1>
          <p className="mt-2 text-sm leading-5 text-slate-200">
            Position the code on your secondary device within the frame to begin pairing.
          </p>
        </div>

        <div className="scanner-frame relative z-10 grid h-[280px] w-[280px] place-items-center rounded-lg border border-white/25">
          <span className="corner corner-tl" />
          <span className="corner corner-tr" />
          <span className="corner corner-bl" />
          <span className="corner corner-br" />
          <span className="scan-beam" />
          <div className="grid h-12 w-12 place-items-center rounded-full border border-white/20">
            <span className="h-1 w-1 rounded-full bg-white/50" />
          </div>
        </div>

        <div className="absolute bottom-8 z-10 w-full max-w-sm px-5">
          <button className="primary-button h-14 w-full justify-center" onClick={() => setScreen("manual")}>
            <KeyRound size={20} />
            Enter Code Manually
          </button>
          <p className="mt-4 text-center text-sm text-slate-200">Having trouble? Use the manual pairing code.</p>
        </div>
      </div>
      <MobileNav active="scan" setScreen={setScreen} />
    </section>
  );
}

function ManualEntryScreen({
  code,
  complete,
  addCodeChar,
  removeCodeChar,
  setScreen,
}: {
  code: string;
  complete: boolean;
  addCodeChar: (value: string) => void;
  removeCodeChar: () => void;
  setScreen: (screen: Screen) => void;
}) {
  const codeSlots = useMemo(() => Array.from({ length: 6 }, (_, index) => code[index] ?? ""), [code]);

  return (
    <section className="-mx-5 -my-6 flex min-h-[calc(100dvh-64px)] flex-1 flex-col items-center bg-surface md:-mx-8 md:-my-10">
      <div className="flex w-full max-w-[640px] flex-1 flex-col items-center px-5 py-8">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold">Enter Pairing Code</h1>
          <p className="mt-2 max-w-sm text-base leading-6 text-on-surface-variant">
            Enter the 6-character code displayed on your other device to synchronize accounts.
          </p>
        </div>

        <div className="mb-8 grid grid-cols-6 gap-2">
          {codeSlots.map((char, index) => (
            <div
              key={index}
              className={`grid h-16 w-12 place-items-center rounded-lg border bg-white font-mono text-3xl font-semibold uppercase text-primary transition ${
                index === code.length ? "border-primary ring-2 ring-primary/40" : "border-outline"
              }`}
            >
              {char}
            </div>
          ))}
        </div>

        <button className="mb-8 inline-flex items-center gap-2 text-sm font-semibold text-primary">
          <CircleHelp size={18} />
          Where is the code?
        </button>

        <button
          className={`h-14 w-full max-w-sm rounded-lg text-base font-bold transition ${
            complete ? "bg-primary text-white active:scale-[0.98]" : "cursor-not-allowed bg-outline text-white opacity-50"
          }`}
          disabled={!complete}
          onClick={() => setScreen("success")}
        >
          Link Device
        </button>
      </div>

      <div className="w-full border-t border-outline-variant bg-surface-container p-2">
        <div className="mx-auto grid max-w-sm grid-cols-3 gap-2">
          {keys.map((key) => (
            <button key={key} className="key-button" onClick={() => addCodeChar(key)}>
              {key}
            </button>
          ))}
          <button className="key-button bg-surface-container-low" onClick={removeCodeChar} aria-label="Backspace">
            <Delete size={22} />
          </button>
        </div>
      </div>
      <MobileNav active="manual" setScreen={setScreen} />
    </section>
  );
}

function SuccessScreen({ setScreen }: { setScreen: (screen: Screen) => void }) {
  return (
    <section className="-mx-5 -my-6 flex min-h-[calc(100dvh-64px)] flex-1 flex-col items-center bg-surface px-5 pb-24 pt-12 md:-mx-8 md:-my-10">
      <div className="mt-auto flex w-full max-w-sm flex-col items-center text-center">
        <div className="success-mark relative mb-8 grid h-32 w-32 place-items-center rounded-full bg-secondary text-white">
          <ShieldCheck size={64} strokeWidth={1.8} />
        </div>
        <h1 className="text-2xl font-bold">Device Paired Successfully</h1>
        <p className="mt-3 leading-6 text-on-surface-variant">
          Your private keys are now securely stored in your device's Secure Enclave.
        </p>

        <div className="mt-8 grid w-full gap-1">
          <InfoRow icon={<LockKeyhole size={20} />} label="Storage Mode" value="Hardware Encrypted" />
          <InfoRow icon={<RefreshCw size={20} />} label="Sync Status" value="Real-time Active" accent="green" />
        </div>

        <div className="mt-8 grid w-full gap-2">
          <button className="primary-button h-12 justify-center" onClick={() => setScreen("laptop")}>
            Get Started
            <ArrowRight size={18} />
          </button>
          <button className="secondary-button h-12 justify-center" onClick={() => setScreen("laptop")}>
            Manage Devices
          </button>
        </div>

        <div className="mt-8 inline-flex items-center gap-2 rounded-full border border-secondary/20 bg-secondary-container/30 px-3 py-1.5 text-sm font-semibold text-on-secondary-container">
          <span className="h-2 w-2 rounded-full bg-secondary" />
          Secure Sync Active
        </div>
      </div>
      <div className="mt-auto" />
      <MobileNav active="history" setScreen={setScreen} />
    </section>
  );
}

function MobileNav({
  active,
  setScreen,
}: {
  active: "scan" | "manual" | "history";
  setScreen: (screen: Screen) => void;
}) {
  const items = [
    { id: "scan" as const, label: "Scan", icon: <ScanLine size={20} />, screen: "scan" as Screen },
    { id: "manual" as const, label: "Manual", icon: <KeyRound size={20} />, screen: "manual" as Screen },
    { id: "history" as const, label: "History", icon: <History size={20} />, screen: "success" as Screen },
  ];

  return (
    <nav className="fixed bottom-0 left-0 z-30 flex h-20 w-full items-center justify-around border-t border-outline-variant bg-surface px-4 shadow-ambient">
      {items.map((item) => (
        <button
          key={item.id}
          className={`flex min-w-20 flex-col items-center justify-center gap-1 rounded-full px-4 py-1 text-sm transition ${
            active === item.id ? "bg-secondary-container text-on-secondary-container" : "text-on-surface-variant"
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

function QrVisual({ payload }: { payload: string }) {
  const cells = useMemo(() => {
    let hash = 0;
    for (const char of payload) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
    return Array.from({ length: 49 }, (_, index) => ((hash >> (index % 24)) + index * 7) % 3 === 0);
  }, [payload]);

  return (
    <div className="qr-grid relative grid h-[220px] w-[220px] grid-cols-7 gap-1 overflow-hidden rounded bg-white p-4 md:h-[240px] md:w-[240px]" title={payload}>
      <span className="qr-eye left-4 top-4" />
      <span className="qr-eye right-4 top-4" />
      <span className="qr-eye bottom-4 left-4" />
      {cells.map((filled, index) => (
        <span key={index} className={filled ? "rounded-sm bg-slate-900" : "rounded-sm bg-white"} />
      ))}
      <span className="scan-line" />
    </div>
  );
}

function formatPairingCode(code?: string) {
  const raw = (code || manualCode.filter((char) => char !== "-").join("")).toUpperCase().replace(/[^A-Z0-9]/g, "");
  const normalized = raw.padEnd(6, " ").slice(0, 6).split("");
  return [normalized[0], normalized[1], "-", normalized[2], normalized[3], "-", normalized[4], normalized[5]];
}

function PreviewStep({ active, icon, label }: { active?: boolean; icon: React.ReactNode; label: string }) {
  return (
    <div className={`flex items-center gap-3 rounded-lg border p-3 ${active ? "border-primary bg-white" : "border-outline-variant bg-white/60"}`}>
      <span className={active ? "text-primary" : "text-on-surface-variant"}>{icon}</span>
      <span className="text-sm font-medium">{label}</span>
    </div>
  );
}

function InfoRow({
  icon,
  label,
  value,
  accent = "blue",
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  accent?: "blue" | "green";
}) {
  return (
    <div className="flex items-center gap-4 rounded-lg border border-outline-variant bg-surface-container-low p-4 text-left">
      <div className={`grid h-10 w-10 place-items-center rounded-lg border border-outline-variant bg-white ${accent === "green" ? "text-secondary" : "text-primary"}`}>
        {icon}
      </div>
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-on-surface-variant">{label}</p>
        <p className="font-semibold">{value}</p>
      </div>
    </div>
  );
}

export default App;
