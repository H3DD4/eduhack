"use client";
// W08 Evidence receipt (minimal) — task/date/origin/mode, answer/help, criteria with quotes, source, delete (UC37).
// Disputes (UC28) arrive in M3.
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { labelText } from "@/components/Roadmap";
import { RubricFeedback } from "@/components/session/RubricFeedback";
import { SubjectShell } from "@/components/SubjectShell";
import { Dialog, ErrorBox, EvidencePill, OriginLabel, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";

export default function Receipt() {
  const { s, e } = useParams<{ s: string; e: string }>();
  const { data, error, reload } = useApi<any>(`/evidence/${e}`);
  const [confirmDel, setConfirmDel] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const ev = data?.evidence;
  return (
    <SubjectShell subjectId={s} crumb="Evidence receipt">
      <div data-screen="W08" className="max-w-prose space-y-4">
        {!data && !error && <Skeleton lines={6} />}
        {error && <ErrorBox message={error.status === 404 ? "Not available." : error.message} onRetry={reload} />}
        {done && <p role="status" className="card">{done}</p>}
        {data?.deleted && <p className="card">This attempt was deleted. Only content-free deletion metadata remains.</p>}
        {ev && !data.deleted && (
          <>
            <div className="card space-y-2">
              <p className="flex flex-wrap items-center gap-2"><EvidencePill label={ev.label} text={ev.label_text || labelText(ev.label)} />
                <span className="text-meta text-ink-muted">{ev.stage} · {new Date(ev.created_at).toLocaleString()} · outcome: {ev.outcome.replace("_", " ")}</span></p>
              {data.concept && <p>Concept: <strong>{data.concept.title}</strong></p>}
              {data.task && <p className="flex flex-wrap items-center gap-2">Task: {data.task.prompt} <OriginLabel origin={data.task.origin} detail={data.task.origin_detail} /></p>}
              {data.task?.mode && <p className="text-meta">Mode: {data.task.mode}{ev.assistance?.note ? ` · ${ev.assistance.note}` : ""}</p>}
              {data.task?.novelty && <p className="text-meta">Novelty: {data.task.novelty.validated_by}</p>}
              <p className="text-meta">Help used: {ev.assistance?.help_steps?.length ? ev.assistance.help_steps.join(", ") : "none recorded"}
                {ev.assistance?.revealed ? " · worked solution viewed" : ""}{ev.assistance?.corrective_feedback ? " · corrective feedback shown" : ""}
                {ev.assistance?.conversion ? " · switched to guided practice" : ""}. Outside help: {ev.assistance?.student_reported ?? "unknown"}.</p>
            </div>
            {data.attempt && (
              <div className="card">
                <p className="font-semibold">Your {data.attempt.response_kind === "audio" ? "confirmed transcript" : "answer"}</p>
                <p className="mt-1 whitespace-pre-line">{data.attempt.response_text}</p>
                {data.attempt.supplement_text && <p className="mt-2 text-meta">Added reasoning (separate): {data.attempt.supplement_text}</p>}
              </div>
            )}
            {data.assessment && <div className="card"><RubricFeedback assessment={data.assessment} subjectId={s} /></div>}
            <div className="flex flex-wrap gap-3">
              <Link className="btn-primary" href={`/subjects/${s}/roadmap${ev.concept_id ? `/concepts/${ev.concept_id}` : ""}`}>Try fresh check</Link>
              {ev.task_id && <button className="btn-secondary" onClick={() => setConfirmDel(true)}>Delete attempt</button>}
            </div>
            <p className="text-meta text-ink-muted">Challenging an assessment arrives in M3. Flagging never shares your content automatically.</p>
          </>
        )}
      </div>
      <Dialog open={confirmDel} title="Delete this attempt?" onClose={() => setConfirmDel(false)}>
        <p>This removes your answer, any transcript and audio for this task, and the evidence derived from it. Your progress is recomputed. Only content-free deletion metadata is kept.</p>
        <div className="mt-6 flex flex-wrap gap-3">
          <button className="btn-primary" onClick={async () => { const r = await api(`/evidence/${e}/attempt`, { method: "DELETE" }); setConfirmDel(false); setDone(`Deletion ${r.status}. ${r.note}`); reload(); }}>Delete attempt</button>
          <button className="btn-secondary" onClick={() => setConfirmDel(false)}>Cancel</button>
        </div>
      </Dialog>
    </SubjectShell>
  );
}
