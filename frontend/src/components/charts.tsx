"use client";

import { Table2, BarChart3 } from "lucide-react";
import { useState } from "react";
import {
  Bar,
  CartesianGrid,
  Cell,
  LabelList,
  ComposedChart,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { AssessmentSummary, MonthRow } from "@/lib/api";
import { dateLabel, inr, monthLabel, signed } from "@/lib/format";

const AXIS = { fontSize: 11, fill: "var(--chart-axis)" };
const GRID = { stroke: "var(--chart-grid)", strokeDasharray: "0", vertical: false } as const;

/* eslint-disable @typescript-eslint/no-explicit-any */
function TipBox({ title, rows }: { title: string; rows: { label: string; value: string; color?: string }[] }) {
  return (
    <div className="min-w-[160px] rounded-md border border-line-strong bg-surface px-3 py-2 text-xs shadow-card">
      <div className="mb-1 font-semibold text-ink">{title}</div>
      {rows.map((r) => (
        <div key={r.label} className="flex items-center justify-between gap-4 py-0.5">
          <span className="flex items-center gap-1.5 text-ink-2">
            {r.color && <span className="inline-block h-2 w-2 rounded-sm" style={{ background: r.color }} />}
            {r.label}
          </span>
          <span className="num text-ink">{r.value}</span>
        </div>
      ))}
    </div>
  );
}

function LegendItem({ color, label, line = false }: { color: string; label: string; line?: boolean }) {
  return (
    <span className="flex items-center gap-1.5 text-xs text-ink-2">
      {line ? <span className="inline-block h-0.5 w-4 rounded" style={{ background: color }} /> : <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: color }} />}
      {label}
    </span>
  );
}

/** Wraps a chart with a legend row and a table-view toggle (accessibility). */
export function ChartFrame({ legend, table, children, height = 240 }: { legend?: React.ReactNode; table: React.ReactNode; children: React.ReactNode; height?: number }) {
  const [asTable, setAsTable] = useState(false);
  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-3">{legend}</div>
        <button className="btn-ghost px-2 py-1 text-xs" onClick={() => setAsTable((v) => !v)} aria-pressed={asTable}>
          {asTable ? <BarChart3 size={13} /> : <Table2 size={13} />} {asTable ? "Chart" : "Table"}
        </button>
      </div>
      {asTable ? <div className="max-h-[300px] overflow-auto">{table}</div> : <div style={{ height }}>{children}</div>}
    </div>
  );
}

