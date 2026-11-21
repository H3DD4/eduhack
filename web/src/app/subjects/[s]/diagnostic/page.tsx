"use client";
// C03 Optional diagnostic (minimal) — UC07. Skipping records insufficient evidence: never zero ability, never locks.
// Sampled baseline items arrive in M3; practice inside sessions already checks extracted exercises.
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { SubjectShell } from "@/components/SubjectShell";
import { api } from "@/lib/api";

export default function Diagnostic() {
  const { s } = useParams<{ s: string }>();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  return (
    <SubjectShell subjectId={s} crumb="Optional baseline">
      <section className="card max-w-prose space-y-3" data-screen="C03">
        <h2 className="text-section">Optional baseline</h2>
        <p>A baseline is optional. Skipping it never lowers anything or locks concepts — it simply records that there is not enough evidence yet.</p>
        <p className="text-meta text-ink-muted">Sampled baseline questions arrive in M3.</p>
        <button className="btn-primary" disabled={busy} onClick={async () => { setBusy(true); await api(`/subjects/${s}/diagnostic/skip`, { method: "POST" }); router.push(`/subjects/${s}/roadmap`); }}>
          Skip and open the roadmap
        </button>
      </section>
    </SubjectShell>
  );
}
