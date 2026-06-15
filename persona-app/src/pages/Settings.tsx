// /app/settings — session management, export, delete data, legal, security.

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Download, FileText, LogOut, Mail, ShieldCheck, Trash2 } from "lucide-react";
import { OfflineBanner, PageHeader } from "../components/states";
import { Button, ConfirmButton, Panel } from "../components/ui";
import { useBackend } from "../lib/backend";
import {
  API_BASE,
  deleteAllContext,
  deleteUserData,
  exportControlCenterData,
} from "../api";
import { clearSession, maskedHint } from "../auth/session";
import { supabase } from "../lib/supabase";

const SECURITY_CONTACT = "security@personallayer.dev";

const LEGAL = [
  { title: "Privacy Policy", body: "Local-first. Raw activity stays on your device unless you explicitly share it. We never sell personal context or train models on it." },
  { title: "Terms of Service", body: "You own your personal data and context. Apps must request minimum scopes, disclose access, and respect revocation immediately." },
  { title: "Data Retention", body: "Raw events kept 90 days by default; query logs 30 days. Derived signals remain until you delete or reset them." },
];

export default function Settings() {
  const navigate = useNavigate();
  const { online, offline } = useBackend();
  const [exporting, setExporting] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const host = (() => {
    try {
      return new URL(API_BASE).host;
    } catch {
      return API_BASE || "(not configured)";
    }
  })();

  const exportData = async () => {
    setExporting(true);
    setNote(null);
    try {
      const data = await exportControlCenterData();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `personalayer-export-${Date.now()}.json`;
      a.click();
      URL.revokeObjectURL(url);
      setNote("Export downloaded.");
    } catch {
      setNote("Couldn’t reach the backend — export is unavailable while offline.");
    } finally {
      setExporting(false);
    }
  };

  const logout = async () => {
    if (supabase) await supabase.auth.signOut().catch(() => undefined);
    clearSession();
    navigate("/app/session", { replace: true });
  };

  return (
    <>
      <PageHeader title="Settings" subtitle="Manage your session, data, and legal preferences." />

      {offline && <OfflineBanner onRetry={() => window.location.reload()} />}

      <div className="flex flex-col gap-4">
        <Panel title="Session">
          <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4">
            <div>
              <dt className="text-xs uppercase tracking-wide text-outline">Account</dt>
              <dd className="truncate font-semibold">{maskedHint()}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-outline">Backend</dt>
              <dd className="truncate font-semibold">{host}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-outline">Status</dt>
              <dd className="font-semibold">{online ? "Connected" : offline ? "Offline" : "Connecting…"}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-outline">Token</dt>
              <dd className="font-semibold text-on-surface-variant">Stored · hidden</dd>
            </div>
          </dl>
          <div className="mt-4">
            <Button variant="default" onClick={logout}>
              <LogOut size={15} /> Clear session &amp; sign out
            </Button>
          </div>
        </Panel>

        <Panel title={<span className="inline-flex items-center gap-2"><Download size={16} /> Export your data</span>}>
          <p className="mb-4 text-sm text-on-surface-variant">Download a copy of your persona signals and settings as JSON.</p>
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="primary" loading={exporting} onClick={exportData}>
              <Download size={15} /> Export JSON
            </Button>
            {note && <span className="text-sm text-on-surface-variant">{note}</span>}
          </div>
        </Panel>

        <Panel title={<span className="inline-flex items-center gap-2"><Trash2 size={16} /> Delete data</span>}>
          <p className="mb-4 text-sm text-on-surface-variant">Permanently remove your context. This cannot be undone.</p>
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-danger/20 bg-danger/[0.03] p-4">
              <div>
                <div className="font-semibold">Delete all context</div>
                <div className="text-xs text-on-surface-variant">Removes signals, events, and synthesized profile.</div>
              </div>
              <ConfirmButton confirmLabel="Delete all context" onConfirm={async () => { await deleteAllContext().catch(() => undefined); }}>
                Delete
              </ConfirmButton>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-danger/20 bg-danger/[0.03] p-4">
              <div>
                <div className="font-semibold">Delete account data</div>
                <div className="text-xs text-on-surface-variant">Removes all records associated with this user.</div>
              </div>
              <ConfirmButton confirmLabel="Delete account data" onConfirm={async () => { await deleteUserData().catch(() => undefined); }}>
                Delete
              </ConfirmButton>
            </div>
          </div>
        </Panel>

        <Panel title={<span className="inline-flex items-center gap-2"><FileText size={16} /> Legal</span>}>
          <ul className="flex flex-col gap-4">
            {LEGAL.map((d) => (
              <li key={d.title}>
                <div className="font-semibold">{d.title}</div>
                <p className="mt-0.5 text-sm leading-6 text-on-surface-variant">{d.body}</p>
              </li>
            ))}
          </ul>
        </Panel>

        <Panel title={<span className="inline-flex items-center gap-2"><ShieldCheck size={16} /> Security</span>}>
          <p className="mb-3 text-sm text-on-surface-variant">Report a vulnerability or security concern.</p>
          <a className="inline-flex items-center gap-2 font-semibold text-primary" href={`mailto:${SECURITY_CONTACT}`}>
            <Mail size={15} /> {SECURITY_CONTACT}
          </a>
        </Panel>
      </div>
    </>
  );
}
