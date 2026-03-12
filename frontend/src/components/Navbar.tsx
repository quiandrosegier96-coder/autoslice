"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { clearAuth, getUser } from "@/lib/auth";

const NAV_LINKS = [
  { href: "/convert", label: "Convert" },
  { href: "/history", label: "History" },
];

export function Navbar({ showAdmin = false }: { showAdmin?: boolean }) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<{ username: string } | null>(null);

  useEffect(() => {
    setUser(getUser());
  }, []);

  return (
    <nav className="sticky top-0 z-30 border-b border-surface-border bg-surface-elevated/90 backdrop-blur-sm px-6 py-0 flex items-center justify-between h-12">
      {/* Logo */}
      <Link href="/convert" className="flex items-center gap-2 shrink-0">
        <div className="w-6 h-6 bg-brand rounded-sm flex items-center justify-center">
          <svg viewBox="0 0 24 24" fill="white" className="w-3.5 h-3.5">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
          </svg>
        </div>
        <span className="font-bold text-white tracking-tight text-sm">
          Auto<span className="text-brand">Slice</span>
        </span>
      </Link>

      {/* Center tabs */}
      <div className="flex items-center h-full">
        {NAV_LINKS.map(({ href, label }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              className={`relative flex items-center h-full px-4 text-sm font-medium transition-colors duration-150
                ${active ? "text-white" : "text-zinc-500 hover:text-zinc-300"}`}
            >
              {label}
              {active && (
                <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-brand rounded-t-full" />
              )}
            </Link>
          );
        })}
        {showAdmin && (
          <Link
            href="/admin"
            className={`relative flex items-center h-full px-4 text-sm font-medium transition-colors duration-150
              ${pathname === "/admin" ? "text-brand" : "text-brand/60 hover:text-brand"}`}
          >
            Admin
            {pathname === "/admin" && (
              <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-brand rounded-t-full" />
            )}
          </Link>
        )}
      </div>

      {/* Right side */}
      <div className="flex items-center gap-3 shrink-0">
        {user?.username && (
          <span className="text-xs text-zinc-500 hidden sm:block">{user.username}</span>
        )}
        <button
          onClick={() => { clearAuth(); router.push("/login"); }}
          className="text-xs text-zinc-500 hover:text-brand transition-colors"
        >
          Sign out
        </button>
      </div>
    </nav>
  );
}
