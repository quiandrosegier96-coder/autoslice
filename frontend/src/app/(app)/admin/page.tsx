"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { isAdmin } from "@/lib/auth";
import { apiGet } from "@/lib/api";
import { Navbar } from "@/components/Navbar";

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

function StatCard({ label, value, icon }: { label: string; value: number; icon: React.ReactNode }) {
  return (
    <div className="bg-surface-card border border-surface-border rounded-xl p-5 flex items-center gap-4">
      <div className="w-10 h-10 rounded-lg bg-brand/10 border border-brand/20 text-brand flex items-center justify-center shrink-0">
        {icon}
      </div>
      <div>
        <p className="text-xs text-zinc-500 uppercase tracking-wide mb-0.5">{label}</p>
        <p className="text-2xl font-bold text-white">{value}</p>
      </div>
    </div>
  );
}

export default function AdminPage() {
  const router = useRouter();
  const [tab, setTab] = useState<"users" | "recent">("users");
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [users, setUsers] = useState<UserRow[]>([]);
  const [recent, setRecent] = useState<RecentJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!isAdmin()) { router.push("/convert"); return; }
    Promise.all([
      apiGet<StatsResponse>("/admin/stats", true),
      apiGet<UserRow[]>("/admin/users", true),
      apiGet<RecentJob[]>("/admin/recent", true),
    ])
      .then(([s, u, r]) => { setStats(s); setUsers(u); setRecent(r); })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Failed to load admin data"))
      .finally(() => setLoading(false));
  }, [router]);

  function formatDate(iso: string) {
    return new Date(iso).toLocaleString("en-BE", {
      day: "2-digit", month: "short", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  }

  function timeAgo(iso: string) {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  }

  return (
    <div className="min-h-screen bg-surface">
      <Navbar showAdmin />

      <main className="max-w-5xl mx-auto px-4 py-10">
        <div className="mb-8 flex items-center gap-3">
          <div>
            <h1 className="text-2xl font-bold text-white mb-1">Admin Dashboard</h1>
            <p className="text-zinc-500 text-sm">Platform overview and user management.</p>
          </div>
          <span className="ml-2 text-xs text-brand bg-brand/10 border border-brand/20 rounded-full px-2.5 py-0.5 font-medium">
            Admin
          </span>
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
            {/* Stats */}
            <div className="grid grid-cols-3 gap-4 mb-8">
              <StatCard
                label="Total Users"
                value={stats?.total_users ?? 0}
                icon={
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                      d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z"/>
                  </svg>
                }
              />
              <StatCard
                label="Total Uploads"
                value={stats?.total_uploads ?? 0}
                icon={
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                      d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/>
                  </svg>
                }
              />
              <StatCard
                label="Total Conversions"
                value={stats?.total_conversions ?? 0}
                icon={
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                      d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
                  </svg>
                }
              />
            </div>

            {/* Tabs */}
            <div className="flex border-b border-surface-border mb-6">
              {(["users", "recent"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  className={`px-5 py-2.5 text-sm font-medium transition-colors relative ${
                    tab === t ? "text-white" : "text-zinc-500 hover:text-zinc-300"
                  }`}
                >
                  {t === "users" ? "Users" : "Recent Activity"}
                  {tab === t && (
                    <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-brand rounded-t-full" />
                  )}
                </button>
              ))}
            </div>

            {/* Users table */}
            {tab === "users" && (
              <div className="bg-surface-card border border-surface-border rounded-xl overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-surface-border bg-surface/30">
                      <th className="text-left px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">User</th>
                      <th className="text-left px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">Email</th>
                      <th className="text-left px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">Joined</th>
                      <th className="text-right px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">Uploads</th>
                      <th className="text-right px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">Conversions</th>
                      <th className="text-center px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">Role</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-border">
                    {users.map((u) => (
                      <tr key={u.id} className="hover:bg-surface/40 transition-colors">
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2.5">
                            <div className="w-7 h-7 rounded-full bg-brand/10 border border-brand/20 flex items-center justify-center text-xs font-semibold text-brand shrink-0">
                              {u.username[0].toUpperCase()}
                            </div>
                            <span className="text-white font-medium">{u.username}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-zinc-400 text-xs">{u.email}</td>
                        <td className="px-4 py-3 text-zinc-500 text-xs whitespace-nowrap">{formatDate(u.created_at)}</td>
                        <td className="px-4 py-3 text-zinc-300 text-right font-mono text-xs">{u.uploads}</td>
                        <td className="px-4 py-3 text-zinc-300 text-right font-mono text-xs">{u.conversions}</td>
                        <td className="px-4 py-3 text-center">
                          {u.is_admin ? (
                            <span className="text-xs bg-brand/20 text-brand border border-brand/30 rounded-full px-2.5 py-0.5 font-medium">
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
                        <td colSpan={6} className="px-4 py-10 text-center text-zinc-500">No users yet.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}

            {/* Recent activity */}
            {tab === "recent" && (
              <div className="bg-surface-card border border-surface-border rounded-xl overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-surface-border bg-surface/30">
                      <th className="text-left px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">Time</th>
                      <th className="text-left px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">User</th>
                      <th className="text-left px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">Action</th>
                      <th className="text-left px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">File</th>
                      <th className="text-left px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">Printer</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-border">
                    {recent.map((r) => (
                      <tr key={r.job_id} className="hover:bg-surface/40 transition-colors">
                        <td className="px-4 py-3 text-zinc-500 text-xs whitespace-nowrap" title={formatDate(r.created_at)}>
                          {timeAgo(r.created_at)}
                        </td>
                        <td className="px-4 py-3 text-zinc-400 text-sm">
                          {r.username ?? <span className="text-zinc-600 italic text-xs">guest</span>}
                        </td>
                        <td className="px-4 py-3">
                          <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${
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
                        <td colSpan={5} className="px-4 py-10 text-center text-zinc-500">No activity yet.</td>
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
