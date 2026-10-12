// Typed client for the CrediPath FastAPI backend (proxied at /api by Next.js).

export type Band = "strength" | "watch" | "concern" | "insufficient_data";
export type ProgressStatus = "pending" | "in_progress" | "completed";

export interface Business {
  id: string;
  name: string;
  owner_name: string;
  category: string;
  city: string;
  years_in_operation: number | null;
  description: string;
  bureau_status: string;
  conventional_view: string;
  is_synthetic: boolean;
  is_seeded: boolean;
  latest_score: number | null;
  latest_display_score: number | null;
  confidence: string | null;
  verification_count: number;
  flag_count: number;
  as_of_date: string | null;
  assessment_count: number;
  avg_monthly_income: number | null;
  record_stats: Record<string, { count: number; first: string; last: string }>;
}

export interface Indicator {
  key: string;
  name: string;
  weight: number;
  effective_weight: number;
  sub_score: number | null;
  contribution: number | null;
  status: "scored" | "insufficient_data";
  band: Band;
  metric: number | null;
  metric_label: string;
  benchmark: number;
  explanation_banker: string;
  explanation_merchant: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  details: Record<string, any>;
}

export interface Flag {
  id: number;
  kind: string;
  category: "data_quality" | "risk" | "verification";
  severity: "info" | "warning" | "high";
  title: string;
  detail: string;
  requires_verification: boolean;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  evidence: Record<string, any>;
}

export interface Recommendation {
  rank: number;
  action_key: string;
  indicator_key: string;
  title: string;
  short_label: string;
  why: string;
  steps: string[];
  current_sub_score: number;
  target_sub_score: number;
  expected_impact: number;
  in_top_plan: boolean;
  status: ProgressStatus;
  hypothetical: boolean;
}

export interface MonthRow {
  month: string;
  has_bank: boolean;
  inflow: number | null;
  outflow: number | null;
  net: number | null;
  month_end_balance: number | null;
  sales_register: number | null;
}

export interface Assessment {
  id: number;
  created_at: string;
  trigger: string;
  upload_id: number | null;
  as_of_date: string;
  window_start: string;
  window_end: string;
  overall_score: number | null;
  display_score: number | null;
  confidence: "low" | "medium" | "high";
  confidence_reasons: string[];
  scoring_version: string;
  record_count: number;
  flag_count: number;
  verification_count: number;
  summary: {
    banker_summary: string;
    merchant_summary: string;
    doing_well: string[];
    needs_work: string[];
    strengths: string[];
    concerns: string[];
    watch: string[];
    not_scored: string[];
    source: string;
  };
  indicators: Indicator[];
  flags: Flag[];
  recommendations: Recommendation[];
  monthly: MonthRow[];
  disclaimer: string;
  formula: string;
}

export interface AssessmentSummary {
  id: number;
  created_at: string;
  trigger: string;
  as_of_date: string;
  window_start: string;
  window_end: string;
  overall_score: number | null;
  display_score: number | null;
  confidence: string;
  flag_count: number;
  verification_count: number;
  indicators: Record<string, number | null>;
}

export interface Comparison {
  previous: AssessmentSummary;
  current: AssessmentSummary;
  score_delta: number;
  indicators: { key: string; name: string; before: number | null; after: number | null; delta: number | null }[];
  flags_resolved: string[];
  flags_new: string[];
  flags_before: number;
  flags_after: number;
}

export interface WhatIf {
  hypothetical: true;
  assessment_id: number;
  baseline_score: number;
  baseline_display: number;
  hypothetical_score: number;
  hypothetical_display: number;
  total_delta: number;
  steps: { action_key: string; short_label: string; title: string; indicator_key: string; current_sub_score: number; target_sub_score: number; delta: number }[];
  ignored_actions: string[];
  note: string;
}

export interface Issue {
  row: number | null;
  field: string | null;
  message: string;
}

