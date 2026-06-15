import { useEffect, useRef, type ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  BarChart3,
  Brain,
  BriefcaseBusiness,
  Check,
  Download,
  FlaskConical,
  HeartPulse,
  Lock,
  MessageSquare,
  Plug,
  Search,
  ShoppingBag,
  Sparkles,
  Target,
  UserRound,
  Zap,
  type LucideIcon,
} from "lucide-react";
import { getStoredSessionToken } from "../api";
import { useReveal } from "../lib/useReveal";

const TICKER = [
  ["TASTE", "coffee preference mapped"],
  ["BEHAVIOR", "3am researcher detected"],
  ["BUDGET", "mid-range buyer signal active"],
  ["CONTEXT", "parent of 2 inferred"],
  ["VALUES", "sustainability weight: high"],
  ["PREDICT", "89% product fit score"],
];

const STATS = [
  { value: "~90%", label: "Predictive accuracy vs real consumers" },
  { value: "Hours", unit: "not weeks", label: "Research timeline for product validation" },
  { value: "0", unit: "breaches", label: "Local-first, you hold the keys" },
  { value: "Always-on", label: "Concept tests without participant fatigue" },
];

const STEPS: { icon: LucideIcon; num: string; title: string; body: string }[] = [
  {
    icon: Brain,
    num: "01 / CAPTURE",
    title: "You build your persona",
    body: "Answer onboarding prompts or let connectors learn from your behavior. Preferences, values, habits, and life context become a structured profile stored under your control.",
  },
  {
    icon: Lock,
    num: "02 / CONTROL",
    title: "You own what's shared",
    body: "Granular permissions decide which apps can access which persona dimensions. Revoke access at any time. No silent resale and no hidden ad targeting.",
  },
  {
    icon: Zap,
    num: "03 / CONNECT",
    title: "AI agents read context instantly",
    body: "Products integrating PersonaLayer query context through secure APIs. The AI starts personalized on day one with no repeated forms or cold starts.",
  },
  {
    icon: Sparkles,
    num: "04 / CONTRIBUTE",
    title: "Opt in to research",
    body: "Share anonymized persona archetypes with the research layer only when you choose. Builders test against real context while users stay in charge.",
  },
];

const PROVIDES: { icon: LucideIcon; title: string; body: string }[] = [
  {
    icon: UserRound,
    title: "Persona Engine",
    body: "A living profile of preferences, values, behavior, and life context. Richer than a cookie, more honest than a survey, and owned by the user.",
  },
  {
    icon: Plug,
    title: "MCP Context API",
    body: "A standardized interface for AI agents to request relevant context. Products integrate once and avoid building their own sensitive profile databases.",
  },
  {
    icon: FlaskConical,
    title: "Synthetic Research Panel",
    body: "A consented pool of anonymized persona archetypes for concept, pricing, message, and market validation in hours.",
  },
  {
    icon: BarChart3,
    title: "Persona Analytics Dashboard",
    body: "For builders: see which archetypes resonate, where fit breaks down, and what product-market signals look like before launch.",
  },
];

const USE_CASES: { icon: LucideIcon; title: string; body: string; tag: string; tone: "user" | "biz" | "both" | "risk" }[] = [
  {
    icon: ShoppingBag,
    title: "Personalized Shopping Agents",
    body: "Shopping assistants know size, budget, style, and ethical filters before the first product page loads.",
    tag: "for users",
    tone: "user",
  },
  {
    icon: FlaskConical,
    title: "Product-Market Fit Testing",
    body: "Test concepts against real-persona archetypes and get predicted conversion, objections, and segment-level resonance.",
    tag: "for builders",
    tone: "biz",
  },
  {
    icon: HeartPulse,
    title: "Health & Wellness Apps",
    body: "Fitness, nutrition, and wellness products start with goals, restrictions, patterns, and preferences already available.",
    tag: "for users",
    tone: "both",
  },
  {
    icon: Target,
    title: "Creative & Ad Testing",
    body: "Evaluate tone, format, hooks, and creative against psychographic segments before campaign launch.",
    tag: "for builders",
    tone: "biz",
  },
  {
    icon: Search,
    title: "Learning Platforms",
    body: "Education tools adapt to prior knowledge, preferred format, pace, and available time instead of generic defaults.",
    tag: "for users",
    tone: "user",
  },
  {
    icon: BriefcaseBusiness,
    title: "Pricing & Packaging Research",
    body: "Find price-sensitivity curves for customer archetypes before your pricing page or sales motion goes live.",
    tag: "for builders",
    tone: "risk",
  },
  {
    icon: MessageSquare,
    title: "Contextual AI Assistants",
    body: "Assistants in the browser, IDE, inbox, or workflow inherit work style, communication preferences, and constraints.",
    tag: "for everyone",
    tone: "both",
  },
  {
    icon: BarChart3,
    title: "Market Expansion Validation",
    body: "Query segment-level persona pools to understand cultural fit, adoption barriers, and localization priorities.",
    tag: "for builders",
    tone: "biz",
  },
];

