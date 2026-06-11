// /app/session — connect and manage your session. Create a session from a
// bootstrap code (or paste a token), optionally remember this browser as a
// trusted device, see when the session expires, and sign out everywhere.

import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  Clock,
  KeyRound,
  Loader2,
  LogOut,
  Smartphone,
  ShieldCheck,
} from "lucide-react";
import {
  API_BASE,
  API_CONFIG,
  clearSessionToken,
  createLocalSession,
  getSessionMeta,
  getStoredSessionToken,
  isSessionExpired,
  rememberBrowserAsDevice,
  storeSessionMeta,
  storeSessionToken,
} from "../api";

function daysLeft(expiresAt?: number) {
  if (!expiresAt) return null;
  const ms = expiresAt - Date.now();
  if (ms <= 0) return "expired";
  const d = Math.floor(ms / 86_400_000);
  const h = Math.floor((ms % 86_400_000) / 3_600_000);
  return d >= 1 ? `${d} day${d === 1 ? "" : "s"}` : `${h} hour${h === 1 ? "" : "s"}`;
}

export default function Session() {
  const navigate = useNavigate();
  const location = useLocation();
  const expiredRedirect = (location.state as { reason?: string } | null)?.reason === "expired";

  const [connected, setConnected] = useState(Boolean(getStoredSessionToken()) && !isSessionExpired());
  const [token, setToken] = useState("");
  const [bootstrap, setBootstrap] = useState("");
  const [userId, setUserId] = useState("local_user");
  const [remember, setRemember] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"token" | "bootstrap" | "remember" | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const host = (() => {
    try {
      return new URL(API_BASE).host;
    } catch {
      return API_BASE || "(not configured)";
    }
  })();

  const finishConnect = async (uid: string) => {
    storeSessionMeta(uid);
    if (remember) await rememberBrowserAsDevice().catch(() => undefined);
    navigate("/app/persona", { replace: true });
  };

  const connectWithToken = async (e: FormEvent) => {
    e.preventDefault();
    const trimmed = token.trim();
    if (!trimmed) {
      setError("Enter a session token to connect.");
      return;
    }
    setBusy("token");
    storeSessionToken(trimmed);
    await finishConnect(userId.trim() || "local_user");
    setBusy(null);
  };

  const connectWithBootstrap = async () => {
    setBusy("bootstrap");
    setError(null);
    const uid = userId.trim() || "local_user";
    try {
      const res = await createLocalSession(uid, bootstrap.trim());
      storeSessionToken(res.session_token || `user:${uid}`);
      await finishConnect(uid);
    } catch (err) {
      // Backend unreachable — store a scoped marker so the control center loads
      // with preview data, and still record session metadata.
      if (err instanceof Error && /not configured|failed to fetch|networkerror/i.test(err.message)) {
        storeSessionToken(`user:${uid}`);
        await finishConnect(uid);
      } else {
        setError(err instanceof Error ? err.message : "Couldn’t create a session. Check your bootstrap code.");
      }
    } finally {
      setBusy(null);
    }
  };

  const signOutEverywhere = () => {
    clearSessionToken();
    setConnected(false);
    setToken("");
    setBootstrap("");
    setNote("Signed out. This browser no longer holds a session.");
  };

  const rememberThisBrowser = async () => {
    setBusy("remember");
    try {
      const res = await rememberBrowserAsDevice();
      setNote(res.status === "pending" || res.device ? "This browser is now a known device." : "Saved.");
    } catch {
      setNote("Couldn’t reach the backend — try again when connected.");
    } finally {
      setBusy(null);
    }
  };

  const meta = getSessionMeta();

  return (
    <div className="grid min-h-dvh place-items-center bg-surface px-4 py-10">
      <div className="w-full max-w-md rounded-2xl border border-outline-variant bg-white p-7 shadow-ambient">
        <span className="mb-4 flex items-center gap-2">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-primary/10 text-primary">
            <ShieldCheck size={20} />
          </span>
          <span className="text-lg font-bold text-primary">PersonaLayer</span>
        </span>

        {expiredRedirect && !connected && (
          <div className="mb-4 flex items-center gap-2 rounded-lg border border-[#fea619]/40 bg-[#fff8ec] px-3 py-2 text-sm font-semibold text-[#9a5b00]">
            <Clock size={15} /> Your session expired. Connect again to continue.
          </div>
        )}
        {note && (
          <div className="mb-4 rounded-lg border border-[#006e2f]/20 bg-[#006e2f]/5 px-3 py-2 text-sm font-semibold text-[#006e2f]">{note}</div>
        )}

        {connected ? (
          // ---- Manage an active session ----
          <>
            <h1 className="text-xl font-bold">Session active</h1>
            <p className="mt-1.5 text-sm leading-6 text-on-surface-variant">
              Connected to <code className="rounded bg-surface-container-low px-1.5 py-0.5 text-xs">{host}</code> as{" "}
              <strong>{meta?.user_id || "local_user"}</strong>.
            </p>

            <dl className="mt-4 grid grid-cols-2 gap-3">
              <div className="rounded-xl border border-outline-variant p-3">
                <dt className="text-xs uppercase tracking-wide text-outline">Expires in</dt>
                <dd className="font-semibold">{daysLeft(meta?.expires_at) || "—"}</dd>
              </div>
              <div className="rounded-xl border border-outline-variant p-3">
                <dt className="text-xs uppercase tracking-wide text-outline">Token</dt>
                <dd className="font-semibold text-on-surface-variant">Stored · hidden</dd>
              </div>
            </dl>

            <Link to="/app/persona" className="primary-button mt-5 w-full justify-center">
              Go to your control center <ArrowRight size={15} />
            </Link>

            <button className="secondary-button mt-3 w-full justify-center" onClick={rememberThisBrowser} disabled={busy === "remember"}>
              {busy === "remember" ? <Loader2 size={15} className="animate-spin" /> : <Smartphone size={15} />}
              Remember this browser as a device
            </button>

            <button
              className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg border border-[#ba1a1a]/30 bg-[#ba1a1a]/5 px-3 py-2.5 text-sm font-semibold text-[#ba1a1a] transition hover:bg-[#ba1a1a]/10"
              onClick={signOutEverywhere}
            >
              <LogOut size={15} /> Sign out everywhere
            </button>
            <p className="mt-2 text-xs text-outline">Clears the session on this browser. Pair again from another device anytime.</p>
          </>
        ) : (
          // ---- Connect ----
          <>
            <h1 className="text-xl font-bold">Connect your session</h1>
            <p className="mt-1.5 text-sm leading-6 text-on-surface-variant">
              Create a session with a bootstrap code from your backend. It’s stored locally and sent only to{" "}
              <code className="rounded bg-surface-container-low px-1.5 py-0.5 text-xs">{host}</code>.
            </p>

            {/* Primary: bootstrap code */}
            <div className="mt-5 flex flex-col gap-3">
              <label className="flex flex-col gap-1.5">
                <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-on-surface-variant">
                  <KeyRound size={13} /> Bootstrap code
                </span>
                <input
                  type="password"
                  autoComplete="off"
                  spellCheck={false}
                  placeholder="Paste your bootstrap code"
                  value={bootstrap}
                  onChange={(e) => { setBootstrap(e.target.value); setError(null); }}
                  className="h-11 rounded-lg border border-outline-variant px-3.5 font-mono text-sm outline-none focus:border-primary"
                />
              </label>
              <label className="flex flex-col gap-1.5">
                <span className="text-xs font-semibold text-on-surface-variant">User ID</span>
                <input
                  type="text"
                  autoComplete="off"
                  spellCheck={false}
                  placeholder="local_user"
                  value={userId}
                  onChange={(e) => setUserId(e.target.value)}
                  className="h-11 rounded-lg border border-outline-variant px-3.5 text-sm outline-none focus:border-primary"
                />
              </label>

              <label className="flex cursor-pointer items-center gap-2.5">
                <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} className="h-4 w-4 accent-[#004ac6]" />
                <span className="text-sm font-semibold">Remember this browser as a device</span>
              </label>

              {error && <p className="text-sm font-semibold text-[#ba1a1a]">{error}</p>}

              <button className="primary-button w-full justify-center" onClick={connectWithBootstrap} disabled={busy === "bootstrap"}>
                {busy === "bootstrap" && <Loader2 size={15} className="animate-spin" />}
                Create session <ArrowRight size={15} />
              </button>
            </div>

            {/* Advanced: paste a token */}
            <details className="mt-4 rounded-lg border border-outline-variant px-3 py-2">
              <summary className="cursor-pointer text-xs font-semibold text-on-surface-variant">Advanced — paste a session token</summary>
              <form onSubmit={connectWithToken} className="mt-3 flex flex-col gap-3">
                <input
                  type="password"
                  autoComplete="off"
                  spellCheck={false}
                  placeholder="Session token"
                  value={token}
                  onChange={(e) => { setToken(e.target.value); setError(null); }}
                  className="h-10 rounded-lg border border-outline-variant px-3 font-mono text-sm outline-none focus:border-primary"
                />
                <button type="submit" className="secondary-button w-full justify-center" disabled={busy === "token"}>
                  {busy === "token" && <Loader2 size={15} className="animate-spin" />}
                  Connect with token
                </button>
              </form>
            </details>

            {/* Pair from another device */}
            <div className="mt-4 flex items-start gap-3 rounded-xl border border-outline-variant bg-surface-container-low p-3">
              <Smartphone size={18} className="mt-0.5 shrink-0 text-primary" />
              <div className="text-sm">
                <div className="font-semibold">Already set up elsewhere?</div>
                <Link to="/app/devices" className="text-primary hover:underline">Pair this browser from another device →</Link>
              </div>
            </div>

            <p className="mt-4 text-xs text-on-surface-variant">
              {API_CONFIG.requiresSession ? "A session is required to use the control center." : "A session is optional in this environment."}
            </p>
          </>
        )}

        <div className="mt-5 flex items-center gap-2 border-t border-outline-variant pt-4 text-xs text-outline">
          <ShieldCheck size={13} /> Codes and tokens are never displayed again after entry.
        </div>
        <Link to="/" className="mt-3 block text-center text-xs text-on-surface-variant hover:text-on-surface">← Back to home</Link>
      </div>
    </div>
  );
}
