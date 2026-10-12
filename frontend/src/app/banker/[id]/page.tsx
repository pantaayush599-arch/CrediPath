"use client";

import { RefreshCw } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { BusinessSwitcher } from "@/components/BusinessSwitcher";
import { BalanceChart, CashFlowChart, ScoreHistoryChart } from "@/components/charts";
import { ComparisonView, IndicatorBreakdown, ScoreDial } from "@/components/score";
import { CONFIDENCE_RULE_TEXT, ConfidenceChecks, ConfidenceChip, EmptyState, ErrorState, FlagRow, HumanDecides, Loading, NotFoundBusiness, PageHeader, Panel, ScoreBar } from "@/components/ui";
import { api, ApiError, type Assessment, type AssessmentSummary, type Business, type Comparison, type Flag, type Indicator } from "@/lib/api";
import { dateLabel, inr } from "@/lib/format";
import { useAsync } from "@/lib/hooks";

interface Bundle {
  business: Business;
  assessment: Assessment | null;
  history: AssessmentSummary[];
  comparison: Comparison | null;
}

async function load(id: string): Promise<Bundle> {
  const business = await api.business(id);
  try {
    const [assessment, history, comparison] = await Promise.all([api.assessment(id), api.assessments(id), api.comparison(id)]);
    return { business, assessment, history, comparison };
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return { business, assessment: null, history: [], comparison: null };
    throw e;
  }
}

