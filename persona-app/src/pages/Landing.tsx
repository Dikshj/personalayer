import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  Calendar,
  Eye,
  Github,
  Lock,
  type LucideIcon,
  MapPin,
  ServerCog,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Trash2,
} from "lucide-react";
import { getStoredSessionToken } from "../api";
import { useReveal } from "../lib/useReveal";

const FEATURES: { icon: LucideIcon; title: string; body: string }[] = [
  { icon: Eye, title: "See what’s known", body: "A clear view of every signal, its confidence, and where it came from — no hidden profile." },
  { icon: SlidersHorizontal, title: "Control every signal", body: "Hide, edit, or delete any signal. Set sharing defaults and per-app permissions." },
  { icon: ShieldCheck, title: "Privacy by default", body: "Always-private categories never leave your layer. Sensitive data is dropped, not shared." },
  { icon: Lock, title: "Local-first", body: "Your context stays close to you. Apps request access; you decide what they receive." },
];

// Reveal-on-scroll wrapper.
function Reveal({ children, className = "", delay = 0 }: { children: ReactNode; className?: string; delay?: number }) {
  const { ref, shown } = useReveal<HTMLDivElement>();
  return (
    <div ref={ref} style={{ transitionDelay: `${delay}ms` }} className={`reveal ${shown ? "is-visible" : ""} ${className}`}>
      {children}
    </div>
  );
}

