// Indian number formatting (lakh / crore grouping).

export function inr(x: number | null | undefined, opts: { compact?: boolean } = {}): string {
  if (x === null || x === undefined || Number.isNaN(x)) return "—";
  const sign = x < 0 ? "−" : "";
  const v = Math.abs(x);
  if (opts.compact) {
    if (v >= 1e7) return `${sign}₹${(v / 1e7).toFixed(2)} Cr`;
    if (v >= 1e5) return `${sign}₹${(v / 1e5).toFixed(2).replace(/\.?0+$/, "")} L`;
    if (v >= 1e3) return `${sign}₹${(v / 1e3).toFixed(0)}k`;
  }
  return `${sign}₹${Math.round(v).toLocaleString("en-IN")}`;
}

export function pct(x: number | null | undefined, digits = 0): string {
  if (x === null || x === undefined) return "—";
  return `${(x * 100).toFixed(digits)}%`;
}

export function score(x: number | null | undefined, digits = 0): string {
  if (x === null || x === undefined) return "—";
  return x.toFixed(digits);
}

export function signed(x: number, digits = 1): string {
  const s = x.toFixed(digits);
  return x > 0 ? `+${s}` : x < 0 ? s.replace("-", "−") : s;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function monthLabel(ym: string, withYear = false): string {
  const [y, m] = ym.split("-").map(Number);
  return withYear ? `${MONTHS[m - 1]} ${String(y).slice(2)}` : MONTHS[m - 1];
}

export function dateLabel(iso: string): string {
  const d = new Date(iso.length === 10 ? iso + "T00:00:00" : iso);
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export function dateTimeLabel(iso: string): string {
  return new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

export function metricText(key: string, metric: number | null): string {
  if (metric === null) return "—";
  switch (key) {
    case "liquidity_resilience":
      return `${metric.toFixed(1)} days`;
    case "repayment_record":
    case "invoice_collection":
    case "data_completeness":
      return pct(metric, 1);
    case "growth_seasonality":
      return `${metric >= 0 ? "+" : ""}${(metric * 100).toFixed(1)}% / yr`;
    default:
      return pct(metric, 1);
  }
}
