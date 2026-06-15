// /app/session — sign up or sign in with Supabase email/password. On success
// the access token + user are stored locally (never shown), and the user is
// routed onward: new signups to onboarding, returning users to the dashboard.

import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Loader2, Lock, LogOut, Mail, ShieldCheck, TriangleAlert } from "lucide-react";
import { isSupabaseConfigured, supabase } from "../lib/supabase";
import { clearSession, hasSession, maskedHint, setSession } from "../auth/session";

type Mode = "signin" | "signup" | "recovery" | "reset";

export default function Session() {
  const navigate = useNavigate();
  const [connected, setConnected] = useState(hasSession());
  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  useEffect(() => {
    if (!supabase) return;
    const { data } = supabase.auth.onAuthStateChange((event) => {
      if (event === "PASSWORD_RECOVERY") {
        setConnected(false);
        setMode("reset");
        setPassword("");
        setError(null);
        setInfo("Enter a new password for your PersonaLayer account.");
      }
    });
    return () => data.subscription.unsubscribe();
  }, []);

  const title =
    mode === "signup"
      ? "Create your account"
      : mode === "recovery"
        ? "Reset your password"
        : mode === "reset"
          ? "Choose a new password"
          : "Welcome back";

  const description =
    mode === "signup"
      ? "Sign up to build your private context layer. Your data stays yours."
      : mode === "recovery"
        ? "Enter your account email and Supabase will send password reset instructions."
        : mode === "reset"
          ? "Set a new password from the recovery link you opened."
          : "Sign in to your PersonaLayer control center.";

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setInfo(null);
    if (!supabase) {
      setError("Sign-in isn’t configured yet. Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY, then reload.");
      return;
    }
    if (mode === "recovery") {
      if (!email.trim()) {
        setError("Enter the email for your account.");
        return;
      }
      setBusy(true);
      try {
        const { error } = await supabase.auth.resetPasswordForEmail(email.trim(), {
          redirectTo: `${window.location.origin}/app/session`,
        });
        if (error) throw error;
        setMode("signin");
        setInfo("If an account exists for that email, reset instructions have been sent.");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not send password reset instructions.");
      } finally {
        setBusy(false);
      }
      return;
    }
    if (mode === "reset") {
      if (!password || password.length < 6) {
        setError("Enter a new password with at least 6 characters.");
        return;
      }
      setBusy(true);
      try {
        const { data, error } = await supabase.auth.updateUser({ password });
        if (error) throw error;
        const { data: sessionData } = await supabase.auth.getSession();
        if (sessionData.session && data.user) {
          setSession(sessionData.session.access_token, { id: data.user.id, email: data.user.email ?? email.trim() });
          setConnected(true);
        }
        setPassword("");
        setMode("signin");
        setInfo("Password updated. Sign in with your new password.");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Password reset failed.");
      } finally {
        setBusy(false);
      }
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
            <h1 className="text-xl font-bold">{title}</h1>
            <p className="mt-1.5 text-sm leading-6 text-on-surface-variant">{description}</p>

            {!isSupabaseConfigured && (
              <div className="mt-4 flex items-start gap-2 rounded-lg border border-warn/40 bg-warn/10 px-3 py-2 text-sm font-semibold text-warn">
                <TriangleAlert size={15} className="mt-0.5 shrink-0" />
                Sign-in isn’t configured in this environment yet.
              </div>
            )}

            <form onSubmit={submit} className="mt-5 flex flex-col gap-4">
              {mode !== "reset" && (
                <label className="flex flex-col gap-1.5">
                  <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-on-surface-variant">
                    <Mail size={13} /> Email
                  </span>
                  <input
                    type="email"
                    autoComplete="email"
                    placeholder="you@example.com"
                    value={email}
                    onChange={(e) => { setEmail(e.target.value); setError(null); setInfo(null); }}
                    className="h-11 rounded-lg border border-outline-variant px-3.5 text-sm outline-none focus:border-primary"
                  />
                </label>
              )}
              {mode !== "recovery" && (
                <label className="flex flex-col gap-1.5">
                  <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-on-surface-variant">
                    <Lock size={13} /> {mode === "reset" ? "New password" : "Password"}
                  </span>
                  <input
                    type="password"
                    autoComplete={mode === "signin" ? "current-password" : "new-password"}
                    placeholder={mode === "reset" || mode === "signup" ? "Choose a strong password" : "Your password"}
                    value={password}
                    onChange={(e) => { setPassword(e.target.value); setError(null); setInfo(null); }}
                    className="h-11 rounded-lg border border-outline-variant px-3.5 text-sm outline-none focus:border-primary"
                  />
                </label>
              )}

              {error && <p className="text-sm font-semibold text-danger">{error}</p>}
              {info && <p className="text-sm font-semibold text-ok">{info}</p>}

              <button type="submit" className="primary-button justify-center" disabled={busy}>
                {busy && <Loader2 size={15} className="animate-spin" />}
                {mode === "signup"
                  ? "Create account"
                  : mode === "recovery"
                    ? "Send reset email"
                    : mode === "reset"
                      ? "Update password"
                      : "Sign in"}{" "}
                <ArrowRight size={15} />
              </button>
            </form>

            <div className="mt-4 flex flex-col gap-2 text-center text-sm text-on-surface-variant">
              {mode === "signin" && (
                <button
                  className="font-semibold text-primary hover:underline"
                  onClick={() => { setMode("recovery"); setError(null); setInfo(null); }}
                >
                  Forgot password?
                </button>
              )}
              {mode !== "reset" && (
                <button
                  className="font-semibold text-primary hover:underline"
                  onClick={() => { setMode(mode === "signup" ? "signin" : "signup"); setError(null); setInfo(null); }}
                >
                  {mode === "signup" ? "Already have an account? Sign in" : "New to PersonaLayer? Create one"}
                </button>
              )}
              {(mode === "recovery" || mode === "reset") && (
                <button
                  className="font-semibold text-primary hover:underline"
                  onClick={() => { setMode("signin"); setError(null); setInfo(null); }}
                >
                  Back to sign in
                </button>
              )}
            </div>
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
