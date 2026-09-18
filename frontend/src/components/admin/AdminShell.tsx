"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { adminLogout, adminMe, UNAUTHORIZED_EVENT } from "@/lib/api";
import { branding } from "@/config/branding";
import { t } from "@/i18n";
import { LiveProvider } from "./LiveContext";

const NAV: { href: string; key: "admin.nav.dashboard" | "admin.nav.participants" | "admin.nav.draws" | "admin.nav.winners" | "admin.nav.settings" | "admin.nav.audit" }[] = [
  { href: "/admin", key: "admin.nav.dashboard" },
  { href: "/admin/participants", key: "admin.nav.participants" },
  { href: "/admin/draws", key: "admin.nav.draws" },
  { href: "/admin/winners", key: "admin.nav.winners" },
  { href: "/admin/settings", key: "admin.nav.settings" },
  { href: "/admin/audit", key: "admin.nav.audit" },
];

/** Client-side auth guard + sidebar. Redirects to /admin/login on 401. */
export function AdminShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [authed, setAuthed] = useState<boolean | null>(null);
  const [login, setLogin] = useState<string>("");
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    adminMe().then(
      (me) => {
        if (cancelled) return;
        setLogin(me.login);
        setAuthed(true);
      },
      () => {
        if (!cancelled) router.replace("/admin/login");
      },
    );
    const onUnauthorized = () => router.replace("/admin/login");
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => {
      cancelled = true;
      window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    };
  }, [router]);

  useEffect(() => {
    setMenuOpen(false);
  }, [pathname]);

  const handleLogout = async () => {
    try {
      await adminLogout();
    } finally {
      router.replace("/admin/login");
    }
  };

  if (authed !== true) {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-slate-50 text-slate-500">{t("admin.checking_session")}</div>
    );
  }

  const isActive = (href: string) => (href === "/admin" ? pathname === "/admin" : pathname.startsWith(href));

  const nav = (
    <nav className="flex flex-col gap-1" aria-label={t("admin.nav.menu")}>
      {NAV.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          aria-current={isActive(item.href) ? "page" : undefined}
          className={`rounded-lg px-3 py-2 text-sm font-medium ${
            isActive(item.href) ? "bg-slate-900 text-white" : "text-slate-700 hover:bg-slate-200"
          }`}
        >
          {t(item.key)}
        </Link>
      ))}
      <a
        href="/draw"
        target="_blank"
        rel="noopener"
        className="mt-2 rounded-lg px-3 py-2 text-sm font-medium text-sky-700 hover:bg-sky-50"
      >
        {t("admin.nav.live")} ↗
      </a>
      <button
        type="button"
        onClick={handleLogout}
        className="mt-2 rounded-lg px-3 py-2 text-left text-sm font-medium text-slate-600 hover:bg-slate-200"
      >
        {t("admin.nav.logout")}
        {login && <span className="ml-1 text-slate-400">({login})</span>}
      </button>
    </nav>
  );

  return (
    <LiveProvider enabled>
      <div className="min-h-dvh bg-slate-50 text-slate-900 lg:flex">
        <aside className="hidden w-60 shrink-0 border-r border-slate-200 bg-slate-100 p-4 lg:block">
          <div className="mb-6 px-3">
            <p className="text-xs font-semibold tracking-widest text-slate-500 uppercase">{t("admin.title")}</p>
            <p className="mt-1 text-sm font-semibold text-slate-900">{branding.eventName}</p>
          </div>
          {nav}
        </aside>

        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3 lg:hidden">
          <p className="text-sm font-semibold">{t("admin.title")}</p>
          <button
            type="button"
            onClick={() => setMenuOpen((v) => !v)}
            aria-expanded={menuOpen}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
          >
            {t("admin.nav.menu")}
          </button>
        </header>
        {menuOpen && <div className="border-b border-slate-200 bg-slate-100 p-4 lg:hidden">{nav}</div>}

        <main className="min-w-0 flex-1 p-4 sm:p-6 lg:p-8">{children}</main>
      </div>
    </LiveProvider>
  );
}
