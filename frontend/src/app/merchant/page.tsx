"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Loading } from "@/components/ui";
import { useCurrentBusiness } from "@/lib/hooks";

export default function MerchantIndex() {
  const router = useRouter();
  const id = useCurrentBusiness();
  useEffect(() => router.replace(`/merchant/${id}`), [id, router]);
  return <Loading label="Opening your dashboard…" />;
}
