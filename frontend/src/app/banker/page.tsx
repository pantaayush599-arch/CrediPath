"use client";

import { AlertTriangle } from "lucide-react";
import Link from "next/link";
import { api, type Business } from "@/lib/api";
import { dateLabel, inr } from "@/lib/format";
import { rememberBusiness, useAsync } from "@/lib/hooks";
import { ConfidenceChip, EmptyState, ErrorState, HumanDecides, Loading, PageHeader } from "@/components/ui";

export default function Portfolio() {
  const { data, error, loading, reload } = useAsync<Business[]>(() => api.businesses(), []);
  return (
    <div>
      <PageHeader
        eyebrow="Lender · risk view"
        title="Applicant portfolio"
        subtitle="Thin-file MSMEs with consented records. Open an applicant to see the score factors, risk flags and what to verify."
      />
      {loading && <Loading label="Loading applicants…" />}
      {error && <ErrorState error={error} onRetry={reload} />}
      {data && data.length === 0 && <EmptyState title="No applicants">Restore the demo data from the Overview page.</EmptyState>}
      {data && data.length > 0 && (
        <div className="panel overflow-x-auto">
          <table className="table-base min-w-[860px]">
            <thead>
              <tr>
                <th>Applicant</th>
                <th>Bureau view</th>
                <th className="text-right">Avg monthly income</th>
                <th className="text-right">CrediPath score</th>
                <th>Confidence</th>
                <th className="text-right">To verify</th>
                <th>Data as of</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.map((b) => (
                <tr key={b.id} className="hover:bg-sunken/50">
                  <td>
                    <Link href={`/banker/${b.id}`} onClick={() => rememberBusiness(b.id)} className="font-medium text-ink hover:text-accent">
                      {b.name}
                    </Link>
                    <div className="text-xs text-ink-3">
                      {b.category} · {b.city}
                    </div>
                  </td>
                  <td className="text-xs text-ink-2">{b.bureau_status}</td>
                  <td className="num text-right">{inr(b.avg_monthly_income, { compact: true })}</td>
                  <td className="text-right">
                    {b.latest_score === null ? (
                      <span className="text-xs text-ink-3">No records yet</span>
                    ) : (
                      <span className="num">
                        <b className="text-base text-ink">{b.latest_display_score}</b>
                        <span className="text-xs text-ink-3"> · {b.latest_score.toFixed(2)}</span>
                      </span>
                    )}
                  </td>
                  <td>
                    <ConfidenceChip level={b.confidence} />
                  </td>
                  <td className="text-right">
                    {b.verification_count > 0 ? (
                      <span className="inline-flex items-center gap-1 text-xs text-warn">
                        <AlertTriangle size={13} /> {b.verification_count}
                      </span>
                    ) : (
                      <span className="text-xs text-ink-3">0</span>
                    )}
                  </td>
                  <td className="text-xs text-ink-2">{b.as_of_date ? dateLabel(b.as_of_date) : "—"}</td>
                  <td className="text-right">
                    <Link href={`/banker/${b.id}`} onClick={() => rememberBusiness(b.id)} className="btn-secondary px-2.5 py-1 text-xs">
                      Assessment
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <HumanDecides className="mt-4" />
    </div>
  );
}
