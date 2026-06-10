import { Link } from "react-router-dom";
import {
  ArrowRight,
  Eye,
  Lock,
  type LucideIcon,
  ServerCog,
  ShieldCheck,
  SlidersHorizontal,
  Trash2,
} from "lucide-react";
import { getStoredSessionToken } from "../api";

const FEATURES: { icon: LucideIcon; title: string; body: string }[] = [
  { icon: Eye, title: "See what’s known", body: "A clear view of every signal, its confidence, and where it came from — no hidden profile." },
  { icon: SlidersHorizontal, title: "Control every signal", body: "Hide, edit, or delete any signal. Set sharing defaults and per-app permissions." },
  { icon: ShieldCheck, title: "Privacy by default", body: "Always-private categories never leave your layer. Sensitive data is dropped, not shared." },
  { icon: Lock, title: "Local-first", body: "Your context stays close to you. Apps request access; you decide what they receive." },
];

export default function Landing() {
  const entered = Boolean(getStoredSessionToken());
  return (
    <div className="min-h-dvh bg-surface text-on-surface">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-5 py-5 md:px-8">
        <span className="flex items-center gap-2">
          <span className="grid h-9 w-9 place-items-center rounded-lg bg-primary/10 text-primary">
            <ShieldCheck size={22} />
          </span>
          <span className="text-lg font-bold text-primary">PersonaLayer</span>
        </span>
        <nav className="flex items-center gap-5 text-sm font-semibold text-on-surface-variant">
          <a href="#how" className="hidden hover:text-on-surface sm:inline">How it works</a>
          <a href="#privacy" className="hidden hover:text-on-surface sm:inline">Privacy</a>
          <Link to="/app/persona" className="primary-button !px-4 !py-2 !text-sm">
            {entered ? "Open app" : "Open control center"} <ArrowRight size={15} />
          </Link>
        </nav>
      </header>

      <section className="mx-auto flex max-w-3xl flex-col items-center gap-5 px-5 py-16 text-center md:py-24">
        <span className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3.5 py-1.5 text-xs font-semibold text-primary">
          <ShieldCheck size={14} /> Local-first personal context layer
        </span>
        <h1 className="text-4xl font-bold leading-[1.1] tracking-tight md:text-6xl">
          See, edit, and control what apps can know about you.
        </h1>
        <p className="max-w-xl text-base leading-7 text-on-surface-variant md:text-lg">
          PersonaLayer is your private control center for personal context. It builds a living picture of your work and
          preferences from your own activity — and puts you in charge of every signal apps can use.
        </p>
        <div className="mt-2 flex flex-wrap items-center justify-center gap-3">
          <Link to="/app/persona" className="primary-button">
            Open control center <ArrowRight size={16} />
          </Link>
          <Link to="/app/session" className="secondary-button">
            Connect a session
          </Link>
        </div>
        <p className="text-xs text-outline">No marketing tracking. No selling data. You hold the keys.</p>
      </section>

      <section id="how" className="mx-auto grid max-w-6xl gap-4 px-5 pb-8 sm:grid-cols-2 lg:grid-cols-4 md:px-8">
        {FEATURES.map(({ icon: Icon, title, body }) => (
          <article key={title} className="rounded-2xl border border-outline-variant bg-white p-6 shadow-ambient">
            <span className="mb-3 inline-grid h-11 w-11 place-items-center rounded-xl bg-primary/10 text-primary">
              <Icon size={20} />
            </span>
            <h3 className="text-base font-bold">{title}</h3>
            <p className="mt-1.5 text-sm leading-6 text-on-surface-variant">{body}</p>
          </article>
        ))}
      </section>

      <section id="privacy" className="mx-auto grid max-w-6xl gap-4 px-5 py-10 sm:grid-cols-2 md:px-8">
        <div className="flex items-start gap-3 rounded-2xl border border-outline-variant bg-white p-6 shadow-ambient">
          <ServerCog size={20} className="mt-0.5 text-primary" />
          <div>
            <strong className="block">Your data stays yours.</strong>
            <span className="text-sm text-on-surface-variant">Apps negotiate scoped access. Every request is logged and revocable.</span>
          </div>
        </div>
        <div className="flex items-start gap-3 rounded-2xl border border-outline-variant bg-white p-6 shadow-ambient">
          <Trash2 size={20} className="mt-0.5 text-primary" />
          <div>
            <strong className="block">Delete anytime.</strong>
            <span className="text-sm text-on-surface-variant">Export or wipe your entire context layer in one action.</span>
          </div>
        </div>
      </section>

      <footer className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 border-t border-outline-variant px-5 py-8 text-sm text-on-surface-variant md:px-8">
        <span className="font-bold text-primary">PersonaLayer</span>
        <div className="flex gap-5">
          <Link to="/app/persona" className="hover:text-on-surface">App</Link>
          <Link to="/app/privacy" className="hover:text-on-surface">Privacy controls</Link>
          <Link to="/app/settings" className="hover:text-on-surface">Legal &amp; data</Link>
        </div>
        <span className="text-outline">© {new Date().getFullYear()} PersonaLayer</span>
      </footer>
    </div>
  );
}
