"use client";
// A01 Authentication — UC01/UC02. Password managers/paste allowed; error summary retains email, never secrets.
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useRef, useState } from "react";
import { DemoLabel } from "@/components/ui";
import { api, ApiError } from "@/lib/api";

function safeReturn(r: string | null) {
  return r && r.startsWith("/") && !r.startsWith("//") ? r : null; // only same-site paths
}

function Welcome() {
  const router = useRouter();
  const params = useSearchParams();
  const [mode, setMode] = useState<"signin" | "create">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ message: string; field?: string } | null>(null);
  const [providers, setProviders] = useState<any>(null);
  const summaryRef = useRef<HTMLDivElement>(null);

  useEffect(() => { api("/auth/providers").then(setProviders).catch(() => {}); }, []);
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

  return (
    <main id="main" className="mx-auto max-w-form px-4 py-10" data-screen="A01">
      <p className="flex items-center gap-2 text-section font-bold"><span aria-hidden className="text-action">◆</span> ThinkFirst</p>
      <p className="mt-2 text-ink-muted">AI that makes you think, not AI that thinks for you.</p>
      <h1 className="mt-8 text-page-compact">{mode === "signin" ? "Sign in" : "Create account"}</h1>
      {error && (
        <div ref={summaryRef} tabIndex={-1} role="alert" className="mt-4 rounded-card border-2 border-review bg-review-surface p-4">
          <p className="font-bold text-review">There is a problem</p>
          <a href={`#${error.field === "password" ? "password" : "email"}`} className="underline">{error.message}</a>
        </div>
      )}
      <form onSubmit={submit} className="mt-6 space-y-4" noValidate>
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
        <button className="btn-link" onClick={() => { setMode(mode === "signin" ? "create" : "signin"); setError(null); }}>
          {mode === "signin" ? "Create an account instead" : "I already have an account"}
        </button>
      </div>
      <div className="mt-6">
        {providers?.google ? (
          <a className="btn-secondary w-full" href="/api/auth/google/start">Continue with Google</a>
        ) : (
          <p className="text-meta text-ink-muted">Google sign-in is not configured in this environment.</p>
        )}
      </div>
      {providers?.demo && providers.demo_credentials && (
        <div className="card mt-8">
          <DemoLabel />
          <p className="mt-2 text-meta">Demo account: <strong>{providers.demo_credentials.email}</strong> / <strong>{providers.demo_credentials.password}</strong></p>
          <button className="btn-secondary mt-3" onClick={() => { setEmail(providers.demo_credentials.email); setPassword(providers.demo_credentials.password); }}>
            Fill demo credentials
          </button>
        </div>
      )}
      <p className="mt-8 text-meta text-ink-muted">Your subjects, uploads, answers, recordings and evidence are private to you.</p>
    </main>
  );
}

export default function Page() {
  return <Suspense><Welcome /></Suspense>;
}
