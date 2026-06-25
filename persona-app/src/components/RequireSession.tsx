// Guards the app shell. When a session is required (production, or the env
// var) and no token is stored, redirect to the session connection screen.

import { useEffect, useState, type ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { hasSession, sessionRequired, setSession } from "../auth/session";
import { isSessionExpired } from "../api";
import { supabase } from "../lib/supabase";

export default function RequireSession({ children }: { children: ReactNode }) {
  const location = useLocation();
  const required = sessionRequired();
  const [checking, setChecking] = useState(required && !hasSession());
  const [authenticated, setAuthenticated] = useState(!required || hasSession());

  useEffect(() => {
    if (!required || authenticated) {
      setChecking(false);
      return;
    }
    let active = true;
    if (!supabase) {
      setChecking(false);
      return;
    }
    supabase.auth.getSession().then(({ data }) => {
      if (!active) return;
      const session = data.session;
      if (session?.user) {
        setSession(session.access_token, {
          id: session.user.id,
          email: session.user.email,
        });
        setAuthenticated(true);
      }
      setChecking(false);
    });
    return () => {
      active = false;
    };
  }, [authenticated, required]);

  if (checking) {
    return <div className="grid min-h-dvh place-items-center bg-surface text-sm text-on-surface-variant">Restoring your session…</div>;
  }

  if (required && !authenticated) {
    const reason = isSessionExpired() ? "expired" : undefined;
    return <Navigate to="/app/session" replace state={{ from: location.pathname, reason }} />;
  }
  return <>{children}</>;
}
