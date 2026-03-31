"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { clearAuth, getUser } from "@/lib/auth";
import { useLang } from "@/contexts/LangContext";
import { LANGS, type Lang } from "@/lib/i18n";

export function Navbar({ showAdmin = false }: { showAdmin?: boolean }) {
  const pathname = usePathname();
  const router = useRouter();
  const { lang, setLang, t } = useLang();
  const [user, setUser] = useState<{ username: string } | null>(null);

  useEffect(() => {
    setUser(getUser());
  }, []);

  const NAV_LINKS = [
    { href: "/convert",   label: t("nav_convert") },
    { href: "/community", label: t("nav_community") },
    { href: "/history",   label: t("nav_history") },
  ];

  return (
    <nav className="sticky top-0 z-30 border-b border-surface-border/60 bg-surface-elevated/80 backdrop-blur-xl px-6 py-0 flex items-center justify-between h-13"
      style={{ height: "52px" }}>

      {/* Logo */}
      <Link href="/convert" className="flex items-center gap-2.5 shrink-0 group">
        <div className="w-7 h-7 bg-brand rounded-lg flex items-center justify-center shadow-sm
                        group-hover:shadow-[0_0_12px_rgba(224,36,36,0.4)] transition-shadow duration-200">
          <svg viewBox="0 0 24 24" fill="white" className="w-3.5 h-3.5">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
          </svg>
        </div>
        <span className="font-semibold text-[15px] text-white tracking-tight">
          Auto<span className="text-brand">Slice</span>
        </span>
      </Link>

      {/* Nav links */}
      <div className="flex items-center h-full">
        {NAV_LINKS.map(({ href, label }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link key={href} href={href}
              className={`relative flex items-center h-full px-4 text-[13px] font-medium transition-colors duration-150
                ${active ? "text-white" : "text-zinc-500 hover:text-zinc-300"}`}>
              {label}
              {active && (
                <span className="absolute bottom-0 left-3 right-3 h-[2px] bg-brand rounded-full
                                 shadow-[0_0_6px_rgba(224,36,36,0.6)]" />
              )}
            </Link>
          );
        })}
        {showAdmin && (
          <Link href="/admin"
            className={`relative flex items-center h-full px-4 text-[13px] font-medium transition-colors duration-150
              ${pathname === "/admin" ? "text-brand" : "text-brand/50 hover:text-brand"}`}>
            {t("nav_admin")}
            {pathname === "/admin" && (
              <span className="absolute bottom-0 left-3 right-3 h-[2px] bg-brand rounded-full" />
            )}
          </Link>
        )}
      </div>

      {/* Right side */}
      <div className="flex items-center gap-3 shrink-0">
        {/* Lang switcher */}
        <div className="flex items-center gap-0.5 bg-surface-card border border-surface-border rounded-lg px-1.5 py-1">
          {LANGS.map(({ code, label }) => (
            <button key={code} onClick={() => setLang(code as Lang)}
              className={`px-1.5 py-0.5 rounded text-[11px] font-semibold transition-colors ${
                lang === code
                  ? "text-brand"
                  : "text-zinc-600 hover:text-zinc-400"
              }`}>
              {label}
            </button>
          ))}
        </div>

        {user?.username && (
          <span className="hidden sm:flex items-center gap-1.5 text-xs text-zinc-500">
            <span className="w-1.5 h-1.5 rounded-full bg-green-500/70" />
            {user.username}
          </span>
        )}

        <button
          onClick={() => { clearAuth(); router.push("/login"); }}
          className="text-[12px] text-zinc-600 hover:text-zinc-300 transition-colors px-2 py-1
                     border border-transparent hover:border-surface-border rounded-md">
          {t("nav_signout")}
        </button>
      </div>
    </nav>
  );
}
