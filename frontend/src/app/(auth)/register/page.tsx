"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiPost } from "@/lib/api";
import { useLang } from "@/contexts/LangContext";
import { LANGS, type Lang } from "@/lib/i18n";

/* ── shared background layer ─────────────────────────────────── */
function AuthBackground() {
  return (
    <div className="pointer-events-none select-none absolute inset-0">
      <div className="absolute -top-32 -left-32 w-[600px] h-[600px] rounded-full bg-brand/20 blur-[120px]" />
      <div className="absolute bottom-0 right-0 w-[400px] h-[400px] rounded-full bg-brand/15 blur-[100px]" />
      <div className="absolute top-1/2 left-1/3 w-[300px] h-[300px] -translate-y-1/2 rounded-full bg-brand/8 blur-[80px]" />
      <svg className="absolute inset-0 w-full h-full opacity-[0.04]" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <pattern id="grid-r" width="48" height="48" patternUnits="userSpaceOnUse">
            <path d="M 48 0 L 0 0 0 48" fill="none" stroke="#e02424" strokeWidth="0.5" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#grid-r)" />
      </svg>
      <svg className="absolute bottom-0 left-0 w-[55%] h-[45%] opacity-[0.10]" viewBox="0 0 800 400" preserveAspectRatio="none">
        {Array.from({ length: 12 }).map((_, i) => (
          <line key={`h${i}`} x1="0" y1={400 - i * 36} x2="800" y2={400 - i * 6} stroke="#e02424" strokeWidth="0.8" />
        ))}
        {Array.from({ length: 16 }).map((_, i) => (
          <line key={`v${i}`} x1={i * 54} y1="400" x2={400 + i * 26} y2="0" stroke="#e02424" strokeWidth="0.8" />
        ))}
      </svg>
    </div>
  );
}

/* ── logo icon ───────────────────────────────────────────────── */
function LogoIcon({ size = "lg" }: { size?: "sm" | "lg" }) {
  const dim = size === "lg" ? "w-16 h-16" : "w-9 h-9";
  const icon = size === "lg" ? "w-8 h-8" : "w-5 h-5";
  return (
    <div className={`${dim} bg-brand rounded-2xl flex items-center justify-center shadow-[0_0_32px_rgba(224,36,36,0.5)] shrink-0`}>
      <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={icon}>
        <polygon points="12 2 22 8.5 22 15.5 12 22 2 15.5 2 8.5 12 2" />
        <line x1="12" y1="22" x2="12" y2="15.5" />
        <polyline points="22 8.5 12 15.5 2 8.5" />
      </svg>
    </div>
  );
}

const STEPS = {
  nl: ["Account aanmaken", "Bevestig je e-mail", "Start met converteren"],
  en: ["Create your account", "Confirm your email", "Start converting"],
  fr: ["Créer votre compte", "Confirmez votre e-mail", "Commencez à convertir"],
  de: ["Konto erstellen", "E-Mail bestätigen", "Mit Konvertieren beginnen"],
  es: ["Crear tu cuenta", "Confirma tu e-mail", "Empieza a convertir"],
  ko: ["계정 만들기", "이메일 확인", "변환 시작"],
};

const HEADING = {
  nl: "Aan de slag",
  en: "Get started",
  fr: "Commencer",
  de: "Loslegen",
  es: "Empezar",
  ko: "시작하기",
};
const SUBHEADING = {
  nl: "Maak je gratis account aan.",
  en: "Create your free account.",
  fr: "Créez votre compte gratuit.",
  de: "Erstellen Sie Ihr kostenloses Konto.",
  es: "Crea tu cuenta gratuita.",
  ko: "무료 계정을 만드세요.",
};

