"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { isLoggedIn, getUser, isAdmin } from "@/lib/auth";
import { apiGet } from "@/lib/api";
import { Navbar } from "@/components/Navbar";

type HistoryJob = {
  job_id: string;
  action: string;
  filename: string | null;
  printer_id: string | null;
  created_at: string;
};

function UploadIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
        d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/>
    </svg>
  );
}

function ConvertIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
        d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
    </svg>
  );
}

export default function HistoryPage() {
  const router = useRouter();
  const [user, setUser] = useState<{ username: string; email: string; is_admin: boolean } | null>(null);
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

  function timeAgo(iso: string) {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  }

  const uploads = jobs.filter(j => j.action === "upload");
  const converts = jobs.filter(j => j.action === "convert");

  return (
    <div className="min-h-screen bg-surface">
      <Navbar showAdmin={isAdmin()} />

      <main className="max-w-3xl mx-auto px-4 py-10">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-white mb-1">History</h1>
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
            <div className="w-16 h-16 rounded-full bg-surface-card border border-surface-border flex items-center justify-center mx-auto mb-4 text-zinc-600">
              <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                  d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
            </div>
            <p className="mb-4 font-medium text-zinc-400">No activity yet</p>
            <Link href="/convert" className="text-brand hover:text-brand-light transition-colors text-sm">
              Convert your first file →
            </Link>
          </div>
        ) : (
          <>
            {/* Stats */}
            <div className="grid grid-cols-2 gap-4 mb-8">
              <div className="bg-surface-card border border-surface-border rounded-xl p-5 flex items-center gap-4">
                <div className="w-10 h-10 rounded-lg bg-blue-500/10 border border-blue-500/20 text-blue-400 flex items-center justify-center shrink-0">
                  <UploadIcon />
                </div>
                <div>
                  <p className="text-xs text-zinc-500 uppercase tracking-wide mb-0.5">Uploads</p>
                  <p className="text-2xl font-bold text-white">{uploads.length}</p>
                </div>
              </div>
              <div className="bg-surface-card border border-surface-border rounded-xl p-5 flex items-center gap-4">
                <div className="w-10 h-10 rounded-lg bg-green-500/10 border border-green-500/20 text-green-400 flex items-center justify-center shrink-0">
                  <ConvertIcon />
                </div>
                <div>
                  <p className="text-xs text-zinc-500 uppercase tracking-wide mb-0.5">Conversions</p>
                  <p className="text-2xl font-bold text-white">{converts.length}</p>
                </div>
              </div>
            </div>

            {/* History list */}
            <div className="bg-surface-card border border-surface-border rounded-xl overflow-hidden">
              <div className="px-5 py-3 border-b border-surface-border flex items-center justify-between">
                <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wide">
                  Activity — {jobs.length} {jobs.length === 1 ? "event" : "events"}
                </span>
              </div>
              <div className="divide-y divide-surface-border">
                {jobs.map((job) => (
                  <div key={job.job_id + job.action}
                    className="flex items-center gap-4 px-5 py-3.5 hover:bg-surface/40 transition-colors">
                    {/* Icon */}
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${
                      job.action === "convert"
                        ? "bg-green-500/10 text-green-400"
                        : "bg-blue-500/10 text-blue-400"
                    }`}>
                      {job.action === "convert" ? <ConvertIcon /> : <UploadIcon />}
                    </div>

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-white truncate">
                        {job.filename ?? <span className="text-zinc-500 italic">unknown file</span>}
                      </p>
                      <p className="text-xs text-zinc-500 mt-0.5">
                        {job.printer_id ? (
                          <span className="text-zinc-400">{job.printer_id}</span>
                        ) : (
                          <span className="italic">no printer</span>
                        )}
                      </p>
                    </div>

                    {/* Badge + time */}
                    <div className="flex flex-col items-end gap-1 shrink-0">
                      <span className={`text-xs font-medium px-2 py-0.5 rounded border ${
                        job.action === "convert"
                          ? "bg-green-500/10 text-green-400 border-green-500/20"
                          : "bg-blue-500/10 text-blue-400 border-blue-500/20"
                      }`}>
                        {job.action}
                      </span>
                      <span className="text-xs text-zinc-600" title={formatDate(job.created_at)}>
                        {timeAgo(job.created_at)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
