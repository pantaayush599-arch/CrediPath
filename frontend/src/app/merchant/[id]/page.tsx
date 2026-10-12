"use client";

import { CheckCircle2, ChevronDown, Circle, CircleDot, FileUp, Info, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { BusinessSwitcher } from "@/components/BusinessSwitcher";
import { ScoreHistoryChart, WhatIfChart } from "@/components/charts";
import { ScoreDial } from "@/components/score";
import { ConfidenceChecks, ConfidenceChip, EmptyState, ErrorState, Hypothetical, Loading, NotFoundBusiness, PageHeader, Panel } from "@/components/ui";
import { api, ApiError, type Assessment, type AssessmentSummary, type Business, type ProgressStatus, type Recommendation, type WhatIf } from "@/lib/api";
import { dateLabel, signed } from "@/lib/format";
import { useAsync } from "@/lib/hooks";

interface Bundle {
  business: Business;
  assessment: Assessment | null;
  history: AssessmentSummary[];
}

async function load(id: string): Promise<Bundle> {
  const business = await api.business(id);
  try {
    const [assessment, history] = await Promise.all([api.assessment(id), api.assessments(id)]);
    return { business, assessment, history };
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return { business, assessment: null, history: [] };
    throw e;
  }
}

const STATUS: { v: ProgressStatus; label: string; icon: React.ReactNode }[] = [
  { v: "pending", label: "Not started", icon: <Circle size={13} /> },
  { v: "in_progress", label: "In progress", icon: <CircleDot size={13} /> },
  { v: "completed", label: "Done", icon: <CheckCircle2 size={13} /> },
];

function FixCard({ rec, onStatus, saving, recordsHref }: { rec: Recommendation; onStatus: (s: ProgressStatus) => void; saving: boolean; recordsHref: string }) {
  const [open, setOpen] = useState(rec.rank === 1);
  return (
    <li className="border-b border-line last:border-0">
      <div className="flex items-start gap-3 px-4 py-3">
        <span className="num mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand text-xs font-semibold text-brand-ink">{rec.rank}</span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <button className="flex items-center gap-1 text-left text-[14px] font-semibold text-ink hover:text-accent" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
              {rec.title}
              <ChevronDown size={14} className={`text-ink-3 transition-transform ${open ? "rotate-180" : ""}`} />
            </button>
            <Hypothetical>est. {signed(rec.expected_impact, 1)} pts</Hypothetical>
          </div>
          <p className="mt-0.5 text-xs text-ink-2">{rec.why}</p>
          {open && (
            <ol className="mt-2 list-decimal space-y-1 pl-4 text-xs text-ink-2">
              {rec.steps.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ol>
          )}
          <div className="mt-2.5 flex flex-wrap items-center gap-2">
            <div role="radiogroup" aria-label={`Progress on ${rec.title}`} className="inline-flex rounded-md border border-line bg-sunken p-0.5">
              {STATUS.map((s) => (
                <button
                  key={s.v}
                  role="radio"
                  aria-checked={rec.status === s.v}
                  disabled={saving}
                  onClick={() => onStatus(s.v)}
                  className={`flex items-center gap-1 rounded px-2 py-1 text-xs transition-colors ${
                    rec.status === s.v ? (s.v === "completed" ? "bg-good-soft font-medium text-good" : "bg-surface font-medium text-ink shadow-card") : "text-ink-3 hover:text-ink"
                  }`}
                >
                  {s.icon}
                  {s.label}
                </button>
              ))}
            </div>
            {rec.status === "completed" && (
              <Link href={recordsHref} className="text-xs text-accent hover:underline">
                Upload records to reassess →
              </Link>
            )}
          </div>
        </div>
      </div>
    </li>
  );
}

function Simulator({ id, assessment }: { id: string; assessment: Assessment }) {
  const plan = assessment.recommendations;
  // Start from the deck's scenario (top 3 fixes + the next action) so the effect is visible at once.
  const deckDemo = plan.slice(0, 4).map((p) => p.action_key);
  const [selected, setSelected] = useState<string[]>(deckDemo);
  const [result, setResult] = useState<WhatIf | null>(null);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let live = true;
    api
      .whatIf(id, selected)
      .then((r) => live && (setResult(r), setError(null)))
      .catch((e) => live && setError(e));
    return () => {
      live = false;
    };
  }, [id, selected, assessment.id]);

  const toggle = (k: string) => setSelected((cur) => (cur.includes(k) ? cur.filter((x) => x !== k) : [...cur, k]));

  if (!plan.length) return <p className="text-sm text-ink-2">Every scored indicator is at or above its benchmark, so there is nothing to simulate.</p>;
  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
      <div>
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <span className="eyebrow">Pick improvements</span>
          <div className="flex gap-1">
            <button className="btn-ghost px-2 py-1 text-xs" onClick={() => setSelected(deckDemo)}>
              Select top {Math.min(4, plan.length)}
            </button>
            <button className="btn-ghost px-2 py-1 text-xs" onClick={() => setSelected([])} disabled={!selected.length}>
              <RotateCcw size={12} /> Reset
            </button>
          </div>
        </div>
        <ul className="divide-y divide-line rounded-md border border-line">
          {plan.map((p) => (
            <li key={p.action_key}>
              <label className="flex cursor-pointer items-center gap-3 px-3 py-2.5 hover:bg-sunken/50">
                <input type="checkbox" className="h-4 w-4 accent-[rgb(var(--accent))]" checked={selected.includes(p.action_key)} onChange={() => toggle(p.action_key)} />
                <span className="min-w-0 flex-1">
                  <span className="block text-[13px] text-ink">{p.title}</span>
                  <span className="block text-2xs text-ink-3">
                    {p.indicator_key.replace(/_/g, " ")}: {p.current_sub_score} → {p.target_sub_score} (benchmark)
                  </span>
                </span>
                <span className="num text-xs text-accent">{signed(p.expected_impact, 1)}</span>
              </label>
            </li>
          ))}
        </ul>
        <div className="mt-3 flex items-baseline gap-3 rounded-md bg-sunken px-3 py-2.5">
          <div>
            <div className="eyebrow">Now</div>
            <div className="num text-xl text-ink">{assessment.display_score}</div>
          </div>
          <span className="text-ink-3">→</span>
          <div>
            <div className="eyebrow">Hypothetical</div>
            <div data-testid="hypothetical-score" className="num text-xl font-semibold text-accent">{result?.hypothetical_display ?? "…"}</div>
          </div>
          <div className="ml-auto text-right">
            <div className="eyebrow">Estimated change</div>
            <div className="num text-sm text-ink">{result ? signed(result.total_delta, 1) : "…"}</div>
          </div>
        </div>
        {error && <p className="mt-2 text-xs text-bad">{error.message}</p>}
      </div>
      <div>
        {result && <WhatIfChart baseline={result.baseline_score} steps={result.steps} result={result.hypothetical_score} />}
        <p className="mt-3 flex gap-2 text-xs leading-relaxed text-ink-3">
          <Info size={14} className="mt-0.5 shrink-0" />
          {result?.note ??
            "Hypothetical estimate. Selecting an action does not change your real assessment; it changes only when updated records are uploaded and rescored."}
        </p>
      </div>
    </div>
  );
}

