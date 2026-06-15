// Tracks backend reachability so the shell and pages can show a consistent
// connection state and fall back to preview data when offline.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { getHealth } from "../api";

type State = "loading" | "online" | "offline";

interface Value {
  state: State;
  online: boolean;
  offline: boolean;
  recheck: () => void;
}

const Ctx = createContext<Value>({ state: "loading", online: false, offline: false, recheck: () => {} });

export function BackendProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State>("loading");
  const timer = useRef<number | null>(null);

  const recheck = useCallback(async () => {
    if (typeof navigator !== "undefined" && !navigator.onLine) {
      setState("offline");
      return;
    }
    try {
      await getHealth();
      setState("online");
    } catch {
      setState("offline");
    }
  }, []);

  useEffect(() => {
    recheck();
    timer.current = window.setInterval(recheck, 60_000);
    const on = () => recheck();
    const off = () => setState("offline");
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      if (timer.current) window.clearInterval(timer.current);
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, [recheck]);

  return (
    <Ctx.Provider value={{ state, online: state === "online", offline: state === "offline", recheck }}>
      {children}
    </Ctx.Provider>
  );
}

export function useBackend(): Value {
  return useContext(Ctx);
}
