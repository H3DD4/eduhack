"use client";
// "/" -> A01 signed out / A02 unfinished setup / G01 otherwise.
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { api } from "@/lib/api";

export default function Root() {
  const router = useRouter();
  useEffect(() => {
    api<{ user: any }>("/auth/me", { retries: 1 })
      .then((r) => router.replace(r.user.setup_complete ? "/today" : "/onboarding"))
      .catch(() => router.replace("/welcome"));
  }, [router]);
  return <p className="p-6" aria-busy="true">Loading…</p>;
}
