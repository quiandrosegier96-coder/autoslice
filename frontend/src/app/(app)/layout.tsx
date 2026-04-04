"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { clearAuth, getUser, isAdmin as checkIsAdmin, isLoggedIn } from "@/lib/auth";
import { useLang } from "@/contexts/LangContext";
import { LANGS, type Lang } from "@/lib/i18n";

// ── Icons ─────────────────────────────────────────────────────────────────

function IconBolt() {
  return (
    <svg className="w-[17px] h-[17px] shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
    </svg>
  );
}

function IconClock() {
  return (
    <svg className="w-[17px] h-[17px] shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
        d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

function IconUsers() {
  return (
    <svg className="w-[17px] h-[17px] shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
        d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  );
}

function IconGear() {
  return (
    <svg className="w-[17px] h-[17px] shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
        d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  );
}

function IconShield() {
  return (
    <svg className="w-[17px] h-[17px] shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
        d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
    </svg>
  );
}

function IconLogout() {
  return (
    <svg className="w-[15px] h-[15px] shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
        d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
    </svg>
  );
}

function IconChevron({ open }: { open: boolean }) {
  return (
    <svg
      className={`w-3.5 h-3.5 shrink-0 transition-transform duration-200 ${open ? "rotate-180" : ""}`}
      fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
    </svg>
  );
}

// ── Layout ─────────────────────────────────────────────────────────────────

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const pathname  = usePathname();
  const router    = useRouter();
  const { lang, setLang, t } = useLang();

  const [user, setUser]               = useState<{ username: string; email: string; is_admin: boolean } | null>(null);
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  useEffect(() => {
    if (!isLoggedIn()) {
      router.push("/login");
      return;
    }
    setUser(getUser());
  }, [router]);

  // Close user dropdown on outside click
  useEffect(() => {
    if (!userMenuOpen) return;
    const close = () => setUserMenuOpen(false);
    document.addEventListener("click", close);
    return () => document.removeEventListener("click", close);
  }, [userMenuOpen]);

  // Viewer page is fullscreen — skip the sidebar shell entirely
  if (pathname.startsWith("/viewer/")) {
    return <>{children}</>;
  }

  const admin = checkIsAdmin();

  const NAV_ITEMS: Array<{
    href: string;
    label: string;
    icon: React.ReactNode;
    disabled?: boolean;
  }> = [
    { href: "/convert",   label: t("nav_convert"),   icon: <IconBolt /> },
    { href: "/history",   label: t("nav_history"),   icon: <IconClock /> },
    { href: "/community", label: t("nav_community"), icon: <IconUsers /> },
    { href: "/settings",  label: "Instellingen",     icon: <IconGear />, disabled: true },
    ...(admin ? [{ href: "/admin", label: t("nav_admin"), icon: <IconShield /> }] : []),
  ];

  function handleSignOut() {
    clearAuth();
    router.push("/login");
  }

  return (
    <div className="flex h-screen bg-[#070709] overflow-hidden">

      {/* ═══════════ SIDEBAR ═══════════ */}
      <aside className="w-[220px] shrink-0 h-screen flex flex-col bg-[#07070b] border-r border-white/[0.055]
                        shadow-[4px_0_32px_rgba(0,0,0,0.4)]">

        {/* Brand */}
        <div className="px-5 pt-5 pb-4 border-b border-white/[0.055]">
          <Link href="/convert" className="flex items-center gap-2.5 group w-fit">
            <div className="w-8 h-8 bg-brand rounded-xl flex items-center justify-center
                            shadow-[0_0_18px_rgba(224,36,36,0.35)]
                            group-hover:shadow-[0_0_24px_rgba(224,36,36,0.5)] transition-shadow duration-200">
              <svg viewBox="0 0 24 24" fill="white" className="w-4 h-4">
                <path d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <div className="leading-none">
              <p className="text-[15px] font-bold text-white tracking-tight">
                Auto<span className="text-brand">Slice</span>
              </p>
              <p className="text-[9px] text-zinc-700 font-semibold tracking-[0.18em] uppercase mt-[3px]">
                Smart 3MF → G-Code
              </p>
            </div>
          </Link>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
          {NAV_ITEMS.map(({ href, label, icon, disabled }) => {
            const active = pathname === href || (!disabled && href !== "/" && pathname.startsWith(href + "/"));

            if (disabled) {
              return (
                <div key={href}
                  className="flex items-center gap-3 px-3 py-2.5 rounded-xl select-none cursor-not-allowed">
                  <span className="text-zinc-800">{icon}</span>
                  <span className="text-sm font-medium text-zinc-700 flex-1">{label}</span>
                  <span className="text-[9px] font-bold text-zinc-700 bg-zinc-800/60 px-1.5 py-0.5
                                   rounded-full uppercase tracking-wider">
                    Soon
                  </span>
                </div>
              );
            }

            return (
              <Link key={href} href={href}
                className={[
                  "relative flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium",
                  "transition-all duration-150 group",
                  active
                    ? "bg-brand/[0.16] text-white shadow-[0_0_20px_rgba(224,36,36,0.1),inset_0_1px_0_rgba(255,255,255,0.05)]"
                    : "text-zinc-500 hover:text-zinc-200 hover:bg-white/[0.04]",
                ].join(" ")}>

                {/* Active left accent bar */}
                {active && (
                  <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-[26px]
                                   bg-brand rounded-r-full shadow-[0_0_12px_rgba(224,36,36,0.9)]" />
                )}

                <span className={active
                  ? "text-brand"
                  : "text-zinc-600 group-hover:text-zinc-400 transition-colors duration-150"}>
                  {icon}
                </span>

                {label}
              </Link>
            );
          })}
        </nav>

        {/* Pro tip card */}
        <div className="px-3 pb-4 shrink-0">
          <div className="bg-white/[0.03] border border-white/[0.055] rounded-2xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-6 h-6 rounded-lg bg-yellow-500/15 flex items-center justify-center shrink-0">
                <svg className="w-3.5 h-3.5 text-yellow-400" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M9 21c0 .55.45 1 1 1h4c.55 0 1-.45 1-1v-1H9v1zm3-19C8.14 2 5 5.14 5 9c0 2.38 1.19 4.47 3 5.74V17c0 .55.45 1 1 1h6c.55 0 1-.45 1-1v-2.26c1.81-1.27 3-3.36 3-5.74 0-3.86-3.14-7-7-7z" />
                </svg>
              </div>
              <span className="text-xs font-semibold text-zinc-300">Pro tip</span>
            </div>
            <p className="text-[11px] text-zinc-500 leading-relaxed">
              Gebruik ACE Pro voor de beste kwaliteit en snelheid.
            </p>
          </div>
        </div>
      </aside>

      {/* ═══════════ MAIN AREA ═══════════ */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden relative">

        {/* Background decorations */}
        <div className="absolute inset-0 pointer-events-none overflow-hidden">
          {/* Top-right red glow blob */}
          <div className="absolute -top-40 -right-40 w-[600px] h-[600px] rounded-full
                          bg-brand/[0.11] blur-[120px]" />
          {/* Center-top secondary glow */}
          <div className="absolute -top-20 left-1/3 w-[360px] h-[280px] rounded-full
                          bg-brand/[0.05] blur-[90px]" />
          {/* Bottom-left ambient glow */}
          <div className="absolute -bottom-20 -left-10 w-[480px] h-[320px] rounded-full
                          bg-brand/[0.07] blur-[100px]" />
          {/* Perspective grid */}
          <div className="absolute bottom-0 left-0 right-0 h-[260px]">
            <div
              className="absolute inset-0"
              style={{
                backgroundImage: [
                  "linear-gradient(rgba(224,36,36,0.085) 1px, transparent 1px)",
                  "linear-gradient(90deg, rgba(224,36,36,0.085) 1px, transparent 1px)",
                ].join(","),
                backgroundSize: "44px 44px",
                transform: "perspective(300px) rotateX(58deg) scaleX(1.7)",
                transformOrigin: "50% 0%",
              }}
            />
            {/* Fade the grid out toward the top */}
            <div className="absolute inset-0 bg-gradient-to-t from-[#070709]/80 via-[#070709]/20 to-transparent" />
          </div>
        </div>

        {/* ── Top bar ── */}
        <header className="relative z-10 h-[50px] shrink-0 flex items-center justify-end px-6 gap-3
                           border-b border-white/[0.055] bg-[#070709]/50 backdrop-blur-md">

          {/* Language switcher */}
          <div className="flex items-center bg-white/[0.05] border border-white/[0.08] rounded-lg px-1 py-1">
            {LANGS.map(({ code, label }) => (
              <button
                key={code}
                onClick={() => setLang(code as Lang)}
                className={[
                  "px-2 py-0.5 rounded text-[11px] font-bold transition-all duration-150",
                  lang === code
                    ? "text-white bg-white/[0.1]"
                    : "text-zinc-600 hover:text-zinc-300",
                ].join(" ")}>
                {label}
              </button>
            ))}
          </div>

          {/* User menu */}
          <div className="relative">
            <button
              onClick={(e) => { e.stopPropagation(); setUserMenuOpen(!userMenuOpen); }}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-white/[0.08]
                         bg-white/[0.04] hover:bg-white/[0.07] transition-colors">
              <span className="w-[7px] h-[7px] rounded-full bg-green-500 shrink-0" />
              <span className="text-zinc-200 font-medium text-[13px]">
                {user?.username ?? "…"}
              </span>
              <IconChevron open={userMenuOpen} />
            </button>

            {userMenuOpen && (
              <div className="absolute right-0 top-full mt-1.5 w-48
                              bg-[#0e0e14] border border-white/[0.08] rounded-xl
                              shadow-[0_12px_40px_rgba(0,0,0,0.6)] z-50 overflow-hidden">
                <div className="px-3 py-2.5 border-b border-white/[0.06]">
                  <p className="text-[11px] text-zinc-500 truncate">{user?.email ?? ""}</p>
                </div>
                <button
                  onClick={handleSignOut}
                  className="w-full flex items-center gap-2.5 px-3 py-2.5 text-[13px]
                             text-zinc-400 hover:text-red-400 hover:bg-red-500/[0.07] transition-colors">
                  <IconLogout />
                  {t("nav_signout")}
                </button>
              </div>
            )}
          </div>
        </header>

        {/* ── Page content ── */}
        <main className="relative z-10 flex-1 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
