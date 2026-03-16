"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiPost } from "@/lib/api";
import { useLang } from "@/contexts/LangContext";
import { LANGS, type Lang } from "@/lib/i18n";

export default function ResetPasswordPage() {
  const router = useRouter();
  const { lang, setLang, t } = useLang();
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (password !== confirm) { setError(t("reg_err_match")); return; }
    if (password.length < 8) { setError(t("reg_err_length")); return; }
    setError("");
    setLoading(true);
    try {
      await apiPost("/auth/reset-password", { token: token.trim(), new_password: password });
      router.push("/login?reset=1");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Reset failed");
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
        <p className="text-zinc-500 text-sm mb-3">{t("rp_subtitle")}</p>
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

      <div className="w-full max-w-sm bg-surface-card border border-surface-border rounded-xl p-8">
        <h1 className="text-xl font-semibold text-white mb-2">{t("rp_heading")}</h1>
        <p className="text-zinc-500 text-sm mb-6">{t("rp_body")}</p>

        {error && (
          <div className="mb-4 p-3 bg-brand/10 border border-brand/30 rounded-lg text-brand text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5 uppercase tracking-wide">
              {t("rp_code")}
            </label>
            <input
              type="text"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder={t("rp_code_ph")}
              required
              className="font-mono text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5 uppercase tracking-wide">
              {t("rp_new_pw")}
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              autoComplete="new-password"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5 uppercase tracking-wide">
              {t("rp_confirm_pw")}
            </label>
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder="••••••••"
              required
              autoComplete="new-password"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full mt-2 py-2.5 px-4 bg-brand hover:bg-brand-dark disabled:opacity-50
                       disabled:cursor-not-allowed text-white font-semibold rounded-lg
                       transition-colors duration-150 text-sm"
          >
            {loading ? t("rp_submitting") : t("rp_submit")}
          </button>
        </form>

        <p className="mt-6 text-center text-xs text-zinc-600">
          <Link href="/login" className="hover:text-zinc-400 transition-colors">
            {t("rp_back")}
          </Link>
        </p>
      </div>
    </div>
  );
}
