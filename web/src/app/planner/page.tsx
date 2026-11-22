"use client";
// G03 Planner — calendar of exams, certificates, assignments and goals (yours + the wizard's exam date), booked and
// memory-based reviews, and "this week's priorities" ranked by importance x concepts left / days left.
import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { ErrorBox, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";

const TYPE: Record<string, { label: string; icon: string; cls: string }> = {
  exam: { label: "Exam", icon: "🎯", cls: "bg-review-surface text-review" },
  certificate: { label: "Certificate", icon: "🏅", cls: "bg-help-surface text-help" },
  assignment: { label: "Assignment", icon: "📝", cls: "bg-soft text-soft-fg" },
  goal: { label: "Goal", icon: "⭐", cls: "bg-success-surface text-ink" },
  review: { label: "Review", icon: "🔁", cls: "bg-surface-subtle text-ink" },
  memory_review: { label: "Refresh", icon: "↻", cls: "bg-surface-subtle text-ink-muted" },
};
const IMPORTANCE = ["", "Low", "Normal", "High"];
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

export default function Planner() {
  const [month, setMonth] = useState(() => { const d = new Date(); return new Date(d.getFullYear(), d.getMonth(), 1); });
  const start = new Date(month.getFullYear(), month.getMonth(), 1 - ((month.getDay() + 6) % 7)); // Monday grid start
  const end = new Date(start); end.setDate(start.getDate() + 41);
  const { data, error, reload } = useApi<any>(`/planner?start=${iso(start)}&end=${iso(end)}`);
  const upcoming = useApi<any>(`/planner?start=${iso(new Date())}&end=${iso(new Date(Date.now() + 120 * 864e5))}`);
  const [form, setForm] = useState({ title: "", kind: "exam", due_on: "", importance: 2, subject_id: "" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  const byDay = useMemo(() => {
    const m: Record<string, any[]> = {};
    (data?.events ?? []).forEach((e: any) => (m[e.date] ||= []).push(e));
    return m;
  }, [data]);
  const refresh = () => { reload(); upcoming.reload(); };

  const add = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      await api("/deadlines", { method: "POST", json: { ...form, subject_id: form.subject_id || null } });
      setForm({ title: "", kind: "exam", due_on: "", importance: 2, subject_id: "" });
      refresh();
    } catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  };
  const patch = async (id: string, json: any) => { await api(`/deadlines/${id}`, { method: "PATCH", json }).catch((x) => setErr(x.message)); refresh(); };
  const remove = async (id: string) => { await api(`/deadlines/${id}`, { method: "DELETE" }).catch((x) => setErr(x.message)); refresh(); };

  const today = iso(new Date());
  const cells = Array.from({ length: 42 }, (_, i) => { const d = new Date(start); d.setDate(start.getDate() + i); return d; });
  const dayEvents = selected ? byDay[selected] ?? [] : [];

  return (
    <AppShell crumbs={[{ label: "Planner" }]}>
      <div data-screen="G03" className="space-y-6">
        <div>
          <h1 className="text-page-compact lg:text-page">Planner</h1>
          <p className="text-ink-muted">Your exams, certificates and deadlines, your review dates, and what to study first.</p>
        </div>
        {err && <ErrorBox message={err} />}
        {error && <ErrorBox message="The planner could not load." onRetry={reload} />}

        {upcoming.data?.priorities?.length > 0 && (
          <section aria-labelledby="prio-h" className="hero p-6">
            <div className="relative z-10 space-y-3">
              <h2 id="prio-h" className="text-section">This week&apos;s priorities</h2>
              <ol className="grid gap-3 md:grid-cols-2">
                {upcoming.data.priorities.slice(0, 4).map((p: any, i: number) => (
                  <li key={`${p.subject_id}-${p.due_on}`} className="game-card p-4">
                    <p className="text-meta font-bold">#{i + 1} · {p.deadline} · in {p.days_left} day(s)</p>
                    <p className="font-bold">{p.subject_name}</p>
                    <p className="text-meta text-ink-muted">{p.reason}</p>
                    <p className="text-meta">Pace: {p.pace}</p>
                    <Link className="btn-primary mt-2" href={p.next_href}>Study now</Link>
                  </li>
                ))}
              </ol>
            </div>
          </section>
        )}

        <div className="grid gap-6 xl:grid-cols-[1fr_360px]">
          <section aria-labelledby="cal-h" className="game-card p-4 md:p-5">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h2 id="cal-h" className="text-section !text-[1.25rem]">{month.toLocaleDateString(undefined, { month: "long", year: "numeric" })}</h2>
              <div className="flex gap-2">
                <button className="btn-secondary !min-h-[40px]" aria-label="Previous month" onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))}>←</button>
                <button className="btn-secondary !min-h-[40px]" onClick={() => { const d = new Date(); setMonth(new Date(d.getFullYear(), d.getMonth(), 1)); }}>Today</button>
                <button className="btn-secondary !min-h-[40px]" aria-label="Next month" onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))}>→</button>
              </div>
            </div>
            {!data && !error && <Skeleton lines={6} />}
            {data && (
              <div className="grid grid-cols-7 gap-1" role="grid" aria-label="Calendar">
                {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => <div key={d} className="text-center text-meta text-ink-muted">{d}</div>)}
                {cells.map((d) => {
                  const k = iso(d), evs = byDay[k] ?? [], other = d.getMonth() !== month.getMonth();
                  return (
                    <button key={k} role="gridcell" onClick={() => setSelected(k)} aria-label={`${d.toDateString()}: ${evs.length} item(s)`}
                      aria-selected={selected === k}
                      className={`min-h-[78px] rounded-detail border p-1 text-left align-top transition hover:border-ink ${other ? "opacity-50" : ""} ${k === today ? "border-2 border-action" : "border-border"} ${selected === k ? "bg-soft" : "bg-surface"}`}>
                      <span className="text-meta font-bold">{d.getDate()}</span>
                      <span className="mt-1 flex flex-col gap-0.5">
                        {evs.slice(0, 3).map((e: any, i: number) => (
                          <span key={i} className={`truncate rounded px-1 text-[0.7rem] ${TYPE[e.type]?.cls ?? ""} ${e.done ? "line-through" : ""}`}>
                            {TYPE[e.type]?.icon} {e.title}
                          </span>
                        ))}
                        {evs.length > 3 && <span className="text-[0.7rem] text-ink-muted">+{evs.length - 3} more</span>}
                      </span>
                    </button>
                  );
                })}
              </div>
            )}
            <ul className="mt-3 flex flex-wrap gap-3 text-meta" aria-label="Legend">
              {Object.entries(TYPE).map(([k, t]) => <li key={k}><span className={`rounded px-1 ${t.cls}`}>{t.icon} {t.label}</span></li>)}
            </ul>
            {selected && (
              <div className="mt-4 rounded-detail border-2 border-ink p-3" aria-live="polite">
                <p className="font-bold">{new Date(selected + "T00:00:00").toDateString()}</p>
                {dayEvents.length === 0 ? <p className="text-meta text-ink-muted">Nothing planned. Add a deadline on the right.</p> : (
                  <ul className="mt-1 space-y-1">
                    {dayEvents.map((e: any, i: number) => (
                      <li key={i} className="text-meta">{TYPE[e.type]?.icon} {e.title}{e.subject_name ? ` · ${e.subject_name}` : ""}
                        {e.subject_id && <Link className="btn-link ml-2" href={e.concept_id ? `/subjects/${e.subject_id}/roadmap/concepts/${e.concept_id}` : `/subjects/${e.subject_id}/start`}>Open</Link>}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </section>

          <aside className="space-y-4">
            <form onSubmit={add} className="game-card space-y-3 p-5" aria-labelledby="add-h">
              <h2 id="add-h" className="text-section !text-[1.2rem]">Add a deadline</h2>
              <div><label htmlFor="dl-title" className="label">Name</label>
                <input id="dl-title" className="field" value={form.title} required maxLength={200} placeholder="e.g. Final exam, AWS certificate"
                  onChange={(e) => setForm({ ...form, title: e.target.value })} /></div>
              <div className="grid grid-cols-2 gap-2">
                <div><label htmlFor="dl-kind" className="label">Type</label>
                  <select id="dl-kind" className="field" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
                    <option value="exam">Exam</option><option value="certificate">Certificate</option>
                    <option value="assignment">Assignment</option><option value="goal">Goal</option>
                  </select></div>
                <div><label htmlFor="dl-date" className="label">Date</label>
                  <input id="dl-date" type="date" className="field" required value={form.due_on} onChange={(e) => setForm({ ...form, due_on: e.target.value })} /></div>
              </div>
              <div><label htmlFor="dl-subject" className="label">Subject (optional)</label>
                <select id="dl-subject" className="field" value={form.subject_id} onChange={(e) => setForm({ ...form, subject_id: e.target.value })}>
                  <option value="">— none —</option>
                  {(data?.subjects ?? []).map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select></div>
              <fieldset><legend className="label">Importance</legend>
                <div className="flex gap-2">{[1, 2, 3].map((n) => (
                  <button key={n} type="button" className="chip" aria-pressed={form.importance === n} onClick={() => setForm({ ...form, importance: n })}>{IMPORTANCE[n]}</button>
                ))}</div></fieldset>
              <button className="btn-primary w-full" disabled={busy}>{busy ? "Saving…" : "Add to calendar"}</button>
              <p className="text-meta text-ink-muted">Tie it to a subject: the priorities then tell you how many concepts per week to cover before that date.</p>
            </form>

            <section className="game-card space-y-2 p-5" aria-labelledby="up-h">
              <h2 id="up-h" className="text-section !text-[1.2rem]">Coming up</h2>
              {!upcoming.data && <Skeleton lines={3} />}
              {upcoming.data && upcoming.data.events.length === 0 && <p className="text-meta text-ink-muted">Nothing in the next 4 months.</p>}
              <ul className="space-y-2">
                {upcoming.data?.events.slice(0, 12).map((e: any, i: number) => {
                  const dl = upcoming.data.deadlines.find((d: any) => d.id === e.deadline_id);
                  return (
                    <li key={i} className="rounded-detail border border-border p-2">
                      <p className={`font-semibold ${e.done ? "line-through" : ""}`}>
                        {TYPE[e.type]?.icon} {e.type === "review" ? `Review on ${new Date(e.date + "T00:00:00").toLocaleDateString()}` : e.title}
                      </p>
                      <p className="text-meta text-ink-muted">{e.type !== "review" ? new Date(e.date + "T00:00:00").toLocaleDateString() : ""}{e.subject_name ? ` · ${e.subject_name}` : ""}
                        {dl ? ` · ${IMPORTANCE[dl.importance]} importance` : ""}</p>
                      <div className="flex flex-wrap gap-3">
                        {e.subject_id && <Link className="btn-link" href={e.concept_id ? `/subjects/${e.subject_id}/roadmap/concepts/${e.concept_id}` : `/subjects/${e.subject_id}/start`}>Open</Link>}
                        {dl && <button className="btn-link" onClick={() => patch(dl.id, { done: !dl.done })}>{dl.done ? "Mark not done" : "Mark done"}</button>}
                        {dl && <button className="btn-link" onClick={() => remove(dl.id)}>Delete<span className="sr-only"> {dl.title}</span></button>}
                      </div>
                    </li>
                  );
                })}
              </ul>
            </section>
          </aside>
        </div>
      </div>
    </AppShell>
  );
}