function Reveal({ children, className = "", delay = 0 }: { children: ReactNode; className?: string; delay?: number }) {
  const { ref, shown } = useReveal<HTMLDivElement>();
  return (
    <div ref={ref} style={{ transitionDelay: `${delay}ms` }} className={`reveal ${shown ? "is-visible" : ""} ${className}`}>
      {children}
    </div>
  );
}

function Label({ children, center = false }: { children: ReactNode; center?: boolean }) {
  return (
    <div className={`pl-label ${center ? "justify-center" : ""}`}>
      <span className="h-px w-5 bg-current" />
      {children}
    </div>
  );
}

function FingerprintCanvas() {
  const ref = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const width = 900;
    const height = 900;
    const cx = width / 2;
    const cy = height / 2;
    const rings = 6;
    const spokes = 72;
    const dims = [
      { color: "#6C47FF", speed: 0.0007, amp: 0.28 },
      { color: "#00C8F0", speed: 0.0005, amp: 0.22 },
      { color: "#6C47FF", speed: 0.0009, amp: 0.19 },
      { color: "#00E5A0", speed: 0.0006, amp: 0.31 },
      { color: "#6C47FF", speed: 0.0008, amp: 0.17 },
      { color: "#00C8F0", speed: 0.0004, amp: 0.25 },
    ];

    let frame = 0;
    const draw = (timestamp: number) => {
      const t = timestamp * 0.001;
      ctx.clearRect(0, 0, width, height);

      for (let r = 0; r < rings; r += 1) {
        const baseR = 80 + r * 60;
        const dim = dims[r % dims.length];
        const pts: { x: number; y: number }[] = [];

        for (let i = 0; i <= spokes; i += 1) {
          const angle = (i / spokes) * Math.PI * 2;
          const wave = Math.sin(angle * (r + 3) + t * dim.speed * 1000 + r) * dim.amp;
          const wave2 = Math.cos(angle * (r * 2 + 1) + t * dim.speed * 700) * (dim.amp * 0.4);
          const rad = baseR * (1 + wave + wave2);
          pts.push({ x: cx + Math.cos(angle) * rad, y: cy + Math.sin(angle) * rad });
        }

        ctx.beginPath();
        ctx.moveTo(pts[0].x, pts[0].y);
        for (let i = 1; i < pts.length; i += 1) ctx.lineTo(pts[i].x, pts[i].y);
        ctx.closePath();
        ctx.strokeStyle = dim.color;
        ctx.lineWidth = 1;
        ctx.globalAlpha = 0.5 - r * 0.04;
        ctx.stroke();
      }

      ctx.beginPath();
      ctx.arc(cx, cy, 4 + Math.sin(t * 2) * 1.5, 0, Math.PI * 2);
      ctx.fillStyle = "#6C47FF";
      ctx.globalAlpha = 0.9;
      ctx.fill();

      for (let i = 0; i < 16; i += 1) {
        const angle = (i / 16) * Math.PI * 2;
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.lineTo(cx + Math.cos(angle) * 380, cy + Math.sin(angle) * 380);
        ctx.strokeStyle = "rgba(108,71,255,0.08)";
        ctx.lineWidth = 0.5;
        ctx.globalAlpha = 1;
        ctx.stroke();
      }

      ctx.globalAlpha = 1;
      frame = window.requestAnimationFrame(draw);
    };

    frame = window.requestAnimationFrame(draw);
    return () => window.cancelAnimationFrame(frame);
  }, []);

  return <canvas ref={ref} className="pl-fingerprint" width={900} height={900} aria-hidden />;
}

