// Stable authenticated shell: desktop sidebar + mobile bottom navigation,
// a top bar with connection status and a session menu (clear session).

import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  Activity,
  AppWindow,
  CircleUser,
  LayoutGrid,
  LogOut,
  type LucideIcon,
  Radio,
  Settings,
  ShieldCheck,
  Smartphone,
} from "lucide-react";
import { BackendProvider, useBackend } from "../lib/backend";
import { getPrivacyProfile } from "../api";
import { clearSession } from "../auth/session";
import { supabase } from "../lib/supabase";

const ONBOARDING_CHECK_KEY = "pl_onboarding_checked";

// Sends brand-new users (onboarding not completed) straight to the welcome
// wizard, once per session. Stays out of the way when the backend is
// unreachable or onboarding is already done, so no one gets trapped.
function useFirstRunRedirect() {
  const navigate = useNavigate();
  useEffect(() => {
    if (sessionStorage.getItem(ONBOARDING_CHECK_KEY)) return;
    let cancelled = false;
    getPrivacyProfile()
      .then((profile) => {
        sessionStorage.setItem(ONBOARDING_CHECK_KEY, "1");
        if (!cancelled && profile && profile.onboarding_completed === false) {
          navigate("/app/onboarding", { replace: true });
        }
      })
      .catch(() => {
        // Offline or error — don't redirect, and retry on the next session.
      });
    return () => {
      cancelled = true;
    };
  }, [navigate]);
}

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
}

const NAV: NavItem[] = [
  { to: "/app/persona", label: "Persona", icon: CircleUser },
  { to: "/app/apps", label: "Apps", icon: AppWindow },
  { to: "/app/privacy", label: "Privacy", icon: ShieldCheck },
  { to: "/app/activity", label: "Activity", icon: Activity },
  { to: "/app/devices", label: "Devices", icon: Smartphone },
  { to: "/app/capture", label: "Capture", icon: Radio },
  { to: "/app/settings", label: "Settings", icon: Settings },
];

const MOBILE_NAV: NavItem[] = [
  NAV[0],
  NAV[1],
  NAV[2],
  NAV[4],
];

function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <span className="flex items-center gap-2">
      <img src="/personalayer-mark.svg" alt="" className="h-8 w-8" />
      {!compact && <span className="text-lg font-bold text-primary">PersonaLayer</span>}
    </span>
  );
}

function ConnectionDot() {
  const { state, recheck } = useBackend();
  const label = state === "online" ? "Connected" : state === "offline" ? "Backend offline" : "Connecting…";
  const dot = state === "online" ? "bg-ok" : state === "offline" ? "bg-danger" : "bg-warn";
  return (
    <button
      className="inline-flex items-center gap-2 rounded-full border border-outline-variant bg-white px-3 py-1.5 text-xs font-semibold text-on-surface-variant"
      onClick={recheck}
      title="Re-check connection"
    >
      <span className={`h-2 w-2 rounded-full ${dot}`} />
      <span className="hidden sm:inline">{label}</span>
    </button>
  );
}

function ShellInner() {
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  useFirstRunRedirect();

  useEffect(() => {
    if (!menuOpen) return;
    const close = () => setMenuOpen(false);
    window.addEventListener("click", close);
    return () => window.removeEventListener("click", close);
  }, [menuOpen]);

  const logout = async () => {
    if (supabase) await supabase.auth.signOut().catch(() => undefined);
    clearSession();
    navigate("/app/session", { replace: true });
  };

  return (
    <div className="min-h-dvh bg-surface text-on-surface">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r border-outline-variant bg-white px-3 py-4 lg:flex">
        <div className="px-2 pb-5">
          <NavLink to="/">
            <Brand />
          </NavLink>
        </div>
        <nav className="flex flex-1 flex-col gap-1">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-semibold transition ${
                  isActive ? "bg-primary/10 text-primary" : "text-on-surface-variant hover:bg-surface-container-low"
                }`
              }
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>
        <button
          className="mt-2 flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-semibold text-on-surface-variant transition hover:bg-surface-container-low"
          onClick={logout}
        >
          <LogOut size={18} /> Clear session
        </button>
      </aside>

      <div className="lg:pl-60">
        {/* Top bar */}
        <header className="sticky top-0 z-20 flex h-14 items-center justify-between gap-3 border-b border-outline-variant bg-surface/90 px-3 backdrop-blur sm:px-4 md:px-6">
          <NavLink to="/app/persona" className="lg:hidden">
            <Brand />
          </NavLink>
          <div className="ml-auto flex items-center gap-2">
            <ConnectionDot />
            <div className="relative" onClick={(e) => e.stopPropagation()}>
              <button
                className="grid h-9 w-9 place-items-center rounded-full border border-outline-variant bg-white text-on-surface"
                onClick={() => setMenuOpen((o) => !o)}
                aria-haspopup="menu"
                aria-label="Session menu"
              >
                <CircleUser size={20} />
              </button>
              {menuOpen && (
                <div className="absolute right-0 top-11 w-52 rounded-xl border border-outline-variant bg-white p-1.5 shadow-ambient" role="menu">
                  <NavLink
                    to="/app/settings"
                    className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-on-surface hover:bg-surface-container-low"
                    role="menuitem"
                  >
                    <Settings size={15} /> Settings
                  </NavLink>
                  <button
                    className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-danger hover:bg-danger/5"
                    onClick={logout}
                    role="menuitem"
                  >
                    <LogOut size={15} /> Clear session
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Content */}
        <main className="mx-auto w-full max-w-5xl min-w-0 px-3 py-5 pb-[calc(6rem+env(safe-area-inset-bottom))] sm:px-4 md:px-6 lg:pb-10">
          <Outlet />
        </main>
      </div>

      {/* Mobile bottom navigation */}
      <nav className="fixed inset-x-0 bottom-0 z-30 flex border-t border-outline-variant bg-white pb-[env(safe-area-inset-bottom)] lg:hidden">
        {MOBILE_NAV.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex flex-1 flex-col items-center gap-0.5 py-2 text-[11px] font-semibold ${
                isActive ? "text-primary" : "text-on-surface-variant"
              }`
            }
          >
            <Icon size={20} />
            <span className="max-w-full truncate">{label}</span>
          </NavLink>
        ))}
        <NavLink
          to="/app/settings"
          className={({ isActive }) =>
            `flex flex-1 flex-col items-center gap-0.5 py-2 text-[11px] font-semibold ${
              isActive ? "text-primary" : "text-on-surface-variant"
            }`
          }
        >
          <LayoutGrid size={20} />
          <span className="max-w-full truncate">More</span>
        </NavLink>
      </nav>
    </div>
  );
}

export default function AppShell() {
  return (
    <BackendProvider>
      <ShellInner />
    </BackendProvider>
  );
}
