"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getSession } from "./session";

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);
  const seq = useRef(0);

  const run = useCallback(() => {
    const id = ++seq.current;
    setLoading(true);
    setError(null);
    fn()
      .then((d) => {
        if (id === seq.current) setData(d);
      })
      .catch((e) => {
        if (id === seq.current) setError(e);
      })
      .finally(() => {
        if (id === seq.current) setLoading(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    run();
  }, [run]);

  return { data, error, loading, reload: run, setData };
}

const BIZ_KEY = "credipath-business";
export const DEFAULT_BUSINESS = "rajs-bakery";

export function rememberBusiness(id: string) {
  try {
    localStorage.setItem(BIZ_KEY, id);
    window.dispatchEvent(new CustomEvent("credipath-business", { detail: id }));
  } catch {}
}

export function useCurrentBusiness(): string {
  const [id, setId] = useState(DEFAULT_BUSINESS);
  useEffect(() => {
    // An owner is always tied to their own business.
    const own = getSession()?.user;
    if (own?.role === "merchant" && own.business_id) {
      setId(own.business_id);
      return;
    }
    try {
      setId(localStorage.getItem(BIZ_KEY) || DEFAULT_BUSINESS);
    } catch {}
    const on = (e: Event) => setId((e as CustomEvent).detail);
    window.addEventListener("credipath-business", on);
    return () => window.removeEventListener("credipath-business", on);
  }, []);
  return id;
}
