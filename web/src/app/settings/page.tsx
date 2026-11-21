"use client";
// A03 Account and settings — UC37 (privacy/data controls), consent grants + immutable access audit log (override §3.9).
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { AppShell, useMe } from "@/components/AppShell";
import { DemoLabel, ErrorBox } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";

const SECTIONS = [
  { k: "account", t: "Account" }, { k: "privacy", t: "Privacy & data" }, { k: "language", t: "Language" },
  { k: "notifications", t: "Notifications" }, { k: "plan", t: "Plan" },
];

function Privacy() {
  const { me, caps, refreshMe } = useMe();
  const grants = useApi<any>("/me/consent-grants");
  const audit = useApi<any>("/me/audit-log");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const prefs = me?.preferences || {};
  const set = async (changes: any) => {
    setErr(null);
    try {
      await api("/me/settings", { method: "PATCH", json: { changes } });
      await refreshMe();
      setMsg("Saved.");
    } catch (e: any) { setErr(e.message); }
  };
  return (
    <div className="space-y-6">
      {err && <ErrorBox message={err} />}
      <p role="status" className="sr-only">{msg}</p>
      <section className="card space-y-3">
        <h2 className="text-section">Recordings</h2>
        <fieldset>
          <legend className="font-semibold">Default audio retention</legend>
          <label className="flex min-h-[44px] items-center gap-2"><input type="radio" name="ret" checked={prefs.audio_retention !== "replay_7_days"} onChange={() => set({ audio_retention: "delete_after_confirmation" })} />
            Delete raw audio after I confirm the transcript (recommended)</label>
          <label className="flex min-h-[44px] items-center gap-2"><input type="radio" name="ret" checked={prefs.audio_retention === "replay_7_days"} onChange={() => set({ audio_retention: "replay_7_days" })} />
            Keep for replay; deleted 7 days after upload</label>
        </fieldset>
        <p className="text-meta text-ink-muted">Transcript and evidence history stay until you delete them (open a receipt → Delete attempt). “Delete audio now” is available on each recording.
          Audio processor: {caps?.audio_processor || "none (demo transcription)"}. Text processors: {caps?.text_processors?.length ? caps.text_processors.join(", ") : "built-in demo assessor"}.
          Your data is never used for training.</p>
      </section>
      <section className="card space-y-3">
        <h2 className="text-section">Display</h2>
        <label className="flex min-h-[44px] items-center gap-2"><input type="checkbox" checked={!!prefs.quiet_mode} onChange={(e) => set({ quiet_mode: e.target.checked })} /> Quiet mode by default</label>
        <label className="flex flex-wrap items-center gap-2">Motion
          <select className="field !w-auto" value={prefs.reduced_motion || "system"} onChange={(e) => set({ reduced_motion: e.target.value })}>
            <option value="system">Follow my system</option><option value="reduce">Reduce motion</option><option value="no-preference">Allow motion</option>
          </select></label>
      </section>
      <section className="card space-y-3">
        <h2 className="text-section">Who can see your data</h2>
        <p>Nobody but you. ThinkFirst staff have <strong>no default access</strong> to your subjects, answers, recordings or evidence. Access requires your specific, time-limited, revocable consent for named items; every access is logged here.</p>
        <h3 className="font-bold">Active consents</h3>
        {grants.data?.grants?.length ? (
          <ul className="space-y-2">{grants.data.grants.map((g: any) => (
            <li key={g.id} className="flex flex-wrap items-center justify-between gap-2"><span>{g.purpose} · expires {new Date(g.expires_at).toLocaleString()}{g.revoked_at ? " · revoked" : ""}</span>
              {!g.revoked_at && <button className="btn-link" onClick={async () => { await api(`/me/consent-grants/${g.id}`, { method: "DELETE" }); grants.reload(); audit.reload(); }}>Revoke</button>}</li>
          ))}</ul>
        ) : <p className="text-meta text-ink-muted">None.</p>}
        <h3 className="font-bold">Access log</h3>
        {audit.data?.entries?.length ? (
          <ul className="space-y-1 text-meta">{audit.data.entries.map((a: any) => (
            <li key={a.id}>{new Date(a.created_at).toLocaleString()} — {a.actor_role}: {a.action.replace("_", " ")}{a.target_type ? ` (${a.target_type})` : ""}{a.purpose ? ` — ${a.purpose}` : ""}</li>
          ))}</ul>
        ) : <p className="text-meta text-ink-muted">No access recorded.</p>}
      </section>
      <section className="card space-y-2">
        <h2 className="text-section">Export and account deletion</h2>
        <p className="text-meta text-ink-muted">Full export and account deletion jobs arrive in a later milestone. Deleting individual attempts and audio works now.</p>
      </section>
      {me?.is_demo && <DemoQuota />}
    </div>
  );
}

function DemoQuota() {
  const q = useApi<any>("/billing/quota");
  return (
    <section className="card space-y-3">
      <DemoLabel>Demo tools</DemoLabel>
      <p>Allowance (mock entitlement provider): {q.data ? `${q.data.used_units} used, ${q.data.held_units} reserved, ${q.data.available_units} available of ${q.data.period_units}` : "…"}</p>
      <div className="flex flex-wrap gap-2">
        <button className="btn-secondary" onClick={async () => { await api("/billing/demo/usage", { method: "POST", json: { used_units: q.data.period_units } }); q.reload(); }}>Simulate exhausted allowance (shows Q01)</button>
        <button className="btn-secondary" onClick={async () => { await api("/billing/demo/usage", { method: "POST", json: { used_units: 0 } }); q.reload(); }}>Reset allowance</button>
      </div>
    </section>
  );
}

function Settings() {
  const params = useSearchParams();
  const section = params.get("section") || "account";
  const { me } = useMe();
  return (
    <div className="grid gap-6 lg:grid-cols-[220px_1fr]" data-screen="A03">
      <nav aria-label="Settings sections">
        <ul className="space-y-1">{SECTIONS.map((x) => (
          <li key={x.k}><Link href={`/settings?section=${x.k}`} aria-current={section === x.k ? "page" : undefined}
            className={`flex min-h-[44px] items-center rounded-control px-3 font-semibold ${section === x.k ? "bg-success-surface text-action-base" : ""}`}>{x.t}</Link></li>
        ))}</ul>
      </nav>
      <div className="max-w-prose">
        <h1 className="mb-4 text-page-compact">{SECTIONS.find((x) => x.k === section)?.t || "Settings"}</h1>
        {section === "account" && <div className="card"><p>Signed in as <strong>{me?.email}</strong>.</p><p className="mt-2 text-meta text-ink-muted">Password changes arrive later.</p></div>}
        {section === "privacy" && <Privacy />}
        {section === "language" && <div className="card"><p>English. French and Arabic (with right-to-left layout) arrive in M7.</p></div>}
        {section === "notifications" && <div className="card"><p>Not connected. Opt-in reminders arrive in M7; ThinkFirst never asks for browser notification permission unprompted.</p></div>}
        {section === "plan" && <div className="card"><p>Free plan (mock entitlement provider). No payments exist in this build.</p></div>}
      </div>
    </div>
  );
}

export default function Page() {
  return <AppShell crumbs={[{ label: "Settings" }]}><Suspense><Settings /></Suspense></AppShell>;
}
