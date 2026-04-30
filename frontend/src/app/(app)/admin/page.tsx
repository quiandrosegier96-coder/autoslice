"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { isAdmin, getUser } from "@/lib/auth";
import { apiGet, apiPatch, getSiteConfig, adminSetSiteConfig, type SiteConfig } from "@/lib/api";

type UserRow = {
  id: number;
  username: string;
  email: string;
  created_at: string;
  last_login: string | null;
  is_admin: boolean;
  is_verified: boolean;
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

type ResetTokenRow = {
  id: number;
  email: string;
  token: string;
  created_at: string;
  used: boolean;
};

type GenerationLogRow = {
  id: number;
  job_id: string;
  printer_id: string | null;
  filament_type: string | null;
  nozzle_size_mm: number | null;
  bbox_x: number | null; bbox_y: number | null; bbox_z: number | null;
  volume_cm3: number | null;
  contact_area_mm2: number | null;
  height_to_base_ratio: number | null;
  overhang_ratio: number | null;
  bridge_span_mm: number | null;
  support_risk: number | null;
  adhesion_risk: number | null;
  stability_risk: number | null;
  detail_risk: number | null;
  created_at: string;
};

type FeedbackRow = {
  id: number;
  job_id: string;
  username: string | null;
  outcome: string;
  notes: string | null;
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

function Toggle({ on, onChange }: { on: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      onClick={() => onChange(!on)}
      className={`relative w-11 h-6 rounded-full transition-colors duration-200 ${on ? "bg-brand" : "bg-white/10"}`}
    >
      <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform duration-200 ${on ? "translate-x-5" : "translate-x-0"}`} />
    </button>
  );
}

export default function AdminPage() {
  const router = useRouter();
  const [tab, setTab] = useState<"users" | "recent" | "resets" | "engine" | "feedback" | "visibility">("users");
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [users, setUsers] = useState<UserRow[]>([]);
  const [recent, setRecent] = useState<RecentJob[]>([]);
  const [resets, setResets] = useState<ResetTokenRow[]>([]);
  const [engineLog, setEngineLog] = useState<GenerationLogRow[]>([]);
  const [feedbackLog, setFeedbackLog] = useState<FeedbackRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState<string | null>(null);
  const [siteConfig, setSiteConfig] = useState<SiteConfig | null>(null);
  const [configSaving, setConfigSaving] = useState(false);
  const [configMsg, setConfigMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  // Role management
  const [roleConfirm, setRoleConfirm] = useState<{ user: UserRow; grant: boolean } | null>(null);
  const [roleLoading, setRoleLoading] = useState(false);
  const [roleMsg, setRoleMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);
  const [verifyLoading, setVerifyLoading] = useState<number | null>(null);
  const currentUser = getUser();

  useEffect(() => {
    if (!isAdmin()) { router.push("/convert"); return; }
    Promise.all([
      apiGet<StatsResponse>("/admin/stats", true),
      apiGet<UserRow[]>("/admin/users", true),
      apiGet<RecentJob[]>("/admin/recent", true),
      apiGet<ResetTokenRow[]>("/admin/reset-tokens", true),
      apiGet<GenerationLogRow[]>("/admin/engine-log", true),
      apiGet<FeedbackRow[]>("/admin/feedback", true),
      getSiteConfig(),
    ])
      .then(([s, u, r, rt, el, fb, cfg]) => { setStats(s); setUsers(u); setRecent(r); setResets(rt); setEngineLog(el); setFeedbackLog(fb); setSiteConfig(cfg); })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Failed to load admin data"))
      .finally(() => setLoading(false));
  }, [router]);

  function copyToken(token: string) {
    navigator.clipboard.writeText(token);
    setCopied(token);
    setTimeout(() => setCopied(null), 2000);
  }

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

  async function verifyUser(u: UserRow) {
    setVerifyLoading(u.id);
    setRoleMsg(null);
    try {
      const updated = await apiPatch<UserRow>(`/admin/users/${u.id}/verify`, {});
      setUsers((prev) => prev.map((x) => x.id === updated.id ? updated : x));
      setRoleMsg({ type: "ok", text: `${u.username} is nu geverifieerd.` });
    } catch (err: unknown) {
      setRoleMsg({ type: "err", text: err instanceof Error ? err.message : "Verificatie mislukt." });
    } finally {
      setVerifyLoading(null);
    }
  }

  async function toggleConfig(key: keyof SiteConfig, value: boolean) {
    if (!siteConfig) return;
    const optimistic = { ...siteConfig, [key]: value };
    setSiteConfig(optimistic);
    setConfigSaving(true);
    setConfigMsg(null);
    try {
      const updated = await adminSetSiteConfig({ [key]: value });
      setSiteConfig(updated);
      setConfigMsg({ type: "ok", text: "Opgeslagen." });
      setTimeout(() => setConfigMsg(null), 2000);
    } catch (err: unknown) {
      setSiteConfig(siteConfig);
      setConfigMsg({ type: "err", text: err instanceof Error ? err.message : "Opslaan mislukt." });
    } finally {
      setConfigSaving(false);
    }
  }

  async function applyRoleChange() {
    if (!roleConfirm) return;
    setRoleLoading(true);
    setRoleMsg(null);
    try {
      const updated = await apiPatch<UserRow>(`/admin/users/${roleConfirm.user.id}/role`, {
        is_admin: roleConfirm.grant,
      });
      setUsers((prev) => prev.map((u) => u.id === updated.id ? updated : u));
      setRoleMsg({
        type: "ok",
        text: roleConfirm.grant
          ? `${roleConfirm.user.username} is now an admin.`
          : `Admin rights removed from ${roleConfirm.user.username}.`,
      });
    } catch (err: unknown) {
      setRoleMsg({ type: "err", text: err instanceof Error ? err.message : "Failed to update role." });
    } finally {
      setRoleLoading(false);
      setRoleConfirm(null);
    }
  }

  return (
    <main className="max-w-5xl mx-auto px-4 py-10">

      {/* ── Role confirm dialog ── */}
      {roleConfirm && (
        <>
          <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm" />
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div className="bg-[#0e0e14] border border-white/[0.1] rounded-2xl w-full max-w-sm
                            shadow-[0_24px_80px_rgba(0,0,0,0.8)]">
              <div className={`h-1 rounded-t-2xl ${roleConfirm.grant ? "bg-brand" : "bg-yellow-500"}`} />
              <div className="p-6">
                <h3 className="text-[15px] font-bold text-white mb-2">
                  {roleConfirm.grant ? "Admin rechten toekennen" : "Admin rechten intrekken"}
                </h3>
                <p className="text-[13px] text-zinc-400 mb-5">
                  {roleConfirm.grant
                    ? <>Weet je zeker dat je <strong className="text-white">{roleConfirm.user.username}</strong> admin rechten wilt geven?</>
                    : <>Weet je zeker dat je de admin rechten van <strong className="text-white">{roleConfirm.user.username}</strong> wilt intrekken?</>
                  }
                </p>
                <div className="flex gap-3">
                  <button
                    onClick={applyRoleChange}
                    disabled={roleLoading}
                    className={`flex-1 h-9 rounded-xl text-white text-[13px] font-semibold transition-all disabled:opacity-50
                      ${roleConfirm.grant
                        ? "bg-brand hover:bg-red-500"
                        : "bg-yellow-600 hover:bg-yellow-500"}`}
                  >
                    {roleLoading ? "Bezig…" : "Bevestigen"}
                  </button>
                  <button
                    onClick={() => setRoleConfirm(null)}
                    disabled={roleLoading}
                    className="flex-1 h-9 rounded-xl bg-white/[0.06] hover:bg-white/[0.1]
                               text-zinc-400 text-[13px] transition-all disabled:opacity-50"
                  >
                    Annuleren
                  </button>
                </div>
              </div>
            </div>
          </div>
        </>
      )}

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
              {([
                { id: "users", label: "Users" },
                { id: "recent", label: "Recent Activity" },
                { id: "resets", label: `Reset Codes${resets.filter(r => !r.used).length > 0 ? ` (${resets.filter(r => !r.used).length})` : ""}` },
              { id: "engine", label: `Engine Log${engineLog.length > 0 ? ` (${engineLog.length})` : ""}` },
              { id: "feedback", label: `Feedback${feedbackLog.length > 0 ? ` (${feedbackLog.length})` : ""}` },
              { id: "visibility", label: "Zichtbaarheid" },
              ] as const).map(({ id, label }) => (
                <button
                  key={id}
                  onClick={() => setTab(id)}
                  className={`px-5 py-2.5 text-sm font-medium transition-colors relative ${
                    tab === id ? "text-white" : "text-zinc-500 hover:text-zinc-300"
                  }`}
                >
                  {label}
                  {tab === id && (
                    <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-brand rounded-t-full" />
                  )}
                </button>
              ))}
            </div>

            {/* Users table */}
            {tab === "users" && (
              <div>
                {roleMsg && (
                  <div className={`mb-4 px-4 py-3 rounded-xl text-sm border ${
                    roleMsg.type === "ok"
                      ? "bg-green-500/10 border-green-500/20 text-green-400"
                      : "bg-red-500/10 border-red-500/20 text-red-400"
                  }`}>
                    {roleMsg.text}
                  </div>
                )}
                <div className="bg-surface-card border border-surface-border rounded-xl overflow-x-auto">
                  <table className="w-full min-w-[980px] text-sm">
                    <thead>
                      <tr className="border-b border-surface-border bg-surface/30">
                        <th className="text-left px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">User</th>
                        <th className="text-left px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">Email</th>
                        <th className="text-left px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">Joined</th>
                        <th className="text-left px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">Last Login</th>
                        <th className="text-right px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">Uploads</th>
                        <th className="text-right px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">Conversions</th>
                        <th className="text-center px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">Verified</th>
                        <th className="text-center px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">Role</th>
                        <th className="text-center px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-surface-border">
                      {users.map((u) => {
                        const isSelf = u.username === currentUser?.username;
                        return (
                          <tr key={u.id} className="hover:bg-surface/40 transition-colors">
                            <td className="px-4 py-3">
                              <div className="flex items-center gap-2.5">
                                <div className="w-7 h-7 rounded-full bg-brand/10 border border-brand/20 flex items-center justify-center text-xs font-semibold text-brand shrink-0">
                                  {u.username[0].toUpperCase()}
                                </div>
                                <span className="text-white font-medium">
                                  {u.username}
                                  {isSelf && <span className="ml-1.5 text-[10px] text-zinc-600">(jij)</span>}
                                </span>
                              </div>
                            </td>
                            <td className="px-4 py-3 text-zinc-400 text-xs">{u.email}</td>
                            <td className="px-4 py-3 text-zinc-500 text-xs whitespace-nowrap">{formatDate(u.created_at)}</td>
                            <td className="px-4 py-3 text-zinc-500 text-xs whitespace-nowrap">{u.last_login ? timeAgo(u.last_login) : "Never"}</td>
                            <td className="px-4 py-3 text-zinc-300 text-right font-mono text-xs">{u.uploads}</td>
                            <td className="px-4 py-3 text-zinc-300 text-right font-mono text-xs">{u.conversions}</td>
                            <td className="px-4 py-3 text-center">
                              {u.is_verified ? (
                                <span className="text-xs bg-green-500/10 text-green-400 border border-green-500/20 rounded-full px-2.5 py-0.5">
                                  ✓ Ja
                                </span>
                              ) : (
                                <span className="text-xs bg-yellow-500/10 text-yellow-400 border border-yellow-500/20 rounded-full px-2.5 py-0.5">
                                  Nee
                                </span>
                              )}
                            </td>
                            <td className="px-4 py-3 text-center">
                              {u.is_admin ? (
                                <span className="text-xs bg-brand/20 text-brand border border-brand/30 rounded-full px-2.5 py-0.5 font-medium">
                                  Admin
                                </span>
                              ) : (
                                <span className="text-xs text-zinc-600">User</span>
                              )}
                            </td>
                            <td className="px-4 py-3 text-center">
                              <div className="flex items-center justify-center gap-2">
                                {!u.is_verified && (
                                  <button
                                    onClick={() => verifyUser(u)}
                                    disabled={verifyLoading === u.id}
                                    className="text-xs px-2.5 py-1 rounded-lg border border-green-500/30 text-green-400
                                               hover:bg-green-500/10 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                                  >
                                    {verifyLoading === u.id ? "…" : "Verifieer"}
                                  </button>
                                )}
                                {u.is_admin ? (
                                  <button
                                    onClick={() => { setRoleMsg(null); setRoleConfirm({ user: u, grant: false }); }}
                                    disabled={isSelf}
                                    title={isSelf ? "Je kunt je eigen admin rechten niet intrekken" : "Admin rechten intrekken"}
                                    className="text-xs px-2.5 py-1 rounded-lg border border-yellow-500/30 text-yellow-400
                                               hover:bg-yellow-500/10 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                                  >
                                    Intrekken
                                  </button>
                                ) : (
                                  <button
                                    onClick={() => { setRoleMsg(null); setRoleConfirm({ user: u, grant: true }); }}
                                    className="text-xs px-2.5 py-1 rounded-lg border border-brand/30 text-brand
                                               hover:bg-brand/10 transition-colors"
                                  >
                                    Maak admin
                                  </button>
                                )}
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                      {users.length === 0 && (
                        <tr>
                          <td colSpan={8} className="px-4 py-10 text-center text-zinc-500">No users yet.</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Reset codes */}
            {tab === "resets" && (
              <div className="bg-surface-card border border-surface-border rounded-xl overflow-hidden">
                <div className="px-5 py-3 border-b border-surface-border">
                  <p className="text-xs text-zinc-500">
                    When a user requests a password reset, the code appears here. Copy it and share it with them.
                    Codes expire after 24 hours.
                  </p>
                </div>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-surface-border bg-surface/30">
                      <th className="text-left px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">Email</th>
                      <th className="text-left px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">Reset Code</th>
                      <th className="text-left px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">Requested</th>
                      <th className="text-center px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-border">
                    {resets.map((r) => (
                      <tr key={r.id} className="hover:bg-surface/40 transition-colors">
                        <td className="px-4 py-3 text-zinc-300 text-xs">{r.email}</td>
                        <td className="px-4 py-3">
                          {r.used ? (
                            <span className="font-mono text-xs text-zinc-600">••••••••••••</span>
                          ) : (
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-xs text-zinc-300 bg-surface-elevated border border-surface-border rounded px-2 py-0.5 max-w-[200px] truncate">
                                {r.token}
                              </span>
                              <button
                                onClick={() => copyToken(r.token)}
                                className="text-xs text-brand hover:text-brand-light transition-colors shrink-0"
                              >
                                {copied === r.token ? "Copied!" : "Copy"}
                              </button>
                            </div>
                          )}
                        </td>
                        <td className="px-4 py-3 text-zinc-500 text-xs">{formatDate(r.created_at)}</td>
                        <td className="px-4 py-3 text-center">
                          {r.used ? (
                            <span className="text-xs text-zinc-600">Used</span>
                          ) : (
                            <span className="text-xs bg-yellow-500/10 text-yellow-400 border border-yellow-500/20 rounded-full px-2 py-0.5">
                              Pending
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                    {resets.length === 0 && (
                      <tr>
                        <td colSpan={4} className="px-4 py-10 text-center text-zinc-500">No reset requests yet.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}

            {/* Engine log */}
            {tab === "engine" && (
              <div className="space-y-3">
                <p className="text-xs text-zinc-500 mb-4">
                  Every conversion is logged here with geometry features and risk scores. Use this to debug the engine.
                </p>
                {engineLog.length === 0 ? (
                  <div className="bg-surface-card border border-surface-border rounded-xl p-10 text-center text-zinc-500 text-sm">No conversions logged yet.</div>
                ) : engineLog.map((row) => (
                  <div key={row.id} className="bg-surface-card border border-surface-border rounded-xl p-4 text-xs">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <span className="font-mono text-zinc-400 text-[10px]">{row.job_id.slice(0, 8)}…</span>
                        <span className="text-zinc-300">{row.printer_id ?? "—"}</span>
                        <span className="text-zinc-500">{row.filament_type?.toUpperCase() ?? "—"}</span>
                        <span className="text-zinc-500">{row.nozzle_size_mm}mm nozzle</span>
                      </div>
                      <span className="text-zinc-600">{timeAgo(row.created_at)}</span>
                    </div>
                    <div className="grid grid-cols-4 gap-2 mb-3 text-zinc-400">
                      <div>Size: {row.bbox_x?.toFixed(0)}×{row.bbox_y?.toFixed(0)}×{row.bbox_z?.toFixed(0)}mm</div>
                      <div>Vol: {row.volume_cm3?.toFixed(1)} cm³</div>
                      <div>Contact: {row.contact_area_mm2?.toFixed(0)} mm²</div>
                      <div>HBR: {row.height_to_base_ratio?.toFixed(2)}</div>
                      <div>Overhang: {((row.overhang_ratio ?? 0) * 100).toFixed(1)}%</div>
                      <div>Bridge: {row.bridge_span_mm?.toFixed(1)} mm</div>
                    </div>
                    <div className="grid grid-cols-4 gap-2">
                      {[
                        { label: "Support", value: row.support_risk ?? 0, color: "bg-orange-500" },
                        { label: "Adhesion", value: row.adhesion_risk ?? 0, color: "bg-yellow-500" },
                        { label: "Stability", value: row.stability_risk ?? 0, color: "bg-red-500" },
                        { label: "Detail", value: row.detail_risk ?? 0, color: "bg-blue-500" },
                      ].map(({ label, value, color }) => (
                        <div key={label}>
                          <div className="flex justify-between text-[10px] text-zinc-500 mb-1">
                            <span>{label}</span><span>{value}</span>
                          </div>
                          <div className="h-1.5 bg-surface-elevated rounded-full overflow-hidden">
                            <div className={`h-full ${color} rounded-full`} style={{ width: `${value}%` }} />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Feedback */}
            {tab === "feedback" && (
              <div className="bg-surface-card border border-surface-border rounded-xl overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-surface-border bg-surface/30">
                      <th className="text-left px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">Time</th>
                      <th className="text-left px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">User</th>
                      <th className="text-left px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">Job</th>
                      <th className="text-left px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">Outcome</th>
                      <th className="text-left px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">Notes</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-border">
                    {feedbackLog.map((f) => (
                      <tr key={f.id} className="hover:bg-surface/40 transition-colors">
                        <td className="px-4 py-3 text-zinc-500 text-xs whitespace-nowrap">{timeAgo(f.created_at)}</td>
                        <td className="px-4 py-3 text-zinc-400 text-xs">{f.username ?? <span className="italic text-zinc-600">guest</span>}</td>
                        <td className="px-4 py-3 font-mono text-zinc-600 text-[10px]">{f.job_id.slice(0, 8)}…</td>
                        <td className="px-4 py-3">
                          <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${
                            f.outcome === "printed_ok" ? "bg-green-500/10 text-green-400 border-green-500/20" :
                            f.outcome.includes("missing") || f.outcome.includes("detached") || f.outcome.includes("collapsed") ? "bg-red-500/10 text-red-400 border-red-500/20" :
                            "bg-yellow-500/10 text-yellow-400 border-yellow-500/20"
                          }`}>
                            {f.outcome.replace(/_/g, " ")}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-zinc-500 text-xs">{f.notes ?? "—"}</td>
                      </tr>
                    ))}
                    {feedbackLog.length === 0 && (
                      <tr><td colSpan={5} className="px-4 py-10 text-center text-zinc-500">No feedback yet.</td></tr>
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
            {/* Visibility */}
            {tab === "visibility" && (
              <div className="space-y-6">
                {configMsg && (
                  <div className={`px-4 py-3 rounded-xl text-sm border ${configMsg.type === "ok" ? "bg-green-500/10 border-green-500/20 text-green-400" : "bg-red-500/10 border-red-500/20 text-red-400"}`}>
                    {configMsg.text}
                  </div>
                )}

                {[
                  {
                    heading: "Landingspagina secties",
                    items: [
                      { key: "landing_trustbar",    label: "Compatibiliteit balk",    desc: "Balk met Bambu Lab, MakerWorld, Anycubic..." },
                      { key: "landing_features",    label: "Features sectie",          desc: "6 feature cards (conversie, AI, multicolor...)" },
                      { key: "landing_how",         label: "Hoe het werkt",            desc: "3-stappen uitleg" },
                      { key: "landing_apppreview",  label: "AI Analyse sectie",        desc: "Printbaarheidscore en analyse mockup" },
                      { key: "landing_multicolor",  label: "Multicolor sectie",        desc: "ACE Pro 2 kleurslots showcase" },
                      { key: "landing_pricing",     label: "Prijzen",                  desc: "Starter / Pro / Team plannen" },
                      { key: "landing_downloadcta", label: "Download CTA",             desc: "Grote download sectie onderaan" },
                      { key: "landing_blog",        label: "Blog sectie",              desc: "3 blog cards (Tutorial, Handleiding, Update)" },
                    ],
                  },
                  {
                    heading: "App navigatie",
                    items: [
                      { key: "nav_history",   label: "Geschiedenis tab",  desc: "Conversie history van de gebruiker" },
                      { key: "nav_community", label: "Community tab",     desc: "Gedeelde community prints" },
                      { key: "nav_settings",  label: "Instellingen tab",  desc: "Gebruikersinstellingen pagina" },
                    ],
                  },
                  {
                    heading: "Platform",
                    items: [
                      { key: "registration_open", label: "Registratie open",   desc: "Nieuwe gebruikers kunnen zich aanmelden" },
                      { key: "maintenance_mode",  label: "Onderhoudsmodus",    desc: "Toont een melding aan alle gebruikers" },
                    ],
                  },
                ].map(({ heading, items }) => (
                  <div key={heading} className="bg-surface-card border border-surface-border rounded-xl overflow-hidden">
                    <div className="px-5 py-3 border-b border-surface-border bg-surface/30">
                      <p className="text-xs font-bold text-zinc-400 uppercase tracking-wider">{heading}</p>
                    </div>
                    <div className="divide-y divide-surface-border">
                      {items.map(({ key, label, desc }) => (
                        <div key={key} className="flex items-center justify-between px-5 py-4">
                          <div>
                            <p className="text-sm font-medium text-white">{label}</p>
                            <p className="text-xs text-zinc-500 mt-0.5">{desc}</p>
                          </div>
                          <Toggle
                            on={siteConfig ? siteConfig[key as keyof SiteConfig] as boolean : true}
                            onChange={(v) => toggleConfig(key as keyof SiteConfig, v)}
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                ))}

                {configSaving && (
                  <p className="text-xs text-zinc-500 text-center">Opslaan...</p>
                )}
              </div>
            )}
          </>
        )}
    </main>
  );
}
