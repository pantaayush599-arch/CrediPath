"use client";

import { BookOpenText, Building2, FileUp, Gauge, Landmark, LayoutGrid, Menu, PlusCircle, Store, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useCurrentBusiness } from "@/lib/hooks";
import { ThemeToggle } from "./theme";

function NavItem({ href, icon, label, active, onClick }: { href: string; icon: React.ReactNode; label: string; active: boolean; onClick?: () => void }) {
  return (
    <Link
      href={href}
      onClick={onClick}
      aria-current={active ? "page" : undefined}
      className={`flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[13px] transition-colors ${
        active ? "bg-nav-active font-medium text-white" : "text-nav-ink hover:bg-nav-active/60 hover:text-white"
      }`}
    >
      <span className="opacity-80">{icon}</span>
      {label}
    </Link>
  );
}

function Brand() {
  return (
    <Link href="/" className="flex items-center gap-2.5">
      <svg width="26" height="26" viewBox="0 0 26 26" aria-hidden>
        <rect width="26" height="26" rx="5" fill="#e9e4d8" />
        <path d="M6 17.5 L11 12.5 L14 15 L20 8.5" stroke="#13294b" strokeWidth="2.2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="20" cy="8.5" r="2" fill="#0e746e" />
      </svg>
      <div className="leading-tight">
        <div className="font-serif text-[17px] font-semibold tracking-tight text-white">CrediPath</div>
        <div className="text-[10px] uppercase tracking-[0.12em] text-nav-ink/70">MSME credit visibility</div>
      </div>
    </Link>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const biz = useCurrentBusiness();
  const [open, setOpen] = useState(false);
  useEffect(() => setOpen(false), [path]);

  const is = (p: string, exact = false) => (exact ? path === p : path === p || path.startsWith(p + "/"));
  const nav = (
    <nav className="flex flex-1 flex-col gap-5 overflow-y-auto px-3 py-4">
      <div className="space-y-0.5">
        <NavItem href="/" icon={<LayoutGrid size={16} />} label="Overview" active={is("/", true)} />
      </div>
      <div>
        <div className="mb-1.5 px-2.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-nav-ink/60">Lender · risk view</div>
        <div className="space-y-0.5">
          <NavItem href="/banker" icon={<Landmark size={16} />} label="Applicant portfolio" active={is("/banker", true)} />
          <NavItem href={`/banker/${biz}`} icon={<Gauge size={16} />} label="Assessment" active={path.startsWith("/banker/")} />
        </div>
      </div>
      <div>
        <div className="mb-1.5 px-2.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-nav-ink/60">Business owner · guidance</div>
        <div className="space-y-0.5">
          <NavItem href={`/merchant/${biz}`} icon={<Store size={16} />} label="My score & plan" active={path.startsWith("/merchant/") && !path.endsWith("/records")} />
          <NavItem href={`/merchant/${biz}/records`} icon={<FileUp size={16} />} label="Records & reassessment" active={path.startsWith("/merchant/") && path.endsWith("/records")} />
          <NavItem href="/onboard" icon={<PlusCircle size={16} />} label="Add a business" active={is("/onboard")} />
        </div>
      </div>
      <div>
        <div className="mb-1.5 px-2.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-nav-ink/60">Reference</div>
        <NavItem href="/methodology" icon={<BookOpenText size={16} />} label="Scoring method" active={is("/methodology")} />
      </div>
    </nav>
  );

  return (
    <div className="min-h-screen lg:pl-60">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col bg-nav lg:flex">
        <div className="border-b border-white/5 px-4 py-4">
          <Brand />
        </div>
        {nav}
        <div className="border-t border-white/5 px-4 py-3 text-[11px] leading-snug text-nav-ink/70">
          <Building2 size={12} className="mb-1 inline" /> Prototype · synthetic data only. Scores are not loan decisions.
        </div>
      </aside>

      {/* Mobile drawer */}
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 flex w-72 max-w-[85vw] flex-col bg-nav">
            <div className="flex items-center justify-between border-b border-white/5 px-4 py-4">
              <Brand />
              <button onClick={() => setOpen(false)} aria-label="Close menu" className="text-nav-ink">
                <X size={18} />
              </button>
            </div>
            {nav}
          </aside>
        </div>
      )}

      <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-line bg-canvas/95 px-4 backdrop-blur sm:px-6">
        <button className="btn-ghost -ml-2 px-2 lg:hidden" onClick={() => setOpen(true)} aria-label="Open menu">
          <Menu size={18} />
        </button>
        <span className="chip border border-warn/30 bg-warn-soft text-warn" title="All businesses and transactions are fictional">
          Synthetic demo data
        </span>
        <div className="ml-auto flex items-center gap-2">
          <ThemeToggle compact />
        </div>
      </header>
      <main className="mx-auto max-w-[1280px] px-4 py-6 sm:px-6">{children}</main>
    </div>
  );
}
