"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { isAdmin, clearAuth } from "@/lib/auth";
import { apiGet } from "@/lib/api";

type UserRow = {
  id: number;
  username: string;
  email: string;
  created_at: string;
  is_admin: boolean;
  uploads: number;
  conversions: number;
};

type StatsResponse = {
  total_users: number;
  total_uploads: number;
  total_conversions: number;
};

type RecentJob = {
  job_id: string;
  username: string | null;
  email: string | null;
  action: string;
  filename: string | null;
  printer_id: string | null;
  created_at: string;
};

export default function AdminPage() {
  const router = useRouter();
  const [tab, setTab] = useState<"users" | "recent">("users");
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [users, setUsers] = useState<UserRow[]>([]);
  const [recent, setRecent] = useState<RecentJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!isAdmin()) {
      router.push("/convert");
      return;
    }
    Promise.all([
      apiGet<StatsResponse>("/admin/stats", true),
      apiGet<UserRow[]>("/admin/users", true),
      apiGet<RecentJob[]>("/admin/recent", true),
    ])
      .then(([s, u, r]) => {
        setStats(s);
        setUsers(u);
        setRecent(r);
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Failed to load admin data"))
      .finally(() => setLoading(false));
  }, [router]);

  function formatDate(iso: string) {
    return new Date(iso).toLocaleString("en-BE", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  return (
    <div className="min-h-screen bg-surface">
      {/* Navbar */}
      <nav className="border-b border-surface-border bg-surface-elevated px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 bg-brand rounded-sm flex items-center justify-center">
            <svg viewBox="0 0 24 24" fill="white" className="w-4 h-4">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
            </svg>
          </div>
          <span className="font-bold text-white tracking-tight">
            Auto<span className="text-brand">Slice</span>
          </span>
          <span className="ml-3 text-xs text-zinc-500 bg-surface-card border border-surface-border rounded px-2 py-0.5">
            Admin
          </span>
        </div>
        <div className="flex items-center gap-4">
          <Link href="/convert" className="text-xs text-zinc-500 hover:text-brand transition-colors">
            Back to Convert
          </Link>
          <button
            onClick={() => { clearAuth(); router.push("/login"); }}
            className="text-xs text-zinc-500 hover:text-brand transition-colors"
          >
            Sign out
          </button>
        </div>
      </nav>

      <main className="max-w-5xl mx-auto px-4 py-10">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-white mb-1">Admin Dashboard</h1>
          <p className="text-zinc-500 text-sm">Platform overview and user management.</p>
        </div>

        {error && (
          <div className="mb-6 p-3 bg-brand/10 border border-brand/30 rounded-lg text-brand text-sm">
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex justify-center py-20">
            <div className="w-8 h-8 border-2 border-brand border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <>
            {/* Stats cards */}
            <div className="grid grid-cols-3 gap-4 mb-8">
              <div className="bg-surface-card border border-surface-border rounded-xl p-5">
                <p className="text-xs text-zinc-500 uppercase tracking-wide mb-1">Total Users</p>
                <p className="text-3xl font-bold text-white">{stats?.total_users ?? 0}</p>
              </div>
              <div className="bg-surface-card border border-surface-border rounded-xl p-5">
                <p className="text-xs text-zinc-500 uppercase tracking-wide mb-1">Total Uploads</p>
                <p className="text-3xl font-bold text-white">{stats?.total_uploads ?? 0}</p>
              </div>
              <div className="bg-surface-card border border-surface-border rounded-xl p-5">
                <p className="text-xs text-zinc-500 uppercase tracking-wide mb-1">Total Conversions</p>
                <p className="text-3xl font-bold text-white">{stats?.total_conversions ?? 0}</p>
              </div>
            </div>

            {/* Tabs */}
            <div className="flex gap-1 mb-6 bg-surface-card border border-surface-border rounded-lg p-1 w-fit">
              <button
                onClick={() => setTab("users")}
                className={`px-4 py-1.5 rounded text-sm font-medium transition-colors ${
                  tab === "users"
                    ? "bg-brand text-white"
                    : "text-zinc-400 hover:text-white"
                }`}
              >
                Users
              </button>
              <button
                onClick={() => setTab("recent")}
                className={`px-4 py-1.5 rounded text-sm font-medium transition-colors ${
                  tab === "recent"
                    ? "bg-brand text-white"
                    : "text-zinc-400 hover:text-white"
                }`}
              >
                Recent Activity
              </button>
            </div>

            {/* Users table */}
            {tab === "users" && (
              <div className="bg-surface-card border border-surface-border rounded-xl overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-surface-border">
                      <th className="text-left px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">User</th>
                      <th className="text-left px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">Email</th>
                      <th className="text-left px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">Joined</th>
                      <th className="text-right px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">Uploads</th>
                      <th className="text-right px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">Conversions</th>
                      <th className="text-center px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">Role</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((u, i) => (
                      <tr
                        key={u.id}
                        className={`border-b border-surface-border last:border-0 ${i % 2 === 0 ? "" : "bg-surface/30"}`}
                      >
                        <td className="px-4 py-3 text-white font-medium">{u.username}</td>
                        <td className="px-4 py-3 text-zinc-400">{u.email}</td>
                        <td className="px-4 py-3 text-zinc-500 text-xs">{formatDate(u.created_at)}</td>
                        <td className="px-4 py-3 text-zinc-300 text-right">{u.uploads}</td>
                        <td className="px-4 py-3 text-zinc-300 text-right">{u.conversions}</td>
                        <td className="px-4 py-3 text-center">
                          {u.is_admin ? (
                            <span className="text-xs bg-brand/20 text-brand border border-brand/30 rounded px-2 py-0.5">
                              Admin
                            </span>
                          ) : (
                            <span className="text-xs text-zinc-600">User</span>
                          )}
                        </td>
                      </tr>
                    ))}
                    {users.length === 0 && (
                      <tr>
                        <td colSpan={6} className="px-4 py-8 text-center text-zinc-500">No users yet.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}

            {/* Recent activity table */}
            {tab === "recent" && (
              <div className="bg-surface-card border border-surface-border rounded-xl overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-surface-border">
                      <th className="text-left px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">Time</th>
                      <th className="text-left px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">User</th>
                      <th className="text-left px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">Action</th>
                      <th className="text-left px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">File</th>
                      <th className="text-left px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">Printer</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recent.map((r, i) => (
                      <tr
                        key={r.job_id}
                        className={`border-b border-surface-border last:border-0 ${i % 2 === 0 ? "" : "bg-surface/30"}`}
                      >
                        <td className="px-4 py-3 text-zinc-500 text-xs whitespace-nowrap">{formatDate(r.created_at)}</td>
                        <td className="px-4 py-3 text-zinc-400">{r.username ?? <span className="text-zinc-600 italic">guest</span>}</td>
                        <td className="px-4 py-3">
                          <span className={`text-xs font-medium px-2 py-0.5 rounded border ${
                            r.action === "convert"
                              ? "bg-green-500/10 text-green-400 border-green-500/20"
                              : "bg-blue-500/10 text-blue-400 border-blue-500/20"
                          }`}>
                            {r.action}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-zinc-400 text-xs max-w-[200px] truncate">{r.filename ?? "—"}</td>
                        <td className="px-4 py-3 text-zinc-500 text-xs">{r.printer_id ?? "—"}</td>
                      </tr>
                    ))}
                    {recent.length === 0 && (
                      <tr>
                        <td colSpan={5} className="px-4 py-8 text-center text-zinc-500">No activity yet.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
