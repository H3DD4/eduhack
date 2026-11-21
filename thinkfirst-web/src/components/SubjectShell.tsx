"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode, useState } from "react";
import { useApi } from "@/lib/hooks";
import { AppShell } from "./AppShell";
import { ErrorBox, NotAvailable } from "./ui";

const TABS = [
  { key: "roadmap", label: "Roadmap" },
  { key: "practice", label: "Practice" },
  { key: "exams", label: "Exams" },
  { key: "resources", label: "Resources" },
  { key: "progress", label: "Progress" },
];

/** Subject header (title + actions) above the 5 subject tabs; mobile: Roadmap, Practice, Exams, More. */
export function SubjectShell({ subjectId, children, action, crumb }:
  { subjectId: string; children: ReactNode; action?: ReactNode; crumb?: string }) {
  const path = usePathname();
  const { data, error } = useApi<{ subject: any }>(`/subjects/${subjectId}`);
  const [more, setMore] = useState(false);
  const base = `/subjects/${subjectId}`;
  const active = TABS.find((t) => path.startsWith(`${base}/${t.key}`))?.key ?? "roadmap";
  const name = data?.subject?.name ?? "Subject";
  return (
    <AppShell crumbs={[{ href: "/subjects", label: "Subjects" }, { href: `${base}/roadmap`, label: name }, ...(crumb ? [{ label: crumb }] : [])]}>
      {error?.status === 404 ? <NotAvailable backHref="/subjects" /> : (
        <>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <h1 className="text-page-compact lg:text-page">{name}</h1>
            {action}
          </div>
          <nav aria-label="Subject sections" className="mb-6 border-b-2 border-border pb-3">
            <ul className="flex flex-wrap gap-2">
              {TABS.map((t, i) => {
                const isActive = active === t.key;
                const hideOnMobile = i >= 3;
                return (
                  <li key={t.key} className={hideOnMobile ? "hidden md:block" : ""}>
                    <Link href={`${base}/${t.key}`} aria-current={isActive ? "page" : undefined}
                      className={`flex min-h-[44px] items-center rounded-pill border-2 px-4 transition-all duration-150 hover:-translate-y-0.5 ${isActive ? "border-ink bg-ink text-white shadow-edge" : "border-border bg-surface text-ink hover:border-ink"}`}>
                      {t.label}
                    </Link>
                  </li>
                );
              })}
              <li className="relative md:hidden">
                <button aria-expanded={more} onClick={() => setMore((m) => !m)}
                  className={`flex min-h-[44px] items-center rounded-pill border-2 px-4 ${["resources", "progress"].includes(active) ? "border-ink bg-ink text-white" : "border-border bg-surface text-ink"}`}>
                  More
                </button>
                {more && (
                  <ul className="fade-in absolute right-0 z-20 mt-2 w-48 rounded-card border-2 border-ink bg-surface p-2 shadow-hard">
                    {TABS.slice(3).map((t) => (
                      <li key={t.key}><Link href={`${base}/${t.key}`} className="flex min-h-[44px] items-center rounded-control px-3 hover:bg-soft">{t.label}</Link></li>
                    ))}
                  </ul>
                )}
              </li>
            </ul>
          </nav>
          {error && error.status !== 404 && <ErrorBox message={error.message} />}
          {children}
        </>
      )}
    </AppShell>
  );
}