// A floating signal node inside the 3D stage. `z` sets its depth.
function Node({
  icon: Icon,
  label,
  className,
  z,
  float,
  locked = false,
}: {
  icon: LucideIcon;
  label: string;
  className: string;
  z: number;
  float: string;
  locked?: boolean;
}) {
  return (
    <div className={`absolute ${className}`} style={{ transform: `translateZ(${z}px)` }}>
      <div className={float}>
        <span
          className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold shadow-lg backdrop-blur ${
            locked
              ? "border-[#fea619]/40 bg-[#1a1305]/80 text-[#fec25a]"
              : "border-white/15 bg-white/10 text-white"
          }`}
        >
          <Icon size={13} /> {label}
        </span>
      </div>
    </div>
  );
}

// Mock persona signal row shown inside the floating glass card.
function SignalRow({ name, source, pct, shared }: { name: string; source: string; pct: number; shared: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg bg-white/[0.04] px-3 py-2">
      <div className="min-w-0">
        <div className="truncate text-sm font-semibold text-white">{name}</div>
        <div className="text-[11px] text-white/50">{source}</div>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <span className="h-1.5 w-14 overflow-hidden rounded-full bg-white/10">
          <span
            className="block h-full rounded-full bg-gradient-to-r from-[#2563eb] to-[#6cf8bb]"
            style={{ width: `${pct}%` }}
          />
        </span>
        <span className={`h-3.5 w-3.5 rounded-full ${shared ? "bg-[#6cf8bb]" : "bg-[#fea619]"}`} />
      </div>
    </div>
  );
}

export default function Landing() {
  const entered = Boolean(getStoredSessionToken());
  const [tilt, setTilt] = useState({ x: 0, y: 0 });

  const onMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const dx = (e.clientX - (r.left + r.width / 2)) / r.width;
    const dy = (e.clientY - (r.top + r.height / 2)) / r.height;
    setTilt({ x: dy * -12, y: dx * 16 });
  };
  const reset = () => setTilt({ x: 0, y: 0 });

  return (
    <div className="min-h-dvh bg-surface text-on-surface">
      {/* ---- Hero: dark, animated, 3D --------------------------------------- */}
      <div className="relative overflow-hidden bg-[#070b16] text-white">
        {/* Aurora glow blobs */}
        <div className="pointer-events-none absolute inset-0" aria-hidden>
          <div className="aurora absolute -left-24 top-[-10%] h-[420px] w-[420px] rounded-full bg-[#2563eb]/50" />
          <div className="aurora aurora-2 absolute right-[-10%] top-[20%] h-[460px] w-[460px] rounded-full bg-[#6cf8bb]/25" />
          <div className="aurora absolute bottom-[-20%] left-1/3 h-[380px] w-[380px] rounded-full bg-[#7c3aed]/30" />
        </div>
        {/* Depth grid */}
        <div
          className="grid-pan pointer-events-none absolute inset-0 opacity-[0.18]"
          aria-hidden
          style={{
            backgroundImage:
              "linear-gradient(rgba(255,255,255,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.5) 1px, transparent 1px)",
            backgroundSize: "56px 56px",
            maskImage: "radial-gradient(ellipse 70% 60% at 50% 40%, #000 40%, transparent 100%)",
            WebkitMaskImage: "radial-gradient(ellipse 70% 60% at 50% 40%, #000 40%, transparent 100%)",
          }}
        />

        <header className="relative mx-auto flex max-w-6xl items-center justify-between px-5 py-5 md:px-8">
          <span className="flex items-center gap-2">
            <span className="grid h-9 w-9 place-items-center rounded-lg bg-white/10 text-white backdrop-blur">
              <ShieldCheck size={22} />
            </span>
            <span className="text-lg font-bold">PersonaLayer</span>
          </span>
          <nav className="flex items-center gap-5 text-sm font-semibold text-white/70">
            <a href="#how" className="hidden hover:text-white sm:inline">How it works</a>
            <a href="#privacy" className="hidden hover:text-white sm:inline">Privacy</a>
            <Link
              to="/app/persona"
              className="inline-flex items-center gap-2 rounded-lg bg-white px-4 py-2 text-sm font-bold text-[#070b16] transition hover:bg-white/90 active:scale-[0.98]"
            >
              {entered ? "Open app" : "Open control center"} <ArrowRight size={15} />
            </Link>
          </nav>
        </header>

        <section
          className="relative mx-auto grid max-w-6xl items-center gap-10 px-5 py-14 md:grid-cols-2 md:gap-6 md:px-8 md:py-24"
          onPointerMove={onMove}
          onPointerLeave={reset}
        >
          {/* Left: copy */}
          <div className="flex flex-col items-start gap-5 text-left">
            <span className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3.5 py-1.5 text-xs font-semibold text-white/80 backdrop-blur">
              <Sparkles size={14} className="text-[#6cf8bb]" /> Local-first personal context layer
            </span>
            <h1 className="text-4xl font-bold leading-[1.05] tracking-tight md:text-6xl">
              See, edit, and control what apps can{" "}
              <span className="bg-gradient-to-r from-[#7db4ff] via-white to-[#6cf8bb] bg-clip-text text-transparent shimmer">
                know about you.
              </span>
            </h1>
            <p className="max-w-xl text-base leading-7 text-white/70 md:text-lg">
              PersonaLayer is your private control center for personal context. It builds a living picture of your work and
              preferences from your own activity — and puts you in charge of every signal apps can use.
            </p>
            <div className="mt-1 flex flex-wrap items-center gap-3">
              <Link
                to="/app/persona"
                className="inline-flex items-center gap-2 rounded-lg bg-gradient-to-r from-[#2563eb] to-[#4f7cff] px-5 py-3 font-bold text-white shadow-lg shadow-[#2563eb]/30 transition hover:brightness-110 active:scale-[0.98]"
              >
                Open control center <ArrowRight size={16} />
              </Link>
              <Link
                to="/app/session"
                className="inline-flex items-center gap-2 rounded-lg border border-white/20 px-5 py-3 font-semibold text-white transition hover:bg-white/10 active:scale-[0.98]"
              >
                Connect a session
              </Link>
            </div>
            <p className="text-xs text-white/45">No marketing tracking. No selling data. You hold the keys.</p>
          </div>

          {/* Right: 3D scene */}
          <div className="scene-3d relative flex h-[380px] items-center justify-center md:h-[460px]">
            <div
              className="stage-3d relative h-full w-full max-w-[420px]"
              style={{ transform: `rotateX(${tilt.x}deg) rotateY(${tilt.y}deg)` }}
            >
              {/* Spinning halo behind the card */}
              <div
                className="absolute inset-0 m-auto h-[300px] w-[300px] rounded-full border border-dashed border-white/10 spin-slow"
                style={{ transform: "translateZ(-70px)" }}
                aria-hidden
              />
              <div
                className="absolute inset-0 m-auto h-[210px] w-[210px] rounded-full bg-[#2563eb]/20 blur-2xl"
                style={{ transform: "translateZ(-90px)" }}
                aria-hidden
              />

              {/* Floating glass control-center card */}
              <div
                className="float-a absolute inset-x-0 top-1/2 mx-auto w-[clamp(240px,82vw,300px)] -translate-y-1/2"
                style={{ transform: "translateZ(40px)" }}
              >
                <div className="rounded-2xl border border-white/15 bg-white/[0.07] p-4 shadow-2xl backdrop-blur-xl">
                  <div className="mb-3 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="grid h-7 w-7 place-items-center rounded-lg bg-[#6cf8bb]/20 text-[#6cf8bb]">
                        <ShieldCheck size={15} />
                      </span>
                      <span className="text-sm font-bold text-white">What we know</span>
                    </div>
                    <span className="rounded-full bg-white/10 px-2 py-0.5 text-[10px] font-semibold text-white/70">
                      Live
                    </span>
                  </div>
                  <div className="flex flex-col gap-2">
                    <SignalRow name="Works in software" source="GitHub · 92%" pct={92} shared />
                    <SignalRow name="Prefers direct tone" source="Inferred · 78%" pct={78} shared />
                    <SignalRow name="Based in India" source="Onboarding · 60%" pct={60} shared={false} />
                  </div>
                  <div className="mt-3 flex items-center justify-between rounded-lg bg-white/[0.04] px-3 py-2">
                    <span className="text-[11px] text-white/60">3 signals · 2 apps · 2 rules</span>
                    <span className="flex items-center gap-1 text-[11px] font-semibold text-[#6cf8bb]">
                      <Lock size={11} /> Private
                    </span>
                  </div>
                </div>
              </div>

              {/* Orbiting signal nodes at varied depths */}
              <Node icon={Github} label="GitHub" className="left-0 top-6" z={90} float="float-b" />
              <Node icon={Calendar} label="Calendar" className="right-0 top-16" z={120} float="float-c" />
              <Node icon={Sparkles} label="TypeScript" className="bottom-10 left-2" z={60} float="float-c" />
              <Node icon={MapPin} label="Location · private" className="bottom-2 right-2" z={140} float="float-b" locked />
            </div>
          </div>
        </section>
      </div>

      {/* ---- Features ------------------------------------------------------- */}
      <section id="how" className="mx-auto grid max-w-6xl gap-4 px-5 py-14 sm:grid-cols-2 lg:grid-cols-4 md:px-8">
        {FEATURES.map(({ icon: Icon, title, body }, i) => (
          <Reveal key={title} delay={i * 90}>
            <article className="tilt-3d h-full rounded-2xl border border-outline-variant bg-white p-6 shadow-ambient">
              <span className="tilt-pop mb-3 inline-grid h-11 w-11 place-items-center rounded-xl bg-primary/10 text-primary">
                <Icon size={20} />
              </span>
              <h3 className="text-base font-bold">{title}</h3>
              <p className="mt-1.5 text-sm leading-6 text-on-surface-variant">{body}</p>
            </article>
          </Reveal>
        ))}
      </section>

      {/* ---- Privacy strip -------------------------------------------------- */}
      <section id="privacy" className="mx-auto grid max-w-6xl gap-4 px-5 py-10 sm:grid-cols-2 md:px-8">
        <Reveal>
          <div className="flex h-full items-start gap-3 rounded-2xl border border-outline-variant bg-white p-6 shadow-ambient">
            <ServerCog size={20} className="mt-0.5 text-primary" />
            <div>
              <strong className="block">Your data stays yours.</strong>
              <span className="text-sm text-on-surface-variant">Apps negotiate scoped access. Every request is logged and revocable.</span>
            </div>
          </div>
        </Reveal>
        <Reveal delay={120}>
          <div className="flex h-full items-start gap-3 rounded-2xl border border-outline-variant bg-white p-6 shadow-ambient">
            <Trash2 size={20} className="mt-0.5 text-primary" />
            <div>
              <strong className="block">Delete anytime.</strong>
              <span className="text-sm text-on-surface-variant">Export or wipe your entire context layer in one action.</span>
            </div>
          </div>
        </Reveal>
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
