// Guards the app shell. When a session is required (production, or the env
// var) and no token is stored, redirect to the session connection screen.

import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { API_CONFIG, getStoredSessionToken, isSessionExpired } from "../api";

export default function RequireSession({ children }: { children: ReactNode }) {
  const location = useLocation();
  if (API_CONFIG.requiresSession && (!getStoredSessionToken() || isSessionExpired())) {
    const reason = isSessionExpired() ? "expired" : undefined;
    return <Navigate to="/app/session" replace state={{ from: location.pathname, reason }} />;
  }
  return <>{children}</>;
}
