export function toMs(value: number | string | null | undefined): number | null {
  if (value == null || value === "") return null;
  if (typeof value === "number") return value < 1e12 ? value * 1000 : value;
  const parsed = Date.parse(value);
  if (!Number.isNaN(parsed)) return parsed;
  const asNum = Number(value);
  if (!Number.isNaN(asNum)) return asNum < 1e12 ? asNum * 1000 : asNum;
  return null;
}

export function relativeTime(value: number | string | null | undefined): string {
  const ms = toMs(value);
  if (ms == null) return "—";
  const abs = Math.abs(Date.now() - ms);
  const min = 60_000;
  const hour = 60 * min;
  const day = 24 * hour;
  if (abs < min) return "just now";
  if (abs < hour) return `${Math.round(abs / min)}m ago`;
  if (abs < day) return `${Math.round(abs / hour)}h ago`;
  if (abs < 7 * day) return `${Math.round(abs / day)}d ago`;
  return new Date(ms).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function titleize(value: string | undefined | null): string {
  if (!value) return "";
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .trim();
}

// Compact, deterministic fingerprint for a public key so the raw key is never
// shown. Folds the key into 8 bytes rendered as colon-separated hex groups.
export function fingerprint(key: string | undefined | null): string {
  if (!key) return "—";
  const bytes = new Array(8).fill(0);
  for (let i = 0; i < key.length; i += 1) {
    const idx = i % 8;
    bytes[idx] = (bytes[idx] * 31 + key.charCodeAt(i)) & 0xff;
  }
  return bytes.map((b) => b.toString(16).padStart(2, "0")).join(":").toUpperCase();
}

// Shortens a long version/hash for display while keeping it recognizable.
export function shortHash(value: string | undefined | null, head = 8): string {
  if (!value) return "—";
  return value.length <= head + 2 ? value : `${value.slice(0, head)}…`;
}
