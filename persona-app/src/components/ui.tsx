// Reusable primitives styled with the app's Tailwind theme. Cards are used
// only for repeated items and tool panels — never nested.

import { useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import { Loader2 } from "lucide-react";

export function Panel({
  title,
  action,
  children,
  className = "",
}: {
  title?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-2xl border border-outline-variant bg-white shadow-ambient ${className}`}>
      {(title || action) && (
        <header className="flex items-center justify-between gap-3 border-b border-outline-variant px-5 py-4">
          {title && <h2 className="text-base font-bold text-on-surface">{title}</h2>}
          {action && <div className="shrink-0">{action}</div>}
        </header>
      )}
      <div className="p-5">{children}</div>
    </section>
  );
}

type Tone = "neutral" | "good" | "warn" | "danger" | "info";
const toneClass: Record<Tone, string> = {
  neutral: "bg-surface-container-low text-on-surface-variant border-outline-variant",
  good: "bg-[#006e2f]/10 text-[#006e2f] border-[#006e2f]/20",
  warn: "bg-[#fea619]/10 text-[#9a5b00] border-[#fea619]/30",
  danger: "bg-[#ba1a1a]/10 text-[#ba1a1a] border-[#ba1a1a]/20",
  info: "bg-primary/10 text-primary border-primary/20",
};

export function Pill({ children, tone = "neutral" }: { children: ReactNode; tone?: Tone }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-semibold ${toneClass[tone]}`}
    >
      {children}
    </span>
  );
}

export function Chip({ children }: { children: ReactNode }) {
  return (
    <span className="whitespace-nowrap rounded-md border border-outline-variant bg-surface-container-low px-2 py-0.5 text-xs font-medium text-on-surface-variant">
      {children}
    </span>
  );
}

export function Button({
  children,
  variant = "default",
  loading = false,
  className = "",
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "default" | "primary" | "ghost" | "danger";
  loading?: boolean;
}) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-sm font-semibold transition active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50";
  const variants: Record<string, string> = {
    default: "border border-outline-variant bg-white text-on-surface hover:bg-surface-container-low",
    primary: "bg-primary text-white hover:bg-primary-container",
    ghost: "text-on-surface-variant hover:bg-surface-container-low",
    danger: "border border-[#ba1a1a]/30 bg-[#ba1a1a]/5 text-[#ba1a1a] hover:bg-[#ba1a1a]/10",
  };
  return (
    <button className={`${base} ${variants[variant]} ${className}`} disabled={loading || rest.disabled} {...rest}>
      {loading && <Loader2 size={15} className="animate-spin" />}
      {children}
    </button>
  );
}

export function Switch({
  checked,
  onChange,
  amber = false,
  label,
  disabled,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  amber?: boolean;
  label?: string;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      className={`relative h-7 w-12 shrink-0 rounded-full transition disabled:opacity-50 ${
        checked ? (amber ? "bg-[#fea619]" : "bg-[#006e2f]") : "bg-[#d3d8dd]"
      }`}
      onClick={() => onChange(!checked)}
    >
      <span
        className={`absolute top-1 h-5 w-5 rounded-full bg-white shadow transition-all ${checked ? "left-6" : "left-1"}`}
      />
    </button>
  );
}

// Two-step confirm to guard destructive actions without a modal dependency.
export function ConfirmButton({
  children,
  confirmLabel = "Confirm",
  onConfirm,
}: {
  children: ReactNode;
  confirmLabel?: string;
  onConfirm: () => void | Promise<void>;
}) {
  const [armed, setArmed] = useState(false);
  const [busy, setBusy] = useState(false);
  if (!armed) {
    return (
      <Button variant="danger" onClick={() => setArmed(true)}>
        {children}
      </Button>
    );
  }
  return (
    <span className="inline-flex items-center gap-2">
      <Button
        variant="danger"
        loading={busy}
        onClick={async () => {
          setBusy(true);
          try {
            await onConfirm();
          } finally {
            setBusy(false);
            setArmed(false);
          }
        }}
      >
        {confirmLabel}
      </Button>
      <Button variant="ghost" onClick={() => setArmed(false)} disabled={busy}>
        Cancel
      </Button>
    </span>
  );
}

export function Stat({ value, label, hint }: { value: ReactNode; label: string; hint?: string }) {
  return (
    <div className="rounded-2xl border border-outline-variant bg-white p-4 shadow-ambient">
      <div className="text-2xl font-bold text-on-surface">{value}</div>
      <div className="mt-0.5 text-sm text-on-surface-variant">{label}</div>
      {hint && <div className="mt-0.5 text-xs text-outline">{hint}</div>}
    </div>
  );
}

export function ConfidenceBar({ value }: { value: number }) {
  const n = value <= 1 ? value * 100 : value;
  const color = n >= 70 ? "bg-[#006e2f]" : n >= 40 ? "bg-[#fea619]" : "bg-outline";
  return (
    <span className="inline-flex h-1.5 w-20 overflow-hidden rounded-full bg-surface-container" title={`${Math.round(n)}% confidence`}>
      <span className={`h-full rounded-full ${color}`} style={{ width: `${Math.min(100, Math.max(5, n))}%` }} />
    </span>
  );
}
