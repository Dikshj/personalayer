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
