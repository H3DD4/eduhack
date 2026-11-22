"use client";
// S03 Session outcome — UC17 (+ review-date persistence). Recognition only after accepted evidence; application and
// retention shown separately; reflection is optional self-report that cannot change evidence; 3-day default adjustable.
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { labelText } from "@/components/Roadmap";
import { SpeakButton } from "@/components/avatar/AvatarSpeakerContext";
import { SubjectShell } from "@/components/SubjectShell";
import { Companion, ErrorBox, EvidencePill, LiveRegion, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";

const STAGE_NAMES: Record<string, string> = {
  learn: "Learn", practice: "Practice", explanation: "Explain-back", followup: "Follow-up", transfer: "New application",
};

export default function Summary() {
  const { s, l } = useParams<{ s: string; l: string }>();
  const router = useRouter();
  const { data, error, reload } = useApi<any>(`/sessions/${l}/summary`);
  const [reflection, setReflection] = useState("");
  const [date, setDate] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (data) setDate(data.review?.due_on || data.default_review_on);
  }, [data]);

  const saveReflection = async (skipped: boolean) => {
    await api(`/sessions/${l}/reflection`, { method: "POST", json: { text: skipped ? "" : reflection, skipped } });
    setMsg(skipped ? "Reflection skipped." : "Reflection saved. It does not change your evidence.");
    reload();
  };
  const finish = async () => {
    setBusy(true);
    setErr(null);
    try {
      await api(`/sessions/${l}/review`, { method: "POST", json: { due_on: date } });
      await api(`/sessions/${l}/complete`, { method: "POST" });
      router.push("/today");
    } catch (e: any) {
      setErr(e.message);
      setBusy(false);
    }
  };

  return (
    <SubjectShell subjectId={s} crumb="Session summary" parent="roadmap">
      <LiveRegion message={msg} />
      <div className="max-w-prose space-y-6" data-screen="S03">
        {!data && !error && <Skeleton lines={5} />}
        {error && <ErrorBox message="The summary could not load. Your evidence is not lost." onRetry={reload} />}
        {data && (
          <>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-section">{data.concept.title}: what you showed</h2>
              <SpeakButton
                text={`${data.concept.title}: what you showed. Application: ${data.application}. Retention: ${data.retention}.`}
                title="Session summary"
                hint={data.concept.title}
                subjectId={s}
                label="Speak summary"
              />
            </div>
            {!data.has_receipts ? <p className="card">Checks pending — no evidence has been accepted yet.</p> : (
              <>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="card !p-4"><p className="text-meta font-semibold text-ink-muted">Application</p><p className="mt-1 font-bold">{data.application}</p></div>
                  <div className="card !p-4"><p className="text-meta font-semibold text-ink-muted">Retention</p><p className="mt-1">{data.retention}</p></div>
                </div>
                <section aria-labelledby="rec-h">
                  <h3 id="rec-h" className="font-bold">Evidence receipts</h3>
                  <ul className="mt-2 space-y-2">
                    {Object.entries(data.evidence_by_stage).map(([stage, evs]: [string, any]) => evs.map((e: any) => (
                      <li key={e.id} className="flex flex-wrap items-center justify-between gap-2 rounded-detail border border-border bg-surface px-3 py-2">
                        <span className="flex flex-wrap items-center gap-2"><span className="font-semibold">{STAGE_NAMES[stage] || stage}</span>
                          <EvidencePill label={e.label} text={e.label_text || labelText(e.label)} />
                          {e.outcome !== "exposure" && e.outcome !== "demonstrated" && <span className="text-meta text-ink-muted">({e.outcome.replace("_", " ")})</span>}
                        </span>
                        <Link className="btn-link" href={`/subjects/${s}/progress/evidence/${e.id}`}>Receipt<span className="sr-only"> for {STAGE_NAMES[stage]}</span></Link>
                      </li>
                    )))}
                  </ul>
                </section>
                {data.application.startsWith("Applied") && <Companion message="You applied it to a new situation without in-app help. A later review is what shows it stuck." />}
              </>
            )}
            <section aria-labelledby="refl-h" className="card space-y-3">
              <h3 id="refl-h" className="font-bold">Reflection (optional)</h3>
              {data.reflection ? (
                <p>{data.reflection.skipped ? "You skipped the reflection." : `“${data.reflection.text}”`}</p>
              ) : (
                <>
                  <label htmlFor="refl" className="label">What would you try next time? This note does not change your evidence score.</label>
                  <textarea id="refl" className="field !min-h-[80px]" value={reflection} onChange={(e) => setReflection(e.target.value)} />
                  <div className="flex flex-wrap gap-3">
                    <button className="btn-secondary" onClick={() => saveReflection(false)} disabled={!reflection.trim()}>Save reflection</button>
                    <button className="btn-secondary" onClick={() => saveReflection(true)}>Skip reflection</button>
                  </div>
                </>
              )}
            </section>
            <section aria-labelledby="rev-h" className="card space-y-3">
              <h3 id="rev-h" className="font-bold">Book a later review</h3>
              <label htmlFor="rev-date" className="label">Review date</label>
              <input id="rev-date" type="date" className="field !w-auto" value={date} min={new Date().toISOString().slice(0, 10)} onChange={(e) => setDate(e.target.value)} />
              <p className="text-meta text-ink-muted">Three days is an adjustable default — a scheduling hypothesis, not an optimum. Only a later review without help adds retention evidence.</p>
            </section>
            {err && <ErrorBox message={err} />}
            {data.parent_session_id ? (
              <button className="btn-primary" onClick={async () => { await finish(); router.push(`/subjects/${s}/sessions/${data.parent_session_id}`); }} disabled={busy}>Return to original task</button>
            ) : (
              <button className="btn-primary" onClick={finish} disabled={busy || !date}>{busy ? "Saving…" : "Finish and save review date"}</button>
            )}
          </>
        )}
      </div>
    </SubjectShell>
  );
}
