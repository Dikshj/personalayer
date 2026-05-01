/**
 * usePersonaLayer — React hook for inbox-zero components.
 *
 * Drop this into: apps/web/hooks/usePersonaLayer.ts
 *
 * Uses SWR so the persona is fetched once per session and shared
 * across all components that call this hook. If PersonaLayer is
 * offline the hook degrades gracefully — returns null persona +
 * default view config, inbox-zero works normally.
 */

"use client";

import useSWR from "swr";
import {
  fetchPersonaLayer,
  resolveRole,
  type PersonaLayerProfile,
  type PersonaRole,
} from "@/utils/personalayer/client";

export interface ViewConfig {
  role: PersonaRole;
  /** Display label shown in the UI banner */
  label: string;
  /** Short explanation of why inbox-zero looks like this */
  description: string;
  /** Which email list layout to default to */
  defaultLayout: "list" | "task" | "pipeline" | "timeline";
  /** CSS class for the persona pill badge */
  colorClass: string;
  /** Comparator for sorting email threads */
  sortThreads: <T extends { plan?: { rule?: unknown } }>(threads: T[]) => T[];
}

const VIEW_CONFIGS: Record<PersonaRole, Omit<ViewConfig, "role">> = {
  founder: {
    label: "🚀 Founder mode",
    description: "Action-first: urgent items surfaced, noise suppressed",
    defaultLayout: "task",
    colorClass: "bg-indigo-950 text-indigo-300",
    sortThreads: (threads) => {
      // Threads with AI plan rules (pending actions) float to top
      return [...threads].sort((a, b) => (b.plan?.rule ? 1 : 0) - (a.plan?.rule ? 1 : 0));
    },
  },
  student: {
    label: "🎓 Student mode",
    description: "Timeline view: grouped by date, deadlines highlighted",
    defaultLayout: "timeline",
    colorClass: "bg-green-950 text-green-300",
    sortThreads: (threads) => threads, // chronological — keep API order
  },
  sales: {
    label: "💼 Sales mode",
    description: "Pipeline view: threads bucketed by conversation stage",
    defaultLayout: "pipeline",
    colorClass: "bg-yellow-950 text-yellow-300",
    sortThreads: (threads) => threads,
  },
  default: {
    label: "👤 Default",
    description: "Standard inbox view",
    defaultLayout: "list",
    colorClass: "bg-zinc-900 text-zinc-400",
    sortThreads: (threads) => threads,
  },
};

export interface UsePersonaLayerResult {
  persona: PersonaLayerProfile | null;
  viewConfig: ViewConfig;
  role: PersonaRole;
  isLoading: boolean;
  /** true if PersonaLayer is online */
  connected: boolean;
}

export function usePersonaLayer(): UsePersonaLayerResult {
  const { data: persona, isLoading } = useSWR<PersonaLayerProfile | null>(
    "personalayer/persona",
    fetchPersonaLayer,
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: false,
      dedupingInterval: 5 * 60 * 1000, // 5 min
      fallbackData: null,
    },
  );

  const role = resolveRole(persona ?? null);
  const base = VIEW_CONFIGS[role];

  return {
    persona: persona ?? null,
    viewConfig: { role, ...base },
    role,
    isLoading,
    connected: !isLoading && persona !== null,
  };
}
