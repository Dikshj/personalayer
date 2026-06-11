// Session connection screen. Accepts a session token or starts a local
// session via the backend bootstrap flow. The raw token is never shown again.

import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, KeyRound, Loader2, ShieldCheck } from "lucide-react";
import { API_BASE, API_CONFIG, createLocalSession, getStoredSessionToken, storeSessionToken } from "../api";

export default function Session() {
  const navigate = useNavigate();
  const [token, setToken] = useState("");
  const [userId, setUserId] = useState("local_user");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const already = Boolean(getStoredSessionToken());
  const host = (() => {
    try {
      return new URL(API_BASE).host;
    } catch {
      return API_BASE || "(not configured)";
    }
  })();

  const connectWithToken = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = token.trim();
    if (!trimmed) {
      setError("Enter a session token to connect.");
      return;
    }
    storeSessionToken(trimmed);
    navigate("/app/persona", { replace: true });
  };

  const startLocalSession = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await createLocalSession(userId.trim() || "local_user");
      // Prefer a returned bearer token; otherwise the backend set an httpOnly
      // cookie and we store a scoped marker so the guard passes.
      storeSessionToken(res.session_token || `user:${userId.trim() || "local_user"}`);
      navigate("/app/persona", { replace: true });
    } catch {
      // Backend unreachable — store a scoped local marker so the control
      // center loads with preview data.
      storeSessionToken(`user:${userId.trim() || "local_user"}`);
      navigate("/app/persona", { replace: true });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid min-h-dvh place-items-center bg-surface px-4 py-10">
      <div className="w-full max-w-md rounded-2xl border border-outline-variant bg-white p-7 shadow-ambient">
        <span className="mb-4 flex items-center gap-2">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-primary/10 text-primary">
            <ShieldCheck size={20} />
          </span>
          <span className="text-lg font-bold text-primary">PersonaLayer</span>
        </span>

        <h1 className="text-xl font-bold">Connect your session</h1>
        <p className="mt-1.5 text-sm leading-6 text-on-surface-variant">
          PersonaLayer connects to your context backend. Your token is stored locally on this device and sent only to{" "}
          <code className="rounded bg-surface-container-low px-1.5 py-0.5 text-xs">{host}</code>.
        </p>

        <form onSubmit={connectWithToken} className="mt-5 flex flex-col gap-4">
          <label className="flex flex-col gap-1.5">
            <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-on-surface-variant">
              <KeyRound size={13} /> Session token
            </span>
            <input
              type="password"
              autoComplete="off"
              spellCheck={false}
              placeholder="Paste your session token"
              value={token}
              onChange={(e) => {
                setToken(e.target.value);
                setError(null);
              }}
              className="h-11 rounded-lg border border-outline-variant px-3.5 font-mono text-sm outline-none focus:border-primary"
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-semibold text-on-surface-variant">User ID (optional)</span>
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

          {error && <p className="text-sm font-semibold text-[#ba1a1a]">{error}</p>}

          <button type="submit" className="primary-button justify-center">
            Connect <ArrowRight size={15} />
          </button>
        </form>

        <div className="my-4 flex items-center gap-3 text-xs text-outline">
          <span className="h-px flex-1 bg-outline-variant" /> or <span className="h-px flex-1 bg-outline-variant" />
        </div>

        <button className="secondary-button w-full justify-center" onClick={startLocalSession} disabled={busy}>
          {busy && <Loader2 size={15} className="animate-spin" />}
          Start a local session
        </button>
        <p className="mt-2 text-xs text-on-surface-variant">
          {API_CONFIG.requiresSession
            ? "A scoped local session lets you explore the control center."
            : "Session is optional in this environment."}
        </p>

        {already && (
          <p className="mt-4 text-xs text-on-surface-variant">
            You already have a session.{" "}
            <Link to="/app/persona" className="font-semibold text-primary">Go to your control center →</Link>
          </p>
        )}

        <div className="mt-5 flex items-center gap-2 border-t border-outline-variant pt-4 text-xs text-outline">
          <ShieldCheck size={13} /> Tokens are never displayed again after entry.
        </div>
        <Link to="/" className="mt-3 block text-center text-xs text-on-surface-variant hover:text-on-surface">
          ← Back to home
        </Link>
      </div>
    </div>
  );
}
