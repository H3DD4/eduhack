"use client";
// E01 — out of scope for this run: truthful scope explanation, not a fake screen.
import Link from "next/link";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { SubjectShell } from "@/components/SubjectShell";
import { ScopeNotice } from "@/components/ui";

export default function Page() {
  const p = useParams<{ s?: string }>();
  const body = (
    <ScopeNotice id="E01" title="Mock exam setup" milestone="M5">
      {p.s ? <Link className="btn-primary mt-4" href={`/subjects/${p.s}/roadmap`}>Open the roadmap</Link> : <Link className="btn-primary mt-4" href="/today">Go to Today</Link>}
    </ScopeNotice>
  );
  return p.s ? <SubjectShell subjectId={p.s}>{body}</SubjectShell> : <AppShell>{body}</AppShell>;
}
