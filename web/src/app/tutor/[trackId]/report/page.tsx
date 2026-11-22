"use client";
// Readiness report: mastery per concept and chapter, independent success, mock exam scores, what to do next.
import Link from "next/link";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { ErrorBox, Skeleton } from "@/components/ui";
import { Section } from "@/components/tutor/bits";
import { useApi } from "@/lib/hooks";
import { LEVEL_LABEL } from "@/lib/tutor";

export default function Report() {
  const { trackId } = useParams<{ trackId: string }>();
  const r = useApi<any>(`/tutor/tracks/${trackId}/report`);
  const d = r.data;
  return (
    <AppShell crumbs={[{ label: "Tutor", href: "/tutor" }, { label: "Track", href: `/tutor/${trackId}` }, { label: "Report" }]}>
      {r.loading && !d && <Skeleton lines={6} />}
      {r.error && <ErrorBox message={r.error.message} onRetry={r.reload} />}
      {d && (
        <div className="space-y-10">
          <section className="hero p-7">
            <span className="badge">{d.valley === "revision" ? "Exam readiness" : "Skill progress"}</span>
            <h1 className="text-page">{Math.round(d.readiness * 100)}% ready</h1>
            <p>Level {d.level.measured ? LEVEL_LABEL[d.level.measured as keyof typeof LEVEL_LABEL] : "—"}
              {d.level.declared && d.level.measured && d.level.declared !== d.level.measured ? ` (you said ${LEVEL_LABEL[d.level.declared as keyof typeof LEVEL_LABEL]})` : ""}</p>
          </section>

          {d.focus_next.length > 0 && (
            <Section title="Focus next">
              <ul className="grid gap-2 md:grid-cols-2">
                {d.focus_next.map((c: any) => (
                  <li key={c.concept_key} className="card flex items-center justify-between p-4">
                    <span>{c.title}</span><span className="pill">{Math.round(c.p_mastery * 100)}%</span>
                  </li>
                ))}
              </ul>
            </Section>
          )}

          <Section title="By chapter">
            <ul className="space-y-2">
              {Object.entries(d.chapters).map(([ch, v]: [string, any]) => (
                <li key={ch} className="flex items-center gap-3">
                  <span className="w-1/3 truncate">{ch}</span>
                  <div className="bar flex-1"><span style={{ width: `${Math.round(v * 100)}%` }} /></div>
                  <span className="w-12 text-right text-meta">{Math.round(v * 100)}%</span>
                </li>
              ))}
            </ul>
          </Section>

          <Section title="Concepts">
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-left">
                <thead className="text-meta text-ink-muted"><tr>
                  <th className="p-2">Concept</th><th className="p-2">Mastery</th><th className="p-2">On your own</th>
                  <th className="p-2">Attempts</th><th className="p-2">Exam weight</th><th className="p-2">Next review</th></tr></thead>
                <tbody>
                  {d.concepts.map((c: any) => (
                    <tr key={c.concept_key} className="border-t border-border">
                      <td className="p-2">{c.title}{c.mastered && <span className="pill ml-2">mastered</span>}</td>
                      <td className="p-2">{Math.round(c.p_mastery * 100)}%</td>
                      <td className="p-2">{c.independent_success == null ? "—" : `${Math.round(c.independent_success * 100)}%`}</td>
                      <td className="p-2">{c.attempts}</td>
                      <td className="p-2">{Math.round(c.exam_weight * 100)}%</td>
                      <td className="p-2">{c.next_review || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>

          {d.mock_exams.length > 0 && (
            <Section title="Mock exams">
              <ul className="flex flex-wrap gap-2">{d.mock_exams.map((m: any, i: number) => <li key={i} className="chip">{m.score} / {m.out_of}</li>)}</ul>
            </Section>
          )}
          <Link className="btn-primary" href={`/tutor/${trackId}`}>Back to the track</Link>
        </div>
      )}
    </AppShell>
  );
}
