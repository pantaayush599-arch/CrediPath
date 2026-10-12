"use client";

import { Link2 } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { BusinessSwitcher } from "@/components/BusinessSwitcher";
import { ComparisonView } from "@/components/score";
import { SampleLinks, UploadPanel } from "@/components/UploadPanel";
import { ErrorState, Loading, NotFoundBusiness, PageHeader, Panel } from "@/components/ui";
import { api, ApiError, type Assessment, type Business, type Comparison, type UploadRow } from "@/lib/api";
import { dateLabel, dateTimeLabel, monthLabel } from "@/lib/format";
import { useAsync } from "@/lib/hooks";

interface Bundle {
  business: Business;
  assessment: Assessment | null;
  uploads: UploadRow[];
  comparison: Comparison | null;
}

const TYPE_LABEL: Record<string, string> = {
  bank: "Bank / UPI statements",
  sale: "Sales register",
  invoice: "Invoices (receivables)",
  supplier_payment: "Supplier payments",
  loan_repayment: "Loan repayments",
};

async function load(id: string): Promise<Bundle> {
  const [business, uploads] = await Promise.all([api.business(id), api.uploads(id)]);
  try {
    const [assessment, comparison] = await Promise.all([api.assessment(id), api.comparison(id)]);
    return { business, uploads, assessment, comparison };
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return { business, uploads, assessment: null, comparison: null };
    throw e;
  }
}

export default function Records() {
  const { id } = useParams<{ id: string }>();
  const { data, error, loading, reload } = useAsync<Bundle>(() => load(id), [id]);

  if (loading && !data) return <Loading label="Loading records…" />;
  if (error) return error instanceof ApiError && error.status === 404 ? <NotFoundBusiness /> : <ErrorState error={error} onRetry={reload} />;
  if (!data) return null;
  const { business: b, assessment: a } = data;
  const coverage = a?.indicators.find((i) => i.key === "data_completeness")?.details?.coverage as
    | Record<string, { expected_months: number; months_present: number; missing_months: string[] }>
    | undefined;

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Business owner · records"
        title="Records & reassessment"
        subtitle={`${b.name} · upload updated records to recalculate your assessment`}
        actions={<BusinessSwitcher current={id} basePath="/merchant" suffix="/records" label="Demo: view as" />}
      />

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <Panel title="Upload records (CSV)" subtitle="Files are checked first; nothing is saved until you confirm the import.">
          <UploadPanel businessId={id} onImported={() => reload()} />
        </Panel>
        <div className="space-y-5">
          <Panel title="Sample files" subtitle="Synthetic CSVs for the demo.">
            <SampleLinks />
            {id === "rajs-bakery" && (
              <p className="mt-3 text-xs text-ink-2">
                For the reassessment demo, download <span className="num">raj_bakery_update_sep2026.csv</span> and upload it here.
              </p>
            )}
          </Panel>
          <Panel title="Other ways to share data">
            <div className="flex items-start gap-3 rounded-md border border-dashed border-line-strong p-3 opacity-80">
              <Link2 size={16} className="mt-0.5 text-ink-3" />
              <div>
                <div className="flex items-center gap-2 text-[13px] font-medium text-ink">
                  Account Aggregator feed <span className="chip bg-sunken text-ink-3">Later · not built</span>
                </div>
                <p className="mt-0.5 text-xs text-ink-3">Consent-based bank data via the RBI Account Aggregator framework is future scope. This prototype only accepts CSV uploads.</p>
              </div>
            </div>
          </Panel>
        </div>
      </div>

      {a && coverage && (
        <Panel title="What we have on file" subtitle={`Assessment window ${dateLabel(a.window_start)} – ${dateLabel(a.window_end)}. Missing months are flagged, never counted as zero.`} bodyClass="overflow-x-auto p-0">
          <table className="table-base min-w-[600px]">
            <thead>
              <tr>
                <th>Record type</th>
                <th className="text-right">Rows (all time)</th>
                <th className="text-right">Months covered</th>
                <th>Missing months in window</th>
              </tr>
            </thead>
            <tbody>
              {Object.keys(TYPE_LABEL).map((t) => {
                const c = coverage[t];
                const stats = b.record_stats[t];
                return (
                  <tr key={t}>
                    <td className="font-medium">{TYPE_LABEL[t]}</td>
                    <td className="num text-right">{stats?.count ?? 0}</td>
                    <td className="num text-right">{c ? `${c.months_present}/${c.expected_months}` : <span className="text-ink-3">not expected</span>}</td>
                    <td className="text-xs text-ink-2">
                      {c ? (c.missing_months.length ? c.missing_months.map((m) => monthLabel(m, true)).join(", ") : <span className="text-good">complete</span>) : <span className="text-ink-3">none shared — fine if you have none</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Panel>
      )}

      <div className="grid gap-5 lg:grid-cols-2">
        <Panel title="Latest reassessment" subtitle="Compared with the previous assessment.">
          {data.comparison ? (
            <ComparisonView cmp={data.comparison} />
          ) : (
            <p className="text-xs text-ink-3">No reassessment yet. Upload updated records to compare before and after.</p>
          )}
          <div className="mt-4 flex flex-wrap gap-2">
            <Link href={`/merchant/${id}`} className="btn-secondary">
              My score &amp; plan
            </Link>
            <Link href={`/banker/${id}`} className="btn-ghost">
              See the lender&apos;s view
            </Link>
          </div>
        </Panel>
        <Panel title="Upload history" bodyClass="overflow-x-auto p-0">
          {data.uploads.length === 0 ? (
            <p className="p-4 text-xs text-ink-3">No uploads yet.</p>
          ) : (
            <table className="table-base min-w-[480px]">
              <thead>
                <tr>
                  <th>File</th>
                  <th>When</th>
                  <th className="text-right">New</th>
                  <th className="text-right">Updated</th>
                  <th className="text-right">Skipped</th>
                </tr>
              </thead>
              <tbody>
                {data.uploads.map((u) => (
                  <tr key={u.id}>
                    <td>
                      <div className="num max-w-[200px] truncate text-xs">{u.filename}</div>
                      {u.source === "seed" && <div className="text-2xs text-ink-3">initial demo data</div>}
                    </td>
                    <td className="text-xs text-ink-2">{dateTimeLabel(u.uploaded_at)}</td>
                    <td className="num text-right">{u.rows_inserted}</td>
                    <td className="num text-right">{u.rows_updated}</td>
                    <td className="num text-right">{u.rows_duplicate + u.rows_rejected}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>
      </div>
    </div>
  );
}
