"use client";

import { useState } from "react";
import Link from "next/link";
import { apiPost } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await apiPost("/auth/forgot-password", { email });
      setSent(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-surface flex flex-col items-center justify-center px-4">
      <div className="mb-8 text-center">
        <div className="flex items-center justify-center gap-2 mb-2">
          <div className="w-8 h-8 bg-brand rounded-sm flex items-center justify-center">
            <svg viewBox="0 0 24 24" fill="white" className="w-5 h-5">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
            </svg>
          </div>
          <span className="text-2xl font-bold text-white tracking-tight">
            Auto<span className="text-brand">Slice</span>
          </span>
        </div>
        <p className="text-zinc-500 text-sm">Reset your password</p>
      </div>

      <div className="w-full max-w-sm bg-surface-card border border-surface-border rounded-xl p-8">
        {sent ? (
          <div className="text-center">
            <div className="w-12 h-12 rounded-full bg-green-500/10 border border-green-500/20 flex items-center justify-center mx-auto mb-4">
              <svg className="w-6 h-6 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7"/>
              </svg>
            </div>
            <h2 className="text-white font-semibold mb-2">Request received</h2>
            <p className="text-zinc-500 text-sm mb-2">
              If your email is registered, a reset code has been generated.
            </p>
            <p className="text-zinc-600 text-xs mb-6">
              Contact your admin to retrieve the code, then use it on the reset page.
            </p>
            <Link
              href="/reset-password"
              className="block w-full py-2.5 bg-brand hover:bg-brand-dark text-white font-semibold rounded-lg text-sm text-center transition-colors"
            >
              Enter reset code →
            </Link>
            <Link href="/login" className="block mt-3 text-xs text-zinc-600 hover:text-zinc-400 transition-colors text-center">
              Back to login
            </Link>
          </div>
        ) : (
          <>
            <h1 className="text-xl font-semibold text-white mb-2">Forgot password</h1>
            <p className="text-zinc-500 text-sm mb-6">
              Enter your email address. Your admin will provide a reset code.
            </p>

            {error && (
              <div className="mb-4 p-3 bg-brand/10 border border-brand/30 rounded-lg text-brand text-sm">
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1.5 uppercase tracking-wide">
                  Email
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                  autoComplete="email"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full mt-2 py-2.5 px-4 bg-brand hover:bg-brand-dark disabled:opacity-50
                           disabled:cursor-not-allowed text-white font-semibold rounded-lg
                           transition-colors duration-150 text-sm"
              >
                {loading ? "Sending…" : "Request reset code"}
              </button>
            </form>

            <p className="mt-6 text-center text-xs text-zinc-600">
              <Link href="/login" className="hover:text-zinc-400 transition-colors">
                ← Back to login
              </Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
