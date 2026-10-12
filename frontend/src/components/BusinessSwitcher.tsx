"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { api, type Business } from "@/lib/api";
import { rememberBusiness, useAsync } from "@/lib/hooks";

/** Demo-only switcher. In the owner view it lists names only, never other businesses' scores. */
export function BusinessSwitcher({ current, basePath, suffix = "", label }: { current: string; basePath: string; suffix?: string; label: string }) {
  const router = useRouter();
  const { data } = useAsync<Business[]>(() => api.businesses(), []);
  useEffect(() => rememberBusiness(current), [current]);
  return (
    <label className="flex items-center gap-2 text-xs text-ink-3">
      <span className="whitespace-nowrap">{label}</span>
      <select
        className="input w-auto max-w-[240px] py-1.5"
        value={current}
        onChange={(e) => {
          rememberBusiness(e.target.value);
          router.push(`${basePath}/${e.target.value}${suffix}`);
        }}
      >
        {!data && <option value={current}>{current}</option>}
        {data?.map((b) => (
          <option key={b.id} value={b.id}>
            {b.name}
          </option>
        ))}
      </select>
    </label>
  );
}
