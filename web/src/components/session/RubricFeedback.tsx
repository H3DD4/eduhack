"use client";
// Criterion feedback (override §3.3): said => confirmed quote; missing => "not demonstrated" + rubric criterion
// + course source; uncertain => unscored (never zero). No mastery percentages; no totals hiding uncertainty.
import Link from "next/link";
import { SimulatedLabel } from "../ui";

const NAMES: Record<string, string> = {
  correctness: "Correctness", essential_coverage: "Essential coverage", why_relationships: "Why / relationships",
  example_application: "Example / application", limits: "Limits",
};
const STATUS: Record<string, { t: string; cls: string; icon: string }> = {
  demonstrated: { t: "Demonstrated", cls: "text-success bg-success-surface", icon: "✓" },
  partial: { t: "Partly shown", cls: "text-help bg-help-surface", icon: "◐" },
  absent: { t: "Not demonstrated", cls: "text-review bg-review-surface", icon: "○" },
  unscored: { t: "Unscored", cls: "text-ink-muted bg-surface", icon: "?" },
  na: { t: "Not applicable", cls: "text-ink-muted bg-surface", icon: "–" },
};

export function RubricFeedback({ assessment, subjectId, compact = false }: { assessment: any; subjectId: string; compact?: boolean }) {
  if (!assessment) return null;
  const crit = (assessment.criteria || []).filter((c: any) => !(compact && c.status === "na"));
  return (
    <section aria-label="Feedback by criterion" className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {assessment.method === "symbolic" ? <span className="pill text-success bg-success-surface">∑ {assessment.method_label}</span>
          : <SimulatedLabel label={assessment.method_label} />}
        {assessment.sufficiency !== "sufficient" && <span className="pill text-ink-muted">Evidence: {assessment.sufficiency}</span>}
      </div>
      {!compact && assessment.feedback && <p>{assessment.feedback}</p>}
      <ul className="space-y-3">
        {crit.map((c: any) => {
          const st = STATUS[c.status] || STATUS.unscored;
          return (
            <li key={c.criterion} className="rounded-detail border border-border bg-surface p-3" data-criterion={c.criterion} data-status={c.status}>
              <p className="flex flex-wrap items-center gap-2 font-semibold">
                {NAMES[c.criterion] || c.criterion}
                <span className={`pill ${st.cls}`}><span aria-hidden>{st.icon}</span> {st.t}</span>
                {c.score !== null && c.score !== undefined && <span className="text-meta text-ink-muted">{c.score}/2</span>}
              </p>
              {c.quotes?.map((q: any, i: number) => (
                <blockquote key={i} className="mt-2 border-l-4 border-action pl-3">
                  <span className="text-meta text-ink-muted">{q.supplement ? "From your added reasoning" : q.sentence_id === "answer" ? "Your answer" : "Your confirmed words"}: </span>“{q.text}”
                </blockquote>
              ))}
              {c.missing?.map((m: any, i: number) => (
                <p key={i} className="mt-2 text-meta">
                  <strong>Not demonstrated:</strong> {m.description} <span className="text-ink-muted">(rubric: {NAMES[m.criterion || c.criterion]}</span>
                  {m.source?.page ? <>, <Link className="underline" href={`/subjects/${subjectId}/resources/${m.source.source_id}?page=${m.source.page}`}>course page {m.source.page}</Link></> : null}
                  <span className="text-ink-muted">)</span>
                </p>
              ))}
              {c.status === "unscored" && <p className="mt-2 text-meta text-ink-muted">{c.rationale || "There is not enough reliable information to score this yet."} Unscored is not wrong.</p>}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