function PersonaDemo() {
  const rows = [
    ["Price sensitivity", "62%", "62%", "bg-[#6C47FF]"],
    ["Feature curiosity", "88%", "88%", "bg-[#00C8F0]"],
    ["Churn risk", "24%", "24%", "bg-[#FF5E6C]"],
  ];

  return (
    <div className="pl-persona-demo">
      <div className="mb-6 flex items-center gap-4">
        <div className="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-gradient-to-br from-[#6C47FF] to-[#00C8F0] font-bold text-white">
          DJ
        </div>
        <div>
          <div className="font-display text-sm font-semibold text-[#F0EEFF]">Digital Persona #4,421</div>
          <div className="text-xs text-[#8A85AA]">Urban / 28-34 / Mid-income / Tech-adjacent</div>
        </div>
      </div>
      <div className="mb-5 flex flex-wrap gap-2">
        {["early adopter", "sustainability-first", "subscription averse", "research-heavy buyer", "night owl"].map((tag, i) => (
          <span key={tag} className={`pl-persona-tag ${i % 3 === 0 ? "tag-indigo" : i % 3 === 1 ? "tag-cyan" : "tag-green"}`}>
            {tag}
          </span>
        ))}
      </div>
      <div className="mb-5 text-xs text-[#8A85AA]">Purchase likelihood signals</div>
      <div className="space-y-3">
        {rows.map(([name, label, width, color]) => (
          <div key={name} className="grid grid-cols-[96px_1fr_34px] items-center gap-3 text-xs">
            <span className="text-[#F0EEFF]/80">{name}</span>
            <span className="h-1 overflow-hidden rounded-full bg-white/10">
              <span className={`block h-full rounded-full ${color}`} style={{ width }} />
            </span>
            <span className="font-mono text-[#8A85AA]">{label}</span>
          </div>
        ))}
      </div>
      <div className="mt-6 flex items-center justify-between rounded-xl border border-[#00E5A0]/20 bg-[#00E5A0]/10 px-4 py-3">
        <div>
          <div className="text-xs text-[#8A85AA]">Overall fit score for your product</div>
          <div className="mt-0.5 text-[11px] text-[#8A85AA]">Based on persona context + product brief</div>
        </div>
        <div className="font-display text-xl font-bold text-[#00E5A0]">87%</div>
      </div>
    </div>
  );
}

