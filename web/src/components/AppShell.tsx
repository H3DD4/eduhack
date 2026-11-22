"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, ReactNode, useContext, useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { AvatarSpeakerProvider } from "./avatar/AvatarSpeakerContext";
import { CommandPalette } from "./CommandPalette";
import { Logo } from "./Logo";

type Me = { id: string; email: string; display_name: string; is_demo: boolean; setup_complete: boolean; preferences: any };
type Caps = { simulated: boolean; label: string; stt_simulated: boolean; audio_processor: string | null; text_processors: string[]; demo_mode: boolean };
const Ctx = createContext<{ me: Me | null; caps: Caps | null; refreshMe: () => Promise<void> }>({ me: null, caps: null, refreshMe: async () => {} });
export const useMe = () => useContext(Ctx);

function Icon({ name }: { name: "today" | "subjects" | "planner" | "progress" | "teachers" }) {
  const p = { fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true">
      {name === "today" && <><circle cx="12" cy="12" r="4" {...p} /><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M5 19l2-2M17 7l2-2" {...p} /></>}
      {name === "subjects" && <><path d="M4 5h6a2 2 0 0 1 2 2v12a2 2 0 0 0-2-2H4z" {...p} /><path d="M20 5h-6a2 2 0 0 0-2 2v12a2 2 0 0 1 2-2h6z" {...p} /></>}
      {name === "planner" && <><rect x="3" y="5" width="18" height="16" rx="3" {...p} /><path d="M3 10h18M8 3v4M16 3v4" {...p} /></>}
      {name === "progress" && <><path d="M4 19V5M4 19h16" {...p} /><path d="M8 15l4-4 3 3 5-6" {...p} /></>}
      {name === "teachers" && <><circle cx="12" cy="8" r="4" {...p} /><path d="M5 20a7 7 0 0 1 14 0" {...p} /></>}
    </svg>
  );
}

const GLOBAL = [
  { href: "/today", label: "Today", icon: "today" as const },
  { href: "/subjects", label: "Subjects", icon: "subjects" as const },
  { href: "/planner", label: "Planner", icon: "planner" as const },
  { href: "/progress", label: "Progress", icon: "progress" as const },
  { href: "/teachers", label: "3D Teachers", icon: "teachers" as const },
];

/** Hook: close a popover on outside click or Escape. */
function useDismiss(open: boolean, close: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) close(); };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") close(); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onDown); document.removeEventListener("keydown", onKey); };
  }, [open, close]);
  return ref;
}

