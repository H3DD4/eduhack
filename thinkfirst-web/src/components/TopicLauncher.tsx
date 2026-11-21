"use client";
// "Learn anything" launcher (UC05): no documents required. Creates an AI-generated roadmap grounded in openly
// licensed sources; the student confirms it with one click on C02.
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";

export function TopicLauncher({ dark = false, autoFocus = false }: { dark?: boolean; autoFocus?: boolean }) {
  const router = useRouter();
  const { data } = useApi<any>("/topics/suggestions");
  const [topic, setTopic] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const go = async (t: string) => {
    if (!t.trim()) return;
    setBusy(true);
    setErr(null);
    try {
      const r = await api("/subjects/topic", { method: "POST", json: { topic: t.trim() }, retries: 0 });
      router.push(`/subjects/${r.subject.id}/setup`);
    } catch (e: any) {
      setErr(e.message);
      setBusy(false);
    }
  };
  const submit = (e: FormEvent) => { e.preventDefault(); go(topic); };

  return (
    <div className="space-y-4">
      <form onSubmit={submit} className="flex flex-col gap-3 sm:flex-row" role="search" aria-label="Learn a topic">
        <label htmlFor="topic" className="sr-only">What do you want to learn?</label>
        <input id="topic" className="field !min-h-[56px] flex-1 text-problem !text-ink" placeholder="What do you want to learn? e.g. Fourier series, Ohm's law, recursion…"
          value={topic} onChange={(e) => setTopic(e.target.value)} autoFocus={autoFocus} maxLength={200} />
        <button className="btn-primary !min-h-[56px] sm:w-48" disabled={busy || !topic.trim()} aria-busy={busy}>
          {busy ? "Building…" : "Start learning"}
        </button>
      </form>
      {err && <p role="alert" className="text-review">{err}</p>}
      {data && (
        <>
          <ul className="flex flex-wrap gap-2" aria-label="Suggested topics">
            {data.suggestions.map((s: any) => (
              <li key={s.topic}>
                <button type="button" className="chip text-ink" disabled={busy} onClick={() => go(s.topic)}>
                  <span aria-hidden className="text-action">{s.icon}</span> {s.topic}
                </button>
              </li>
            ))}
          </ul>
          <p className={`text-meta ${dark ? "muted" : "text-ink-muted"}`}>
            {data.ai_available
              ? "Roadmaps and lessons are AI-generated and grounded in openly licensed sources (Wikipedia, CC BY-SA), with citations. Only your topic text is used to search."
              : "No AI service is configured here: only the built-in algebra starter is available. Add an AI key to learn any topic."}
          </p>
        </>
      )}
    </div>
  );
}
