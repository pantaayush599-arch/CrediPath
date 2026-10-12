"use client";

import { ArrowDownRight, ArrowRight, ArrowUpRight, ChevronDown } from "lucide-react";
import { Fragment, useState } from "react";
import type { Comparison, Indicator } from "@/lib/api";
import { metricText, signed } from "@/lib/format";
import { BandChip, ScoreBar } from "./ui";

export function ScoreDial({ value, exact, size = 132, label = "out of 100" }: { value: number | null; exact?: number | null; size?: number; label?: string }) {
  const r = size / 2 - 9;
  const c = 2 * Math.PI * r;
  const frac = value === null ? 0 : Math.max(0, Math.min(100, value)) / 100;
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }} role="img" aria-label={value === null ? "No score" : `Score ${value} out of 100`}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgb(var(--sunken))" strokeWidth={9} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="rgb(var(--accent))"
          strokeWidth={9}
          strokeLinecap="round"
          strokeDasharray={`${c * frac} ${c}`}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <div className="num text-[34px] font-semibold leading-none text-ink">{value ?? "—"}</div>
        <div className="mt-1 text-2xs text-ink-3">{label}</div>
        {exact !== undefined && exact !== null && <div data-testid="score-exact" className="num mt-0.5 text-2xs text-ink-3">{exact.toFixed(2)} exact</div>}
      </div>
    </div>
  );
}

/** Banker view: every indicator with weight, sub-score, contribution and the sum. */
export function IndicatorBreakdown({ indicators, overall }: { indicators: Indicator[]; overall: number | null }) {
  const [open, setOpen] = useState<string | null>(null);
  const renorm = indicators.some((i) => i.sub_score === null);
  return (
    <div className="overflow-x-auto">
      <table className="table-base min-w-[640px]">
        <thead>
          <tr>
            <th>Indicator</th>
            <th className="text-right">Weight</th>
            <th className="w-[30%]">Sub-score (0–100) · benchmark tick</th>
            <th className="text-right">Sub-score</th>
            <th className="text-right">Points</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {indicators.map((i) => (
            <Fragment key={i.key}>
              <tr className="cursor-pointer hover:bg-sunken/60" onClick={() => setOpen(open === i.key ? null : i.key)}>
                <td>
                  <div className="font-medium text-ink">{i.name}</div>
                  <div className="mt-0.5"><BandChip band={i.band} /></div>
                </td>
                <td className="num text-right text-ink-2">
                  {(i.weight * 100).toFixed(0)}%
                  {renorm && i.sub_score !== null && <div className="text-2xs text-ink-3">eff. {(i.effective_weight * 100).toFixed(1)}%</div>}
                </td>
                <td className="pt-3">
                  <ScoreBar value={i.sub_score} band={i.band} benchmark={i.benchmark} />
                </td>
                <td className="num text-right">{i.sub_score === null ? <span className="text-ink-3">n/a</span> : i.sub_score.toFixed(0)}</td>
                <td className="num text-right font-medium">{i.contribution === null ? <span className="text-ink-3">—</span> : i.contribution.toFixed(2)}</td>
                <td className="w-6 text-ink-3">
                  <ChevronDown size={14} className={`transition-transform ${open === i.key ? "rotate-180" : ""}`} />
                </td>
              </tr>
              {open === i.key && (
                <tr className="bg-sunken/50">
                  <td colSpan={6} className="text-xs leading-relaxed text-ink-2">
                    <div className="grid gap-2 py-1 sm:grid-cols-[1fr_auto]">
                      <div>
                        <div className="text-ink">{i.explanation_banker}</div>
                        <div className="mt-1 text-ink-3">Metric: {i.metric_label}</div>
                      </div>
                      <div className="num whitespace-nowrap text-right">
                        <div>
                          Raw metric: <b className="text-ink">{metricText(i.key, i.metric)}</b>
                        </div>
                        <div>Benchmark: {i.benchmark}</div>
                      </div>
                    </div>
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <td className="pt-3 font-semibold text-ink">Overall = Σ (sub-score × weight)</td>
            <td className="num pt-3 text-right text-ink-2">100%</td>
            <td />
            <td />
            <td className="num pt-3 text-right text-base font-semibold text-ink">{overall?.toFixed(2) ?? "—"}</td>
            <td />
          </tr>
        </tfoot>
      </table>
      {renorm && (
        <p className="mt-2 text-xs text-ink-3">
          Indicators without enough data are not scored as zero. They are left out and the remaining weights are re-normalised (shown as “eff.”); the gap lowers data completeness instead.
        </p>
      )}
    </div>
  );
}

export function Delta({ value, digits = 1 }: { value: number | null; digits?: number }) {
  if (value === null) return <span className="text-ink-3">—</span>;
  const Icon = value > 0 ? ArrowUpRight : value < 0 ? ArrowDownRight : ArrowRight;
  const cls = value > 0 ? "text-good" : value < 0 ? "text-bad" : "text-ink-3";
  return (
    <span className={`num inline-flex items-center gap-0.5 ${cls}`}>
      <Icon size={13} />
      {signed(value, digits)}
    </span>
  );
}

export function ComparisonView({ cmp }: { cmp: Comparison }) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-4">
        <div>
          <div className="eyebrow">Before</div>
          <div className="num text-2xl font-semibold text-ink-2">{cmp.previous.overall_score?.toFixed(2)}</div>
          <div className="text-2xs text-ink-3">data to {cmp.previous.as_of_date}</div>
        </div>
        <ArrowRight className="text-ink-3" size={18} />
        <div>
          <div className="eyebrow">After</div>
          <div className="num text-2xl font-semibold text-ink">{cmp.current.overall_score?.toFixed(2)}</div>
          <div className="text-2xs text-ink-3">data to {cmp.current.as_of_date}</div>
        </div>
        <div className="ml-2 rounded-md bg-sunken px-3 py-2">
          <div className="eyebrow">Change</div>
          <div className="text-lg">
            <Delta value={cmp.score_delta} digits={2} />
          </div>
        </div>
        <div className="rounded-md bg-sunken px-3 py-2">
          <div className="eyebrow">Open flags</div>
          <div className="num text-lg text-ink">
            {cmp.flags_before} → {cmp.flags_after}
          </div>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="table-base min-w-[420px]">
          <thead>
            <tr>
              <th>Indicator</th>
              <th className="text-right">Before</th>
              <th className="text-right">After</th>
              <th className="text-right">Change</th>
            </tr>
          </thead>
          <tbody>
            {cmp.indicators.map((r) => (
              <tr key={r.key}>
                <td>{r.name}</td>
                <td className="num text-right text-ink-2">{r.before ?? "n/a"}</td>
                <td className="num text-right">{r.after ?? "n/a"}</td>
                <td className="text-right">
                  <Delta value={r.delta} digits={0} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {(cmp.flags_resolved.length > 0 || cmp.flags_new.length > 0) && (
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <div className="eyebrow mb-1">Flags cleared or changed</div>
            <ul className="space-y-1 text-xs text-ink-2">
              {cmp.flags_resolved.length ? cmp.flags_resolved.map((t) => <li key={t} className="line-through decoration-ink-3/60">{t}</li>) : <li>None</li>}
            </ul>
          </div>
          <div>
            <div className="eyebrow mb-1">New or updated flags</div>
            <ul className="space-y-1 text-xs text-ink-2">{cmp.flags_new.length ? cmp.flags_new.map((t) => <li key={t}>{t}</li>) : <li>None</li>}</ul>
          </div>
        </div>
      )}
    </div>
  );
}
