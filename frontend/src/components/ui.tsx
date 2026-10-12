"use client";

import { AlertOctagon, AlertTriangle, CheckCircle2, Info, Loader2, RefreshCw, ShieldCheck, XCircle } from "lucide-react";
import Link from "next/link";
import { useEffect } from "react";
import { DEFAULT_BUSINESS, rememberBusiness } from "@/lib/hooks";
import type { Band, ConfidenceCheck, Flag } from "@/lib/api";

export function PageHeader({ eyebrow, title, subtitle, actions }: { eyebrow?: string; title: React.ReactNode; subtitle?: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        {eyebrow && <div className="eyebrow mb-1">{eyebrow}</div>}
        <h1 className="font-serif text-2xl font-semibold tracking-tight text-ink">{title}</h1>
        {subtitle && <div className="mt-1 text-sm text-ink-2">{subtitle}</div>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Panel({ title, subtitle, actions, children, className = "", bodyClass = "p-4" }: { title?: React.ReactNode; subtitle?: React.ReactNode; actions?: React.ReactNode; children: React.ReactNode; className?: string; bodyClass?: string }) {
  return (
    <section className={`panel ${className}`}>
      {(title || actions) && (
        <div className="panel-head">
          <div className="min-w-0">
            {title && <h2 className="text-[13px] font-semibold text-ink">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-xs text-ink-3">{subtitle}</p>}
          </div>
          {actions}
        </div>
      )}
      <div className={bodyClass}>{children}</div>
    </section>
  );
}

export function Loading({ label = "Loading assessment…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-16 text-sm text-ink-3" role="status">
      <Loader2 size={16} className="animate-spin" /> {label}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: Error; onRetry?: () => void }) {
  return (
    <div className="panel flex flex-col items-start gap-3 border-bad/30 bg-bad-soft/40 p-5" role="alert">
      <div className="flex items-center gap-2 font-medium text-bad">
        <AlertOctagon size={16} /> Something went wrong
      </div>
      <p className="text-sm text-ink-2">{error.message}</p>
      {onRetry && (
        <button className="btn-secondary" onClick={onRetry}>
          <RefreshCw size={14} /> Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="panel flex flex-col items-start gap-2 p-6">
      <div className="font-medium text-ink">{title}</div>
      {children && <div className="text-sm text-ink-2">{children}</div>}
    </div>
  );
}

const BAND_STYLE: Record<Band, { label: string; cls: string }> = {
  strength: { label: "Strength", cls: "bg-good-soft text-good" },
  watch: { label: "Watch", cls: "bg-sunken text-ink-2" },
  concern: { label: "Concern", cls: "bg-bad-soft text-bad" },
  insufficient_data: { label: "Not scored", cls: "border border-dashed border-line-strong text-ink-3" },
};

export function BandChip({ band }: { band: Band }) {
  const s = BAND_STYLE[band];
  return <span className={`chip ${s.cls}`}>{s.label}</span>;
}

export function bandColor(band: Band): string {
  return band === "strength" ? "rgb(var(--good))" : band === "concern" ? "rgb(var(--bad))" : band === "watch" ? "rgb(var(--ink-3))" : "transparent";
}

export function ScoreBar({ value, band, benchmark }: { value: number | null; band: Band; benchmark?: number }) {
  return (
    <div className="relative h-2 w-full rounded-sm bg-sunken" role="img" aria-label={value === null ? "Not scored" : `${value} out of 100`}>
      {value !== null && <div className="h-2 rounded-sm" style={{ width: `${value}%`, background: bandColor(band) }} />}
      {benchmark !== undefined && (
        <div className="absolute -top-0.5 h-3 w-px bg-ink-2" style={{ left: `${benchmark}%` }} title={`Benchmark ${benchmark}`} />
      )}
    </div>
  );
}

export function ConfidenceChip({ level }: { level: string | null }) {
  if (!level) return null;
  const cls = level === "high" ? "bg-good-soft text-good" : level === "medium" ? "bg-sunken text-ink-2" : "bg-bad-soft text-bad";
  return <span className={`chip ${cls}`}>{level} confidence</span>;
}

export const CONFIDENCE_RULE_TEXT = "High: all three checks pass. Medium: at least one warning. Low: any check fails.";

const CHECK_STYLE = {
  pass: { icon: <CheckCircle2 size={14} />, cls: "text-good", label: "Pass" },
  warn: { icon: <AlertTriangle size={14} />, cls: "text-warn", label: "Warning" },
  fail: { icon: <XCircle size={14} />, cls: "text-bad", label: "Fail" },
};

/** The three checks that decide high / medium / low confidence. */
export function ConfidenceChecks({ checks, compact = false }: { checks: ConfidenceCheck[]; compact?: boolean }) {
  if (!checks?.length) return null;
  return (
    <ul className={compact ? "space-y-1" : "space-y-2"}>
      {checks.map((c) => {
        const st = CHECK_STYLE[c.status];
        return (
          <li key={c.key} className="flex items-start gap-2 text-xs">
            <span className={`mt-px shrink-0 ${st.cls}`} aria-label={st.label} title={st.label}>
              {st.icon}
            </span>
            <span className="min-w-0">
              <span className="font-medium text-ink">{c.label}:</span> <span className="text-ink-2">{c.value}</span>
              {c.detail && <span className="block text-ink-3">{c.detail}</span>}
              {!compact && <span className="block text-2xs text-ink-3">{c.rule}</span>}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

/** Chip plus an expandable "why" with the checks behind it. */
export function ConfidenceWithReasons({ level, checks, reasons }: { level: string | null; checks: ConfidenceCheck[]; reasons?: string[] }) {
  if (!level) return null;
  const issues = checks.filter((c) => c.status !== "pass");
  return (
    <details className="group">
      <summary className="cursor-pointer list-none [&::-webkit-details-marker]:hidden">
        <span className="flex items-center gap-1.5">
          <ConfidenceChip level={level} />
          <span className="text-2xs text-accent underline-offset-2 group-open:underline">Why?</span>
        </span>
        {reasons && level !== "high" && <span className="mt-1 block max-w-[220px] text-2xs leading-snug text-ink-3 group-open:hidden">{reasons.join("; ")}</span>}
      </summary>
      <div className="mt-2 w-64 rounded-md border border-line bg-surface p-2.5 shadow-card">
        <ConfidenceChecks checks={checks} compact />
        <p className="mt-2 border-t border-line pt-1.5 text-2xs text-ink-3">
          {issues.length === 0 ? "All three checks pass." : `${issues.length} check(s) not passed.`} {CONFIDENCE_RULE_TEXT}
        </p>
      </div>
    </details>
  );
}

const SEV = {
  high: { icon: <AlertOctagon size={15} />, cls: "text-bad", label: "High" },
  warning: { icon: <AlertTriangle size={15} />, cls: "text-warn", label: "Review" },
  info: { icon: <Info size={15} />, cls: "text-ink-3", label: "Info" },
};

export function FlagRow({ flag, children }: { flag: Flag; children?: React.ReactNode }) {
  const s = SEV[flag.severity];
  return (
    <li className="flex gap-3 border-b border-line/70 px-4 py-3 last:border-0">
      <span className={`mt-0.5 shrink-0 ${s.cls}`} aria-label={s.label}>
        {s.icon}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[13px] font-medium text-ink">{flag.title}</span>
          {flag.requires_verification && <span className="chip bg-warn-soft text-warn">Verify</span>}
          <span className="chip bg-sunken text-ink-3">{flag.category.replace("_", " ")}</span>
        </div>
        <p className="mt-1 text-xs leading-relaxed text-ink-2">{flag.detail}</p>
        {children}
      </div>
    </li>
  );
}

export function HumanDecides({ className = "" }: { className?: string }) {
  return (
    <div className={`flex items-start gap-2 rounded-md border border-line bg-sunken px-3 py-2 text-xs text-ink-2 ${className}`}>
      <ShieldCheck size={14} className="mt-0.5 shrink-0 text-accent" />
      <span>
        <b className="font-semibold text-ink">A human decides.</b> This score summarises evidence for a loan officer. It is not an approval, a rejection or a bureau score, and it is not a validated credit-risk model.
      </span>
    </div>
  );
}

export function Hypothetical({ children }: { children: React.ReactNode }) {
  return (
    <span className="chip border border-dashed border-accent/50 text-accent" title="Hypothetical estimate, not a calculated assessment">
      {children}
    </span>
  );
}

export function Stat({ label, value, sub }: { label: string; value: React.ReactNode; sub?: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <div className="eyebrow">{label}</div>
      <div className="num mt-1 text-lg font-medium text-ink">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-ink-3">{sub}</div>}
    </div>
  );
}

export function SuccessNote({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2 rounded-md border border-good/30 bg-good-soft px-3 py-2 text-sm text-ink" role="status">
      <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-good" />
      <div>{children}</div>
    </div>
  );
}

export function NotFoundBusiness() {
  // The remembered business no longer exists (e.g. removed by a demo reset):
  // point the sidebar links back at the default demo business.
  useEffect(() => rememberBusiness(DEFAULT_BUSINESS), []);
  return (
    <EmptyState title="Business not found">
      <p>This business is not in the database any more. Businesses added during the demo are removed when demo data is restored, and on a deployment without a persistent database the data also resets when the server restarts.</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Link className="btn-primary" href={`/merchant/${DEFAULT_BUSINESS}`}>Open Raj&apos;s Bakery</Link>
        <Link className="btn-secondary" href="/banker">Open the portfolio</Link>
      </div>
    </EmptyState>
  );
}
