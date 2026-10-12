"use client";

import Link from "next/link";
import { useState } from "react";
import { SampleLinks, UploadPanel } from "@/components/UploadPanel";
import { ErrorState, PageHeader, Panel, SuccessNote } from "@/components/ui";
import { api, type Business, type UploadResult } from "@/lib/api";
import { rememberBusiness } from "@/lib/hooks";

export default function Onboard() {
  const [form, setForm] = useState({ name: "", owner_name: "", category: "", city: "", years_in_operation: "", description: "", consent: false });
  const [biz, setBiz] = useState<Business | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [done, setDone] = useState<UploadResult | null>(null);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.type === "checkbox" ? (e.target as HTMLInputElement).checked : e.target.value }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const b = await api.createBusiness({ ...form, years_in_operation: form.years_in_operation ? Number(form.years_in_operation) : null });
      setBiz(b);
      rememberBusiness(b.id);
    } catch (err) {
      setError(err as Error);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-5">
      <PageHeader eyebrow="Onboard" title="Add a business" subtitle="Create a demo profile, then share its records as a CSV to get a first assessment." />
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Panel title="1 · Business profile">
          {biz ? (
            <SuccessNote>
              <b>{biz.name}</b> created. Now upload its records.
            </SuccessNote>
          ) : (
            <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2">
              <label className="text-xs text-ink-2 sm:col-span-2">
                Business name
                <input required minLength={2} className="input mt-1" value={form.name} onChange={set("name")} placeholder="e.g. Fresh Fruits Co" />
              </label>
              <label className="text-xs text-ink-2">
                Owner name
                <input required minLength={2} className="input mt-1" value={form.owner_name} onChange={set("owner_name")} />
              </label>
              <label className="text-xs text-ink-2">
                Business type
                <input required minLength={2} className="input mt-1" value={form.category} onChange={set("category")} placeholder="Kirana, bakery, retail…" />
              </label>
              <label className="text-xs text-ink-2">
                City
                <input required minLength={2} className="input mt-1" value={form.city} onChange={set("city")} />
              </label>
              <label className="text-xs text-ink-2">
                Years in operation
                <input type="number" min={0} max={150} className="input mt-1" value={form.years_in_operation} onChange={set("years_in_operation")} />
              </label>
              <label className="text-xs text-ink-2 sm:col-span-2">
                Short description (optional)
                <textarea className="input mt-1" rows={2} maxLength={1000} value={form.description} onChange={set("description")} />
              </label>
              <label className="flex items-start gap-2 rounded-md border border-line bg-sunken p-3 text-xs text-ink-2 sm:col-span-2">
                <input type="checkbox" className="mt-0.5 h-4 w-4" checked={form.consent} onChange={set("consent")} required />
                <span>
                  I consent to these records being used to assess this business. <b className="text-ink">Demo only:</b> please use synthetic data — do not upload real bank or personal information.
                </span>
              </label>
              {error && (
                <div className="sm:col-span-2">
                  <ErrorState error={error} />
                </div>
              )}
              <div className="sm:col-span-2">
                <button className="btn-primary" disabled={busy || !form.consent}>
                  {busy ? "Creating…" : "Create profile"}
                </button>
              </div>
            </form>
          )}
        </Panel>
        <Panel title="2 · Upload records" subtitle={biz ? `For ${biz.name}` : "Available after the profile is created."}>
          {biz ? (
            <>
              <UploadPanel businessId={biz.id} onImported={setDone} />
              {done?.assessment && (
                <div className="mt-4 flex flex-wrap gap-2">
                  <Link href={`/merchant/${biz.id}`} className="btn-primary">
                    Owner view
                  </Link>
                  <Link href={`/banker/${biz.id}`} className="btn-secondary">
                    Lender view
                  </Link>
                </div>
              )}
            </>
          ) : (
            <div className="space-y-3">
              <p className="text-xs text-ink-2">Use the new-business sample (12 months of synthetic records) or the template to build your own file.</p>
              <SampleLinks only={["new_business_sample.csv", "credipath_template.csv"]} />
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}