export default function Landing() {
  const entered = Boolean(getStoredSessionToken());
  const tickerItems = [...TICKER, ...TICKER];

  return (
    <main className="pl-landing min-h-dvh bg-[#07070E] text-[#F0EEFF]">
      <header className="fixed inset-x-0 top-0 z-50 border-b border-white/[0.06] bg-[#07070E]/85 px-5 py-4 backdrop-blur md:px-12">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <Link to="/" className="font-display flex items-center gap-2 text-lg font-bold text-[#F0EEFF]">
            <img src="/personalayer-mark.svg" alt="" className="h-8 w-8" />
            PersonaLayer
          </Link>
          <nav className="hidden items-center gap-8 text-sm text-[#8A85AA] md:flex">
            <a href="#for-you" className="hover:text-[#F0EEFF]">For You</a>
            <a href="#for-business" className="hover:text-[#F0EEFF]">For Business</a>
            <a href="#how" className="hover:text-[#F0EEFF]">How It Works</a>
            <a href="#usecases" className="hover:text-[#F0EEFF]">Use Cases</a>
          </nav>
          <Link to={entered ? "/app/persona" : "/app/session"} className="pl-nav-cta">
            {entered ? "Open App" : "Get Started"}
          </Link>
        </div>
      </header>

      <section className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-5 pb-16 pt-32 text-center">
        <FingerprintCanvas />
        <div className="pl-hero-eyebrow fade-up">Your Digital Persona Layer</div>
        <h1 className="fade-up delay-1 font-display relative z-10 max-w-5xl text-[clamp(2.35rem,7vw,5.5rem)] font-bold leading-[1.05]">
          The AI agents that know you.
          <br />
          <span className="text-[#6C47FF]">Everything, personalized.</span>
          <br />
          <span className="text-[#00C8F0]">Nothing, exploited.</span>
        </h1>
        <p className="fade-up delay-2 relative z-10 mt-7 max-w-2xl text-base leading-8 text-[#8A85AA] md:text-lg">
          Build your digital persona once. Every AI product you touch, from shopping to health apps to productivity tools,
          can understand who you are without making you repeat yourself.
        </p>
        <div className="fade-up delay-3 relative z-10 mt-10 flex flex-wrap items-center justify-center gap-4">
          <Link to="/app/session" className="pl-btn-primary">
            <Download size={16} />
            Add to Browser - Free
          </Link>
          <a href="#how" className="pl-btn-ghost">See how it works</a>
        </div>
        <div className="fade-up delay-4 pl-ticker-wrap">
          <div className="pl-ticker">
            {tickerItems.map(([tag, text], i) => (
              <span key={`${tag}-${i}`} className="pl-ticker-item">
                <span className="pl-ticker-tag">{tag}</span>
                {text}
                <span className="text-[#8A85AA]/50">/</span>
              </span>
            ))}
          </div>
        </div>
      </section>

      <section className="border-y border-white/[0.06] bg-[#0F0F1A] px-5 py-12">
        <div className="mx-auto grid max-w-6xl gap-8 text-center sm:grid-cols-2 lg:grid-cols-4">
          {STATS.map((stat, i) => (
            <Reveal key={stat.label} delay={i * 70}>
              <div>
                <div className="font-display mb-2 text-4xl font-bold tracking-tight text-[#F0EEFF]">
                  {stat.value}
                  {stat.unit && <span className="ml-1 text-base text-[#6C47FF]">{stat.unit}</span>}
                </div>
                <div className="text-sm text-[#8A85AA]">{stat.label}</div>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      <section id="for-you" className="px-5 py-24">
        <div className="mx-auto max-w-6xl">
          <Label>Who it's for</Label>
          <h2 className="font-display max-w-2xl text-3xl font-bold leading-tight tracking-tight md:text-5xl">
            Built for both sides of the screen.
          </h2>
          <p className="mt-4 max-w-2xl text-[#8A85AA]">
            One persona layer. Two different superpowers, depending on which side you are on.
          </p>

          <div className="mt-12 grid overflow-hidden rounded-3xl border border-white/[0.06] bg-white/[0.06] lg:grid-cols-2">
            <Reveal>
              <article className="pl-audience-panel border-b border-white/[0.06] lg:border-b-0 lg:border-r">
                <div className="pl-badge-user">For You, the Person</div>
                <h3 className="font-display text-2xl font-bold">Stop re-explaining yourself to every app you open.</h3>
                <p className="mt-4 leading-8 text-[#8A85AA]">
                  Your preferences, context, life stage, values, and habits are built once, owned by you, and shared only
                  on your terms.
                </p>
                <ul className="mt-8 space-y-4 text-sm leading-7 text-[#8A85AA]">
                  {[
                    "Shopping recommendations know your size, budget, and sustainability threshold.",
                    "Health apps start with diet, goals, and allergies on day one.",
                    "Productivity tools adapt to work style, hours, and communication preferences.",
                    "Your persona stays local until you choose what to share.",
                  ].map((item) => (
                    <li key={item} className="flex gap-3">
                      <span className="pl-check-indigo"><Check size={13} /></span>
                      {item}
                    </li>
                  ))}
                </ul>
              </article>
            </Reveal>
            <Reveal delay={100}>
              <article id="for-business" className="pl-audience-panel">
                <div className="pl-badge-biz">For Builders & Researchers</div>
                <h3 className="font-display text-2xl font-bold">A consented pre-market validation layer.</h3>
                <p className="mt-4 leading-8 text-[#8A85AA]">
                  Test product concepts, pricing, messaging, and features against living persona archetypes and get answers
                  in hours, not months.
                </p>
                <ul className="mt-8 space-y-4 text-sm leading-7 text-[#8A85AA]">
                  {[
                    "Run concept tests across persona types before writing code.",
                    "Predict how demographic and psychographic segments will react.",
                    "Replace slow focus groups with always-on synthetic consumer panels.",
                    "Use consented data with user-controlled participation.",
                  ].map((item) => (
                    <li key={item} className="flex gap-3">
                      <span className="pl-check-cyan"><Check size={13} /></span>
                      {item}
                    </li>
                  ))}
                </ul>
              </article>
            </Reveal>
          </div>
        </div>
      </section>

      <section className="px-5 pb-24">
        <div className="mx-auto max-w-6xl">
          <div className="pl-validation">
            <div>
              <Label>Pre-Market Research</Label>
              <h2 className="font-display text-3xl font-bold leading-tight tracking-tight md:text-5xl">
                The validation engine nobody built. Until now.
              </h2>
              <p className="mt-5 max-w-xl leading-8 text-[#8A85AA]">
                Instead of surveying static panels, query living digital personas enriched with behavior, preferences, and
                context signals. It is not generic synthetic guesswork. It is a simulation of actual future customers.
              </p>
              <div className="mt-10 space-y-5">
                {[
                  ["Predictive accuracy", "90%", "bg-[#6C47FF]"],
                  ["Speed vs traditional research", "96%", "bg-[#00C8F0]"],
                  ["Cost reduction", "80%", "bg-[#00E5A0]"],
                ].map(([label, width, color]) => (
                  <div key={label} className="grid grid-cols-[170px_1fr_44px] items-center gap-4 text-xs md:text-sm">
                    <span className="font-mono text-[#8A85AA]">{label}</span>
                    <span className="h-1 overflow-hidden rounded-full bg-white/10">
                      <span className={`block h-full rounded-full ${color}`} style={{ width }} />
                    </span>
                    <span className="font-display font-bold text-[#F0EEFF]">{width}</span>
                  </div>
                ))}
              </div>
            </div>
            <Reveal>
              <PersonaDemo />
            </Reveal>
          </div>
        </div>
      </section>

      <section id="how" className="bg-[#0F0F1A] px-5 py-24">
        <div className="mx-auto max-w-6xl">
          <Label>How It Works</Label>
          <h2 className="font-display text-3xl font-bold tracking-tight md:text-5xl">Three layers. One persona.</h2>
          <p className="mt-4 max-w-2xl text-[#8A85AA]">
            From raw context to embedded intelligence in every product you use or build.
          </p>
          <div className="mt-12 grid overflow-hidden rounded-2xl border border-white/[0.06] bg-white/[0.06] sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map(({ icon: Icon, num, title, body }, i) => (
              <Reveal key={title} delay={i * 80}>
                <article className="pl-step h-full">
                  <div className="mb-5 font-mono text-xs tracking-[0.14em] text-[#6C47FF]/80">{num}</div>
                  <div className="mb-5 grid h-11 w-11 place-items-center rounded-xl border border-[#6C47FF]/25 bg-[#6C47FF]/10 text-[#F0EEFF]">
                    <Icon size={20} />
                  </div>
                  <h3 className="font-display font-semibold">{title}</h3>
                  <p className="mt-3 text-sm leading-7 text-[#8A85AA]">{body}</p>
                </article>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section className="px-5 py-24">
        <div className="mx-auto max-w-6xl">
          <Label>What We Provide</Label>
          <h2 className="font-display text-3xl font-bold tracking-tight md:text-5xl">
            The full stack, from identity to intelligence.
          </h2>
          <div className="mt-12 grid overflow-hidden rounded-3xl border border-white/[0.06] bg-white/[0.06] md:grid-cols-2">
            {PROVIDES.map(({ icon: Icon, title, body }, i) => (
              <Reveal key={title} delay={i * 80}>
                <article className="pl-provide-card h-full">
                  <div className="mb-5 flex items-center gap-3">
                    <span className="grid h-10 w-10 place-items-center rounded-xl border border-[#6C47FF]/25 bg-[#6C47FF]/10">
                      <Icon size={18} />
                    </span>
                    <h3 className="font-display font-semibold">{title}</h3>
                  </div>
                  <p className="text-sm leading-7 text-[#8A85AA]">{body}</p>
                </article>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section id="usecases" className="bg-[#0F0F1A] px-5 py-24">
        <div className="mx-auto max-w-6xl">
          <Label>Use Cases</Label>
          <h2 className="font-display text-3xl font-bold tracking-tight md:text-5xl">
            Built for how people actually use AI today.
          </h2>
          <p className="mt-4 max-w-2xl leading-8 text-[#8A85AA]">
            Whether you are tired of repeating yourself or validating before building, PersonaLayer fits directly into the workflow.
          </p>
          <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {USE_CASES.map(({ icon: Icon, title, body, tag, tone }, i) => (
              <Reveal key={title} delay={i * 55}>
                <article className="pl-usecase-card h-full">
                  <div className={`mb-5 grid h-10 w-10 place-items-center rounded-xl ${tone === "biz" ? "bg-[#00C8F0]/10 text-[#00C8F0]" : tone === "both" ? "bg-[#00E5A0]/10 text-[#00E5A0]" : tone === "risk" ? "bg-[#FF5E6C]/10 text-[#FF5E6C]" : "bg-[#6C47FF]/10 text-[#8B70FF]"}`}>
                    <Icon size={18} />
                  </div>
                  <h3 className="font-display font-semibold">{title}</h3>
                  <p className="mt-3 text-sm leading-7 text-[#8A85AA]">{body}</p>
                  <span className={`mt-5 inline-flex rounded px-2.5 py-1 font-mono text-[11px] uppercase tracking-[0.08em] ${tone === "biz" ? "bg-[#00C8F0]/10 text-[#00C8F0]" : tone === "both" ? "bg-[#00E5A0]/10 text-[#00E5A0]" : tone === "risk" ? "bg-[#FF5E6C]/10 text-[#FF5E6C]" : "bg-[#6C47FF]/15 text-[#8B70FF]"}`}>
                    {tag}
                  </span>
                </article>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section id="download" className="relative overflow-hidden px-5 py-28 text-center">
        <div className="absolute left-1/2 top-1/2 h-72 w-[640px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[#6C47FF]/10 blur-3xl" aria-hidden />
        <div className="relative z-10">
          <Label center>Get Started</Label>
          <h2 className="font-display text-4xl font-bold leading-tight tracking-tight md:text-6xl">
            Your persona.
            <br />
            <span className="text-[#6C47FF]">Your rules.</span>
          </h2>
          <p className="mx-auto mt-5 max-w-2xl leading-8 text-[#8A85AA]">
            Connect a session, build your digital persona in minutes, and start experiencing AI that actually knows you.
          </p>
          <div className="mt-10 flex flex-wrap justify-center gap-4">
            <Link to="/app/session" className="pl-btn-primary">
              <Download size={16} />
              Start Free
            </Link>
            <Link to="/app/apps" className="pl-btn-ghost">
              Request API Access <ArrowRight size={16} />
            </Link>
          </div>
          <p className="mt-8 font-mono text-xs tracking-[0.12em] text-[#8A85AA]">LOCAL-FIRST / NO ADS / YOUR DATA, YOUR CALL</p>
        </div>
      </section>

      <footer className="flex flex-wrap items-center justify-between gap-4 border-t border-white/[0.06] px-5 py-10 text-sm text-[#8A85AA] md:px-12">
        <div className="font-display flex items-center gap-2 font-bold">
          <img src="/personalayer-mark.svg" alt="" className="h-7 w-7" />
          PersonaLayer
        </div>
        <div className="font-mono text-xs opacity-70">Built local-first. Opt-in everywhere. Copyright 2026 PersonaLayer</div>
      </footer>
    </main>
  );
}
