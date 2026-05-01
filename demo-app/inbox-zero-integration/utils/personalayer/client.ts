/**
 * PersonaLayer client for inbox-zero.
 *
 * Drop this into: apps/web/utils/personalayer/client.ts
 *
 * PersonaLayer runs locally at localhost:7823.
 * It exposes the user's behavioral profile — role, interests,
 * communication style, current focus — derived from their
 * browsing + activity data. Entirely on-device. No cloud.
 */

const PERSONALAYER_BASE = process.env.NEXT_PUBLIC_PERSONALAYER_URL ?? "http://localhost:7823";

export interface PersonaLayerProfile {
  identity: {
    role: string;           // "SaaS founder", "PhD student", "Sales Engineer"
    seniority?: string;
    industry?: string;
    location?: string;
  };
  voice: {
    tone: string;           // "direct", "analytical", "casual"
    preferred_length: string;
    formality: string;
  };
  decisions: {
    speed: string;          // "fast", "deliberate"
    risk_tolerance: string;
    priorities: string[];
  };
  context: {
    current_focus: string;
    active_projects: string[];
    tools: string[];
  };
  interests: {
    primary: string[];
    domains: string[];
  };
  meta: {
    event_count: number;
    generated_at: string;
    model: string;
  };
}

export type PersonaRole = "founder" | "student" | "sales" | "default";

/** Resolve structured role from persona data */
export function resolveRole(persona: PersonaLayerProfile | null): PersonaRole {
  if (!persona) return "default";

  const role = (persona.identity?.role ?? "").toLowerCase();
  if (/founder|ceo|cto|entrepreneur/.test(role)) return "founder";
  if (/student|learner|research|phd/.test(role)) return "student";
  if (/sales|bdr|account|revenue/.test(role)) return "sales";

  // Fallback: infer from interests
  const interests = JSON.stringify(persona.interests ?? "").toLowerCase();
  if (/startup|fundrais|pitch/.test(interests)) return "founder";
  if (/cours|study|exam/.test(interests)) return "student";
  if (/pipeline|crm|quota/.test(interests)) return "sales";

  return "founder"; // persona exists but unknown role → treat as founder
}

/** Fetch persona from PersonaLayer. Returns null if server not running. */
export async function fetchPersonaLayer(): Promise<PersonaLayerProfile | null> {
  try {
    const res = await fetch(`${PERSONALAYER_BASE}/persona`, {
      next: { revalidate: 300 }, // cache 5 min (Next.js fetch cache)
    });
    if (!res.ok) return null;
    return (await res.json()) as PersonaLayerProfile;
  } catch {
    return null;
  }
}
