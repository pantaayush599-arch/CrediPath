"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { ThemeToggle } from "@/components/theme";
import { SampleLinks, UploadPanel } from "@/components/UploadPanel";
import { ErrorState, PageHeader, Panel, SuccessNote } from "@/components/ui";
import { api, type Business, type UploadResult } from "@/lib/api";
import { setSession } from "@/lib/session";

export default function Register() {
  const [form, setForm] = useState({ name: "", owner_name: "", category: "", city: "", years_in_operation: "", description: "", email: "", password: "", consent: false });
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
      const r = await api.register({ ...form, years_in_operation: form.years_in_operation ? Number(form.years_in_operation) : null });
      setSession({ token: r.token, user: r.user });
      setBiz(r.business);
    } catch (err) {
      setError(err as Error);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-canvas">
      <header className="flex items-center justify-between border-b border-line px-4 py-3 sm:px-8">
        <Link href="/login" className="btn-ghost -ml-2 text-xs">
          <ArrowLeft size={14} /> Back to sign in
        </Link>
        <ThemeToggle compact />
      </header>
      <main className="mx-auto max-w-6xl space-y-5 px-4 py-6 sm:px-8">
        <PageHeader eyebrow="MSME owner" title="Register your business" subtitle="Create your owner account, then share your records as a CSV to get your first assessment." />
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <Panel title="1 · Business and sign-in details">
            {biz ? (
              <SuccessNote>
                <b>{biz.name}</b> registered and you are signed in. Now upload its records.
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
                <label className="text-xs text-ink-2">
                  Email (your sign-in)
                  <input required type="email" autoComplete="username" className="input mt-1" value={form.email} onChange={set("email")} />
                </label>
                <label className="text-xs text-ink-2">
                  Password (6+ characters)
                  <input required type="password" minLength={6} autoComplete="new-password" className="input mt-1" value={form.password} onChange={set("password")} />
                </label>
                <label className="flex items-start gap-2 rounded-md border border-line bg-sunken p-3 text-xs text-ink-2 sm:col-span-2">
                  <input type="checkbox" className="mt-0.5 h-4 w-4" checked={form.consent} onChange={set("consent")} required />
                  <span>
                    I consent to these records being used to assess this business. <b className="text-ink">Demo only:</b> use synthetic data and a throwaway password — do not upload real bank or personal information.
                  </span>
                </label>
                {error && (
                  <div className="sm:col-span-2">
                    <ErrorState error={error} />
                  </div>
                )}
                <div className="sm:col-span-2">
                  <button className="btn-primary" disabled={busy || !form.consent}>
                    {busy ? "Registering…" : "Register and sign in"}
                  </button>
                </div>
              </form>
            )}
          </Panel>
          <Panel title="2 · Upload records" subtitle={biz ? `For ${biz.name}` : "Available after you register."}>
            {biz ? (
              <>
                <UploadPanel businessId={biz.id} onImported={setDone} />
                {done?.assessment && (
                  <div className="mt-4">
                    <Link href={`/merchant/${biz.id}`} className="btn-primary">
                      Go to my score &amp; plan
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
      </main>
    </div>
  );
}
