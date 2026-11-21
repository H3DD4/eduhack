"use client";
// S02 Active learning workspace — UC02/UC11–UC16/UC21/UC22. Focused shell (no global nav while active).
// Saves: local draft first ("On this device"), then server checkpoint with revision + owner lease ("Synced").
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { AppShell, useMe } from "@/components/AppShell";
import { ExplainFlow } from "@/components/session/ExplainFlow";
import { FocusSheet } from "@/components/session/FocusSheet";
import { ProfessorPanel } from "@/components/session/ProfessorPanel";
import { LearnStage, PracticeStage, RecallStage, TransferStage } from "@/components/session/Stages";
import { Dialog, ErrorBox, SaveBadge, SaveState, Skeleton } from "@/components/ui";
import { api, ApiError, deviceId } from "@/lib/api";

const STAGE_LABEL: Record<string, string> = {
  recall: "Recall", learn: "Learn", practice: "Practice", explanation: "Explain it back", followup: "One follow-up",
  transfer: "New application", summary: "Summary",
};

function Workspace() {
  const { s, l } = useParams<{ s: string; l: string }>();
  const router = useRouter();
  const { me, caps } = useMe();
  const [view, setView] = useState<any>(null);
  const [loadErr, setLoadErr] = useState<ApiError | null>(null);
  const [lease, setLease] = useState<string | null>(null);
  const [conflict, setConflict] = useState<"held" | "lost" | "stale" | null>(null);
  const [readOnly, setReadOnly] = useState(false);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [save, setSave] = useState<SaveState>("synced");
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [help, setHelp] = useState(false);
  const [locked, setLocked] = useState(false);
  const [focus, setFocus] = useState(false);
  const [pausing, setPausing] = useState(false);
  const [quiet, setQuiet] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [leaveOpen, setLeaveOpen] = useState(false);
  const revRef = useRef<number>(0);
  const leaseRef = useRef<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const localKey = `tf_draft_${l}`;

  const load = useCallback(async () => {
    try {
      const v = await api(`/sessions/${l}`);
      setView(v);
      revRef.current = v.session.revision;
      if (v.session.status === "draft") router.replace(`/subjects/${s}/sessions/${l}/setup`);
      if (v.session.status === "completed" || v.session.stage === "summary") router.replace(`/subjects/${s}/sessions/${l}/summary`);
      return v;
    } catch (e) {
      setLoadErr(e as ApiError);
    }
  }, [l, router, s]);

  const acquire = useCallback(async (takeover = false) => {
    try {
      const r = await api(`/sessions/${l}/lease`, { method: "POST", json: { device_id: deviceId(), takeover } });
      leaseRef.current = r.lease_token;
      setLease(r.lease_token);
      revRef.current = r.revision;
      setConflict(null);
      setReadOnly(false);
      await load();
    } catch (e) {
      if ((e as ApiError).code === "LEASE_HELD") setConflict("held");
    }
  }, [l, load]);

  useEffect(() => {
    load().then((v) => {
      if (!v) return;
      let local: any = null;
      try { local = JSON.parse(localStorage.getItem(localKey) || "null"); } catch { /* storage unavailable */ }
      const server = v.session.checkpoint?.drafts || {};
      if (local && local.rev >= v.session.revision) {
        setDrafts({ ...server, ...local.drafts });
        setSave("device");
      } else setDrafts(server);
      setQuiet(!!v.session.config?.focus_quiet);
    });
    acquire();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [l]);

  const pushCheckpoint = useCallback(async (d: Record<string, string>, extra: Record<string, any> = {}) => {
    if (!leaseRef.current) return false;
    setSave("saving");
    try {
      const r = await api(`/sessions/${l}/checkpoint`, { method: "PUT", headers: { "x-lease-token": leaseRef.current },
        json: { expected_revision: revRef.current, checkpoint: { drafts: d, ...extra } } });
      revRef.current = r.revision;
      setSave("synced");
      setSavedAt(r.saved_at);
      try { localStorage.setItem(localKey, JSON.stringify({ rev: r.revision, drafts: d })); } catch { /* noop */ }
      return true;
    } catch (e) {
      const code = (e as ApiError).code;
      setSave("device");
      if (code === "LEASE_LOST" || code === "LEASE_HELD") setConflict("lost");
      else if (code === "STALE_REVISION") setConflict("stale");
      return false;
    }
  }, [l, localKey]);

  const setDraft = (k: string, v: string) => {
    if (readOnly) return;
    const next = { ...drafts, [k]: v };
    setDrafts(next);
    try {
      localStorage.setItem(localKey, JSON.stringify({ rev: revRef.current, drafts: next }));
      setSave("device");
    } catch {
      setSave("unsaved");
    }
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => pushCheckpoint(next), 1200);
  };

  const advance = async () => {
    if (timer.current) clearTimeout(timer.current);
    await pushCheckpoint(drafts);
    try {
      const v = await api(`/sessions/${l}/advance`, { method: "POST", json: { expected_revision: revRef.current } });
      setView(v);
      revRef.current = v.session.revision;
      setHelp(false);
      if (v.session.stage === "summary") router.push(`/subjects/${s}/sessions/${l}/summary`);
      setTimeout(() => document.getElementById("st-h")?.focus(), 60);
    } catch (e) {
      const ae = e as ApiError;
      if (ae.code === "STALE_REVISION") { await load(); }
      else setNotice(ae.message);
    }
  };

  const reload = async () => {
    const v = await load();
    if (v) setLocked(!!v.lock);
  };

  // Poll while a follow-up/transfer job is preparing (retry reconciles the same job).
  useEffect(() => {
    const packPending = view?.pack_status === "pending" && ["learn", "practice"].includes(view?.session?.stage);
    if (!packPending && (!view?.pending_job || ["succeeded", "failed", "cancelled"].includes(view.pending_job.status))) return;
    const id = setInterval(load, 1500);
    return () => clearInterval(id);
  }, [view?.pending_job, view?.pack_status, view?.session?.stage, load]);

  const saveAndPause = async () => {
    setPausing(true);
    if (timer.current) clearTimeout(timer.current);
    try {
      await api(`/sessions/${l}/pause`, { method: "POST", headers: { "x-lease-token": leaseRef.current || "" },
        json: { expected_revision: revRef.current, checkpoint: { drafts, phase: view?.session.stage } } });
      try { localStorage.removeItem(localKey); } catch { /* noop */ }
      router.push("/today");
    } catch (e) {
      setPausing(false);
      setNotice(`Could not save: ${(e as ApiError).message} Retry, or leave without saving (your local draft stays on this device).`);
    }
  };
  const saveAndExit = async () => {
    if (timer.current) clearTimeout(timer.current);
    const ok = readOnly || (await pushCheckpoint(drafts));
    if (!ok) { setLeaveOpen(true); return; }
    router.push("/today");
  };
  const resume = async () => {
    try {
      const v = await api(`/sessions/${l}/resume`, { method: "POST", headers: { "x-lease-token": leaseRef.current || "" } });
      setView(v);
      revRef.current = v.session.revision;
    } catch (e) {
      if ((e as ApiError).code === "LEASE_LOST") setConflict("lost");
    }
  };

  if (loadErr) return <div className="p-6"><ErrorBox title="Not available" message={loadErr.status === 404 ? "This session does not exist or is not yours." : loadErr.message} onRetry={load}><Link className="btn-secondary" href="/today">Go to Today</Link></ErrorBox></div>;
  if (!view) return <div className="p-6"><Skeleton lines={6} label="Loading session" /></div>;

  const sess = view.session;
  const stage = sess.stage;
  const stages = sess.stages.filter((x: string) => x !== "summary");
  const pos = stages.indexOf(stage) + 1;
  const cur = view.current_task;
  const draftKey = cur ? `task:${cur.id}` : stage;
  const draft = drafts[draftKey] || "";
  const onDraft = (t: string) => setDraft(draftKey, t);
  const paused = sess.status === "paused";
  const lockedNow = !!view.lock || locked;

  return (
    <div className="min-h-screen" data-screen="S02" data-stage={stage} data-quiet={quiet ? "1" : "0"}>
      <header className="sticky top-0 z-30 border-b-2 border-ink bg-surface">
        <div className="mx-auto flex max-w-overview items-center justify-between gap-3 px-4 py-2 md:px-6">
          <button className="btn-secondary" onClick={saveAndExit}>Save and exit</button>
          <div className="min-w-0 text-center">
            <p className="truncate text-problem">{view.concept.title}</p>
            <p className="text-meta text-ink-muted">Step {pos} of {stages.length}: {STAGE_LABEL[stage]}</p>
          </div>
          <div className="flex items-center gap-2">
            <span className="hidden sm:inline"><SaveBadge state={readOnly ? "unsaved" : save} at={savedAt} /></span>
            <button className="btn-secondary" onClick={() => setFocus(true)} disabled={paused}>Focus</button>
          </div>
        </div>
        <ol aria-label="Session steps" className="mx-auto flex max-w-overview flex-wrap gap-2 px-4 pb-3 md:px-6">
          {stages.map((x: string, i: number) => {
            const state = i + 1 < pos ? "done" : i + 1 === pos ? "now" : "next";
            return (
              <li key={x} aria-current={state === "now" ? "step" : undefined}
                className={`inline-flex items-center gap-1.5 rounded-pill border-2 px-3 py-1 text-meta transition-colors ${state === "now" ? "border-ink bg-ink text-white" : state === "done" ? "border-ink bg-hl text-ink" : "border-border bg-surface text-ink-muted"}`}>
                <span aria-hidden>{state === "done" ? "✓" : state === "now" ? "●" : "○"}</span>{STAGE_LABEL[x] || x}
              </li>
            );
          })}
        </ol>
      </header>

      {notice && (
        <div className="mx-auto mt-4 max-w-overview px-4 md:px-6">
          <ErrorBox message={notice}><button className="btn-secondary" onClick={() => setNotice(null)}>Dismiss</button></ErrorBox>
        </div>
      )}
      {conflict && (
        <div role="alert" className="mx-auto mt-4 max-w-overview px-4 md:px-6">
          <ErrorBox title="Another session has newer work" message={conflict === "stale" ? "A newer change was saved first. Reload to see it; your local draft stays on this device." : "This session is open on another tab or device. Open it read-only here, or take over (the other copy keeps its draft separately)."}>
            {conflict === "stale" ? <button className="btn-secondary" onClick={() => { setConflict(null); load(); }}>Reload</button> : (
              <>
                <button className="btn-secondary" onClick={() => { setReadOnly(true); setConflict(null); }}>Open read-only</button>
                <button className="btn-primary" onClick={() => acquire(true)}>Take over</button>
              </>
            )}
          </ErrorBox>
        </div>
      )}

      <main id="main" className="mx-auto grid max-w-overview gap-6 px-4 py-6 md:px-6 xl:grid-cols-[minmax(0,48rem)_320px]">
        <div className="min-w-0 max-w-prose">
          <p className="mb-4 text-meta text-ink-muted">Objective: {view.concept.objective}</p>
          {paused ? (
            <div className="card space-y-3">
              <h2 className="text-section">Paused</h2>
              <p>Your work is saved{stage === "transfer" && lockedNow ? ". Independent mode stays on: help remains unavailable until you finish or switch to guided practice" : ""}.</p>
              <button className="btn-primary" onClick={resume} disabled={!lease}>Resume</button>
            </div>
          ) : readOnly ? (
            <p className="card">Read-only view. Take over to continue here.</p>
          ) : (
            <>
              {stage === "recall" && <RecallStage view={view} draft={draft} onDraft={onDraft} onContinue={advance} />}
              {stage === "learn" && <LearnStage view={view} subjectId={s} sessionId={l} draft={draft} onDraft={onDraft} onContinue={advance} />}
              {stage === "practice" && <PracticeStage view={view} subjectId={s} draft={draft} onDraft={onDraft} onHelp={() => setHelp(true)} onReload={reload} onContinue={advance} />}
              {(stage === "explanation" || stage === "followup") && (cur ? (
                <div className="space-y-4">
                  {stage === "followup" && <p className="text-meta font-semibold text-help">One more question about that idea.</p>}
                  <h2 id="st-h" tabIndex={-1} className="text-problem font-bold">{cur.prompt}</h2>
                  {cur.context?.rubric && (
                    <details className="rounded-detail border border-border p-3">
                      <summary className="cursor-pointer font-semibold">What will be checked (declared before you answer)</summary>
                      <ul className="mt-2 list-disc pl-5 text-meta">
                        {cur.context.rubric.criteria.filter((c: any) => c.applicable && (stage !== "followup" || [cur.targets_criterion, "correctness"].includes(c.criterion))).map((c: any) => (
                          <li key={c.criterion}>{c.criterion.replace("_", " ")}{c.essentials.length ? `: ${c.essentials.map((e: any) => e.description).join("; ")}` : ""}</li>
                        ))}
                      </ul>
                      <p className="mt-2 text-meta text-ink-muted">{cur.context.rubric.approval_label}</p>
                    </details>
                  )}
                  <ExplainFlow key={cur.id} task={cur} subjectId={s} caps={caps} defaultInput={sess.config?.input_mode === "voice" ? "voice" : "text"}
                    draft={draft} onDraft={onDraft} onAssessed={reload} retentionPref={me?.preferences?.audio_retention}
                    next={() => (
                      <div className="flex flex-wrap gap-3">
                        <button className="btn-primary" onClick={advance}>{stage === "explanation" ? "Answer one follow-up" : "Try new application"}</button>
                        <Link className="btn-secondary" href={`/subjects/${s}/progress`}>Review evidence</Link>
                      </div>
                    )} />
                  {cur.status !== "committed" && <button className="btn-help" onClick={() => setHelp(true)}>Get help</button>}
                </div>
              ) : <div className="card" aria-busy="true"><p>Preparing one question about your reasoning…</p><button className="btn-primary mt-3" disabled>Preparing question</button></div>)}
              {stage === "transfer" && <TransferStage view={view} subjectId={s} draft={draft} onDraft={onDraft} onReload={reload} onReflect={advance} onHelp={() => setHelp(true)} />}
            </>
          )}
        </div>
        {help && !paused && (
          lockedNow && cur?.mode === "independent-transfer" ? (
            <aside className="card h-fit" role="alert">
              <p className="font-semibold">Independent application: no in-app lesson or hint access.</p>
              <p className="mt-2 text-meta">Use “Use guided help” on the task to switch (your work is kept), or return to the task.</p>
              <button className="btn-secondary mt-3" onClick={() => setHelp(false)}>Return to task</button>
            </aside>
          ) : (
            <ProfessorPanel task={cur} subjectId={s} onClose={() => setHelp(false)} onChanged={() => reload()} onLocked={() => setLocked(true)} />
          )
        )}
      </main>
      <FocusSheet open={focus} onClose={() => setFocus(false)} onPause={saveAndPause} quiet={quiet} setQuiet={setQuiet}
        timerMinutes={sess.config?.timer_minutes ?? null} saving={pausing} />
      <Dialog open={leaveOpen} title="Leave without syncing?" onClose={() => setLeaveOpen(false)}>
        <p>This draft is not synced. It stays on this device only.</p>
        <div className="mt-6 flex flex-wrap gap-3">
          <button className="btn-primary" onClick={() => setLeaveOpen(false)}>Stay and retry</button>
          <button className="btn-secondary" onClick={() => router.push("/today")}>Leave anyway</button>
        </div>
      </Dialog>
    </div>
  );
}

export default function Page() {
  return <AppShell focused><Workspace /></AppShell>;
}