export default function RegisterPage() {
  const router = useRouter();
  const { lang, setLang, t } = useLang();
  const [appVersion, setAppVersion] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    window.autoslice?.getVersion?.().then((v) => setAppVersion(`v${v}`)).catch(() => {});
  }, []);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    const cleanedUsername = username.trim();
    const cleanedEmail = email.trim().toLowerCase();
    if (password !== confirm) { setError(t("reg_err_match")); return; }
    if (password.length < 8) { setError(t("reg_err_length")); return; }
    setLoading(true);
    try {
      const res = await apiPost<{ needs_verification: boolean; email: string; username: string }>(
        "/auth/register",
        { username: cleanedUsername, email: cleanedEmail, password }
      );
      if (res.needs_verification) {
        router.push(`/verify-email?email=${encodeURIComponent(res.email)}&username=${encodeURIComponent(res.username)}`);
      } else {
        router.push("/convert");
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  }

  const steps = STEPS[lang] ?? STEPS.en;

  return (
    <div className="relative min-h-screen bg-[#0a0a0d] overflow-x-hidden flex flex-col">
      <AuthBackground />

      {/* Language switcher */}
      <div className="relative z-10 flex justify-end px-8 pt-6">
        <div className="flex items-center gap-0.5 bg-white/5 border border-white/8 rounded-full px-2 py-1.5 backdrop-blur-sm">
          {LANGS.map(({ code, label }) => (
            <button
              key={code}
              onClick={() => setLang(code as Lang)}
              className={`px-3 py-1 rounded-full text-xs font-semibold transition-all duration-150 ${
                lang === code
                  ? "bg-brand text-white shadow-[0_0_10px_rgba(224,36,36,0.4)]"
                  : "text-zinc-500 hover:text-zinc-300"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Main */}
      <div className="relative z-10 flex flex-1 items-center justify-center px-6 py-10 gap-8 lg:gap-16 max-w-[1200px] mx-auto w-full">

        {/* LEFT */}
        <div className="hidden lg:flex flex-col flex-1 max-w-[480px]">
          <div className="flex items-center gap-4 mb-12">
            <LogoIcon size="lg" />
            <div>
              <h1 className="text-4xl font-bold text-white tracking-tight leading-none">
                Auto<span className="text-brand">Slice</span>
              </h1>
              <p className="text-[11px] font-semibold text-zinc-500 tracking-[0.18em] mt-1 uppercase">
                ONE FILE. ANY SLICE.
              </p>
            </div>
          </div>

          {/* Steps */}
          <p className="text-xs font-semibold text-zinc-600 uppercase tracking-[0.14em] mb-5">
            {lang === "nl" ? "Hoe het werkt" : lang === "fr" ? "Comment ça marche" : lang === "de" ? "So funktioniert es" : lang === "es" ? "Cómo funciona" : lang === "ko" ? "사용 방법" : "How it works"}
          </p>
          <div className="space-y-4">
            {steps.map((step, i) => (
              <div key={i} className="flex items-center gap-4 group">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-sm font-bold transition-all duration-200 ${
                  i === 0
                    ? "bg-brand text-white shadow-[0_0_16px_rgba(224,36,36,0.4)]"
                    : "bg-white/5 border border-white/10 text-zinc-600 group-hover:border-white/20"
                }`}>
                  {i + 1}
                </div>
                <p className={`text-sm font-medium ${i === 0 ? "text-white" : "text-zinc-500"}`}>{step}</p>
              </div>
            ))}
          </div>

          <div className="mt-12 pt-8 border-t border-white/[0.06]">
            <p className="text-xs text-zinc-700 leading-relaxed">
              {lang === "nl"
                ? "Door je te registreren ga je akkoord met onze servicevoorwaarden."
                : lang === "fr"
                ? "En vous inscrivant, vous acceptez nos conditions de service."
                : lang === "de"
                ? "Mit der Registrierung stimmen Sie unseren Nutzungsbedingungen zu."
                : lang === "es"
                ? "Al registrarte, aceptas nuestros términos de servicio."
                : lang === "ko"
                ? "등록함으로써 서비스 약관에 동의합니다."
                : "By registering you agree to our terms of service."}
            </p>
          </div>
        </div>

        {/* RIGHT — card */}
        <div className="w-full max-w-[440px] shrink-0">
          <div className="relative bg-white/[0.04] border border-white/[0.09] rounded-2xl p-8
                          shadow-[0_8px_40px_rgba(0,0,0,0.5),inset_0_1px_0_rgba(255,255,255,0.06)]
                          backdrop-blur-xl">
            <div className="absolute inset-x-6 top-0 h-px bg-gradient-to-r from-transparent via-brand/50 to-transparent" />

            {/* Mobile logo */}
            <div className="flex lg:hidden items-center gap-3 mb-7">
              <LogoIcon size="sm" />
              <span className="text-xl font-bold text-white tracking-tight">
                Auto<span className="text-brand">Slice</span>
              </span>
            </div>

            <h2 className="text-2xl font-bold text-white mb-1">{HEADING[lang] ?? HEADING.en}</h2>
            <p className="text-sm text-zinc-500 mb-7">{SUBHEADING[lang] ?? SUBHEADING.en}</p>

            {error && (
              <div className="mb-5 p-3.5 bg-brand/8 border border-brand/25 rounded-xl text-brand text-sm flex items-center gap-2.5">
                <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                </svg>
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">

              {/* Username */}
              <div>
                <label className="block text-[11px] font-semibold text-zinc-500 mb-2 uppercase tracking-[0.12em]">
                  {t("reg_username")}
                </label>
                <div className="relative">
                  <input type="text" value={username} onChange={(e) => setUsername(e.target.value)}
                    placeholder={t("reg_placeholder_username")} required minLength={3} autoComplete="username"
                    className="w-full px-5 py-3 bg-white/[0.05] border border-white/[0.09] rounded-xl
                               text-white placeholder-zinc-600 text-sm
                               focus:outline-none focus:border-brand/50 focus:bg-white/[0.07]
                               focus:shadow-[0_0_0_3px_rgba(224,36,36,0.12)]
                               transition-all duration-150" />
                </div>
              </div>

              {/* Email */}
              <div>
                <label className="block text-[11px] font-semibold text-zinc-500 mb-2 uppercase tracking-[0.12em]">
                  {t("reg_email")}
                </label>
                <div className="relative">
                  <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                    placeholder={t("reg_placeholder_email")} required autoComplete="email"
                    inputMode="email" autoCapitalize="none" spellCheck={false}
                    className="w-full px-5 py-3 bg-white/[0.05] border border-white/[0.09] rounded-xl
                               text-white placeholder-zinc-600 text-sm
                               focus:outline-none focus:border-brand/50 focus:bg-white/[0.07]
                               focus:shadow-[0_0_0_3px_rgba(224,36,36,0.12)]
                               transition-all duration-150" />
                </div>
              </div>

              {/* Password */}
              <div>
                <label className="block text-[11px] font-semibold text-zinc-500 mb-2 uppercase tracking-[0.12em]">
                  {t("reg_password")}
                </label>
                <div className="relative">
                  <input type={showPw ? "text" : "password"} value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder={t("reg_placeholder_pw")} required minLength={8} autoComplete="new-password"
                    className="w-full pl-5 pr-12 py-3 bg-white/[0.05] border border-white/[0.09] rounded-xl
                               text-white placeholder-zinc-600 text-sm
                               focus:outline-none focus:border-brand/50 focus:bg-white/[0.07]
                               focus:shadow-[0_0_0_3px_rgba(224,36,36,0.12)]
                               transition-all duration-150" />
                  <button type="button" onClick={() => setShowPw(!showPw)} tabIndex={-1}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 text-zinc-600 hover:text-zinc-400 transition-colors">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      {showPw
                        ? <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                        : <><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></>
                      }
                    </svg>
                  </button>
                </div>

                {/* Strength bar */}
                {password.length > 0 && (
                  <div className="mt-2 flex gap-1">
                    {[1, 2, 3, 4].map((lvl) => {
                      const strength = Math.min(4, Math.floor(password.length / 3));
                      return (
                        <div key={lvl} className={`h-0.5 flex-1 rounded-full transition-all duration-300 ${
                          lvl <= strength
                            ? strength <= 1 ? "bg-red-500" : strength <= 2 ? "bg-yellow-500" : strength <= 3 ? "bg-blue-500" : "bg-green-500"
                            : "bg-white/10"
                        }`} />
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Confirm password */}
              <div>
                <label className="block text-[11px] font-semibold text-zinc-500 mb-2 uppercase tracking-[0.12em]">
                  {t("reg_confirm")}
                </label>
                <div className="relative">
                  <input type={showConfirm ? "text" : "password"} value={confirm}
                    onChange={(e) => setConfirm(e.target.value)}
                    placeholder={t("reg_placeholder_confirm")} required autoComplete="new-password"
                    className={`w-full pl-5 pr-12 py-3 bg-white/[0.05] border rounded-xl
                               text-white placeholder-zinc-600 text-sm
                               focus:outline-none focus:bg-white/[0.07]
                               transition-all duration-150 ${
                                 confirm.length > 0
                                   ? confirm === password
                                     ? "border-green-500/40 focus:border-green-500/60 focus:shadow-[0_0_0_3px_rgba(34,197,94,0.1)]"
                                     : "border-brand/40 focus:border-brand/60 focus:shadow-[0_0_0_3px_rgba(224,36,36,0.12)]"
                                   : "border-white/[0.09] focus:border-brand/50 focus:shadow-[0_0_0_3px_rgba(224,36,36,0.12)]"
                               }`} />
                  <button type="button" onClick={() => setShowConfirm(!showConfirm)} tabIndex={-1}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 text-zinc-600 hover:text-zinc-400 transition-colors">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      {showConfirm
                        ? <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                        : <><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></>
                      }
                    </svg>
                  </button>
                </div>
              </div>

              {/* Submit */}
              <button type="submit" disabled={loading}
                className="w-full py-3.5 px-5 mt-1 rounded-xl font-semibold text-white text-sm
                           bg-gradient-to-r from-brand to-brand-dark
                           hover:from-brand-light hover:to-brand
                           disabled:opacity-40 disabled:cursor-not-allowed
                           shadow-[0_4px_16px_rgba(224,36,36,0.35)]
                           hover:shadow-[0_6px_24px_rgba(224,36,36,0.5)]
                           hover:-translate-y-0.5 active:translate-y-0
                           transition-all duration-150
                           flex items-center justify-center gap-2">
                {loading ? (
                  <>
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    {t("reg_submitting")}
                  </>
                ) : (
                  <>
                    {t("reg_submit")}
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13 7l5 5-5 5M6 12h12" />
                    </svg>
                  </>
                )}
              </button>
            </form>

            <div className="mt-6 pt-5 border-t border-white/[0.07] text-center">
              <p className="text-sm text-zinc-500">
                {t("reg_has_account")}{" "}
                <Link href="/login" className="text-brand hover:text-brand-light font-semibold transition-colors duration-150">
                  {t("reg_signin")}
                </Link>
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="relative z-10 pb-6 text-center">
        <p className="text-[11px] text-zinc-700 tracking-wide">
          © {new Date().getFullYear()} AutoSlice {appVersion}
          <span className="mx-2 text-zinc-800">•</span>
          Built for makers &amp; professionals
        </p>
      </div>
    </div>
  );
}
