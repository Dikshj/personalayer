// Reusable primitives styled with the app's Tailwind theme. Cards are used
// only for repeated items and tool panels — never nested.

import { useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import { Check, Copy, Loader2 } from "lucide-react";

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
    <section className={`min-w-0 rounded-2xl border border-outline-variant bg-white shadow-ambient ${className}`}>
      {(title || action) && (
        <header className="flex flex-col gap-3 border-b border-outline-variant px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-5">
          {title && <h2 className="min-w-0 text-base font-bold text-on-surface">{title}</h2>}
          {action && <div className="shrink-0">{action}</div>}
        </header>
      )}
      <div className="p-4 sm:p-5">{children}</div>
    </section>
  );
}

type Tone = "neutral" | "good" | "warn" | "danger" | "info";
const toneClass: Record<Tone, string> = {
  neutral: "bg-surface-container-low text-on-surface-variant border-outline-variant",
  good: "bg-ok/10 text-ok border-ok/20",
  warn: "bg-warn/10 text-warn border-warn/30",
  danger: "bg-danger/10 text-danger border-danger/20",
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
    danger: "border border-danger/30 bg-danger/5 text-danger hover:bg-danger/10",
  };
  return (
    <button className={`${base} min-h-10 ${variants[variant]} ${className}`} disabled={loading || rest.disabled} {...rest}>
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
        checked ? (amber ? "bg-warn" : "bg-ok") : "bg-[#d3d8dd]"
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
  disabled = false,
}: {
  children: ReactNode;
  confirmLabel?: string;
  onConfirm: () => void | Promise<void>;
  disabled?: boolean;
}) {
  const [armed, setArmed] = useState(false);
  const [busy, setBusy] = useState(false);
  if (!armed) {
    return (
      <Button variant="danger" disabled={disabled} onClick={() => setArmed(true)}>
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
    <div className="min-w-0 rounded-2xl border border-outline-variant bg-white p-4 shadow-ambient">
      <div className="break-words text-2xl font-bold text-on-surface">{value}</div>
      <div className="mt-0.5 text-sm text-on-surface-variant">{label}</div>
      {hint && <div className="mt-0.5 text-xs text-outline">{hint}</div>}
    </div>
  );
}

// Copies text to the clipboard with a transient confirmation. Renders inline
// so it can sit next to a code, fingerprint, or token.
export function CopyButton({
  value,
  label = "Copy",
  className = "",
}: {
  value: string;
  label?: string;
  className?: string;
}) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      // Fallback for non-secure contexts.
      const ta = document.createElement("textarea");
      ta.value = value;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand("copy");
      } catch {
        /* ignore */
      }
      document.body.removeChild(ta);
    }
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  };
  return (
    <button
      type="button"
      onClick={copy}
      className={`inline-flex items-center gap-1.5 rounded-lg border border-outline-variant px-2.5 py-1.5 text-xs font-semibold text-on-surface-variant transition hover:bg-surface-container-low ${className}`}
    >
      {copied ? <Check size={13} className="text-ok" /> : <Copy size={13} />}
      {copied ? "Copied" : label}
    </button>
  );
}

// Horizontal stepper for the pairing flow. Compact and wraps on narrow widths.
export function Stepper({ steps, current }: { steps: string[]; current: number }) {
  return (
    <ol className="flex flex-wrap items-center gap-x-2 gap-y-2">
      {steps.map((label, i) => {
        const state = i < current ? "done" : i === current ? "active" : "todo";
        return (
          <li key={label} className="flex items-center gap-2">
            <span
              className={`grid h-6 w-6 shrink-0 place-items-center rounded-full text-xs font-bold ${
                state === "done"
                  ? "bg-ok text-white"
                  : state === "active"
                    ? "bg-primary text-white"
                    : "bg-surface-container text-on-surface-variant"
              }`}
            >
              {state === "done" ? <Check size={13} /> : i + 1}
            </span>
            <span
              className={`text-xs font-semibold ${state === "todo" ? "text-outline" : "text-on-surface"}`}
            >
              {label}
            </span>
            {i < steps.length - 1 && <span className="hidden h-px w-6 bg-outline-variant sm:block" />}
          </li>
        );
      })}
    </ol>
  );
}

export function ConfidenceBar({ value }: { value: number }) {
  const n = value <= 1 ? value * 100 : value;
  const color = n >= 70 ? "bg-ok" : n >= 40 ? "bg-warn" : "bg-outline";
  return (
    <span className="inline-flex h-1.5 w-20 overflow-hidden rounded-full bg-surface-container" title={`${Math.round(n)}% confidence`}>
      <span className={`h-full rounded-full ${color}`} style={{ width: `${Math.min(100, Math.max(5, n))}%` }} />
    </span>
  );
}
