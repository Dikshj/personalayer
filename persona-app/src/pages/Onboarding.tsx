// /app/onboarding — first-run persona seed. A focused, full-screen wizard that
// seeds the first persona before connectors have data, then records the initial
// privacy posture (fully private by default) and routes to /app/persona.

import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  Briefcase,
  Check,
  Lock,
  Plus,
  Sparkles,
  Target,
  Wrench,
} from "lucide-react";
import { Button, Pill, Stepper } from "../components/ui";
import { titleize } from "../lib/format";
import { seedOnboarding, submitOnboardingFlow } from "../api";
import { markOnboardingComplete } from "../auth/session";

const STEPS = ["Welcome", "Work", "Goals", "Tools", "Privacy", "Confirm"];

const GOAL_OPTIONS = [
  { value: "app_recommendations", label: "Recommend useful features" },
  { value: "workflow_optimization", label: "Optimize my workflow" },
  { value: "writing_help", label: "Draft & write faster" },
  { value: "context_surfacing", label: "Surface relevant context" },
  { value: "task_automation", label: "Automate routine tasks" },
  { value: "better_search", label: "Find things faster" },
];

const TOOL_OPTIONS = [
  "GitHub", "VS Code", "Notion", "Slack", "Figma", "Linear",
  "Gmail", "Calendar", "Spotify", "Terminal", "ChatGPT", "Claude",
];

const POSTURES = [
  { value: "private", label: "Fully private", hint: "Nothing is shared until you allow it. Recommended.", privacy_level: "strict", sharing_default: "deny" },
  { value: "balanced", label: "Ask each time", hint: "Apps ask before using sensitive context.", privacy_level: "balanced", sharing_default: "ask" },
  { value: "open", label: "Share low-sensitivity", hint: "Share non-sensitive signals automatically.", privacy_level: "permissive", sharing_default: "allow" },
];

const WORKFLOWS = [
  { value: "minimal", label: "Quick & minimal" },
  { value: "balanced", label: "Balanced" },
  { value: "detailed", label: "Deep & detailed" },
];

function Field({ label, children, error }: { label: string; children: React.ReactNode; error?: string }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-sm font-semibold">{label}</span>
      {children}
      {error && <span className="text-xs font-semibold text-danger">{error}</span>}
    </label>
  );
}

const inputClass =
  "w-full rounded-lg border border-outline-variant bg-white px-3 py-2 text-sm outline-none focus:border-primary";

