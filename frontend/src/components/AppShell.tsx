"use client";

import { BookOpenText, FileUp, Gauge, Landmark, LayoutGrid, Loader2, LogOut, Menu, Store, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useCurrentBusiness } from "@/lib/hooks";
import { clearSession, type SessionUser, useSession } from "@/lib/session";
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

const PUBLIC_PATHS = ["/login", "/onboard"];

/** Where a signed-in user may go; anything else redirects to their home. */
function allowedPath(path: string, user: SessionUser): string | null {
  if (path === "/methodology") return null;
  if (user.role === "banker") return null;
  const own = `/merchant/${user.business_id}`;
  if (path === own || path.startsWith(own + "/")) return null;
  return own;
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const session = useSession();
  const biz = useCurrentBusiness();
  const [open, setOpen] = useState(false);
  const signingOut = useRef(false);
  useEffect(() => setOpen(false), [path]);

  const isPublic = PUBLIC_PATHS.some((p) => path === p || path.startsWith(p + "/"));
  const redirect = session === null ? `/login?next=${encodeURIComponent(path)}` : session ? allowedPath(path, session.user) : null;
  useEffect(() => {
    if (!isPublic && redirect && !signingOut.current) router.replace(redirect);
  }, [isPublic, redirect, router]);

  if (isPublic) return <>{children}</>;
  if (!session || redirect) {
    return (
      <div className="flex min-h-screen items-center justify-center gap-2 text-sm text-ink-3">
        <Loader2 size={16} className="animate-spin" /> Checking your sign-in…
      </div>
    );
  }
  const user = session.user;
  const banker = user.role === "banker";

  const signOut = () => {
    signingOut.current = true; // go to a plain /login, not /login?next=...
    clearSession();
    router.replace("/login");
  };

  const is = (p: string, exact = false) => (exact ? path === p : path === p || path.startsWith(p + "/"));
  const section = (label: string) => <div className="mb-1.5 px-2.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-nav-ink/60">{label}</div>;
  const nav = (
    <nav className="flex flex-1 flex-col gap-5 overflow-y-auto px-3 py-4">
      {banker ? (
        <>
          <div className="space-y-0.5">
            <NavItem href="/" icon={<LayoutGrid size={16} />} label="Overview" active={is("/", true)} />
          </div>
          <div>
            {section("Lender · risk view")}
            <div className="space-y-0.5">
              <NavItem href="/banker" icon={<Landmark size={16} />} label="Applicant portfolio" active={is("/banker", true)} />
              <NavItem href={`/banker/${biz}`} icon={<Gauge size={16} />} label="Assessment" active={path.startsWith("/banker/")} />
            </div>
          </div>
        </>
      ) : (
        <div>
          {section("My business")}
          <div className="space-y-0.5">
            <NavItem href={`/merchant/${user.business_id}`} icon={<Store size={16} />} label="My score & plan" active={path.startsWith("/merchant/") && !path.endsWith("/records")} />
            <NavItem href={`/merchant/${user.business_id}/records`} icon={<FileUp size={16} />} label="Records & reassessment" active={path.startsWith("/merchant/") && path.endsWith("/records")} />
          </div>
        </div>
      )}
      <div>
        {section("Reference")}
        <NavItem href="/methodology" icon={<BookOpenText size={16} />} label="Scoring method" active={is("/methodology")} />
      </div>
    </nav>
  );

  const account = (
    <div className="border-t border-white/5 px-4 py-3">
      <div className="text-[13px] font-medium text-white">{user.display_name}</div>
      <div className="text-[11px] text-nav-ink/80">{user.organisation}</div>
      <div className="mt-0.5 text-[10px] uppercase tracking-[0.12em] text-nav-ink/60">{banker ? "Banker" : "MSME owner"} · demo account</div>
      <button onClick={signOut} className="mt-2 inline-flex items-center gap-1.5 text-[12px] text-nav-ink hover:text-white">
        <LogOut size={13} /> Sign out
      </button>
    </div>
  );

  return (
    <div className="min-h-screen lg:pl-60">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col bg-nav lg:flex">
        <div className="border-b border-white/5 px-4 py-4">
          <Brand />
        </div>
        {nav}
        {account}
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
            {account}
          </aside>
        </div>
      )}

      <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-line bg-canvas/95 px-4 backdrop-blur sm:px-6">
        <button className="btn-ghost -ml-2 px-2 lg:hidden" onClick={() => setOpen(true)} aria-label="Open menu">
          <Menu size={18} />
        </button>
        <span className={`chip ${banker ? "bg-brand/10 text-brand" : "bg-accent-soft text-accent"}`}>{banker ? "Banker view" : "MSME owner view"}</span>
        <span className="chip hidden border border-warn/30 bg-warn-soft text-warn sm:inline-flex" title="All businesses and transactions are fictional">
          Synthetic demo data
        </span>
        <div className="ml-auto flex items-center gap-2">
          <span className="hidden text-xs text-ink-2 md:inline">{user.display_name}</span>
          <ThemeToggle compact />
          <button onClick={signOut} className="btn-ghost px-2 text-xs" title="Sign out">
            <LogOut size={14} /> <span className="hidden sm:inline">Sign out</span>
          </button>
        </div>
      </header>
      <main className="mx-auto max-w-[1280px] px-4 py-6 sm:px-6">{children}</main>
    </div>
  );
}
