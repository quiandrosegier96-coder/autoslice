"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiPost } from "@/lib/api";
import { saveAuth } from "@/lib/auth";
import { useLang } from "@/contexts/LangContext";
import { LANGS, type Lang } from "@/lib/i18n";

export default function RegisterPage() {
  const router = useRouter();
  const { lang, setLang, t } = useLang();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (password !== confirm) { setError(t("reg_err_match")); return; }
    if (password.length < 8) { setError(t("reg_err_length")); return; }
    setLoading(true);
    try {
      const res = await apiPost<{ access_token: string; username: string; email: string; is_admin: boolean }>(
        "/auth/register",
        { username, email, password }
      );
      saveAuth({ token: res.access_token, username: res.username, email: res.email, is_admin: res.is_admin });
      router.push("/convert");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-surface flex flex-col items-center justify-center px-4">

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
        <p className="text-zinc-500 text-sm mb-4">{t("reg_subtitle")}</p>
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

        <h1 className="text-xl font-semibold text-white mb-6">{t("reg_heading")}</h1>

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
              {t("reg_username")}
            </label>
            <input type="text" value={username} onChange={(e) => setUsername(e.target.value)}
              placeholder="yourname" required minLength={3} autoComplete="username" />
          </div>
          <div>
            <label className="block text-[11px] font-semibold text-zinc-500 mb-2 uppercase tracking-widest">
              {t("reg_email")}
            </label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com" required autoComplete="email" />
          </div>
          <div>
            <label className="block text-[11px] font-semibold text-zinc-500 mb-2 uppercase tracking-widest">
              {t("reg_password")}
            </label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              placeholder={t("reg_placeholder_pw")} required minLength={8} autoComplete="new-password" />
          </div>
          <div>
            <label className="block text-[11px] font-semibold text-zinc-500 mb-2 uppercase tracking-widest">
              {t("reg_confirm")}
            </label>
            <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)}
              placeholder={t("reg_placeholder_confirm")} required autoComplete="new-password" />
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
                {t("reg_submitting")}
              </span>
            ) : t("reg_submit")}
          </button>
        </form>

        <div className="mt-6 pt-5 border-t border-surface-border text-center">
          <p className="text-sm text-zinc-500">
            {t("reg_has_account")}{" "}
            <Link href="/login" className="text-brand hover:text-brand-light transition-colors font-medium">
              {t("reg_signin")}
            </Link>
          </p>
        </div>
      </div>

      <p className="mt-6 text-[11px] text-zinc-800 tracking-wide">
        AutoSlice © {new Date().getFullYear()} — Bambu to Anycubic converter
      </p>
    </div>
  );
}
