"use client";

import { useEffect, useState } from "react";

export interface SessionUser {
  email: string;
  role: "banker" | "merchant";
  display_name: string;
  organisation: string;
  business_id: string | null;
}

export interface Session {
  token: string;
  user: SessionUser;
}

const KEY = "credipath-session";
const EVT = "credipath-session";

export function getSession(): Session | null {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}

export function setSession(s: Session) {
  try {
    localStorage.setItem(KEY, JSON.stringify(s));
  } catch {}
  window.dispatchEvent(new Event(EVT));
}

export function clearSession() {
  try {
    localStorage.removeItem(KEY);
  } catch {}
  window.dispatchEvent(new Event(EVT));
}

/** undefined while loading (first render), null when signed out. */
export function useSession(): Session | null | undefined {
  const [s, setS] = useState<Session | null | undefined>(undefined);
  useEffect(() => {
    const sync = () => setS(getSession());
    sync();
    window.addEventListener(EVT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(EVT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);
  return s;
}

export function homeFor(user: SessionUser): string {
  return user.role === "banker" ? "/banker" : `/merchant/${user.business_id}`;
}
