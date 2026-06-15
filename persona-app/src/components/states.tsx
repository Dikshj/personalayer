// Shared loading / empty / error / offline states.

import type { ReactNode } from "react";
import { AlertTriangle, CloudOff, Inbox, Loader2, RefreshCw } from "lucide-react";
import { Button } from "./ui";

export function PageHeader({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}) {
  return (
    <header className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-on-surface">{title}</h1>
        {subtitle && <p className="mt-1 max-w-2xl text-sm leading-6 text-on-surface-variant">{subtitle}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </header>
  );
}

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12 text-on-surface-variant" role="status">
      <Loader2 className="animate-spin" size={22} />
      <span className="text-sm">{label}</span>
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  hint,
  action,
}: {
  icon?: ReactNode;
  title: string;
  hint?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-10 text-center">
      <span className="grid h-12 w-12 place-items-center rounded-xl bg-surface-container-low text-on-surface-variant">
        {icon ?? <Inbox size={22} />}
      </span>
      <div className="font-semibold text-on-surface">{title}</div>
      {hint && <p className="max-w-sm text-sm text-on-surface-variant">{hint}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-10 text-center">
      <span className="grid h-12 w-12 place-items-center rounded-xl bg-danger/10 text-danger">
        <AlertTriangle size={22} />
      </span>
      <div className="font-semibold text-on-surface">Couldn’t load this</div>
      <p className="max-w-sm text-sm text-on-surface-variant">{message}</p>
      {onRetry && (
        <Button variant="default" onClick={onRetry} className="mt-1">
          <RefreshCw size={15} /> Try again
        </Button>
      )}
    </div>
  );
}

export function OfflineBanner({ onRetry }: { onRetry?: () => void }) {
  return (
    <div className="mb-5 flex flex-wrap items-center gap-3 rounded-xl border border-warn/40 bg-warn/10 px-4 py-3 text-sm text-warn">
      <CloudOff size={16} />
      <span className="flex-1">
        <strong className="text-on-surface">Backend offline.</strong> Showing preview data — changes won’t be saved.
      </span>
      {onRetry && (
        <button className="rounded-full border border-warn/50 px-3 py-1 text-xs font-semibold" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}
