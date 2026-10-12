"use client";

import { ArrowRight, Database, Landmark, RotateCcw, Store } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { api, type Business } from "@/lib/api";
import { inr } from "@/lib/format";
import { rememberBusiness, useAsync } from "@/lib/hooks";
import { ConfidenceWithReasons, ErrorState, Loading, SuccessNote } from "@/components/ui";

const LOOP = [
  { step: "Assess", text: "Consented bank/UPI, sales, invoice, supplier and loan records are validated and turned into 8 indicators.", where: "Records & reassessment" },
  { step: "Explain", text: "One weighted, rules-based score. Every point traces back to a metric the lender and owner can both see.", where: "Assessment" },
  { step: "Improve", text: "The owner gets ranked fixes, a what-if simulator and a progress tracker.", where: "My score & plan" },
  { step: "Reassess", text: "New records are uploaded and rescored; the lender sees the updated profile and what changed.", where: "Records & reassessment" },
];

export default function Home() {
  const { data, error, loading, reload } = useAsync<Business[]>(() => api.businesses(), []);
  const health = useAsync(() => api.health(), []);
  const [confirming, setConfirming] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [resetMsg, setResetMsg] = useState<string | null>(null);
  const [resetErr, setResetErr] = useState<Error | null>(null);
  const raj = data?.find((b) => b.id === "rajs-bakery");

  const doReset = async () => {
    setResetting(true);
    setResetErr(null);
    try {
      const r = await api.reset();
      setResetMsg(`${r.message} ${r.restored.length} businesses reloaded.`);
      rememberBusiness("rajs-bakery");
      reload();
    } catch (e) {
      setResetErr(e as Error);
    } finally {
      setResetting(false);
      setConfirming(false);
    }
  };

  return (
    <div className="space-y-8">
      <section className="grid gap-6 lg:grid-cols-[1.4fr_1fr] lg:items-end">
        <div>
          <div className="eyebrow mb-2">Hack On Track · FinTech prototype</div>
          <h1 className="max-w-2xl font-serif text-[30px] font-semibold leading-tight tracking-tight text-ink sm:text-[34px]">
            Credit visibility for banks, a clear path forward for MSMEs.
          </h1>
          <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-ink-2">
            One explainable score, built from consented cash-flow and business records, powers two views: a risk view for loan officers assessing thin-file
            businesses, and a guidance view that tells the owner what to fix next.
          </p>
        </div>
        <div className="panel divide-y divide-line">
          <Link href="/banker" className="group flex items-center gap-3 px-4 py-3 hover:bg-sunken/60">
            <Landmark size={18} className="text-brand" />
            <div className="flex-1">
              <div className="text-sm font-semibold text-ink">Open the lender view</div>
              <div className="text-xs text-ink-3">Applicant portfolio, score factors, risk flags, what to verify</div>
            </div>
            <ArrowRight size={16} className="text-ink-3 transition-transform group-hover:translate-x-0.5" />
          </Link>
          <Link href="/merchant/rajs-bakery" onClick={() => rememberBusiness("rajs-bakery")} className="group flex items-center gap-3 px-4 py-3 hover:bg-sunken/60">
            <Store size={18} className="text-accent" />
            <div className="flex-1">
              <div className="text-sm font-semibold text-ink">Open the business-owner view</div>
              <div className="text-xs text-ink-3">Plain-language findings, ranked fixes, what-if, progress</div>
            </div>
            <ArrowRight size={16} className="text-ink-3 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2 className="text-[13px] font-semibold">The loop: Assess → Explain → Improve → Reassess</h2>
        </div>
        <ol className="grid divide-y divide-line sm:grid-cols-2 sm:divide-y-0 lg:grid-cols-4 lg:divide-x">
          {LOOP.map((l, i) => (
            <li key={l.step} className="px-4 py-4 sm:[&:nth-child(n+3)]:border-t sm:[&:nth-child(n+3)]:border-line lg:[&:nth-child(n+3)]:border-t-0">
              <div className="flex items-baseline gap-2">
                <span className="num text-xs text-ink-3">0{i + 1}</span>
                <span className="font-semibold text-ink">{l.step}</span>
              </div>
              <p className="mt-1.5 text-xs leading-relaxed text-ink-2">{l.text}</p>
              <p className="mt-2 text-2xs uppercase tracking-wide text-ink-3">In app: {l.where}</p>
            </li>
          ))}
        </ol>
      </section>

      {loading && <Loading label="Loading demo businesses…" />}
      {error && <ErrorState error={error} onRetry={reload} />}

      {raj && (
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2 className="text-[13px] font-semibold">Primary walkthrough · {raj.name}</h2>
              <p className="mt-0.5 text-xs text-ink-3">Illustrative business from the deck. Synthetic records; the score below is calculated from them.</p>
            </div>
            <ConfidenceWithReasons level={raj.confidence} checks={raj.confidence_checks} />
          </div>
          <div className="grid gap-4 p-4 sm:grid-cols-4">
            <div>
              <div className="eyebrow">Avg monthly sales</div>
              <div className="num mt-1 text-xl text-ink">{inr(raj.avg_monthly_income, { compact: true })}</div>
            </div>
            <div>
              <div className="eyebrow">CrediPath score</div>
              <div className="num mt-1 text-xl text-ink">
                {raj.latest_display_score}
                <span className="text-sm text-ink-3"> /100 · {raj.latest_score?.toFixed(2)}</span>
              </div>
            </div>
            <div>
              <div className="eyebrow">Bureau view</div>
              <div className="mt-1 text-sm text-ink">{raj.bureau_status}</div>
            </div>
            <div className="flex flex-wrap items-end gap-2 sm:justify-end">
              <Link className="btn-secondary" href="/banker/rajs-bakery" onClick={() => rememberBusiness("rajs-bakery")}>
                Lender view
              </Link>
              <Link className="btn-primary" href="/merchant/rajs-bakery" onClick={() => rememberBusiness("rajs-bakery")}>
                Owner view
              </Link>
            </div>
          </div>
          <div className="border-t border-line px-4 py-3 text-xs text-ink-2">
            <b className="text-ink">Suggested demo:</b> open the lender view (62/100, overdue receivables to verify) → owner view (top 3 fixes, what-if 62 → 73) → Records &amp; reassessment → upload{" "}
            <span className="num">raj_bakery_update_sep2026.csv</span> → back to the lender view to see the updated profile.
          </div>
        </section>
      )}

      {data && (
        <section className="panel">
          <div className="panel-head">
            <h2 className="text-[13px] font-semibold">Demo businesses</h2>
            <span className="text-xs text-ink-3">All fictional</span>
          </div>
          <div className="overflow-x-auto">
            <table className="table-base min-w-[560px]">
              <thead>
                <tr>
                  <th>Business</th>
                  <th>Type · city</th>
                  <th>Why it is in the demo</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {data.map((b) => (
                  <tr key={b.id}>
                    <td className="font-medium text-ink">{b.name}</td>
                    <td className="text-ink-2">
                      {b.category} · {b.city}
                    </td>
                    <td className="text-xs text-ink-2">{DEMO_NOTES[b.id] ?? (b.is_seeded ? "" : "Added during this demo")}</td>
                    <td className="text-right">
                      <Link className="text-xs font-medium text-accent hover:underline" href={`/banker/${b.id}`} onClick={() => rememberBusiness(b.id)}>
                        Open
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="grid gap-4 md:grid-cols-2">
        <div className="panel p-4">
          <div className="flex items-center gap-2 text-[13px] font-semibold">
            <RotateCcw size={15} /> Restore demo data
          </div>
          <p className="mt-1.5 text-xs text-ink-2">Deletes uploads, added businesses, reassessments and progress, then reloads the original synthetic businesses and assessments.</p>
          {resetMsg && (
            <div className="mt-3">
              <SuccessNote>{resetMsg}</SuccessNote>
            </div>
          )}
          {resetErr && (
            <div className="mt-3">
              <ErrorState error={resetErr} />
            </div>
          )}
          {!confirming ? (
            <button className="btn-secondary mt-3" onClick={() => setConfirming(true)}>
              Restore demo data…
            </button>
          ) : (
            <div className="mt-3 flex flex-wrap items-center gap-2 rounded-md border border-warn/40 bg-warn-soft p-3" role="alertdialog" aria-label="Confirm restore">
              <span className="text-xs text-ink">This removes everything changed during the demo. Continue?</span>
              <button className="btn-primary" disabled={resetting} onClick={doReset}>
                {resetting ? "Restoring…" : "Yes, restore"}
              </button>
              <button className="btn-ghost" onClick={() => setConfirming(false)}>
                Cancel
              </button>
            </div>
          )}
        </div>
        <div className="panel p-4">
          <div className="flex items-center gap-2 text-[13px] font-semibold">
            <Database size={15} /> System status
          </div>
          <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-xs">
            <dt className="text-ink-3">API</dt>
            <dd className="text-ink">{health.error ? <span className="text-bad">unreachable</span> : health.data ? "connected" : "checking…"}</dd>
            <dt className="text-ink-3">Storage</dt>
            <dd className="text-ink">{health.data?.database ?? "—"}</dd>
            <dt className="text-ink-3">Scoring</dt>
            <dd className="text-ink">Rules engine (no machine learning)</dd>
            <dt className="text-ink-3">Explanations</dt>
            <dd className="text-ink">Template-based from scoring output</dd>
          </dl>
        </div>
      </section>
    </div>
  );
}

const DEMO_NOTES: Record<string, string> = {
  "rajs-bakery": "Deck example: ₹1.5 L/month, thin file, 62/100, overdue receivables",
  "meena-general-store": "Strong file with 24 months of data (year-on-year growth) and assessment history",
  "sharma-mobile-electronics": "Risk flags: possible circular flow, one-off spike, record mismatch, late EMIs",
  "green-leaf-tiffin": "New to credit: 5 months of data, several indicators not scorable, low confidence",
};
