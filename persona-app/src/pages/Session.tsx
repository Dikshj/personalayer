// /app/session — sign up or sign in with Supabase email/password. On success
// the access token + user are stored locally (never shown), and the user is
// routed onward: new signups to onboarding, returning users to the dashboard.

import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Loader2, Lock, LogOut, Mail, ShieldCheck, TriangleAlert } from "lucide-react";
import { isSupabaseConfigured, supabase } from "../lib/supabase";
import { clearSession, hasSession, maskedHint, setSession } from "../auth/session";

type Mode = "signin" | "signup";

export default function Session() {
  const navigate = useNavigate();
  const [connected, setConnected] = useState(hasSession());
  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setInfo(null);
    if (!supabase) {
      setError("Sign-in isn’t configured yet. Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY, then reload.");
      return;
    }
    if (!email.trim() || !password) {
      setError("Enter your email and password.");
      return;
    }
    setBusy(true);
    try {
      if (mode === "signup") {
        const { data, error } = await supabase.auth.signUp({ email: email.trim(), password });
        if (error) throw error;
        if (data.session && data.user) {
          setSession(data.session.access_token, { id: data.user.id, email: data.user.email ?? email.trim() });
          navigate("/app/onboarding", { replace: true });
        } else {
          setInfo("Check your email to confirm your account, then sign in.");
          setMode("signin");
        }
      } else {
        const { data, error } = await supabase.auth.signInWithPassword({ email: email.trim(), password });
        if (error) throw error;
        if (data.session && data.user) {
          setSession(data.session.access_token, { id: data.user.id, email: data.user.email ?? email.trim() });
          navigate("/app/persona", { replace: true });
        } else {
          setError("Couldn’t start a session. Try again.");
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed. Check your details and try again.");
    } finally {
      setBusy(false);
    }
  };

  const signOut = async () => {
    if (supabase) await supabase.auth.signOut().catch(() => undefined);
    clearSession();
    setConnected(false);
  };

  return (
    <div className="grid min-h-dvh place-items-center bg-surface px-4 py-10 text-on-surface">
      <div className="w-full max-w-md rounded-2xl border border-outline-variant bg-white p-7 shadow-ambient">
        <span className="mb-4 flex items-center gap-2">
          <img src="/personalayer-mark.svg" alt="" className="h-8 w-8" />
          <span className="text-lg font-bold text-primary">PersonaLayer</span>
        </span>

        {connected ? (
          <>
            <h1 className="text-xl font-bold">You’re signed in</h1>
            <p className="mt-1.5 text-sm text-on-surface-variant">Signed in as <strong>{maskedHint()}</strong>.</p>
            <Link to="/app/persona" className="primary-button mt-5 w-full justify-center">
              Go to your control center <ArrowRight size={15} />
            </Link>
            <button
              className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg border border-danger/30 bg-danger/5 px-3 py-2.5 text-sm font-semibold text-danger transition hover:bg-danger/10"
              onClick={signOut}
            >
              <LogOut size={15} /> Sign out
            </button>
          </>
        ) : (
          <>
            <h1 className="text-xl font-bold">{mode === "signup" ? "Create your account" : "Welcome back"}</h1>
            <p className="mt-1.5 text-sm leading-6 text-on-surface-variant">
              {mode === "signup"
                ? "Sign up to build your private context layer. Your data stays yours."
                : "Sign in to your PersonaLayer control center."}
            </p>

            {!isSupabaseConfigured && (
              <div className="mt-4 flex items-start gap-2 rounded-lg border border-warn/40 bg-warn/10 px-3 py-2 text-sm font-semibold text-warn">
                <TriangleAlert size={15} className="mt-0.5 shrink-0" />
                Sign-in isn’t configured in this environment yet.
              </div>
            )}

            <form onSubmit={submit} className="mt-5 flex flex-col gap-4">
              <label className="flex flex-col gap-1.5">
                <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-on-surface-variant">
                  <Mail size={13} /> Email
                </span>
                <input
                  type="email"
                  autoComplete="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => { setEmail(e.target.value); setError(null); }}
                  className="h-11 rounded-lg border border-outline-variant px-3.5 text-sm outline-none focus:border-primary"
                />
              </label>
              <label className="flex flex-col gap-1.5">
                <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-on-surface-variant">
                  <Lock size={13} /> Password
                </span>
                <input
                  type="password"
                  autoComplete={mode === "signup" ? "new-password" : "current-password"}
                  placeholder={mode === "signup" ? "Choose a strong password" : "Your password"}
                  value={password}
                  onChange={(e) => { setPassword(e.target.value); setError(null); }}
                  className="h-11 rounded-lg border border-outline-variant px-3.5 text-sm outline-none focus:border-primary"
                />
              </label>

              {error && <p className="text-sm font-semibold text-danger">{error}</p>}
              {info && <p className="text-sm font-semibold text-ok">{info}</p>}

              <button type="submit" className="primary-button justify-center" disabled={busy}>
                {busy && <Loader2 size={15} className="animate-spin" />}
                {mode === "signup" ? "Create account" : "Sign in"} <ArrowRight size={15} />
              </button>
            </form>

            <p className="mt-4 text-center text-sm text-on-surface-variant">
              {mode === "signup" ? "Already have an account?" : "New to PersonaLayer?"}{" "}
              <button
                className="font-semibold text-primary hover:underline"
                onClick={() => { setMode(mode === "signup" ? "signin" : "signup"); setError(null); setInfo(null); }}
              >
                {mode === "signup" ? "Sign in" : "Create one"}
              </button>
            </p>
          </>
        )}

        <div className="mt-5 flex items-center gap-2 border-t border-outline-variant pt-4 text-xs text-outline">
          <ShieldCheck size={13} /> Your session token is stored only on this device and never displayed.
        </div>
        <Link to="/" className="mt-3 block text-center text-xs text-on-surface-variant hover:text-on-surface">← Back to home</Link>
      </div>
    </div>
  );
}
