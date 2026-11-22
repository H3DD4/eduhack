"use client";
// S01 Session setup — UC10/UC23/UC38. Reserves the validation bundle BEFORE capture/typed assessment.
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { QuotaDialog } from "@/components/QuotaDialog";
import { SubjectShell } from "@/components/SubjectShell";
import { ErrorBox, Skeleton } from "@/components/ui";
import { api, ApiError, newKey } from "@/lib/api";
import { useApi } from "@/lib/hooks";

export default function SessionSetup() {
  const { s, l } = useParams<{ s: string; l: string }>();
  const router = useRouter();
  const { data, error, reload } = useApi<any>(`/sessions/${l}`);
  const me = useApi<any>("/auth/me");
  const [input, setInput] = useState<"text" | "voice">("text");
  const [quiet, setQuiet] = useState(false);
  const [timer, setTimer] = useState<string>("off");
  const [busy, setBusy] = useState(false);
  const [quota, setQuota] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [key] = useState(newKey);

  useEffect(() => {
    if (me.data?.user?.preferences?.input_preference === "voice") setInput("voice");
  }, [me.data]);
  useEffect(() => {
    if (data && data.session.status !== "draft") router.replace(`/subjects/${s}/sessions/${l}`);
  }, [data, l, router, s]);

  const start = async () => {
    setBusy(true);
    setErr(null);
    try {
      await api(`/sessions/${l}/start`, { method: "POST", json: { idempotency_key: key,
        config: { input_mode: input, focus_quiet: quiet, timer_minutes: timer === "off" ? null : Number(timer) } } });
      router.push(`/subjects/${s}/sessions/${l}`);
    } catch (e) {
      const ae = e as ApiError;
      if (ae.code === "QUOTA_EXHAUSTED") setQuota(ae.data);
      else setErr(ae.message);
      setBusy(false);
    }
  };

  const q = data?.quota;
  return (
    <SubjectShell subjectId={s} crumb="Session setup" parent="roadmap">
      <div className="max-w-prose space-y-6" data-screen="S01">
        {!data && !error && <Skeleton />}
        {error && <ErrorBox message="This session could not load." onRetry={reload} />}
        {err && <ErrorBox message={err} />}
        {data && (
          <>
            <div>
              <p className="text-meta font-semibold text-ink-muted">{data.session.kind === "learn" ? "Learn" : "Practice"}</p>
              <h2 className="text-section">{data.concept.title}</h2>
              <p className="mt-1">Objective: {data.concept.objective || "—"}</p>
            </div>
            <div className="card space-y-2">
              <p className="font-semibold">What this session includes</p>
              <ol className="list-decimal space-y-1 pl-5">
                {data.session.stages.filter((x: string) => x !== "summary").map((st: string) => (
                  <li key={st}>{({ recall: "Quick recall (or “I don't know”)", learn: "Cited course section and a different example",
                    practice: "Practice with help available at any time", explanation: "Explain it back (voice or text) — you confirm the text first",
                    followup: "One follow-up question", transfer: "A new problem without in-app help (you can switch to guided help)" } as any)[st]}</li>
                ))}
              </ol>
            </div>
            <fieldset>
              <legend className="label">Answer by</legend>
              <div className="flex flex-wrap gap-2">
                {(["text", "voice"] as const).map((v) => (
                  <label key={v} className={`flex min-h-[48px] items-center gap-2 rounded-control border-2 px-4 ${input === v ? "border-action bg-success-surface" : "border-stroke bg-surface"}`}>
                    <input type="radio" name="input" checked={input === v} onChange={() => setInput(v)} /> {v === "text" ? "Text" : "Voice"}
                  </label>
                ))}
                <span className="pill self-center text-ink-muted">Paper and Code modes arrive later</span>
              </div>
              <p className="mt-2 text-meta text-ink-muted">Both use the same rubric. The microphone is only requested when you choose to record.</p>
            </fieldset>
            <fieldset>
              <legend className="label">Focus (optional)</legend>
              <label className="flex min-h-[44px] items-center gap-2"><input type="checkbox" checked={quiet} onChange={(e) => setQuiet(e.target.checked)} /> Quiet mode (hides in-app decoration; never changes your evidence)</label>
              <label className="mt-2 flex flex-wrap items-center gap-2">Timer
                <select className="field !w-auto" value={timer} onChange={(e) => setTimer(e.target.value)}>
                  <option value="off">Off</option><option value="15">15 min</option><option value="25">25 min</option><option value="45">45 min</option>
                </select>
                <span className="text-meta text-ink-muted">No time credit and no penalty for pausing.</span>
              </label>
            </fieldset>
            <p className="text-meta text-ink-muted">
              Starting reserves {3} units for the explanation, follow-up and application checks so they are never interrupted.
              {q ? ` Available: ${q.available_units} of ${q.period_units}.` : ""}
            </p>
            <div className="flex flex-wrap gap-3">
              <button className="btn-primary" onClick={start} disabled={busy} aria-busy={busy}>{busy ? "Preparing…" : "Start session"}</button>
              <button className="btn-secondary" onClick={() => router.back()}>Back</button>
            </div>
          </>
        )}
      </div>
      <QuotaDialog open={!!quota} info={quota} subjectId={s} onClose={() => setQuota(null)} onRetry={() => { setQuota(null); start(); }} />
    </SubjectShell>
  );
}
