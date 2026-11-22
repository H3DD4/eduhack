"use client";
/* Study material: résumé, fiche deck (flip + Leitner boxes kept on this device), ask-your-course box. */
import { useEffect, useMemo, useState } from "react";
import { SpeakButton } from "@/components/avatar/AvatarSpeakerContext";
import { ApiError } from "@/lib/api";
import { tutor, type Citation, type Fiche } from "@/lib/tutor";
import { Citations } from "./bits";
import { Md, Tex } from "./Tex";

export function ResumeView({ content }: { content: any }) {
  return (
    <div className="space-y-5">
      {content.sections.map((s: any, i: number) => (
        <section key={i} className="game-card space-y-2 p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-problem font-semibold">{s.heading}</h3>
            <SpeakButton
              text={`${s.heading}. ${(s.bullets || []).join(". ")}. ${(s.formulas || []).join(". ")}. ${(s.pitfalls || []).join(". ")}`}
              title={s.heading}
              hint={s.heading}
              label="Speak section"
            />
          </div>
          {s.bullets?.length > 0 && <ul className="list-disc space-y-1 pl-6">{s.bullets.map((b: string, j: number) => <li key={j}><Tex text={b} /></li>)}</ul>}
          {s.formulas?.length > 0 && (
            <div className="rounded-control border-2 border-ink bg-soft p-3">
              <p className="text-meta font-semibold">Formulas</p>
              {s.formulas.map((f: string, j: number) => <p key={j}><Tex text={f} /></p>)}
            </div>
          )}
          {s.pitfalls?.length > 0 && (
            <div className="rounded-control border-2 border-ink bg-review-surface p-3">
              <p className="text-meta font-semibold">Watch out</p>
              <ul className="list-disc pl-6">{s.pitfalls.map((p: string, j: number) => <li key={j}><Tex text={p} /></li>)}</ul>
            </div>
          )}
          <Citations items={s.citations} />
        </section>
      ))}
    </div>
  );
}

const KEY = (id: string) => `tf-fiches-${id}`;

export function FicheDeck({ artifactId, fiches }: { artifactId: string; fiches: Fiche[] }) {
  const [box, setBox] = useState<Record<string, number>>({});
  const [i, setI] = useState(0);
  const [flipped, setFlipped] = useState(false);
  useEffect(() => {
    try { setBox(JSON.parse(localStorage.getItem(KEY(artifactId)) || "{}")); } catch { /* storage unavailable */ }
  }, [artifactId]);
  const save = (b: Record<string, number>) => { setBox(b); try { localStorage.setItem(KEY(artifactId), JSON.stringify(b)); } catch { /* ignore */ } };
  // lowest Leitner box first: cards you miss come back sooner
  const order = useMemo(() => [...fiches].sort((a, b) => (box[a.id] || 0) - (box[b.id] || 0)), [fiches, box]);
  const card = order[i % Math.max(1, order.length)];
  if (!card) return <p>No cards.</p>;
  const known = fiches.filter((f) => (box[f.id] || 0) >= 2).length;
  const next = (knew: boolean) => {
    save({ ...box, [card.id]: knew ? (box[card.id] || 0) + 1 : 0 });
    setFlipped(false);
    setI((x) => x + 1);
  };
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3 text-meta">
        <div className="flex items-center gap-3">
          <div className="bar w-48"><span style={{ width: `${Math.round((known / fiches.length) * 100)}%` }} /></div>
          <span>{known}/{fiches.length} known</span>
        </div>
        <SpeakButton text={flipped ? card.back : card.front} title={card.fiche_type} hint={card.concept_key} label={flipped ? "Speak answer" : "Speak question"} />
      </div>
      <button type="button" onClick={() => setFlipped((f) => !f)} aria-label={flipped ? "Show the question" : "Show the answer"}
        className="game-card block min-h-[220px] w-full p-8 text-left transition hover:-translate-y-1">
        <span className="badge mb-3">{card.fiche_type}</span>
        <div className="text-problem">{flipped ? <Md text={card.back} /> : <Tex text={card.front} />}</div>
        {!flipped && <p className="mt-6 text-meta text-ink-muted">Answer in your head, then click to flip.</p>}
        {flipped && <Citations items={card.citations as Citation[]} />}
      </button>
      {flipped && (
        <div className="flex gap-2">
          <button className="btn-secondary" onClick={() => next(false)}>Again</button>
          <button className="btn-primary" onClick={() => next(true)}>I knew it</button>
        </div>
      )}
    </div>
  );
}

export function AskBox({ trackId, mode = "study" }: { trackId: string; mode?: "study" | "practice" }) {
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [a, setA] = useState<{ answer: string; citations: Citation[]; grounded: boolean } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const go = async () => {
    setBusy(true); setErr(null);
    try { setA(await tutor.ask(trackId, q, mode)); } catch (e) { setErr((e as ApiError).message); } finally { setBusy(false); }
  };
  return (
    <div className="game-card space-y-3 p-5">
      <label className="label" htmlFor="ask">Ask your course</label>
      <div className="flex gap-2">
        <input id="ask" className="field flex-1" value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. Why is (uv)' not u'v'?"
          onKeyDown={(e) => { if (e.key === "Enter" && q.trim().length > 1) go(); }} />
        <button className="btn-primary" disabled={busy || q.trim().length < 2} onClick={go}>{busy ? "…" : "Ask"}</button>
      </div>
      {err && <p className="rounded-control bg-review-surface p-2">{err}</p>}
      {a && (
        <div className="fade-in space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            {!a.grounded ? <p className="text-meta text-ink-muted">Not found in your documents.</p> : <span className="text-meta text-ink-muted">Grounded in your course</span>}
            <SpeakButton text={a.answer} title="Course Q&A" label="Speak answer" />
          </div>
          <Md text={a.answer} />
          <Citations items={a.citations} />
        </div>
      )}
    </div>
  );
}