/** Auth gate + global shell. `focused` hides global navigation (active session, onboarding). */
export function AppShell({ children, crumbs = [], focused = false, requireSetup = true, back }:
  { children: ReactNode; crumbs?: { href?: string; label: string }[]; focused?: boolean; requireSetup?: boolean;
    /** Where Back goes. Default: the nearest parent in `crumbs`, else Today. `false` = the page has its own Back. */
    back?: { href: string; label: string } | false }) {
  const router = useRouter();
  const path = usePathname();
  const [me, setMe] = useState<Me | null>(null);
  const [caps, setCaps] = useState<Caps | null>(null);
  const [menu, setMenu] = useState(false);
  const [bell, setBell] = useState(false);
  const [palette, setPalette] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const menuRef = useDismiss(menu, () => setMenu(false));
  const bellRef = useDismiss(bell, () => setBell(false));

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
  useEffect(() => {
    if (focused) return;
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setPalette((p) => !p); }
    };
    const onScroll = () => setScrolled(window.scrollY > 8);
    document.addEventListener("keydown", onKey);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => { document.removeEventListener("keydown", onKey); window.removeEventListener("scroll", onScroll); };
  }, [focused]);

  if (!me) {
    return (
      <div className="grid min-h-screen place-items-center" aria-busy="true">
        <span className="animate-pulse"><Logo size={44} /></span><span className="sr-only">Loading</span>
      </div>
    );
  }

  const signOut = async () => {
    await api("/auth/logout", { method: "POST" }).catch(() => {});
    router.replace("/welcome");
  };
  // Back goes to a fixed, named parent (not browser history: history could reopen a session the student just left).
  const parent = [...crumbs].slice(0, -1).reverse().find((c) => c.href) as { href: string; label: string } | undefined;
  const backTo = back === false || path === "/today" ? null : back ?? parent ?? { href: "/today", label: "Today" };
  const initial = (me.display_name || me.email || "?").trim().charAt(0).toUpperCase();

  return (
    <Ctx.Provider value={{ me, caps, refreshMe }}>
      <AvatarSpeakerProvider>
      <a href="#main" className="skip-link btn-secondary">Skip to content</a>
      {!focused && (
        <header className={`sticky top-0 z-30 px-3 pt-3 transition-[padding] duration-200 md:px-6 ${scrolled ? "md:pt-2" : "md:pt-5"}`}>
          <nav aria-label="Main" className="topnav mx-auto flex max-w-overview items-center justify-between gap-3 py-2 pl-4 pr-2">
            <Link href="/today" aria-label="ThinkFirst home" className="shrink-0 transition-transform duration-150 hover:-rotate-2 hover:scale-105"><Logo size={34} /></Link>
            <ul className="hidden items-center gap-1 md:flex">
              {GLOBAL.map((g) => (
                <li key={g.href}>
                  <Link href={g.href} aria-current={path.startsWith(g.href) ? "page" : undefined} className="navlink"><Icon name={g.icon} />{g.label}</Link>
                </li>
              ))}
            </ul>
            <div className="flex items-center gap-2">
              <button type="button" onClick={() => setPalette(true)} aria-label="Search or jump to (Ctrl K)"
                className="hidden min-h-[42px] items-center gap-2 rounded-pill border-2 border-border bg-paper px-3 text-meta text-ink-muted transition-colors hover:border-ink hover:text-ink lg:inline-flex">
                <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7" fill="none" stroke="currentColor" strokeWidth="2" /><path d="M20 20l-4-4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg>
                Jump to… <span className="kbd">Ctrl K</span>
              </button>
              {/* wrapper: .btn-primary sets display itself, which overrode `hidden` and overflowed 320px screens */}
              <span className="hidden sm:inline-flex"><Link href="/subjects/new" className="btn-primary !min-h-[42px] !px-4 !py-1">+ Learn something</Link></span>
              <div ref={bellRef} className="relative">
                <button className="btn-secondary !min-h-[42px] !rounded-pill !px-3" aria-expanded={bell} aria-label="Notifications" onClick={() => setBell((b) => !b)}>
                  <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 16V11a6 6 0 1 1 12 0v5l2 2H4z M10 20a2 2 0 0 0 4 0" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" /></svg>
                </button>
                {bell && (
                  <div role="dialog" aria-label="Notifications" className="fade-in absolute right-0 top-14 w-72 rounded-card border-2 border-ink bg-surface p-4 shadow-hard" data-screen="N01">
                    <p>No reminders yet</p>
                    <p className="mt-1 text-meta text-ink-muted">Your review dates are in Planner.</p>
                  </div>
                )}
              </div>
              <div ref={menuRef} className="relative">
                <button className="grid h-[42px] w-[42px] place-items-center rounded-pill border-2 border-ink bg-slate text-white transition-transform hover:-translate-y-0.5 hover:shadow-hard"
                  aria-expanded={menu} aria-haspopup="menu" aria-label={`Account menu for ${me.display_name || me.email}`} onClick={() => setMenu((m) => !m)}>
                  {initial}
                </button>
                {menu && (
                  <div role="menu" className="fade-in absolute right-0 top-14 w-60 rounded-card border-2 border-ink bg-surface p-2 shadow-hard">
                    <p className="truncate px-3 py-2 text-meta text-ink-muted">{me.email}</p>
                    <Link role="menuitem" href="/settings?section=account" className="flex min-h-[44px] items-center rounded-control px-3 hover:bg-soft">Settings</Link>
                    <Link role="menuitem" href="/settings?section=privacy" className="flex min-h-[44px] items-center rounded-control px-3 hover:bg-soft">Privacy and data</Link>
                    <button role="menuitem" onClick={signOut} className="flex min-h-[44px] w-full items-center rounded-control px-3 text-left hover:bg-soft">Sign out</button>
                  </div>
                )}
              </div>
            </div>
          </nav>
          {backTo && (
            <div className="mx-auto mt-2 flex max-w-overview px-1 print:hidden">
              <Link href={backTo.href} data-testid="back"
                className="inline-flex min-h-[42px] max-w-full items-center gap-2 rounded-pill border-2 border-ink bg-surface px-4 text-meta font-bold text-ink shadow-hard transition-transform hover:-translate-y-0.5">
                <span aria-hidden>←</span><span className="truncate">Back to {backTo.label}</span>
              </Link>
            </div>
          )}
        </header>
      )}
      <main id="main" className={focused ? "" : "mx-auto max-w-overview px-4 py-6 pb-28 md:px-6 md:pb-12 2xl:px-8"}>
        <div className="fade-in" key={path}>{children}</div>
      </main>
      {!focused && me.is_demo && <p className="pb-24 text-center text-meta text-ink-muted md:pb-6">Demo account · data is labeled Demo</p>}
      {!focused && (
        <nav aria-label="Main" className="fixed inset-x-3 bottom-3 z-30 rounded-[22px] border-2 border-ink bg-surface pb-[env(safe-area-inset-bottom)] shadow-hard md:hidden">
          <ul className="grid h-16 grid-cols-4">
            {GLOBAL.slice(0, 4).map((g) => {
              const active = path.startsWith(g.href);
              return (
                <li key={g.href} className="p-1">
                  <Link href={g.href} aria-current={active ? "page" : undefined}
                    className={`flex h-full flex-col items-center justify-center rounded-[16px] text-meta transition-colors ${active ? "bg-hl text-ink" : "text-ink-muted hover:bg-soft"}`}>
                    <Icon name={g.icon} />{g.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      )}
      <CommandPalette open={palette} onClose={() => setPalette(false)} />
      </AvatarSpeakerProvider>
    </Ctx.Provider>
  );
}
