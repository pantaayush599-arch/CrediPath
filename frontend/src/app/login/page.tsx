"use client";

import { AlertTriangle, ArrowRight, Check, FileText, Flag, Gauge, Landmark, Lightbulb, Loader2, Store, TrendingUp } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ThemeToggle } from "@/components/theme";
import { api, type DemoAccount } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { getSession, homeFor, setSession } from "@/lib/session";

type Role = "merchant" | "banker";

const ROLES: Record<Role, { title: string; who: string; icon: React.ReactNode; tone: string; ring: string; outputs: { icon: React.ReactNode; label: string }[] }> = {
  merchant: {
    title: "MSME owner",
    who: "Kiranas, bakeries, retailers",
    icon: <Store size={20} />,
    tone: "text-accent",
    ring: "border-accent ring-2 ring-accent/25",
    outputs: [
      { icon: <Gauge size={15} />, label: "Credit score" },
      { icon: <Lightbulb size={15} />, label: "Key strengths & concerns" },
      { icon: <TrendingUp size={15} />, label: "Improvement steps" },
    ],
  },
  banker: {
    title: "Banker",
    who: "Bank & NBFC loan officers",
    icon: <Landmark size={20} />,
    tone: "text-brand",
    ring: "border-brand ring-2 ring-brand/25",
    outputs: [
      { icon: <AlertTriangle size={15} />, label: "Risk indicators" },
      { icon: <FileText size={15} />, label: "Supporting evidence" },
      { icon: <Flag size={15} />, label: "Anomaly flags" },
    ],
  },
};

