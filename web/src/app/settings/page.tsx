"use client";
// A03 Account and settings — UC37 (privacy/data controls), consent grants + immutable access audit log (override §3.9).
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { AppShell, useMe } from "@/components/AppShell";
import { DemoLabel, Dialog, ErrorBox } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { AccessibilityProfile, isAccessibilityActive } from "@/lib/accessibility/profile";

const SECTIONS = [
  { k: "account", t: "Account" }, { k: "privacy", t: "Privacy & data" }, { k: "language", t: "Language" },
  { k: "notifications", t: "Notifications" }, { k: "plan", t: "Plan" },
];

function ReadingAids() {
  const { caps, accessibilityProfile, accessibilityError, refreshAccessibility } = useMe();
  const [consentOpen, setConsentOpen] = useState(false);
  const [consentAccepted, setConsentAccepted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const profile = accessibilityProfile;
  const active = isAccessibilityActive(profile);
  const subjects = useApi<any>("/subjects");

  if (!caps?.accessibility_module) return <p className="card">Reading aids are not available in this environment.</p>;

  const save = async (changes: Partial<AccessibilityProfile>) => {
    setBusy(true);
    setError(null);
    try {
      await api("/me/accessibility", { method: "PATCH", json: { changes } });
      await refreshAccessibility();
      setMessage("Reading-aid settings saved.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const agree = async () => {
    if (!consentAccepted) return;
    setBusy(true);
    setError(null);
    try {
      await api("/me/accessibility/consent", { method: "POST", json: { accepted: true } });
      await refreshAccessibility();
      setConsentOpen(false);
      setConsentAccepted(false);
      setMessage("Reading aids enabled. You can adjust or turn them off at any time.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const exportProfile = async () => {
    setError(null);
    try {
      const data = await api("/me/accessibility/export");
      const blob = new Blob([JSON.stringify(data.profile, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "thinkfirst-reading-aids.json";
      link.click();
      URL.revokeObjectURL(url);
      setMessage("Your reading-aid profile was exported.");
    } catch (e) { setError((e as Error).message); }
  };
  const removeProfile = async () => {
    if (!window.confirm("Delete your saved reading-aid profile? This cannot be undone.")) return;
    setError(null);
    try {
      await api("/me/accessibility", { method: "DELETE" });
      await refreshAccessibility();
      setMessage("Your reading-aid profile was deleted.");
    } catch (e) { setError((e as Error).message); }
  };
  const select = (label: string, key: keyof AccessibilityProfile, options: [string, string][]) => (
    <label className="flex flex-wrap items-center justify-between gap-2">
      <span>{label}</span>
      <select className="field !w-auto" disabled={!active || busy}
        value={profile?.[key] == null ? "" : options.find(([value]) =>
          value === String(profile[key]) || typeof profile[key] === "number" && Number(value) === profile[key])?.[0] || ""}
        onChange={(e) => {
          const value = e.target.value;
          const numeric = ["font_size", "line_spacing", "letter_spacing", "word_spacing", "line_width",
            "tts_speed", "extra_time_factor"].includes(key);
          save({ [key]: value === "" ? null : numeric ? Number(value) : value } as Partial<AccessibilityProfile>);
        }}>
        <option value="">Use app default</option>
        {options.map(([value, name]) => <option key={value} value={value}>{name}</option>)}
      </select>
    </label>
  );
  const toggle = (label: string, key: keyof AccessibilityProfile) => (
    <label className="flex min-h-[44px] items-center gap-2">
      <input type="checkbox" disabled={!active || busy} checked={Boolean(profile?.[key])}
        onChange={(e) => save({ [key]: e.target.checked } as Partial<AccessibilityProfile>)} />
      {label}
    </label>
  );
  const previewFont = profile?.font || "Acme";
  const previewStyle = {
    fontFamily: `"${previewFont}", "Noto Sans Arabic", sans-serif`,
    fontSize: `${profile?.font_size || 17}px`,
    lineHeight: profile?.line_spacing || 1.65,
    letterSpacing: `${profile?.letter_spacing || 0}em`,
    wordSpacing: `${profile?.word_spacing || 0}em`,
    maxWidth: `${profile?.line_width || 70}ch`,
  };

  return (
    <div className="space-y-5">
      {(error || accessibilityError) && <ErrorBox message={error || accessibilityError || ""} />}
      <p className="sr-only" role="status" aria-live="polite">{message}</p>
      {!profile?.consent_given_at ? (
        <section className="card space-y-3">
          <p>Optional reading aids can change text presentation and provide read-aloud or dictation controls. They do not diagnose you or change the learning goals.</p>
          <button type="button" className="btn-primary" onClick={() => setConsentOpen(true)}>Review privacy and enable</button>
        </section>
      ) : (
        <>
          <section className="card space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div><h2 className="text-section">Reading aids</h2><p className="text-meta text-ink-muted">Adjust any aid individually. Your profile is private to your account.</p></div>
              <button type="button" role="switch" aria-checked={active} disabled={busy}
                className="btn-secondary" onClick={() => save({ enabled: !active })}>
                {active ? "On — turn off" : "Off — turn on"}
              </button>
            </div>
            <fieldset disabled={!active} className="space-y-3">
              <legend className="font-semibold">Text presentation</legend>
              {select("Font", "font", [["Arial", "Arial"], ["Verdana", "Verdana"], ["Lexend", "Lexend"],
                ["Atkinson Hyperlegible", "Atkinson Hyperlegible"], ["OpenDyslexic", "OpenDyslexic"]])}
              {select("Text size", "font_size", [14, 16, 18, 20].map((n) => [String(n), `${n} px`]))}
              {select("Line spacing", "line_spacing", [["1.5", "1.5"], ["1.75", "1.75"], ["2", "2"]])}
              {select("Letter spacing", "letter_spacing", [["0", "Default"], ["0.03", "Slight"], ["0.06", "More"]])}
              {select("Word spacing", "word_spacing", [["0", "Default"], ["0.08", "Slight"], ["0.16", "More"]])}
              {select("Line width", "line_width", [["50", "50 characters"], ["60", "60 characters"], ["70", "70 characters"]])}
              {select("Theme", "theme", [["cream", "Cream"], ["pastel", "Pastel"], ["dark", "Dark"], ["high-contrast", "High contrast"]])}
              {select("Focus aid", "focus_mode", [["off", "Off"], ["ruler", "Line ruler"], ["dim", "Dim around pointer"]])}
              <div className="rounded-detail border-2 border-border bg-surface p-4" aria-label="Live reading preview">
                <p className="text-meta font-semibold">Preview</p>
                <p className="mt-2 text-left" style={previewStyle}>A clear layout can make a long explanation easier to follow. The ideas and level stay the same.</p>
              </div>
            </fieldset>
          </section>
          <section className="card space-y-3">
            <h2 className="text-section">Speech and input</h2>
            {toggle("Read-aloud controls", "tts_enabled")}
            {select("Speech language", "speech_language", [["en-GB", "English"], ["fr-FR", "French"], ["ar-SA", "Arabic"]])}
            {select("Speech speed", "tts_speed", [["0.75", "0.75×"], ["0.9", "0.9×"], ["1", "1×"], ["1.2", "1.2×"], ["1.5", "1.5×"]])}
            {toggle("Enable browser dictation in answer fields", "stt_enabled")}
            <p className="text-meta text-ink-muted">Browser dictation may be processed by your browser provider. The transcript stays editable before you submit it. Read-aloud voices depend on your device; unavailable voices are reported.</p>
            {toggle("Optional spelling suggestions", "spelling_suggestions")}
            <p className="text-meta text-ink-muted">Word prediction and Arabic diacritic display are not available in this English-only interface.</p>
            <fieldset disabled={!active || busy} className="space-y-2">
              <legend className="font-semibold">Language-learning subjects</legend>
              <p className="text-meta text-ink-muted">Mark subjects where spelling is part of the learning goal. This helps keep spelling separate from subject understanding.</p>
              {subjects.data?.subjects?.map((subject: any) => (
                <label key={subject.id} className="flex min-h-[44px] items-center gap-2">
                  <input type="checkbox" checked={(profile?.language_subject_ids || []).includes(subject.id)}
                    onChange={(e) => {
                      const selected = new Set(profile?.language_subject_ids || []);
                      if (e.target.checked) selected.add(subject.id);
                      else selected.delete(subject.id);
                      save({ language_subject_ids: Array.from(selected) });
                    }} />
                  {subject.name}
                </label>
              ))}
              {subjects.data?.subjects?.length === 0 && <p className="text-meta text-ink-muted">No subjects are available to classify yet.</p>}
            </fieldset>
          </section>
          <section className="card space-y-3">
            <h2 className="text-section">Exercise preferences</h2>
            {select("Extra time preference", "extra_time_factor", [["1", "No extra time"], ["1.25", "1.25×"], ["1.5", "1.5×"], ["2", "2×"]])}
            {toggle("Hide the timer", "hide_timer")}
            <p className="text-meta text-ink-muted">This version has no exam mode. These preferences are saved but do not change the current informational session timer.</p>
          </section>
          <section className="card flex flex-wrap gap-3">
            <button type="button" className="btn-secondary" onClick={exportProfile}>Export profile</button>
            <button type="button" className="btn-secondary" onClick={removeProfile}>Delete profile</button>
          </section>
        </>
      )}
      <Dialog open={consentOpen} title="Privacy for reading aids" onClose={() => setConsentOpen(false)}>
        <div className="space-y-4">
          <p>Your selected reading settings are stored in a private profile associated with your account. They are not shown to teachers or used for ranking. You can export or delete the profile at any time.</p>
          <p>Dictation uses your browser’s speech-recognition feature when enabled; the browser may process microphone audio. You can keep dictation off and type instead.</p>
          <label className="flex items-start gap-2"><input type="checkbox" checked={consentAccepted} onChange={(e) => setConsentAccepted(e.target.checked)} />
            <span>I agree to store my reading-aid settings in my private profile.</span></label>
          <div className="flex flex-wrap gap-3">
            <button type="button" className="btn-primary" disabled={!consentAccepted || busy} onClick={agree}>Agree and enable</button>
            <button type="button" className="btn-secondary" onClick={() => setConsentOpen(false)}>Not now</button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}

function Privacy() {
  const { me, caps, refreshMe } = useMe();
  const grants = useApi<any>("/me/consent-grants");
  const audit = useApi<any>("/me/audit-log");
  const trackingConsent = useApi<any>("/me/consent");
  const indicators = useApi<any>("/me/tracking/indicators");
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
  const toggleTier = async (tier: string, granted: boolean) => {
    setErr(null);
    try {
      await api("/me/consent", {
        method: "PATCH",
        json: granted ? { revoke: [tier] } : { grant: [tier] },
      });
      trackingConsent.reload();
      indicators.reload();
      setMsg("Consent updated.");
    } catch (e: any) { setErr(e.message); }
  };
  const cData = trackingConsent.data?.consent;
  const grantedSet = new Set<string>(cData?.granted_tiers || ["essential"]);
  return (
    <div className="space-y-6">
      {err && <ErrorBox message={err} />}
      <p role="status" className="sr-only">{msg}</p>
      <section className="card space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-section">Adaptation &amp; behavioral tracking tiers</h2>
          {indicators.data?.actor && <span className="badge">Pseudonymous ID: {indicators.data.actor}</span>}
        </div>
        <p className="text-meta text-ink-muted">
          Events use a pseudonymous ID and never track camera, microphone outside voice explain-back, keystrokes outside the answer box, or location.
        </p>
        {cData?.tiers?.map((t: any) => {
          const isOn = grantedSet.has(t.tier);
          return (
            <div key={t.tier} className="flex flex-wrap items-center justify-between gap-3 rounded-detail border-2 border-border p-3">
              <div className="max-w-md">
                <p className="font-semibold capitalize">{t.tier.replace("_", " ")}</p>
                <p className="text-meta text-ink-muted">{t.covers}</p>
              </div>
              {t.can_turn_off ? (
                <button
                  type="button"
                  role="switch"
                  aria-checked={isOn}
                  onClick={() => toggleTier(t.tier, isOn)}
                  className="btn-secondary !min-h-[38px] !px-3 text-meta"
                >
                  {isOn ? "On (Turn off)" : "Off (Turn on)"}
                </button>
              ) : (
                <span className="badge">Always on</span>
              )}
            </div>
          );
        })}
        {indicators.data?.student_effects?.length > 0 && (
          <div className="rounded-detail bg-soft p-3 text-meta">
            <p className="font-semibold">Current pacing adaptations:</p>
            <ul className="mt-1 list-disc pl-5">
              {indicators.data.student_effects.map((ef: string, i: number) => <li key={i}>{ef}</li>)}
            </ul>
          </div>
        )}
      </section>
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
  const { me, caps } = useMe();
  const sections = caps?.accessibility_module ? [...SECTIONS, { k: "reading-aids", t: "Reading aids" }] : SECTIONS;
  return (
    <div className="grid gap-6 lg:grid-cols-[220px_1fr]" data-screen="A03">
      <nav aria-label="Settings sections">
        <ul className="space-y-1">{sections.map((x) => (
          <li key={x.k}><Link href={`/settings?section=${x.k}`} aria-current={section === x.k ? "page" : undefined}
            className={`flex min-h-[44px] items-center rounded-control px-3 font-semibold ${section === x.k ? "bg-success-surface text-action-base" : ""}`}>{x.t}</Link></li>
        ))}</ul>
      </nav>
      <div className="max-w-prose">
        <h1 className="mb-4 text-page-compact">{sections.find((x) => x.k === section)?.t || "Settings"}</h1>
        {section === "account" && <div className="card"><p>Signed in as <strong>{me?.email}</strong>.</p><p className="mt-2 text-meta text-ink-muted">Password changes arrive later.</p><Link href="/onboarding" className="btn-secondary mt-4">Edit my learning profile</Link></div>}
        {section === "privacy" && <Privacy />}
        {section === "reading-aids" && <ReadingAids />}
        {section === "language" && <div className="card"><p>English. French and Arabic (with right-to-left layout) are coming soon.</p></div>}
        {section === "notifications" && <div className="card"><p>Not connected. Opt-in reminders are coming soon; ThinkFirst never asks for browser notification permission unprompted.</p></div>}
        {section === "plan" && <div className="card"><p>Free plan (mock entitlement provider). No payments exist in this build.</p></div>}
      </div>
    </div>
  );
}

export default function Page() {
  return <AppShell crumbs={[{ label: "Settings" }]}><Suspense><Settings /></Suspense></AppShell>;
}