export default function Onboarding() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);

  const [occupation, setOccupation] = useState("");
  const [domain, setDomain] = useState("");
  const [company, setCompany] = useState("");
  const [building, setBuilding] = useState("");
  const [workflow, setWorkflow] = useState("balanced");
  const [goals, setGoals] = useState<string[]>([]);
  const [goalsText, setGoalsText] = useState("");
  const [tools, setTools] = useState<string[]>([]);
  const [customTool, setCustomTool] = useState("");
  const [posture, setPosture] = useState("private");

  const [touched, setTouched] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const occupationError = touched && !occupation.trim() ? "Tell us your role so we can seed your persona." : "";

  const toggle = <T,>(list: T[], value: T, set: (v: T[]) => void) =>
    set(list.includes(value) ? list.filter((x) => x !== value) : [...list, value]);

  const addCustomTool = () => {
    const v = customTool.trim();
    if (v && !tools.includes(v)) setTools([...tools, v]);
    setCustomTool("");
  };

  const postureCfg = POSTURES.find((p) => p.value === posture)!;

  const seedAnswers = useMemo(
    () => ({
      identity: [occupation.trim(), domain.trim()].filter(Boolean).join(", "),
      features: tools,
      behavior:
        workflow === "minimal" ? "quick minimal flows" : workflow === "detailed" ? "deep detailed flows" : "balanced flows",
      active_context: building.trim(),
      preferences: [...goals.map((g) => GOAL_OPTIONS.find((o) => o.value === g)?.label || g), ...(goalsText.trim() ? [goalsText.trim()] : [])],
    }),
    [occupation, domain, tools, workflow, building, goals, goalsText],
  );

  const next = () => {
    if (step === 1) {
      setTouched(true);
      if (!occupation.trim()) return;
    }
    setError("");
    setStep((s) => Math.min(STEPS.length - 1, s + 1));
  };
  const back = () => setStep((s) => Math.max(0, s - 1));

  const finish = async () => {
    setSaving(true);
    setError("");
    try {
      // Fire both calls in parallel: persona seed + privacy posture.
      await Promise.all([
        seedOnboarding(seedAnswers),
        submitOnboardingFlow({
          privacy_level: postureCfg.privacy_level,
          sharing_default: postureCfg.sharing_default,
          personalization_goals: goals,
          personalization_aggression: "medium",
          enabled_integrations: [],
          never_share: [],
        }),
      ]);
      markOnboardingComplete();
      navigate("/app/persona", { replace: true });
    } catch (err) {
      setError(
        err instanceof Error && /not configured|failed to fetch|networkerror/i.test(err.message)
          ? "Backend offline — we couldn’t save your persona. Reconnect and try again."
          : err instanceof Error
            ? err.message
            : "Something went wrong saving your persona.",
      );
    } finally {
      setSaving(false);
    }
  };

  const skip = async () => {
    setSaving(true);
    try {
      await submitOnboardingFlow({});
    } catch {
      /* best effort — still leave onboarding */
    } finally {
      setSaving(false);
      markOnboardingComplete();
      navigate("/app/persona", { replace: true });
    }
  };

  return (
    <div className="min-h-dvh bg-surface text-on-surface">
      <header className="mx-auto flex max-w-2xl items-center justify-between px-5 py-5">
        <span className="flex items-center gap-2 font-bold text-primary">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-primary/10">
            <Sparkles size={18} />
          </span>
          PersonaLayer
        </span>
        <button onClick={skip} disabled={saving} className="text-sm font-semibold text-on-surface-variant hover:text-on-surface">
          Skip for now
        </button>
      </header>

      <main className="mx-auto w-full max-w-2xl px-5 pb-16">
        <div className="mb-6 overflow-x-auto">
          <Stepper steps={STEPS} current={step} />
        </div>

        <div className="rounded-2xl border border-outline-variant bg-white p-6 shadow-ambient sm:p-8">
          {/* Step 0 — Welcome */}
          {step === 0 && (
            <div className="flex flex-col gap-4">
              <span className="inline-grid h-12 w-12 place-items-center rounded-xl bg-primary/10 text-primary">
                <Sparkles size={24} />
              </span>
              <h1 className="text-2xl font-bold">Let’s seed your persona</h1>
              <p className="leading-7 text-on-surface-variant">
                PersonaLayer builds a living picture of your work and preferences. We’ll start with a few questions so apps
                have useful context from day one — before any connectors sync. Everything stays private by default; you
                decide what’s ever shared.
              </p>
              <ul className="flex flex-col gap-2 text-sm text-on-surface-variant">
                <li className="flex items-center gap-2"><Check size={16} className="text-ok" /> Takes about a minute</li>
                <li className="flex items-center gap-2"><Check size={16} className="text-ok" /> Nothing is shared without your say-so</li>
                <li className="flex items-center gap-2"><Check size={16} className="text-ok" /> You can edit or delete any signal later</li>
              </ul>
            </div>
          )}

          {/* Step 1 — Work */}
          {step === 1 && (
            <div className="flex flex-col gap-4">
              <h1 className="flex items-center gap-2 text-2xl font-bold"><Briefcase size={22} className="text-primary" /> Your work</h1>
              <p className="text-on-surface-variant">What do you do, and what are you working on?</p>
              <Field label="Your role or occupation" error={occupationError}>
                <input className={inputClass} value={occupation} placeholder="e.g. Software engineer" onChange={(e) => setOccupation(e.target.value)} />
              </Field>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Field or domain (optional)">
                  <input className={inputClass} value={domain} placeholder="e.g. AI / fintech" onChange={(e) => setDomain(e.target.value)} />
                </Field>
                <Field label="Company (optional)">
                  <input className={inputClass} value={company} placeholder="e.g. Acme" onChange={(e) => setCompany(e.target.value)} />
                </Field>
              </div>
              <Field label="What are you building or focused on right now? (optional)">
                <input className={inputClass} value={building} placeholder="e.g. Launching a new mobile app" onChange={(e) => setBuilding(e.target.value)} />
              </Field>
              <Field label="How do you like to work?">
                <div className="flex flex-wrap gap-2">
                  {WORKFLOWS.map((w) => (
                    <button
                      key={w.value}
                      onClick={() => setWorkflow(w.value)}
                      className={`rounded-lg border px-3 py-2 text-sm font-semibold transition ${
                        workflow === w.value ? "border-primary bg-primary/10 text-primary" : "border-outline-variant hover:bg-surface-container-low"
                      }`}
                    >
                      {w.label}
                    </button>
                  ))}
                </div>
              </Field>
            </div>
          )}

          {/* Step 2 — Goals */}
          {step === 2 && (
            <div className="flex flex-col gap-4">
              <h1 className="flex items-center gap-2 text-2xl font-bold"><Target size={22} className="text-primary" /> Your goals</h1>
              <p className="text-on-surface-variant">What do you want agents and apps to help you with? Pick any that fit.</p>
              <div className="grid gap-2 sm:grid-cols-2">
                {GOAL_OPTIONS.map((g) => {
                  const on = goals.includes(g.value);
                  return (
                    <button
                      key={g.value}
                      onClick={() => toggle(goals, g.value, setGoals)}
                      className={`flex items-center justify-between gap-2 rounded-lg border px-3 py-2.5 text-left text-sm font-semibold transition ${
                        on ? "border-primary bg-primary/10 text-primary" : "border-outline-variant hover:bg-surface-container-low"
                      }`}
                    >
                      {g.label}
                      {on && <Check size={16} />}
                    </button>
                  );
                })}
              </div>
              <Field label="Anything else? (optional)">
                <textarea className={inputClass} rows={2} value={goalsText} placeholder="In your own words…" onChange={(e) => setGoalsText(e.target.value)} />
              </Field>
            </div>
          )}

          {/* Step 3 — Tools */}
          {step === 3 && (
            <div className="flex flex-col gap-4">
              <h1 className="flex items-center gap-2 text-2xl font-bold"><Wrench size={22} className="text-primary" /> Your tools</h1>
              <p className="text-on-surface-variant">Which tools and apps do you use? Tap to select.</p>
              <div className="flex flex-wrap gap-2">
                {[...TOOL_OPTIONS, ...tools.filter((t) => !TOOL_OPTIONS.includes(t))].map((t) => {
                  const on = tools.includes(t);
                  return (
                    <button
                      key={t}
                      onClick={() => toggle(tools, t, setTools)}
                      className={`rounded-full border px-3.5 py-1.5 text-sm font-semibold transition ${
                        on ? "border-primary bg-primary/10 text-primary" : "border-outline-variant hover:bg-surface-container-low"
                      }`}
                    >
                      {t}
                    </button>
                  );
                })}
              </div>
              <div className="flex items-center gap-2">
                <input
                  className={inputClass}
                  value={customTool}
                  placeholder="Add another tool"
                  onChange={(e) => setCustomTool(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addCustomTool())}
                />
                <Button variant="default" onClick={addCustomTool} disabled={!customTool.trim()}>
                  <Plus size={15} /> Add
                </Button>
              </div>
            </div>
          )}

          {/* Step 4 — Privacy */}
          {step === 4 && (
            <div className="flex flex-col gap-4">
              <h1 className="flex items-center gap-2 text-2xl font-bold"><Lock size={22} className="text-primary" /> Privacy posture</h1>
              <p className="text-on-surface-variant">
                Your starting point. PersonaLayer has <strong>no default rules</strong> — nothing is blocked or shared by the
                system. This sets how apps may ask; you build the actual rules later.
              </p>
              <div className="flex flex-col gap-2">
                {POSTURES.map((p) => (
                  <button
                    key={p.value}
                    onClick={() => setPosture(p.value)}
                    className={`flex items-start justify-between gap-3 rounded-xl border p-4 text-left transition ${
                      posture === p.value ? "border-primary bg-primary/[0.06]" : "border-outline-variant hover:bg-surface-container-low"
                    }`}
                  >
                    <div>
                      <div className="font-semibold">{p.label}</div>
                      <div className="text-sm text-on-surface-variant">{p.hint}</div>
                    </div>
                    <span className={`mt-1 grid h-5 w-5 shrink-0 place-items-center rounded-full border ${posture === p.value ? "border-primary bg-primary text-white" : "border-outline-variant"}`}>
                      {posture === p.value && <Check size={13} />}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Step 5 — Confirm */}
          {step === 5 && (
            <div className="flex flex-col gap-4">
              <h1 className="flex items-center gap-2 text-2xl font-bold"><Check size={22} className="text-ok" /> Review your persona</h1>
              <p className="text-on-surface-variant">Here’s what we’ll seed. You can jump back to edit anything.</p>

              <ReviewRow label="Role" value={seedAnswers.identity || "—"} onEdit={() => setStep(1)} />
              {company.trim() && <ReviewRow label="Company" value={company} onEdit={() => setStep(1)} />}
              {building.trim() && <ReviewRow label="Focus" value={building} onEdit={() => setStep(1)} />}
              <ReviewRow label="Work style" value={titleize(workflow)} onEdit={() => setStep(1)} />
              <ReviewRow
                label="Goals"
                value={seedAnswers.preferences.length ? seedAnswers.preferences.join(" · ") : "None selected"}
                onEdit={() => setStep(2)}
              />
              <ReviewRow label="Tools" value={tools.length ? tools.join(", ") : "None selected"} onEdit={() => setStep(3)} />
              <div className="flex items-center justify-between gap-3 rounded-xl border border-outline-variant p-4">
                <div>
                  <div className="text-xs uppercase tracking-wide text-outline">Privacy</div>
                  <div className="mt-0.5 flex items-center gap-2 font-semibold">
                    <Pill tone="good"><Lock size={12} /> {postureCfg.label}</Pill>
                  </div>
                </div>
                <button className="text-sm font-semibold text-primary hover:underline" onClick={() => setStep(4)}>Edit</button>
              </div>

              {error && (
                <p className="rounded-lg border border-danger/20 bg-danger/5 px-3 py-2 text-sm font-semibold text-danger">{error}</p>
              )}
            </div>
          )}

          {/* Nav */}
          <div className="mt-8 flex items-center justify-between gap-3">
            {step > 0 ? (
              <Button variant="ghost" onClick={back} disabled={saving}>
                <ArrowLeft size={15} /> Back
              </Button>
            ) : (
              <button
                type="button"
                onClick={skip}
                disabled={saving}
                className="text-sm font-semibold text-on-surface-variant hover:text-on-surface disabled:opacity-60"
              >
                Maybe later
              </button>
            )}
            {step < STEPS.length - 1 ? (
              <Button variant="primary" onClick={next}>
                {step === 0 ? "Get started" : "Next"} <ArrowRight size={15} />
              </Button>
            ) : (
              <Button variant="primary" loading={saving} onClick={finish}>
                <Check size={15} /> Confirm & finish
              </Button>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

function ReviewRow({ label, value, onEdit }: { label: string; value: string; onEdit: () => void }) {
  return (
    <div className="flex items-start justify-between gap-3 rounded-xl border border-outline-variant p-4">
      <div className="min-w-0">
        <div className="text-xs uppercase tracking-wide text-outline">{label}</div>
        <div className="mt-0.5 break-words font-semibold">{value}</div>
      </div>
      <button className="shrink-0 text-sm font-semibold text-primary hover:underline" onClick={onEdit}>Edit</button>
    </div>
  );
}