export function CashFlowChart({ monthly }: { monthly: MonthRow[] }) {
  const data = monthly.map((m) => ({ ...m, label: monthLabel(m.month, true) }));
  return (
    <ChartFrame
      legend={
        <>
          <LegendItem color="var(--series-in)" label="Business income" />
          <LegendItem color="var(--series-out)" label="Outflows" />
          <LegendItem color="var(--series-3)" label="Net cash flow" line />
        </>
      }
      table={
        <table className="table-base">
          <thead>
            <tr>
              <th>Month</th>
              <th className="text-right">Income</th>
              <th className="text-right">Outflows</th>
              <th className="text-right">Net</th>
            </tr>
          </thead>
          <tbody>
            {monthly.map((m) => (
              <tr key={m.month}>
                <td>{monthLabel(m.month, true)}</td>
                <td className="num text-right">{m.has_bank ? inr(m.inflow) : "missing"}</td>
                <td className="num text-right">{m.has_bank ? inr(m.outflow) : "missing"}</td>
                <td className="num text-right">{m.has_bank ? inr(m.net) : "missing"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    >
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 6, right: 6, left: 0, bottom: 0 }} barGap={2} barCategoryGap="22%">
          <CartesianGrid {...GRID} />
          <XAxis dataKey="label" tick={AXIS} tickLine={false} axisLine={{ stroke: "var(--chart-grid)" }} interval="preserveStartEnd" />
          <YAxis tick={AXIS} tickLine={false} axisLine={false} width={52} tickFormatter={(v) => inr(v, { compact: true })} />
          <ReferenceLine y={0} stroke="var(--chart-axis)" strokeOpacity={0.5} />
          <Tooltip
            cursor={{ fill: "var(--chart-grid)", fillOpacity: 0.5 }}
            content={({ active, payload }: any) => {
              if (!active || !payload?.length) return null;
              const p = payload[0].payload as MonthRow & { label: string };
              if (!p.has_bank) return <TipBox title={p.label} rows={[{ label: "Bank records", value: "missing" }]} />;
              return (
                <TipBox
                  title={p.label}
                  rows={[
                    { label: "Income", value: inr(p.inflow), color: "var(--series-in)" },
                    { label: "Outflows", value: inr(p.outflow), color: "var(--series-out)" },
                    { label: "Net", value: inr(p.net), color: "var(--series-3)" },
                  ]}
                />
              );
            }}
          />
          <Bar dataKey="inflow" fill="var(--series-in)" radius={[3, 3, 0, 0]} maxBarSize={18} isAnimationActive={false} />
          <Bar dataKey="outflow" fill="var(--series-out)" radius={[3, 3, 0, 0]} maxBarSize={18} isAnimationActive={false} />
          <Line dataKey="net" stroke="var(--series-3)" strokeWidth={2} dot={{ r: 3, strokeWidth: 0, fill: "var(--series-3)" }} connectNulls={false} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

export function BalanceChart({ monthly, benchmarkDays, avgOutflow }: { monthly: MonthRow[]; benchmarkDays: number; avgOutflow: number | null }) {
  const data = monthly.map((m) => ({ ...m, label: monthLabel(m.month, true) }));
  const target = avgOutflow ? (benchmarkDays * avgOutflow) / 30 : null;
  return (
    <ChartFrame
      height={200}
      legend={
        <>
          <LegendItem color="var(--series-3)" label="Month-end balance" line />
          {target && <span className="text-xs text-ink-3">Dashed: {benchmarkDays}-day buffer ({inr(target, { compact: true })})</span>}
        </>
      }
      table={
        <table className="table-base">
          <thead>
            <tr>
              <th>Month</th>
              <th className="text-right">Month-end balance</th>
            </tr>
          </thead>
          <tbody>
            {monthly.map((m) => (
              <tr key={m.month}>
                <td>{monthLabel(m.month, true)}</td>
                <td className="num text-right">{m.month_end_balance === null ? "not provided" : inr(m.month_end_balance)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 6, right: 6, left: 0, bottom: 0 }}>
          <CartesianGrid {...GRID} />
          <XAxis dataKey="label" tick={AXIS} tickLine={false} axisLine={{ stroke: "var(--chart-grid)" }} interval="preserveStartEnd" />
          <YAxis tick={AXIS} tickLine={false} axisLine={false} width={52} tickFormatter={(v) => inr(v, { compact: true })} />
          {target && <ReferenceLine y={target} stroke="var(--chart-axis)" strokeDasharray="4 4" />}
          <Tooltip
            cursor={{ stroke: "var(--chart-axis)", strokeDasharray: "3 3" }}
            content={({ active, payload }: any) =>
              active && payload?.length ? (
                <TipBox title={payload[0].payload.label} rows={[{ label: "Balance", value: payload[0].payload.month_end_balance === null ? "not provided" : inr(payload[0].payload.month_end_balance), color: "var(--series-3)" }]} />
              ) : null
            }
          />
          <Line dataKey="month_end_balance" stroke="var(--series-3)" strokeWidth={2} dot={{ r: 3, strokeWidth: 0, fill: "var(--series-3)" }} connectNulls={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

export function ScoreHistoryChart({ history }: { history: AssessmentSummary[] }) {
  const data = [...history].reverse().map((h, i) => ({ ...h, label: `#${i + 1} · ${dateLabel(h.as_of_date).replace(/ \d{4}$/, "")}` }));
  return (
    <ChartFrame
      height={180}
      legend={<LegendItem color="var(--series-in)" label="Overall score (0–100)" line />}
      table={
        <table className="table-base">
          <thead>
            <tr>
              <th>Assessment</th>
              <th>Data as of</th>
              <th className="text-right">Score</th>
            </tr>
          </thead>
          <tbody>
            {data.map((h) => (
              <tr key={h.id}>
                <td>{h.trigger}</td>
                <td>{dateLabel(h.as_of_date)}</td>
                <td className="num text-right">{h.overall_score?.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 16, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid {...GRID} />
          <XAxis dataKey="label" tick={AXIS} tickLine={false} axisLine={{ stroke: "var(--chart-grid)" }} />
          <YAxis domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} tick={AXIS} tickLine={false} axisLine={false} width={32} />
          <Tooltip
            content={({ active, payload }: any) =>
              active && payload?.length ? (
                <TipBox
                  title={`Data as of ${dateLabel(payload[0].payload.as_of_date)}`}
                  rows={[
                    { label: "Score", value: payload[0].payload.overall_score?.toFixed(2), color: "var(--series-in)" },
                    { label: "Trigger", value: payload[0].payload.trigger },
                  ]}
                />
              ) : null
            }
          />
          <Line dataKey="overall_score" stroke="var(--series-in)" strokeWidth={2} dot={{ r: 4, strokeWidth: 2, stroke: "var(--chart-surface)", fill: "var(--series-in)" }} isAnimationActive={false} label={{ position: "top", fontSize: 11, fill: "var(--chart-axis)", formatter: (v: any) => Number(v).toFixed(0) }} />
        </LineChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

/** Waterfall: baseline → each selected action's estimated delta → hypothetical result. */
export function WhatIfChart({ baseline, steps, result }: { baseline: number; steps: { short_label: string; delta: number }[]; result: number }) {
  let run = baseline;
  const data = [
    { label: "Now", base: 0, value: baseline, kind: "actual", text: baseline.toFixed(2) },
    ...steps.map((s) => {
      const row = { label: s.short_label, base: run, value: s.delta, kind: "step", text: signed(s.delta, 1) };
      run += s.delta;
      return row;
    }),
    { label: "If done", base: 0, value: result, kind: "result", text: result.toFixed(2) },
  ];
  const fill = (k: string) => (k === "actual" ? "var(--chart-axis)" : k === "step" ? "var(--series-in)" : "var(--series-3)");
  return (
    <ChartFrame
      height={210}
      legend={
        <>
          <LegendItem color="var(--chart-axis)" label="Current score (calculated)" />
          <LegendItem color="var(--series-in)" label="Estimated gain" />
          <LegendItem color="var(--series-3)" label="Hypothetical result" />
        </>
      }
      table={
        <table className="table-base">
          <tbody>
            {data.map((d) => (
              <tr key={d.label}>
                <td>{d.label}</td>
                <td className="num text-right">{d.kind === "step" ? signed(d.value, 1) : d.value.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    >
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 20, right: 6, left: 0, bottom: 0 }} barCategoryGap="28%">
          <CartesianGrid {...GRID} />
          <XAxis dataKey="label" tick={AXIS} tickLine={false} axisLine={{ stroke: "var(--chart-grid)" }} />
          <YAxis domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} tick={AXIS} tickLine={false} axisLine={false} width={32} />
          <Tooltip
            cursor={{ fill: "var(--chart-grid)", fillOpacity: 0.5 }}
            content={({ active, payload }: any) => {
              if (!active || !payload?.length) return null;
              const p = payload[0].payload;
              return <TipBox title={p.label} rows={[{ label: p.kind === "step" ? "Estimated gain" : p.kind === "actual" ? "Calculated score" : "Hypothetical score", value: p.kind === "step" ? signed(p.value, 1) : p.value.toFixed(2) }]} />;
            }}
          />
          <Bar dataKey="base" stackId="w" fill="transparent" isAnimationActive={false} />
          <Bar
            dataKey="value"
            stackId="w"
            radius={[3, 3, 0, 0]}
            maxBarSize={44}
            isAnimationActive={false}
          >
            <LabelList dataKey="text" position="top" style={{ fontSize: 11, fill: "var(--chart-axis)" }} />
            {data.map((d, i) => (
              <Cell key={i} fill={fill(d.kind)} fillOpacity={d.kind === "result" ? 1 : 0.95} />
            ))}
          </Bar>
        </ComposedChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
