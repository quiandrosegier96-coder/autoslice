"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { isLoggedIn, getUser, clearAuth } from "@/lib/auth";
import { apiGet } from "@/lib/api";

type HistoryJob = {
  job_id: string;
  action: string;
  filename: string | null;
  printer_id: string | null;
  created_at: string;
};

export default function HistoryPage() {
  const router = useRouter();
  const [user, setUser] = useState<{ username: string; email: string } | null>(null);
  const [jobs, setJobs] = useState<HistoryJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!isLoggedIn()) { router.push("/login"); return; }
    setUser(getUser());
    apiGet<HistoryJob[]>("/auth/history", true)
      .then(setJobs)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Failed to load history"))
      .finally(() => setLoading(false));
  }, [router]);

  function formatDate(iso: string) {
    return new Date(iso).toLocaleString("en-BE", {
      day: "2-digit", month: "short", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  }

  const uploads = jobs.filter(j => j.action === "upload");
  const converts = jobs.filter(j => j.action === "convert");

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
        </div>
        <div className="flex items-center gap-4">
          <span className="text-zinc-500 text-sm hidden sm:block">{user?.username}</span>
          <Link href="/convert" className="text-xs text-zinc-500 hover:text-brand transition-colors">
            Convert
          </Link>
          <button
            onClick={() => { clearAuth(); router.push("/login"); }}
            className="text-xs text-zinc-500 hover:text-brand transition-colors"
          >
            Sign out
          </button>
        </div>
      </nav>

      <main className="max-w-3xl mx-auto px-4 py-10">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-white mb-1">My History</h1>
          <p className="text-zinc-500 text-sm">Your recent uploads and conversions.</p>
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
        ) : jobs.length === 0 ? (
          <div className="text-center py-20 text-zinc-500">
            <p className="mb-4">No activity yet.</p>
            <Link href="/convert" className="text-brand hover:text-brand-light transition-colors text-sm">
              Convert your first file →
            </Link>
          </div>
        ) : (
          <>
            {/* Summary */}
            <div className="grid grid-cols-2 gap-4 mb-8">
              <div className="bg-surface-card border border-surface-border rounded-xl p-5">
                <p className="text-xs text-zinc-500 uppercase tracking-wide mb-1">Uploads</p>
                <p className="text-3xl font-bold text-white">{uploads.length}</p>
              </div>
              <div className="bg-surface-card border border-surface-border rounded-xl p-5">
                <p className="text-xs text-zinc-500 uppercase tracking-wide mb-1">Conversions</p>
                <p className="text-3xl font-bold text-white">{converts.length}</p>
              </div>
            </div>

            {/* History list */}
            <div className="bg-surface-card border border-surface-border rounded-xl overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-surface-border">
                    <th className="text-left px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">Time</th>
                    <th className="text-left px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">Action</th>
                    <th className="text-left px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">File</th>
                    <th className="text-left px-4 py-3 text-xs text-zinc-500 uppercase tracking-wide font-medium">Printer</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map((job, i) => (
                    <tr key={job.job_id + job.action} className={`border-b border-surface-border last:border-0 ${i % 2 === 0 ? "" : "bg-surface/30"}`}>
                      <td className="px-4 py-3 text-zinc-500 text-xs whitespace-nowrap">{formatDate(job.created_at)}</td>
                      <td className="px-4 py-3">
                        <span className={`text-xs font-medium px-2 py-0.5 rounded border ${
                          job.action === "convert"
                            ? "bg-green-500/10 text-green-400 border-green-500/20"
                            : "bg-blue-500/10 text-blue-400 border-blue-500/20"
                        }`}>
                          {job.action}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-zinc-400 text-xs max-w-[220px] truncate">{job.filename ?? "—"}</td>
                      <td className="px-4 py-3 text-zinc-500 text-xs">{job.printer_id ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