export default function Login() {
  const router = useRouter();
  const [role, setRole] = useState<Role>("merchant");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const accounts = useAsync<DemoAccount[]>(() => api.demoAccounts(), []);

  // Already signed in: go straight to the right dashboard.
  useEffect(() => {
    const s = getSession();
    if (s) router.replace(homeFor(s.user));
  }, [router]);

  const pick = (r: Role) => {
    setRole(r);
    setError(null);
    setEmail("");
    setPassword("");
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const s = await api.login(email, password, role);
      setSession(s);
      const next = new URLSearchParams(window.location.search).get("next");
      const allowed = next && next.startsWith("/") && !next.startsWith("//") && (s.user.role === "banker" || next.startsWith(`/merchant/${s.user.business_id}`));
      router.replace(allowed ? next : homeFor(s.user));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const samples = (accounts.data || []).filter((a) => a.role === role);
  const R = ROLES[role];

  return (
    <div className="min-h-screen bg-canvas">
      <header className="flex items-center justify-between border-b border-line px-4 py-3 sm:px-8">
        <div className="flex items-center gap-2.5">
          <svg width="28" height="28" viewBox="0 0 26 26" aria-hidden>
            <rect width="26" height="26" rx="5" fill="rgb(var(--brand))" />
            <path d="M6 17.5 L11 12.5 L14 15 L20 8.5" stroke="rgb(var(--canvas))" strokeWidth="2.2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
            <circle cx="20" cy="8.5" r="2" fill="rgb(var(--accent))" />
          </svg>
          <div className="leading-tight">
            <div className="font-serif text-lg font-semibold text-ink">CrediPath</div>
            <div className="text-[10px] uppercase tracking-[0.12em] text-ink-3">MSME credit visibility</div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="chip hidden border border-warn/30 bg-warn-soft text-warn sm:inline-flex">Synthetic demo data</span>
          <ThemeToggle compact />
        </div>
      </header>

      <main className="mx-auto grid max-w-6xl gap-8 px-4 py-8 sm:px-8 lg:grid-cols-[1.25fr_1fr] lg:py-12">
        <section>
          <div className="eyebrow mb-2">One score, two views</div>
          <h1 className="max-w-xl font-serif text-[28px] font-semibold leading-tight tracking-tight text-ink sm:text-[32px]">
            Credit visibility for banks, a clear path forward for MSMEs.
          </h1>
          <p className="mt-3 max-w-xl text-[15px] leading-relaxed text-ink-2">Choose how you want to sign in. Both views are powered by the same explainable scoring engine.</p>

          <div className="mt-6 grid gap-4 sm:grid-cols-2" role="radiogroup" aria-label="Sign in as">
            {(Object.keys(ROLES) as Role[]).map((r) => {
              const x = ROLES[r];
              const active = role === r;
              return (
                <button
                  key={r}
                  type="button"
                  role="radio"
                  aria-checked={active}
                  onClick={() => pick(r)}
                  className={`panel relative p-4 text-left transition-shadow hover:shadow-card ${active ? x.ring : ""}`}
                >
                  {active && (
                    <span className="absolute right-3 top-3 flex h-5 w-5 items-center justify-center rounded-full bg-brand text-brand-ink">
                      <Check size={12} />
                    </span>
                  )}
                  <div className={`flex items-center gap-2 ${x.tone}`}>
                    {x.icon}
                    <span className="text-[15px] font-semibold text-ink">{x.title} output</span>
                  </div>
                  <div className="mt-0.5 text-xs text-ink-3">{x.who}</div>
                  <ul className="mt-3 space-y-2 border-t border-line pt-3">
                    {x.outputs.map((o) => (
                      <li key={o.label} className="flex items-center gap-2 text-[13px] text-ink">
                        <span className={x.tone}>{o.icon}</span>
                        {o.label}
                      </li>
                    ))}
                  </ul>
                </button>
              );
            })}
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-2 text-xs text-ink-2">
            <span className="rounded-md border border-line bg-surface px-2.5 py-1.5">Consented business data</span>
            <ArrowRight size={14} className="text-ink-3" />
            <span className="rounded-md border border-brand/40 bg-brand px-2.5 py-1.5 font-semibold tracking-wide text-brand-ink">CrediPath scoring engine</span>
            <ArrowRight size={14} className="text-ink-3" />
            <span className="rounded-md border border-line bg-surface px-2.5 py-1.5">Owner view + Banker view</span>
          </div>
        </section>

        <section className="panel self-start">
          <div className="panel-head">
            <div>
              <h2 className="text-[15px] font-semibold text-ink">Sign in as {role === "merchant" ? "MSME owner" : "banker"}</h2>
              <p className="mt-0.5 text-xs text-ink-3">{role === "merchant" ? "See your score and what to improve next." : "Review applicants, risks and what to verify."}</p>
            </div>
            <span className={R.tone}>{R.icon}</span>
          </div>
          <form onSubmit={submit} className="space-y-3 p-4">
            <label className="block text-xs text-ink-2">
              Email
              <input className="input mt-1" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
            </label>
            <label className="block text-xs text-ink-2">
              Password
              <input className="input mt-1" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
            </label>
            {error && (
              <p className="rounded-md border border-bad/30 bg-bad-soft px-3 py-2 text-xs text-bad" role="alert">
                {error}
              </p>
            )}
            <button className="btn-primary w-full py-2" disabled={busy}>
              {busy && <Loader2 size={14} className="animate-spin" />} Sign in
            </button>
            {role === "merchant" && (
              <p className="text-center text-xs text-ink-3">
                New business?{" "}
                <Link href="/onboard" className="font-medium text-accent hover:underline">
                  Register and upload records
                </Link>
              </p>
            )}
          </form>

          <div className="border-t border-line p-4">
            <div className="eyebrow mb-2">Sample {role === "merchant" ? "owner" : "banker"} accounts (demo)</div>
            {accounts.error && <p className="text-xs text-bad">{accounts.error.message}</p>}
            {!accounts.data && !accounts.error && <p className="text-xs text-ink-3">Loading…</p>}
            <ul className="divide-y divide-line rounded-md border border-line">
              {samples.map((a) => (
                <li key={a.email} className="flex items-center gap-3 px-3 py-2">
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[13px] font-medium text-ink">{a.organisation}</div>
                    <div className="num truncate text-2xs text-ink-3">
                      {a.email} · {a.password}
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn-secondary shrink-0 px-2.5 py-1 text-xs"
                    onClick={() => {
                      setEmail(a.email);
                      setPassword(a.password);
                      setError(null);
                    }}
                  >
                    Use
                  </button>
                </li>
              ))}
            </ul>
            <p className="mt-3 text-2xs leading-relaxed text-ink-3">
              Demo sign-in for a prototype: these accounts are public and all businesses are fictional. Owners can only see their own business; bankers see every applicant. Not production authentication.
            </p>
          </div>
        </section>
      </main>
    </div>
  );
}