export interface ValidationReport {
  filename: string;
  rows_total: number;
  rows_valid: number;
  rows_rejected: number;
  error_count: number;
  warning_count: number;
  errors: Issue[];
  warnings: Issue[];
  by_type: Record<string, number>;
  date_range: [string, string] | null;
  can_import: boolean;
}

export interface UploadResult {
  upload_id: number;
  filename: string;
  rows_inserted: number;
  rows_updated: number;
  rows_duplicate: number;
  rows_rejected: number;
  validation: ValidationReport;
  assessment: Assessment | null;
  comparison: Comparison | null;
  message: string;
}

export interface UploadRow {
  id: number;
  filename: string;
  source: string;
  uploaded_at: string;
  rows_total: number;
  rows_inserted: number;
  rows_updated: number;
  rows_duplicate: number;
  rows_rejected: number;
}

export interface Sample {
  name: string;
  description: string;
  url: string;
}

export class ApiError extends Error {
  status: number;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  detail: any;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  constructor(status: number, message: string, detail?: any) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, { cache: "no-store", ...init });
  } catch {
    throw new ApiError(0, "Cannot reach the CrediPath API. If running locally, start the backend on port 8000.");
  }
  const text = await res.text();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let body: any = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = text;
  }
  if (!res.ok) {
    const d = body?.detail;
    let msg = typeof d === "string" ? d : d?.message;
    if (!msg && Array.isArray(d)) msg = d.map((x: { msg: string }) => x.msg.replace("Value error, ", "")).join("; ");
    if (!msg && res.status >= 500) msg = "The CrediPath API is not responding. If running locally, start the backend (port 8000) and try again.";
    throw new ApiError(res.status, msg || `Request failed (${res.status})`, d);
  }
  return body as T;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  health: () => request<{ status: string; database: string }>("/health"),
  businesses: () => request<Business[]>("/businesses"),
  business: (id: string) => request<Business>(`/businesses/${id}`),
  createBusiness: (body: Record<string, unknown>) => request<Business>("/businesses", json(body)),
  assessment: (id: string) => request<Assessment>(`/businesses/${id}/assessment`),
  assessments: (id: string) => request<AssessmentSummary[]>(`/businesses/${id}/assessments`),
  comparison: (id: string) => request<Comparison | null>(`/businesses/${id}/comparison`),
  reassess: (id: string) => request<Assessment>(`/businesses/${id}/assess`, { method: "POST" }),
  whatIf: (id: string, actions: string[]) => request<WhatIf>(`/businesses/${id}/what-if`, json({ actions })),
  setProgress: (id: string, action: string, status: ProgressStatus) =>
    request(`/businesses/${id}/progress/${action}`, { method: "PUT", headers: { "content-type": "application/json" }, body: JSON.stringify({ status }) }),
  uploads: (id: string) => request<UploadRow[]>(`/businesses/${id}/uploads`),
  validate: (id: string, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<ValidationReport>(`/businesses/${id}/uploads/validate`, { method: "POST", body: fd });
  },
  upload: (id: string, file: File, skipInvalid: boolean) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<UploadResult>(`/businesses/${id}/uploads?skip_invalid=${skipInvalid}`, { method: "POST", body: fd });
  },
  samples: () => request<Sample[]>("/samples"),
  config: () => request<ScoringConfig>("/scoring/config"),
  schema: () => request<RecordSchema>("/schema"),
  reset: () => request<{ restored: string[]; message: string }>("/demo/reset?confirm=true", { method: "POST" }),
};

export interface ScoringConfig {
  version: string;
  window_months: number;
  formula: string;
  bands: { strength_min: number; concern_below: number };
  indicators: { key: string; name: string; weight: number; metric_label: string; thresholds: [number, number][]; benchmark: number; description: string; rule: string }[];
  anomaly_rules: Record<string, number>;
}

export interface RecordSchema {
  columns: string[];
  record_types: string[];
  required: Record<string, string[]>;
  recommended: Record<string, string[]>;
  help: Record<string, string>;
  max_file_mb: number;
}
