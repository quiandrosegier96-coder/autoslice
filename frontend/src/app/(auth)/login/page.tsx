"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiPost, apiGet } from "@/lib/api";
import { saveAuth } from "@/lib/auth";
import { useLang } from "@/contexts/LangContext";
import { LANGS, type Lang } from "@/lib/i18n";

const NOTICE_KEY = "autoslice_notice_v3_dismissed";

export default function LoginPage() {
  const router = useRouter();
  const { lang, setLang, t } = useLang();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showNotice, setShowNotice] = useState(false);
  const [avgRating, setAvgRating] = useState<{ average: number; total: number } | null>(null);

  useEffect(() => {
    if (!localStorage.getItem(NOTICE_KEY)) setShowNotice(true);
    apiGet<{ average: number; total: number }>("/ratings/average")
      .then(setAvgRating)
      .catch(() => {});
  }, []);

  function dismissNotice() {
    localStorage.setItem(NOTICE_KEY, "1");
    setShowNotice(false);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await apiPost<{ access_token: string; username: string; email: string; is_admin: boolean }>(
        "/auth/login",
        { email, password }
      );
      saveAuth({ token: res.access_token, username: res.username, email: res.email, is_admin: res.is_admin });
      router.push("/convert");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-surface flex flex-col items-center justify-center px-4">

      {/* Notice modal */}
      {showNotice && (
        <div className="fixed inset-0 z-50 flex items-center justify-center px-4 bg-black/70 backdrop-blur-md">
          <div className="w-full max-w-md bg-surface-card border border-surface-border rounded-2xl p-7
                          shadow-[0_24px_64px_rgba(0,0,0,0.6)]">
            <div className="flex items-center gap-3 mb-5">
              <div className="w-9 h-9 rounded-xl bg-brand/10 border border-brand/20 flex items-center justify-center shrink-0">
                <svg className="w-4 h-4 text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M13 16h-1v-4h-1m1-4h.01M12 2a10 10 0 100 20A10 10 0 0012 2z"/>
                </svg>
              </div>
              <h2 className="text-[15px] font-semibold text-white">Mededeling</h2>
            </div>
            <p className="text-sm text-zinc-300 leading-relaxed mb-1">Beste gebruiker,</p>
            <p className="text-sm text-zinc-400 leading-relaxed mb-5">
              Deze webapp is momenteel volop in ontwikkeling. Hierdoor kan het zijn dat uw account opnieuw werd gereset.
              Onze excuses voor het ongemak.
              <br /><br />
              Team AutoSlice doet er alles aan om dit probleem zo snel mogelijk op te sporen en op te lossen.
              <br /><br />
              Bedankt voor uw begrip en vertrouwen.
            </p>
            <p className="text-xs text-zinc-600 mb-5 font-medium tracking-wide">— Team AutoSlice —</p>
            <button onClick={dismissNotice}
              className="w-full py-2.5 bg-brand-gradient hover:opacity-90 text-white font-semibold rounded-xl
                         transition-opacity duration-150 text-sm shadow-[0_2px_8px_rgba(224,36,36,0.3)]">
              Begrepen
            </button>
          </div>
        </div>
      )}

      {/* Logo */}
      <div className="mb-10 text-center">
        <div className="flex items-center justify-center gap-3 mb-3">
          <div className="w-10 h-10 bg-brand rounded-xl flex items-center justify-center
                          shadow-[0_0_20px_rgba(224,36,36,0.35)]">
            <svg viewBox="0 0 24 24" fill="white" className="w-5 h-5">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
            </svg>
          </div>
          <span className="text-[26px] font-bold text-white tracking-tight">
            Auto<span className="text-brand">Slice</span>
          </span>
        </div>
        <p className="text-zinc-500 text-sm mb-4">{t("login_subtitle")}</p>
        <div className="inline-flex items-center gap-0.5 bg-surface-card border border-surface-border rounded-lg px-2 py-1.5">
          {LANGS.map(({ code, label }) => (
            <button key={code} onClick={() => setLang(code as Lang)}
              className={`px-2 py-0.5 rounded-md text-xs font-semibold transition-colors ${
                lang === code ? "text-brand" : "text-zinc-600 hover:text-zinc-400"
              }`}>
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Card */}
      <div className="w-full max-w-sm bg-surface-card border border-surface-border rounded-2xl p-8
                      shadow-[0_8px_32px_rgba(0,0,0,0.4),inset_0_1px_0_rgba(255,255,255,0.04)]">

        <h1 className="text-xl font-semibold text-white mb-1">{t("login_welcome")}</h1>
        <p className="text-sm text-zinc-500 mb-6">{t("login_subtitle")}</p>

        {error && (
          <div className="mb-5 p-3.5 bg-brand/8 border border-brand/20 rounded-xl text-brand text-sm flex items-center gap-2.5">
            <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
            </svg>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-[11px] font-semibold text-zinc-500 mb-2 uppercase tracking-widest">
              {t("login_email")}
            </label>
            <input type="text" value={email} onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com" required autoComplete="username" />
          </div>
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-[11px] font-semibold text-zinc-500 uppercase tracking-widest">
                {t("login_password")}
              </label>
              <Link href="/forgot-password"
                className="text-[11px] text-zinc-600 hover:text-zinc-400 transition-colors">
                {t("login_forgot")}
              </Link>
            </div>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••" required autoComplete="current-password" />
          </div>
          <button type="submit" disabled={loading}
            className="w-full mt-2 py-2.5 px-4 bg-brand hover:bg-brand-dark disabled:opacity-40
                       disabled:cursor-not-allowed text-white font-semibold rounded-xl
                       transition-all duration-150 text-sm
                       shadow-[0_2px_8px_rgba(224,36,36,0.25)] hover:shadow-[0_4px_16px_rgba(224,36,36,0.35)]
                       hover:-translate-y-px active:translate-y-0">
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                {t("login_submitting")}
              </span>
            ) : t("login_submit")}
          </button>
        </form>

        <div className="mt-6 pt-5 border-t border-surface-border text-center">
          <p className="text-sm text-zinc-500">
            {t("login_no_account")}{" "}
            <Link href="/register" className="text-brand hover:text-brand-light transition-colors font-medium">
              {t("login_create")}
            </Link>
          </p>
        </div>
      </div>

      {avgRating && avgRating.total > 0 && (
        <div className="mt-8 flex items-center gap-2 text-xs text-zinc-600">
          <span className="text-yellow-400/80 tracking-tight">
            {"★".repeat(Math.round(avgRating.average))}{"☆".repeat(5 - Math.round(avgRating.average))}
          </span>
          <span className="text-zinc-500 font-medium">{avgRating.average.toFixed(1)}</span>
          <span className="text-zinc-700">·</span>
          <span>{avgRating.total} {t("rating_reviews")}</span>
        </div>
      )}

      <p className="mt-4 text-[11px] text-zinc-800 tracking-wide">
        © {new Date().getFullYear()} AutoSlice v1.3.41 — Bambu to Anycubic
      </p>
    </div>
  );
}
