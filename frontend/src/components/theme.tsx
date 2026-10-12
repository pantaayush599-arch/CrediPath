"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useState } from "react";

export type ThemePref = "light" | "dark" | "system";
const KEY = "credipath-theme";

// Runs before first paint (inlined in <head>) so the page never flashes the wrong theme.
export const themeInitScript = `(function(){try{var p=localStorage.getItem('${KEY}')||'system';var d=p==='dark'||(p==='system'&&window.matchMedia('(prefers-color-scheme: dark)').matches);document.documentElement.setAttribute('data-theme',d?'dark':'light');}catch(e){document.documentElement.setAttribute('data-theme','light');}})();`;

const Ctx = createContext<{ pref: ThemePref; resolved: "light" | "dark"; setPref: (p: ThemePref) => void }>({
  pref: "system",
  resolved: "light",
  setPref: () => {},
});

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [pref, setPrefState] = useState<ThemePref>("system");
  const [resolved, setResolved] = useState<"light" | "dark">("light");

  const apply = useCallback((p: ThemePref) => {
    const dark = p === "dark" || (p === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
    setResolved(dark ? "dark" : "light");
  }, []);

  useEffect(() => {
    let p: ThemePref = "system";
    try {
      p = (localStorage.getItem(KEY) as ThemePref) || "system";
    } catch {}
    setPrefState(p);
    apply(p);
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => {
      let cur: ThemePref = "system";
      try {
        cur = (localStorage.getItem(KEY) as ThemePref) || "system";
      } catch {}
      if (cur === "system") apply("system");
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [apply]);

  const setPref = (p: ThemePref) => {
    try {
      localStorage.setItem(KEY, p);
    } catch {}
    setPrefState(p);
    apply(p);
  };

  return <Ctx.Provider value={{ pref, resolved, setPref }}>{children}</Ctx.Provider>;
}

export const useTheme = () => useContext(Ctx);

export function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const { pref, setPref } = useTheme();
  const opts: { v: ThemePref; icon: React.ReactNode; label: string }[] = [
    { v: "light", icon: <Sun size={14} />, label: "Light" },
    { v: "dark", icon: <Moon size={14} />, label: "Dark" },
    { v: "system", icon: <Monitor size={14} />, label: "System" },
  ];
  return (
    <div role="radiogroup" aria-label="Colour theme" className="inline-flex rounded-md border border-line bg-sunken p-0.5">
      {opts.map((o) => (
        <button
          key={o.v}
          role="radio"
          aria-checked={pref === o.v}
          title={`${o.label} theme`}
          onClick={() => setPref(o.v)}
          className={`flex items-center gap-1.5 rounded px-2 py-1 text-xs font-medium transition-colors ${
            pref === o.v ? "bg-surface text-ink shadow-card" : "text-ink-3 hover:text-ink"
          }`}
        >
          {o.icon}
          {!compact && <span>{o.label}</span>}
        </button>
      ))}
    </div>
  );
}
