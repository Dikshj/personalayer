// Session helpers shared by the auth guard and pages. The Supabase access
// token is stored under personalayer_session_token (the same key api.ts reads
// for the Bearer header) and the user object under personalayer_user. Tokens
// are never logged or rendered.

import { API_CONFIG, clearSessionToken, getStoredSessionToken, isSessionExpired, storeSessionToken, storeSessionMeta } from "../api";

const USER_KEY = "personalayer_user";
const ONBOARDING_DONE_PREFIX = "personalayer_onboarding_done:";

export type StoredUser = { id: string; email?: string };

export function setSession(accessToken: string, user: StoredUser) {
  storeSessionToken(accessToken);
  storeSessionMeta(`supabase:${user.id}`);
  localStorage.setItem(USER_KEY, JSON.stringify({ id: user.id, email: user.email }));
}

export function getUser(): StoredUser | null {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? (JSON.parse(raw) as StoredUser) : null;
  } catch {
    return null;
  }
}

export function currentUserKey(): string {
  const user = getUser();
  return user?.id ? `supabase:${user.id}` : "local_user";
}

export function markOnboardingComplete() {
  localStorage.setItem(`${ONBOARDING_DONE_PREFIX}${currentUserKey()}`, "1");
}

export function hasCompletedOnboarding(): boolean {
  return localStorage.getItem(`${ONBOARDING_DONE_PREFIX}${currentUserKey()}`) === "1";
}

export function clearSession() {
  clearSessionToken();
  localStorage.removeItem(USER_KEY);
}

export function hasSession(): boolean {
  return Boolean(getStoredSessionToken()) && !isSessionExpired();
}

export function sessionRequired(): boolean {
  return API_CONFIG.requiresSession;
}

// A non-sensitive hint of the signed-in account for the settings screen, e.g.
// "j•••@example.com". Never reveals the token.
export function maskedHint(): string {
  const user = getUser();
  if (!user?.email) return "Signed in";
  const [name, domain] = user.email.split("@");
  if (!domain) return "Signed in";
  const head = name.slice(0, 1);
  return `${head}${"•".repeat(Math.max(1, name.length - 1))}@${domain}`;
}
