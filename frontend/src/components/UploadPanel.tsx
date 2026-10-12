"use client";

import { Download, FileSpreadsheet, Loader2, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { api, ApiError, type Sample, type UploadResult, type ValidationReport } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { ComparisonView } from "./score";
import { ErrorState, SuccessNote } from "./ui";

export function SampleLinks({ only }: { only?: string[] }) {
  const { data } = useAsync<Sample[]>(() => api.samples(), []);
  const list = (data || []).filter((s) => !only || only.includes(s.name));
  if (!list.length) return null;
  return (
    <ul className="divide-y divide-line rounded-md border border-line">
      {list.map((s) => (
        <li key={s.name} className="flex items-start gap-3 px-3 py-2">
          <FileSpreadsheet size={15} className="mt-0.5 shrink-0 text-accent" />
          <div className="min-w-0 flex-1">
            <div className="num truncate text-xs font-medium text-ink">{s.name}</div>
            <div className="text-xs text-ink-3">{s.description}</div>
          </div>
          <a href={s.url} download className="btn-ghost shrink-0 px-2 py-1 text-xs">
            <Download size={13} /> Download
          </a>
        </li>
      ))}
    </ul>
  );
}

function ValidationSummary({ report }: { report: ValidationReport }) {
  const [showAll, setShowAll] = useState(false);
  const errs = showAll ? report.errors : report.errors.slice(0, 6);
  return (
    <div className="space-y-3 rounded-md border border-line p-3">
      <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
        <div>
          <span className="eyebrow block">Rows read</span>
          <span className="num">{report.rows_total}</span>
        </div>
        <div>
          <span className="eyebrow block">Valid</span>
          <span className="num text-good">{report.rows_valid}</span>
        </div>
        <div>
          <span className="eyebrow block">Rejected</span>
          <span className={`num ${report.rows_rejected ? "text-bad" : ""}`}>{report.rows_rejected}</span>
        </div>
        <div>
          <span className="eyebrow block">Warnings</span>
          <span className={`num ${report.warning_count ? "text-warn" : ""}`}>{report.warning_count}</span>
        </div>
        {report.date_range && (
          <div>
            <span className="eyebrow block">Date range</span>
            <span className="num">
              {report.date_range[0]} → {report.date_range[1]}
            </span>
          </div>
        )}
      </div>
      {Object.keys(report.by_type).length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(report.by_type).map(([t, n]) => (
            <span key={t} className="chip bg-sunken text-ink-2">
              {t.replace("_", " ")} · {n}
            </span>
          ))}
        </div>
      )}
      {report.errors.length > 0 && (
        <div>
          <div className="mb-1 text-xs font-semibold text-bad">Errors (these rows will not be imported)</div>
          <ul className="space-y-0.5 text-xs text-ink-2">
            {errs.map((e, i) => (
              <li key={i}>
                <span className="num text-ink-3">row {e.row ?? "–"}</span>
                {e.field && <span className="num text-ink-3"> · {e.field}</span>} — {e.message}
              </li>
            ))}
          </ul>
          {report.errors.length > 6 && (
            <button className="mt-1 text-xs text-accent underline" onClick={() => setShowAll((v) => !v)}>
              {showAll ? "Show fewer" : `Show all ${report.error_count}`}
            </button>
          )}
        </div>
      )}
      {report.warnings.length > 0 && (
        <div>
          <div className="mb-1 text-xs font-semibold text-warn">Warnings (rows are imported; blanks stay blank)</div>
          <ul className="space-y-0.5 text-xs text-ink-2">
            {report.warnings.slice(0, 8).map((w, i) => (
              <li key={i}>
                {w.row && <span className="num text-ink-3">row {w.row} · </span>}
                {w.message}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export function UploadPanel({ businessId, onImported }: { businessId: string; onImported?: (r: UploadResult) => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [report, setReport] = useState<ValidationReport | null>(null);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [busy, setBusy] = useState<"validate" | "import" | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [drag, setDrag] = useState(false);

  const pick = async (f: File | null) => {
    setFile(f);
    setReport(null);
    setResult(null);
    setError(null);
    if (!f) return;
    setBusy("validate");
    try {
      setReport(await api.validate(businessId, f));
    } catch (e) {
      setError(e as Error);
    } finally {
      setBusy(null);
    }
  };

  const doImport = async () => {
    if (!file || !report) return;
    setBusy("import");
    setError(null);
    try {
      const r = await api.upload(businessId, file, report.error_count > 0);
      setResult(r);
      onImported?.(r);
    } catch (e) {
      const err = e as ApiError;
      if (err.detail?.validation) setReport(err.detail.validation);
      setError(err);
    } finally {
      setBusy(null);
    }
  };

  const reset = () => {
    setFile(null);
    setReport(null);
    setResult(null);
    setError(null);
    if (input.current) input.current.value = "";
  };

  return (
    <div className="space-y-4">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          pick(e.dataTransfer.files?.[0] ?? null);
        }}
        className={`flex flex-col items-center justify-center gap-2 rounded-md border border-dashed px-4 py-7 text-center transition-colors ${drag ? "border-accent bg-accent-soft" : "border-line-strong bg-sunken/50"}`}
      >
        <Upload size={18} className="text-ink-3" />
        <div className="text-sm text-ink">
          {file ? <span className="num">{file.name}</span> : "Drop a CSV file here, or"}
        </div>
        <input ref={input} type="file" accept=".csv,text/csv" className="sr-only" id={`csv-${businessId}`} onChange={(e) => pick(e.target.files?.[0] ?? null)} />
        <label htmlFor={`csv-${businessId}`} className="btn-secondary cursor-pointer">
          {file ? "Choose a different file" : "Choose CSV file"}
        </label>
        <div className="text-2xs text-ink-3">Max 5 MB · columns: record_type, date, amount, … (see template)</div>
      </div>

      {busy === "validate" && (
        <div className="flex items-center gap-2 text-sm text-ink-3">
          <Loader2 size={14} className="animate-spin" /> Validating…
        </div>
      )}
      {error && <ErrorState error={error} />}
      {report && !result && (
        <>
          <ValidationSummary report={report} />
          <div className="flex flex-wrap items-center gap-2">
            <button className="btn-primary" disabled={!report.can_import || busy !== null} onClick={doImport}>
              {busy === "import" && <Loader2 size={14} className="animate-spin" />}
              {report.error_count > 0 ? `Import ${report.rows_valid} valid rows & reassess` : `Import ${report.rows_valid} rows & reassess`}
            </button>
            <button className="btn-ghost" onClick={reset}>
              Cancel
            </button>
            {report.error_count > 0 && report.can_import && <span className="text-xs text-warn">{report.rows_rejected} row(s) with errors will be skipped.</span>}
            {!report.can_import && <span className="text-xs text-bad">No valid rows — fix the file and try again.</span>}
          </div>
        </>
      )}
      {result && (
        <div className="space-y-4">
          <SuccessNote>
            <div className="font-medium">{result.message}</div>
            <div className="text-xs text-ink-2">
              {result.rows_inserted} new · {result.rows_updated} updated · {result.rows_duplicate} already on file · {result.rows_rejected} rejected
            </div>
          </SuccessNote>
          {result.comparison && (
            <div className="rounded-md border border-line p-4">
              <div className="mb-3 text-[13px] font-semibold">Before and after this upload</div>
              <ComparisonView cmp={result.comparison} />
            </div>
          )}
          {result.assessment && !result.comparison && (
            <div className="text-sm text-ink-2">
              First assessment created: <b className="num text-ink">{result.assessment.overall_score?.toFixed(2)}</b> / 100.
            </div>
          )}
          <button className="btn-secondary" onClick={reset}>
            Upload another file
          </button>
        </div>
      )}
    </div>
  );
}
