"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, ReactNode, useContext, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";

type Me = { id: string; email: string; display_name: string; is_demo: boolean; setup_complete: boolean; preferences: any };
type Caps = { simulated: boolean; label: string; stt_simulated: boolean; audio_processor: string | null; text_processors: string[]; demo_mode: boolean };
const Ctx = createContext<{ me: Me | null; caps: Caps | null; refreshMe: () => Promise<void> }>({ me: null, caps: null, refreshMe: async () => {} });
export const useMe = () => useContext(Ctx);

const GLOBAL = [
  { href: "/today", label: "Today", icon: "◎" },
  { href: "/subjects", label: "Subjects", icon: "▤" },
  { href: "/planner", label: "Planner", icon: "▦" },
  { href: "/progress", label: "Progress", icon: "↗" },
];

/** Auth gate + global shell. `focused` hides global navigation (active S02/C03, blueprint). */
export function AppShell({ children, crumbs = [], focused = false, requireSetup = true }:
  { children: ReactNode; crumbs?: { href?: string; label: string }[]; focused?: boolean; requireSetup?: boolean }) {
  const router = useRouter();
  const path = usePathname();
  const [me, setMe] = useState<Me | null>(null);
  const [caps, setCaps] = useState<Caps | null>(null);
  const [menu, setMenu] = useState(false);
  const [bell, setBell] = useState(false);

  const refreshMe = async () => {
    try {
      const r = await api<{ user: Me }>("/auth/me", { retries: 1 });
      setMe(r.user);
      if (requireSetup && !r.user.setup_complete) router.replace("/onboarding");
    } catch (e) {
      if ((e as ApiError).status === 401) router.replace(`/welcome?return=${encodeURIComponent(path)}`);
    }
  };
  useEffect(() => {
    refreshMe();
    api<Caps>("/capabilities").then(setCaps).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    const m = me?.preferences?.reduced_motion;
    document.documentElement.dataset.motion = m === "reduce" ? "reduce" : "";
  }, [me]);

  if (!me) return <div className="p-6" aria-busy="true"><span className="sr-only">Loading</span></div>;

  const signOut = async () => {
    await api("/auth/logout", { method: "POST" }).catch(() => {});
    router.replace("/welcome");
  };

  return (
    <Ctx.Provider value={{ me, caps, refreshMe }}>
      <a href="#main" className="skip-link btn-secondary">Skip to content</a>
      {!focused && (
        <nav aria-label="Main" className="sidebar-game fixed inset-y-0 left-0 z-30 hidden w-[208px] flex-col p-4 md:flex">
          <Link href="/today" className="mb-6 flex items-center gap-2 text-section font-bold" aria-label="ThinkFirst home">
            <span aria-hidden className="text-discovery">◆</span> ThinkFirst
          </Link>
          <ul className="space-y-1">
            {GLOBAL.map((g) => {
              const active = path.startsWith(g.href);
              return (
                <li key={g.href}>
                  <Link href={g.href} aria-current={active ? "page" : undefined}
                    className="flex min-h-[48px] items-center gap-3 rounded-control px-3 font-bold">
                    <span aria-hidden>{g.icon}</span>{g.label}
                  </Link>
                </li>
              );
            })}
          </ul>
          <Link href="/subjects/new" className="btn-primary mt-6 !min-h-[48px] w-full">+ Learn something</Link>
          {me.is_demo && <p className="mt-auto text-meta text-[#CFE6E2]">Demo account · labeled Demo data</p>}
        </nav>
      )}
      <div className={focused ? "" : "md:pl-[208px]"}>
        {!focused && (
          <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border bg-surface/95 px-4 lg:h-16 lg:px-6">
            <nav aria-label="Breadcrumb" className="min-w-0 truncate text-meta">
              <ol className="flex items-center gap-2">
                <li className="md:hidden font-bold">ThinkFirst</li>
                {crumbs.map((c, i) => (
                  <li key={i} className="hidden items-center gap-2 md:flex">
                    {i > 0 && <span aria-hidden className="text-ink-muted">/</span>}
                    {c.href ? <Link className="underline-offset-2 hover:underline" href={c.href}>{c.label}</Link> : <span aria-current="page">{c.label}</span>}
                  </li>
                ))}
              </ol>
            </nav>
            <div className="relative flex items-center gap-2">
              <button className="btn-secondary !min-h-[44px] !px-3" aria-expanded={bell} aria-label="Notifications" onClick={() => setBell((b) => !b)}>🔔</button>
              {bell && (
                <div role="dialog" aria-label="Notifications" className="absolute right-12 top-12 w-72 rounded-card border border-border bg-surface p-4 shadow-lg" data-screen="N01">
                  <p className="font-bold">No reminders</p>
                  <p className="mt-1 text-meta text-ink-muted">Reminders and the inbox arrive in a later milestone (M7). Your review dates are in Planner.</p>
                </div>
              )}
              <button className="btn-secondary !min-h-[44px] !px-3" aria-expanded={menu} aria-haspopup="menu" onClick={() => setMenu((m) => !m)}>
                <span aria-hidden>●</span><span className="sr-only">Account menu for</span> <span className="hidden sm:inline">{me.display_name || me.email}</span>
              </button>
              {menu && (
                <div role="menu" className="absolute right-0 top-12 w-56 rounded-card border border-border bg-surface p-2 shadow-lg">
                  <Link role="menuitem" href="/settings?section=account" className="flex min-h-[44px] items-center rounded-detail px-3 hover:bg-canvas">Settings</Link>
                  <Link role="menuitem" href="/settings?section=privacy" className="flex min-h-[44px] items-center rounded-detail px-3 hover:bg-canvas">Privacy &amp; data</Link>
                  <button role="menuitem" onClick={signOut} className="flex min-h-[44px] w-full items-center rounded-detail px-3 text-left hover:bg-canvas">Sign out</button>
                </div>
              )}
            </div>
          </header>
        )}
        <main id="main" className={focused ? "" : "mx-auto max-w-overview px-4 py-6 pb-28 md:px-6 md:pb-10 2xl:px-8"}>{children}</main>
      </div>
      {!focused && (
        <nav aria-label="Main" className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-surface pb-[env(safe-area-inset-bottom)] md:hidden">
          <ul className="grid h-16 grid-cols-4">
            {GLOBAL.map((g) => {
              const active = path.startsWith(g.href);
              return (
                <li key={g.href}>
                  <Link href={g.href} aria-current={active ? "page" : undefined}
                    className={`flex h-full flex-col items-center justify-center text-meta font-semibold ${active ? "text-action-base" : "text-ink-muted"}`}>
                    <span aria-hidden>{g.icon}</span>{g.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      )}
    </Ctx.Provider>
  );
}
