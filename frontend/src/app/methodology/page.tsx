"use client";

import { api, type RecordSchema, type ScoringConfig } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { CONFIDENCE_RULE_TEXT, ErrorState, HumanDecides, Loading, PageHeader, Panel } from "@/components/ui";

const STATUS = [
  { area: "Rules-based scoring engine (8 indicators, weighted)", state: "Functional", note: "Python / pandas, unit-tested; same function for both dashboards and the what-if." },
  { area: "CSV upload, validation, storage, reassessment", state: "Functional", note: "Row-level errors and warnings; invoices and EMIs upserted by reference." },
  { area: "Risk & data-quality flags", state: "Functional", note: "Missing data, circular flows, one-off spikes, record mismatches, overdue receivables." },
  { area: "Lender & owner dashboards, progress tracking, history", state: "Functional", note: "Persisted in SQLite locally, or PostgreSQL / Supabase via DATABASE_URL." },
  { area: "What-if simulator", state: "Hypothetical", note: "Assumes each selected indicator reaches its benchmark; never saved as an assessment." },
  { area: "Plain-language explanations", state: "Template-based", note: "Generated from scoring output by fixed templates. No LLM is called in this build." },
  { area: "Business data", state: "Synthetic", note: "All businesses and transactions are fictional." },
  { area: "Account Aggregator / GST / ULI feeds", state: "Future scope", note: "Not built. Shown only as a labelled placeholder." },
  { area: "ML scoring, lender workflows, approvals", state: "Out of scope", note: "Needs validated repayment outcomes first. A human decides." },
];

export default function Methodology() {
  const cfg = useAsync<ScoringConfig>(() => api.config(), []);
  const schema = useAsync<RecordSchema>(() => api.schema(), []);
  if (cfg.loading) return <Loading label="Loading scoring rules…" />;
  if (cfg.error) return <ErrorState error={cfg.error} onRetry={cfg.reload} />;
  const c = cfg.data!;
  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Reference"
        title="How the score works"
        subtitle={`${c.version} · ${c.window_months}-month window · ${c.formula}`}
      />
      <Panel title="Indicators, weights and prototype thresholds" subtitle="Thresholds are prototype values, not yet back-tested on repayment outcomes." bodyClass="overflow-x-auto p-0">
        <table className="table-base min-w-[760px]">
          <thead>
            <tr>
              <th>Indicator</th>
              <th className="text-right">Weight</th>
              <th>Metric</th>
              <th>Scaling rule (0–100)</th>
              <th className="text-right">Benchmark</th>
            </tr>
          </thead>
          <tbody>
            {c.indicators.map((i) => (
              <tr key={i.key}>
                <td>
                  <div className="font-medium">{i.name}</div>
                  <div className="text-xs text-ink-3">{i.description}</div>
                </td>
                <td className="num text-right">{(i.weight * 100).toFixed(0)}%</td>
                <td className="text-xs text-ink-2">{i.metric_label}</td>
                <td className="text-xs text-ink-2">{i.rule}</td>
                <td className="num text-right">{i.benchmark}</td>
              </tr>
            ))}
            <tr>
              <td className="font-semibold">Total</td>
              <td className="num text-right font-semibold">{(c.indicators.reduce((s, i) => s + i.weight, 0) * 100).toFixed(0)}%</td>
              <td colSpan={3} className="text-xs text-ink-3">
                Bands: strength ≥ {c.bands.strength_min}, concern &lt; {c.bands.concern_below}. Plan actions target the benchmark.
              </td>
            </tr>
          </tbody>
        </table>
      </Panel>

      <Panel title="Confidence scale (high / medium / low)" subtitle="How much evidence sits behind a score, separate from whether the score is good." bodyClass="overflow-x-auto p-0">
        <table className="table-base min-w-[560px]">
          <thead>
            <tr>
              <th>Check</th>
              <th>Pass</th>
              <th>Warning</th>
              <th>Fail</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className="font-medium">Bank / UPI history in the 12-month window</td>
              <td className="num">{c.confidence_rules.bank_months.pass}+ months</td>
              <td className="num">{c.confidence_rules.bank_months.warn}–{c.confidence_rules.bank_months.pass - 1} months</td>
              <td className="num">&lt; {c.confidence_rules.bank_months.warn} months</td>
            </tr>
            <tr>
              <td className="font-medium">Record completeness (data-completeness sub-score)</td>
              <td className="num">{c.confidence_rules.completeness.pass}+</td>
              <td className="num">{c.confidence_rules.completeness.warn}–{c.confidence_rules.completeness.pass - 1}</td>
              <td className="num">&lt; {c.confidence_rules.completeness.warn}</td>
            </tr>
            <tr>
              <td className="font-medium">Applicable indicators that could not be scored</td>
              <td className="num">none</td>
              <td className="num">1–{c.confidence_rules.missing_indicators.warn}</td>
              <td className="num">more than {c.confidence_rules.missing_indicators.warn}</td>
            </tr>
          </tbody>
        </table>
        <p className="border-t border-line px-3 py-2 text-xs text-ink-2">
          {CONFIDENCE_RULE_TEXT} An indicator that does not apply (invoice collection for a business with no credit sales) is excluded from the count.
        </p>
      </Panel>

      <div className="grid gap-5 lg:grid-cols-2">
        <Panel title="Data-quality rules">
          <dl className="space-y-3 text-xs">
            <div>
              <dt className="font-semibold text-ink">Missing data</dt>
              <dd className="text-ink-2">Flagged, never scored as zero. Missing months are gaps; an indicator without enough data is left out and the other weights re-normalised. The gap lowers data completeness.</dd>
            </div>
            <div>
              <dt className="font-semibold text-ink">Abnormal transactions</dt>
              <dd className="text-ink-2">
                Circular flows (money sent to and received back from the same party within {c.anomaly_rules.circular_window_days} days, ±{c.anomaly_rules.circular_amount_tolerance * 100}%) and one-off credits ≥{" "}
                {c.anomaly_rules.spike_share_of_month * 100}% of a month&apos;s income and ≥ {c.anomaly_rules.spike_multiple_of_median}× the typical credit raise a flag for review.
              </dd>
            </div>
            <div>
              <dt className="font-semibold text-ink">Inconsistent records</dt>
              <dd className="text-ink-2">
                Paid invoices and supplier payments are matched to bank entries (±{c.anomaly_rules.match_window_days} days, same amount); sales registers are compared with bank income (±
                {c.anomaly_rules.sales_vs_bank_tolerance * 100}%).
              </dd>
            </div>
          </dl>
        </Panel>
        <Panel title="CSV format">
          {schema.data && (
            <div className="space-y-2 text-xs">
              <div className="num rounded bg-sunken p-2 text-ink">{schema.data.columns.join(",")}</div>
              <ul className="space-y-1 text-ink-2">
                {Object.entries(schema.data.help).map(([k, v]) => (
                  <li key={k}>
                    <span className="num text-ink">{k}</span> — {v}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Panel>
      </div>

      <Panel title="What is functional, simulated, or out of scope" bodyClass="overflow-x-auto p-0">
        <table className="table-base min-w-[600px]">
          <tbody>
            {STATUS.map((s) => (
              <tr key={s.area}>
                <td className="font-medium">{s.area}</td>
                <td>
                  <span className={`chip ${s.state === "Functional" ? "bg-good-soft text-good" : s.state === "Future scope" || s.state === "Out of scope" ? "bg-sunken text-ink-3" : "bg-warn-soft text-warn"}`}>{s.state}</span>
                </td>
                <td className="text-xs text-ink-2">{s.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
      <HumanDecides />
    </div>
  );
}
