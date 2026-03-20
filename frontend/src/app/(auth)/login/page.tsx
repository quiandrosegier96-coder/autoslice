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

      {/* Reset notice modal */}
      {showNotice && (
        <div className="fixed inset-0 z-50 flex items-center justify-center px-4 bg-black/60 backdrop-blur-sm">
          <div className="w-full max-w-md bg-surface-card border border-surface-border rounded-xl p-7 shadow-xl">
            <div className="flex items-center gap-3 mb-5">
              <div className="w-8 h-8 rounded-full bg-brand/15 border border-brand/30 flex items-center justify-center shrink-0">
                <svg className="w-4 h-4 text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M13 16h-1v-4h-1m1-4h.01M12 2a10 10 0 100 20A10 10 0 0012 2z"/>
                </svg>
              </div>
              <h2 className="text-base font-semibold text-white">Mededeling</h2>
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
            <p className="text-xs text-zinc-500 mb-5 font-medium">— Team AutoSlice —</p>
            <button onClick={dismissNotice}
              className="w-full py-2.5 bg-brand hover:bg-brand-dark text-white font-semibold rounded-lg
                         transition-colors duration-150 text-sm">
              Begrepen
            </button>
          </div>
        </div>
      )}

      {/* Logo + lang switcher */}
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
        <p className="text-zinc-500 text-sm mb-3">{t("login_subtitle")}</p>
        <div className="flex items-center justify-center gap-1">
          {LANGS.map(({ code, label }) => (
            <button key={code} onClick={() => setLang(code as Lang)}
              className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
                lang === code ? "text-brand" : "text-zinc-600 hover:text-zinc-400"
              }`}>
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Card */}
      <div className="w-full max-w-sm bg-surface-card border border-surface-border rounded-xl p-8">
        <h1 className="text-xl font-semibold text-white mb-6">{t("login_welcome")}</h1>

        {error && (
          <div className="mb-4 p-3 bg-brand/10 border border-brand/30 rounded-lg text-brand text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5 uppercase tracking-wide">
              {t("login_email")}
            </label>
            <input type="text" value={email} onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com or username" required autoComplete="username" />
          </div>
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5 uppercase tracking-wide">
              {t("login_password")}
            </label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••" required autoComplete="current-password" />
          </div>
          <button type="submit" disabled={loading}
            className="w-full mt-2 py-2.5 px-4 bg-brand hover:bg-brand-dark disabled:opacity-50
                       disabled:cursor-not-allowed text-white font-semibold rounded-lg
                       transition-colors duration-150 text-sm">
            {loading ? t("login_submitting") : t("login_submit")}
          </button>
        </form>

        <div className="mt-6 flex flex-col gap-2 text-center">
          <p className="text-sm text-zinc-500">
            {t("login_no_account")}{" "}
            <Link href="/register" className="text-brand hover:text-brand-light transition-colors">
              {t("login_create")}
            </Link>
          </p>
          <Link href="/forgot-password" className="text-xs text-zinc-600 hover:text-zinc-400 transition-colors">
            {t("login_forgot")}
          </Link>
        </div>
      </div>

      {avgRating && avgRating.total > 0 && (
        <div className="mt-6 flex items-center gap-2 text-sm text-zinc-500">
          <span className="text-yellow-400 text-base">{"★".repeat(Math.round(avgRating.average))}{"☆".repeat(5 - Math.round(avgRating.average))}</span>
          <span className="font-medium text-zinc-400">{avgRating.average.toFixed(1)}/5</span>
          <span>— {t("rating_avg")} {avgRating.total} {t("rating_reviews")}</span>
        </div>
      )}

      <p className="mt-4 text-xs text-zinc-700">
        AutoSlice v1.3.6 © {new Date().getFullYear()} — Bambu to Anycubic converter
      </p>
    </div>
  );
}