export default function MerchantDashboard() {
  const { id } = useParams<{ id: string }>();
  const { data, error, loading, reload, setData } = useAsync<Bundle>(() => load(id), [id]);
  const [saving, setSaving] = useState<string | null>(null);
  const [saveErr, setSaveErr] = useState<string | null>(null);

  const a = data?.assessment;
  const top = useMemo(() => a?.recommendations.filter((r) => r.in_top_plan) ?? [], [a]);

  if (loading && !data) return <Loading label="Loading your dashboard…" />;
  if (error) return error instanceof ApiError && error.status === 404 ? <NotFoundBusiness /> : <ErrorState error={error} onRetry={reload} />;
  if (!data) return null;
  const b = data.business;

  const setStatus = async (rec: Recommendation, status: ProgressStatus) => {
    setSaving(rec.action_key);
    setSaveErr(null);
    try {
      await api.setProgress(id, rec.action_key, status);
      setData((cur) =>
        cur && cur.assessment
          ? { ...cur, assessment: { ...cur.assessment, recommendations: cur.assessment.recommendations.map((r) => (r.action_key === rec.action_key ? { ...r, status } : r)) } }
          : cur,
      );
    } catch (e) {
      setSaveErr((e as Error).message);
    } finally {
      setSaving(null);
    }
  };

  const header = (
    <PageHeader
      eyebrow="Business owner · guidance view"
      title={`Hello, ${b.owner_name.replace(" (fictional)", "").split(" ")[0]}`}
      subtitle={
        <span>
          {b.name} · <span className="chip bg-warn-soft text-warn">synthetic demo</span>
        </span>
      }
      actions={<BusinessSwitcher current={id} basePath="/merchant" label="Demo: view as" />}
    />
  );

  if (!a)
    return (
      <div>
        {header}
        <EmptyState title="Let's get your first score">
          Upload your bank/UPI statements, sales, invoices, supplier and loan records on the{" "}
          <Link className="text-accent underline" href={`/merchant/${id}/records`}>
            Records page
          </Link>
          .
        </EmptyState>
      </div>
    );

  const done = top.filter((r) => r.status === "completed").length;
  const started = top.filter((r) => r.status === "in_progress").length;

  return (
    <div className="space-y-5">
      {header}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.25fr)]">
        <Panel title="My score">
          <div className="flex flex-col items-center gap-5 sm:flex-row sm:items-start">
            <ScoreDial value={a.display_score} />
            <div className="flex-1 space-y-3">
              <p className="text-[14px] leading-relaxed text-ink">{a.summary.merchant_summary}</p>
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <div className="eyebrow mb-1 text-good">Doing well</div>
                  <ul className="space-y-0.5 text-[13px] text-ink">{a.summary.doing_well.length ? a.summary.doing_well.map((d) => <li key={d}>{d[0].toUpperCase() + d.slice(1)}</li>) : <li className="text-ink-3">—</li>}</ul>
                </div>
                <div>
                  <div className="eyebrow mb-1 text-bad">Needs work</div>
                  <ul className="space-y-0.5 text-[13px] text-ink">{a.summary.needs_work.length ? a.summary.needs_work.map((d) => <li key={d}>{d[0].toUpperCase() + d.slice(1)}</li>) : <li className="text-ink-3">—</li>}</ul>
                </div>
              </div>
              <p className="text-2xs text-ink-3">
                Based on records up to {dateLabel(a.as_of_date)}. A score is not a loan approval — the bank&apos;s loan officer decides.
              </p>
              <details className="rounded-md border border-line p-2.5">
                <summary className="flex cursor-pointer items-center gap-2 text-xs text-ink-2">
                  How sure is this score? <ConfidenceChip level={a.confidence} />
                </summary>
                <div className="mt-2">
                  <ConfidenceChecks checks={a.summary.confidence_checks ?? []} compact />
                  <p className="mt-2 text-2xs text-ink-3">
                    {a.confidence === "high"
                      ? "You have shared enough records for a reliable score."
                      : "Sharing more months of records, with all details filled in, will make your score more reliable."}
                  </p>
                </div>
              </details>
            </div>
          </div>
        </Panel>

        <section className="panel">
          <div className="panel-head">
            <div>
              <h2 className="text-[13px] font-semibold">Your top {top.length} fixes</h2>
              <p className="mt-0.5 text-xs text-ink-3">Ranked by estimated score impact. Track your progress here.</p>
            </div>
            <span className="num text-xs text-ink-2">
              {done}/{top.length} done{started ? ` · ${started} in progress` : ""}
            </span>
          </div>
          {top.length === 0 ? (
            <p className="p-4 text-sm text-ink-2">Every scored area is at or above its benchmark. Keep sharing complete records to stay there.</p>
          ) : (
            <ul>
              {top.map((r) => (
                <FixCard key={r.action_key} rec={r} recordsHref={`/merchant/${id}/records`} saving={saving === r.action_key} onStatus={(s) => setStatus(r, s)} />
              ))}
            </ul>
          )}
          {saveErr && <p className="px-4 pb-3 text-xs text-bad">{saveErr}</p>}
          <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line px-4 py-3">
            <span className="text-xs text-ink-3">Marking a fix as done does not change your score. New records do.</span>
            <Link href={`/merchant/${id}/records`} className="btn-primary">
              <FileUp size={14} /> Upload new records &amp; reassess
            </Link>
          </div>
        </section>
      </div>

      <Panel title="What-if simulator" subtitle="See how your score could change if you made these improvements." actions={<Hypothetical>Hypothetical</Hypothetical>}>
        <Simulator key={a.id} id={id} assessment={a} />
      </Panel>

      <div className="grid gap-5 lg:grid-cols-[1.2fr_1fr]">
        <Panel title="What each area means for you" bodyClass="p-0">
          <ul>
            {a.indicators.map((i) => (
              <li key={i.key} className="grid grid-cols-[minmax(0,1fr)_auto] gap-3 border-b border-line/70 px-4 py-2.5 last:border-0">
                <div className="min-w-0">
                  <div className="text-[13px] font-medium text-ink">{i.name}</div>
                  <div className="text-xs leading-relaxed text-ink-2">{i.explanation_merchant}</div>
                </div>
                <div className="num pt-0.5 text-right text-sm">
                  {i.sub_score === null ? <span className="text-xs text-ink-3">not yet</span> : <span className={i.band === "concern" ? "text-bad" : i.band === "strength" ? "text-good" : "text-ink"}>{i.sub_score}</span>}
                </div>
              </li>
            ))}
          </ul>
        </Panel>
        <Panel title="My progress over time" subtitle="Each point is a real assessment from your uploaded records.">
          {data.history.length > 1 ? (
            <ScoreHistoryChart history={data.history} />
          ) : (
            <p className="text-xs text-ink-3">Your first assessment. After you act on the fixes, upload new records to see your progress here.</p>
          )}
          <p className="mt-3 text-2xs text-ink-3">Explanations are written by fixed templates from your scoring results. They never change the score.</p>
        </Panel>
      </div>
    </div>
  );
}
