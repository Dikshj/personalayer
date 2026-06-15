// /request-access — public page for companies/builders requesting MCP Context
// API access. Separate from the consumer sign-up flow (/app/session): this is
// a lightweight contact form, not an account.

import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, ArrowRight, Building2, CheckCircle2, Mail, Sparkles } from "lucide-react";
import { Button } from "../components/ui";

export default function RequestAccess() {
  const [company, setCompany] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [useCase, setUseCase] = useState("");
  const [sent, setSent] = useState(false);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    setSent(true);
  };

  return (
    <div className="min-h-dvh bg-surface text-on-surface">
      <header className="mx-auto flex max-w-2xl items-center justify-between px-5 py-5">
        <Link to="/" className="flex items-center gap-2 font-bold text-primary">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-primary/10">
            <Sparkles size={18} />
          </span>
          PersonaLayer
        </Link>
        <Link to="/" className="text-sm font-semibold text-on-surface-variant hover:text-on-surface">
          ← Back to home
        </Link>
      </header>

      <main className="mx-auto w-full max-w-2xl px-5 pb-16">
        <div className="rounded-2xl border border-outline-variant bg-white p-6 shadow-ambient sm:p-8">
          {sent ? (
            <div className="flex flex-col items-center gap-4 py-8 text-center">
              <span className="grid h-12 w-12 place-items-center rounded-xl bg-secondary-container text-on-secondary-container">
                <CheckCircle2 size={24} />
              </span>
              <h1 className="text-2xl font-bold">Request received</h1>
              <p className="max-w-md leading-7 text-on-surface-variant">
                Thanks{name.trim() ? `, ${name.trim()}` : ""} — our team will review your request and follow up at{" "}
                <strong>{email.trim() || "the email you provided"}</strong> with next steps for MCP Context API access.
              </p>
              <Link to="/" className="primary-button mt-2">
                <ArrowLeft size={15} /> Back to home
              </Link>
            </div>
          ) : (
            <>
              <span className="inline-grid h-12 w-12 place-items-center rounded-xl bg-primary/10 text-primary">
                <Building2 size={24} />
              </span>
              <h1 className="mt-4 text-2xl font-bold">Request API access</h1>
              <p className="mt-1.5 leading-7 text-on-surface-variant">
                Building a product that needs personalized context? Tell us about your use case and we'll set you up with
                MCP Context API access and a builder account.
              </p>

              <form onSubmit={submit} className="mt-6 flex flex-col gap-4">
                <label className="flex flex-col gap-1.5">
                  <span className="text-sm font-semibold">Company / project name</span>
                  <input
                    required
                    value={company}
                    onChange={(e) => setCompany(e.target.value)}
                    placeholder="e.g. Acme Inc."
                    className="h-11 rounded-lg border border-outline-variant px-3.5 text-sm outline-none focus:border-primary"
                  />
                </label>
                <label className="flex flex-col gap-1.5">
                  <span className="text-sm font-semibold">Your name</span>
                  <input
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. Jordan Lee"
                    className="h-11 rounded-lg border border-outline-variant px-3.5 text-sm outline-none focus:border-primary"
                  />
                </label>
                <label className="flex flex-col gap-1.5">
                  <span className="inline-flex items-center gap-1.5 text-sm font-semibold">
                    <Mail size={13} /> Work email
                  </span>
                  <input
                    required
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@company.com"
                    className="h-11 rounded-lg border border-outline-variant px-3.5 text-sm outline-none focus:border-primary"
                  />
                </label>
                <label className="flex flex-col gap-1.5">
                  <span className="text-sm font-semibold">What are you building?</span>
                  <textarea
                    required
                    rows={4}
                    value={useCase}
                    onChange={(e) => setUseCase(e.target.value)}
                    placeholder="Tell us about your product and how you'd use persona context…"
                    className="rounded-lg border border-outline-variant px-3.5 py-2.5 text-sm outline-none focus:border-primary"
                  />
                </label>

                <Button type="submit" variant="primary">
                  Submit request <ArrowRight size={15} />
                </Button>
              </form>

              <p className="mt-4 text-center text-sm text-on-surface-variant">
                Looking to use PersonaLayer yourself instead?{" "}
                <Link to="/app/session" className="font-semibold text-primary hover:underline">
                  Sign in or create an account
                </Link>
              </p>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
