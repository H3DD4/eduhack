"use client";
// A01 Authentication — UC01/UC02. Password managers/paste allowed; error summary retains email, never secrets.
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useRef, useState } from "react";
import { Logo, Mark } from "@/components/Logo";
import { DemoLabel } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { AvatarSpeakerProvider, useAvatarSpeaker } from "@/components/avatar/AvatarSpeakerContext";

function safeReturn(r: string | null) {
  return r && r.startsWith("/") && !r.startsWith("//") ? r : null; // only same-site paths
}

function Welcome() {
  const router = useRouter();
  const params = useSearchParams();
  const { startVoiceGuide } = useAvatarSpeaker();
  const [mode, setMode] = useState<"signin" | "create">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ message: string; field?: string } | null>(null);
  const [providers, setProviders] = useState<any>(null);
  const summaryRef = useRef<HTMLDivElement>(null);

  useEffect(() => { api("/auth/providers").then(setProviders).catch(() => {}); }, []);
  useEffect(() => { if (params.get("mode") === "create") setMode("create"); }, [params]);
  useEffect(() => { if (error) summaryRef.current?.focus(); }, [error]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await api<{ user: any }>(mode === "signin" ? "/auth/login" : "/auth/register",
        { method: "POST", json: { email, password }, retries: 0 });
      setPassword("");
      const ret = safeReturn(params.get("return"));
      router.replace(!r.user.setup_complete ? "/onboarding" : ret || "/today");
    } catch (err) {
      const e2 = err as ApiError;
      setPassword("");
      setError({ message: e2.message, field: e2.data?.field });
    } finally {
      setBusy(false);
    }
  };

  const subjects = ["Algebra", "Physics", "Databases", "Recursion", "Biology", "Bac maths", "Circuits", "Statistics"];
  return (
    <main id="main" className="min-h-screen overflow-hidden" data-screen="A01">
      <div className="mx-auto grid max-w-overview gap-10 px-4 py-8 md:px-6 lg:grid-cols-[1.15fr_1fr] lg:items-center lg:py-16">
        <section aria-labelledby="pitch-h" className="space-y-6">
          <Logo size={40} />
          <h1 id="pitch-h" className="text-page md:text-hero">AI that makes you <span className="hl">think</span>, not AI that <span className="hl-dark">thinks for you</span></h1>
          <p className="max-w-xl text-problem text-ink-muted">One AI professor per subject, a roadmap built from your own courses, and a planner around your exam dates. You do the thinking.</p>
          <div className="max-w-xl rounded-card border-2 border-ink bg-surface p-4">
            <p className="font-semibold">Blind or prefer spoken guidance?</p>
            <p className="mt-1 text-meta text-ink-muted">The avatar can read the next steps and help you navigate. The microphone stays off until you press its button; your browser may process speech recognition.</p>
            <button type="button" className="btn-secondary mt-3" onClick={startVoiceGuide}>Start spoken guide</button>
          </div>
          <ul className="grid max-w-xl gap-3 sm:grid-cols-3">
            {["Try first", "Help one step at a time", "Proof you can do it alone"].map((t, i) => (
              <li key={t} className="game-card flex items-center gap-3 p-3">
                <span aria-hidden className="grid h-9 w-9 shrink-0 place-items-center rounded-pill border-2 border-ink bg-hl">{i + 1}</span>{t}
              </li>
            ))}
          </ul>
        </section>

        <section aria-labelledby="auth-h" className="card !p-6 md:!p-8 shadow-hard-lg">
          <div className="flex items-center justify-between gap-3">
            <h2 id="auth-h" className="text-page-compact">{mode === "signin" ? "Sign in" : "Create account"}</h2>
            <Mark size={48} />
          </div>
          {error && (
            <div ref={summaryRef} tabIndex={-1} role="alert" className="fade-in mt-4 rounded-card border-2 border-review bg-review-surface p-4">
              <p className="text-review">There is a problem</p>
              <a href={`#${error.field === "password" ? "password" : "email"}`} className="underline">{error.message}</a>
            </div>
          )}
          <form data-voice-form="auth" onSubmit={submit} className="mt-6 space-y-4" noValidate>
            <div>
              <label htmlFor="email" className="label">Email</label>
              <input id="email" className="field" type="email" autoComplete="email" required value={email}
                aria-invalid={error?.field === "email"} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div>
              <label htmlFor="password" className="label">Password</label>
              <input id="password" className="field" type="password" required value={password}
                autoComplete={mode === "signin" ? "current-password" : "new-password"} aria-invalid={error?.field === "password"}
                aria-describedby={mode === "create" ? "pw-hint" : undefined} onChange={(e) => setPassword(e.target.value)} />
              {mode === "create" && <p id="pw-hint" className="mt-1 text-meta text-ink-muted">At least 8 characters.</p>}
            </div>
            <button className="btn-primary w-full" disabled={busy} aria-busy={busy}>
              {busy ? (mode === "signin" ? "Signing in..." : "Creating account...") : mode === "signin" ? "Sign in" : "Create account"}
            </button>
          </form>
          <div className="mt-4">
            <button type="button" data-voice-action={mode === "signin" ? "create-account" : "sign-in"} className="btn-link" onClick={() => { setMode(mode === "signin" ? "create" : "signin"); setError(null); }}>
              {mode === "signin" ? "Create an account instead" : "I already have an account"}
            </button>
          </div>
          <div className="mt-4">
            {providers?.google ? (
              <a className="btn-secondary w-full" href="/api/auth/google/start">Continue with Google</a>
            ) : (
              <p className="text-meta text-ink-muted">Google sign-in is not configured in this environment.</p>
            )}
          </div>
          {providers?.demo && providers.demo_credentials && (
            <div className="mt-6 rounded-card border-2 border-dashed border-ink p-4">
              <DemoLabel />
              <p className="mt-2 text-meta">Demo account: {providers.demo_credentials.email} / {providers.demo_credentials.password}</p>
              <button className="btn-secondary mt-3" onClick={() => { setEmail(providers.demo_credentials.email); setPassword(providers.demo_credentials.password); }}>
                Fill demo credentials
              </button>
            </div>
          )}
          <p className="mt-6 text-meta text-ink-muted">Your subjects, uploads, answers, recordings and evidence are private to you.</p>
        </section>
      </div>
      <div className="marquee mt-4" aria-hidden="true">
        <div className="marquee-track text-section">
          {[...subjects, ...subjects].map((t, i) => (
            <span key={i} className="flex items-center gap-12">{t}<span className="text-hl">◆</span></span>
          ))}
        </div>
      </div>
    </main>
  );
}

export default function Page() {
  return <Suspense><AvatarSpeakerProvider><Welcome /></AvatarSpeakerProvider></Suspense>;
}