function FactorList({ title, items, tone }: { title: string; items: Indicator[]; tone: "good" | "bad" }) {
  return (
    <div>
      <div className={`eyebrow mb-2 ${tone === "good" ? "text-good" : "text-bad"}`}>{title}</div>
      {items.length === 0 ? (
        <div className="text-xs text-ink-3">None</div>
      ) : (
        <ul className="space-y-2.5">
          {items.map((i) => (
            <li key={i.key} className="grid grid-cols-[minmax(0,1fr)_64px_24px] items-center gap-2.5 text-[13px]">
              <span className="leading-tight text-ink">{i.name}</span>
              <ScoreBar value={i.sub_score} band={i.band} />
              <span className="num text-right text-ink">{i.sub_score}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Evidence({ flag }: { flag: Flag }) {
  const items = flag.evidence?.items as Record<string, string | number | null>[] | undefined;
  if (!items?.length) return null;
  const cols = Object.keys(items[0]);
  return (
    <div className="mt-2 overflow-x-auto rounded border border-line">
      <table className="table-base text-xs">
        <thead>
          <tr>
            {cols.map((c) => (
              <th key={c}>{c.replace(/_/g, " ")}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.slice(0, 8).map((it, n) => (
            <tr key={n}>
              {cols.map((c) => (
                <td key={c} className={typeof it[c] === "number" ? "num" : ""}>
                  {c === "amount" || c === "sales_register" || c === "bank_income" ? inr(it[c] as number) : it[c] === null ? "—" : String(it[c])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function BankerAssessment() {
  const { id } = useParams<{ id: string }>();
  const { data, error, loading, reload } = useAsync<Bundle>(() => load(id), [id]);
  const [recalc, setRecalc] = useState(false);

  if (loading && !data) return <Loading />;
  if (error) return error instanceof ApiError && error.status === 404 ? <NotFoundBusiness /> : <ErrorState error={error} onRetry={reload} />;
  if (!data) return null;
  const { business: b, assessment: a, history, comparison } = data;

  const header = (
    <PageHeader
      eyebrow="Lender · risk view"
      title={b.name}
      subtitle={
        <span>
          {b.category} · {b.city} · {b.years_in_operation ?? "?"} yrs in operation · <span className="chip bg-warn-soft text-warn">synthetic</span>
        </span>
      }
      actions={<BusinessSwitcher current={id} basePath="/banker" label="Applicant" />}
    />
  );
  if (!a)
    return (
      <div>
        {header}
        <EmptyState title="No assessment yet">
          No records have been shared for this business. Records are added from{" "}
          <Link className="text-accent underline" href={`/merchant/${id}/records`}>
            Records &amp; reassessment
          </Link>
          .
        </EmptyState>
      </div>
    );

  const strengths = a.indicators.filter((i) => i.band === "strength").sort((x, y) => y.sub_score! - x.sub_score!);
  const concerns = a.indicators.filter((i) => i.band === "concern").sort((x, y) => x.sub_score! - y.sub_score!);
  const verify = a.flags.filter((f) => f.requires_verification);
  const other = a.flags.filter((f) => !f.requires_verification);
  const liq = a.indicators.find((i) => i.key === "liquidity_resilience");
  const scoredMonths = a.monthly.filter((m) => m.has_bank);
  const avgOut = scoredMonths.length ? scoredMonths.reduce((s, m) => s + (m.outflow ?? 0), 0) / scoredMonths.length : null;
  const avgIn = scoredMonths.length ? scoredMonths.reduce((s, m) => s + (m.inflow ?? 0), 0) / scoredMonths.length : null;

  const doRecalc = async () => {
    setRecalc(true);
    try {
      await api.reassess(id);
      reload();
    } finally {
      setRecalc(false);
    }
  };

  return (
    <div className="space-y-5">
      {header}

      <div className="grid gap-5 xl:grid-cols-[1.35fr_1fr]">
        <Panel
          title="CrediPath assessment"
          subtitle={`Records ${dateLabel(a.window_start)} – ${dateLabel(a.window_end)} · ${a.record_count} records · ${a.scoring_version}`}
          actions={<ConfidenceChip level={a.confidence} />}
        >
          <div className="flex flex-col gap-6 sm:flex-row sm:items-start">
            <div className="flex flex-col items-center gap-2">
              <ScoreDial value={a.display_score} exact={a.overall_score} />
              <div className="text-center text-2xs text-ink-3">Alternative-data score</div>
            </div>
            <div className="grid flex-1 gap-5 sm:grid-cols-2">
              <FactorList title="Strengths" items={strengths} tone="good" />
              <FactorList title="Concerns" items={concerns} tone="bad" />
              <div className="sm:col-span-2">
                <p className="text-xs leading-relaxed text-ink-2">{a.summary.banker_summary}</p>

              </div>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-line pt-3">
            {verify.slice(0, 3).map((f) => (
              <a key={f.id} href="#verify" className="chip bg-warn-soft text-warn hover:underline">
                ⚑ {f.title.replace(/^Verify: /, "Verify: ")}
              </a>
            ))}
            {verify.length === 0 && <span className="text-xs text-ink-3">No items flagged for verification.</span>}
          </div>
        </Panel>

        <Panel title="Conventional view vs CrediPath evidence">
          <div className="grid gap-4 text-xs sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
            <div className="rounded-md border border-line bg-sunken/60 p-3">
              <div className="eyebrow mb-1">Conventional (bureau-led)</div>
              <div className="mb-1 text-sm font-semibold text-ink">{b.bureau_status}</div>
              <p className="leading-relaxed text-ink-2">{b.conventional_view}</p>
            </div>
            <div className="rounded-md border border-accent/30 bg-accent-soft/50 p-3">
              <div className="eyebrow mb-1 text-accent">With consented records</div>
              <ul className="space-y-1 text-ink-2">
                <li>
                  Avg monthly income <b className="num text-ink">{inr(avgIn, { compact: true })}</b> over {scoredMonths.length} months of bank data
                </li>
                <li>
                  {a.indicators.filter((i) => i.sub_score !== null).length} of 8 indicators scored from {a.record_count} records
                </li>
                <li>
                  {strengths.length} strength(s), {concerns.length} concern(s), {verify.length} item(s) to verify
                </li>
              </ul>
            </div>
          </div>
          <div className="mt-4 rounded-md border border-line p-3">
            <div className="mb-2 flex items-center justify-between gap-2">
              <span className="eyebrow">Why {a.confidence} confidence</span>
              <ConfidenceChip level={a.confidence} />
            </div>
            <ConfidenceChecks checks={a.summary.confidence_checks ?? []} />
            <p className="mt-2 border-t border-line pt-2 text-2xs text-ink-3">{CONFIDENCE_RULE_TEXT}</p>
          </div>
          <HumanDecides className="mt-4" />
        </Panel>
      </div>

      <Panel
        title="Why this score — eight weighted indicators"
        subtitle="Click a row for the metric and the explanation. Points = sub-score × weight; they add up to the overall score."
        actions={
          <button className="btn-ghost text-xs" onClick={doRecalc} disabled={recalc} title="Re-run the rules engine on the stored records">
            <RefreshCw size={13} className={recalc ? "animate-spin" : ""} /> Recalculate
          </button>
        }
        bodyClass="p-2 sm:p-3"
      >
        <IndicatorBreakdown indicators={a.indicators} overall={a.overall_score} />
      </Panel>

      <div className="grid gap-5 lg:grid-cols-2">
        <Panel title="Monthly cash flow" subtitle="Business income vs all outflows from bank / UPI records. Missing months are gaps, not zero.">
          <CashFlowChart monthly={a.monthly} />
        </Panel>
        <Panel title="Cash buffer" subtitle={liq?.explanation_banker ?? ""}>
          <BalanceChart monthly={a.monthly} benchmarkDays={Math.round((liq?.benchmark ?? 65) * 0.4)} avgOutflow={avgOut} />
        </Panel>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <section id="verify" className="panel scroll-mt-20">
          <div className="panel-head">
            <h2 className="text-[13px] font-semibold">To verify ({verify.length})</h2>
            <span className="text-2xs text-ink-3">Flags prompt review; they are not findings of fraud</span>
          </div>
          {verify.length === 0 ? (
            <p className="p-4 text-xs text-ink-3">Nothing flagged for verification.</p>
          ) : (
            <ul>
              {verify.map((f) => (
                <FlagRow key={f.id} flag={f}>
                  <Evidence flag={f} />
                </FlagRow>
              ))}
            </ul>
          )}
        </section>
        <section className="panel">
          <div className="panel-head">
            <h2 className="text-[13px] font-semibold">Data quality &amp; other flags ({other.length})</h2>
          </div>
          {other.length === 0 ? (
            <p className="p-4 text-xs text-ink-3">No data-quality issues.</p>
          ) : (
            <ul>
              {other.map((f) => (
                <FlagRow key={f.id} flag={f} />
              ))}
            </ul>
          )}
        </section>
      </div>

      <div className="grid gap-5 lg:grid-cols-[1fr_1.2fr]">
        <Panel title="Assessment history" subtitle={`${history.length} assessment(s). A new one is created whenever records are uploaded and rescored.`}>
          {history.length > 1 ? <ScoreHistoryChart history={history} /> : <p className="text-xs text-ink-3">Only the initial assessment so far. Upload updated records to reassess.</p>}
        </Panel>
        <Panel title="Latest change" subtitle="Most recent assessment compared with the one before it.">
          {comparison ? <ComparisonView cmp={comparison} /> : <p className="text-xs text-ink-3">No reassessment yet.</p>}
        </Panel>
      </div>

      <p className="text-2xs leading-relaxed text-ink-3">{a.disclaimer}</p>
    </div>
  );
}
