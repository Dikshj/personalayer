/**
 * PersonaLayerBanner — shows the active persona + layout mode.
 *
 * Drop into: apps/web/components/email-list/PersonaLayerBanner.tsx
 * Mount it at the top of the <List> component in EmailList.tsx.
 *
 * Layer 1 = Persona Pack  (role-level: Founder / Student / Sales)
 * Layer 2 = Personal Delta (individual fine-tuning on top of pack)
 */

"use client";

import { usePersonaLayer } from "@/hooks/usePersonaLayer";

export function PersonaLayerBanner() {
  const { persona, viewConfig, connected, isLoading } = usePersonaLayer();

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 border-b border-border bg-background px-4 py-2 text-xs text-muted-foreground">
        <span className="animate-pulse">⟳</span>
        <span>Connecting to PersonaLayer…</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 border-b border-border bg-background px-4 py-2 text-xs">
      {/* Layer 1: Persona Pack badge */}
      <span
        className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-semibold ${viewConfig.colorClass}`}
      >
        {viewConfig.label}
      </span>

      {/* Layer 2: Personal delta (from live persona) */}
      {persona?.context?.current_focus && (
        <>
          <span className="text-muted-foreground">·</span>
          <span className="text-muted-foreground">
            Focus: <span className="text-foreground">{persona.context.current_focus}</span>
          </span>
        </>
      )}

      <span className="text-muted-foreground">·</span>
      <span className="text-muted-foreground">{viewConfig.description}</span>

      {/* Connection status */}
      <span className="ml-auto flex items-center gap-1 text-muted-foreground">
        <span
          className={`inline-block h-1.5 w-1.5 rounded-full ${connected ? "bg-green-500" : "bg-zinc-600"}`}
        />
        {connected ? "PersonaLayer connected" : "PersonaLayer offline — default view"}
      </span>
    </div>
  );
}
