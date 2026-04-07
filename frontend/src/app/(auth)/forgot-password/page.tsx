"use client";

export const dynamic = "force-dynamic";

import { useState, useEffect } from "react";
import Link from "next/link";
import { apiPost } from "@/lib/api";
import { useLang } from "@/contexts/LangContext";
import { LANGS, type Lang } from "@/lib/i18n";

function AuthBackground() {
  return (
    <div className="pointer-events-none select-none absolute inset-0">
      <div className="absolute -top-32 -left-32 w-[600px] h-[600px] rounded-full bg-brand/20 blur-[120px]" />
      <div className="absolute bottom-0 right-0 w-[400px] h-[400px] rounded-full bg-brand/15 blur-[100px]" />
      <svg className="absolute inset-0 w-full h-full opacity-[0.04]" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <pattern id="grid-fp" width="48" height="48" patternUnits="userSpaceOnUse">
            <path d="M 48 0 L 0 0 0 48" fill="none" stroke="#e02424" strokeWidth="0.5" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#grid-fp)" />
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

const HEADING    = { nl: "Wachtwoord vergeten?", en: "Forgot your password?", fr: "Mot de passe oublié ?", de: "Passwort vergessen?" };
const BODY       = { nl: "Voer je e-mailadres in en we sturen je een herstelcode.", en: "Enter your email and we'll send you a reset code.", fr: "Entrez votre e-mail et nous vous enverrons un code de réinitialisation.", de: "Geben Sie Ihre E-Mail ein und wir senden Ihnen einen Reset-Code." };
const SUCCESS_H  = { nl: "E-mail verzonden!", en: "Email sent!", fr: "E-mail envoyé !", de: "E-Mail gesendet!" };
const SUCCESS_B  = { nl: "Controleer je inbox voor de herstelcode.", en: "Check your inbox for the reset code.", fr: "Vérifiez votre boîte de réception.", de: "Prüfen Sie Ihren Posteingang." };
const BTN_SUBMIT = { nl: "Stuur herstelcode", en: "Send reset code", fr: "Envoyer le code", de: "Code senden" };
const BTN_WAIT   = { nl: "Verzenden…", en: "Sending…", fr: "Envoi…", de: "Senden…" };
const BTN_GOTO   = { nl: "Naar aanmeldpagina", en: "Go to login", fr: "Aller à la connexion", de: "Zur Anmeldung" };
const BACK       = { nl: "← Terug naar aanmelden", en: "← Back to login", fr: "← Retour à la connexion", de: "← Zurück zur Anmeldung" };
const EMAIL_LBL  = { nl: "E-mailadres", en: "Email address", fr: "Adresse e-mail", de: "E-Mail-Adresse" };

export default function ForgotPasswordPage() {
  const { lang, setLang, t } = useLang();
  const [appVersion, setAppVersion] = useState("");
  const [email, setEmail]   = useState("");
  const [sent, setSent]     = useState(false);
  const [error, setError]   = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    window.autoslice?.getVersion?.().then((v) => setAppVersion(`v${v}`)).catch(() => {});
  }, []);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
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
    <div className="relative min-h-screen bg-[#0a0a0d] overflow-hidden flex flex-col">
      <AuthBackground />

      {/* Language switcher */}
      <div className="relative z-10 flex justify-end px-8 pt-6">
        <div className="flex items-center gap-0.5 bg-white/5 border border-white/8 rounded-full px-2 py-1.5 backdrop-blur-sm">
          {LANGS.map(({ code, label }) => (
            <button key={code} onClick={() => setLang(code as Lang)}
              className={`px-3 py-1 rounded-full text-xs font-semibold transition-all duration-150 ${
                lang === code ? "bg-brand text-white shadow-[0_0_10px_rgba(224,36,36,0.4)]" : "text-zinc-500 hover:text-zinc-300"
              }`}>
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Center card */}
      <div className="relative z-10 flex flex-1 items-center justify-center px-6 py-10">
        <div className="w-full max-w-[420px]">

          {/* Logo */}
          <div className="flex items-center gap-3 mb-8 justify-center">
            <div className="w-10 h-10 bg-brand rounded-xl flex items-center justify-center shadow-[0_0_20px_rgba(224,36,36,0.45)]">
              <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
                <polygon points="12 2 22 8.5 22 15.5 12 22 2 15.5 2 8.5 12 2" />
                <line x1="12" y1="22" x2="12" y2="15.5" />
                <polyline points="22 8.5 12 15.5 2 8.5" />
              </svg>
            </div>
            <span className="text-2xl font-bold text-white tracking-tight">
              Auto<span className="text-brand">Slice</span>
            </span>
          </div>

          {/* Glass card */}
          <div className="relative bg-white/[0.04] border border-white/[0.09] rounded-2xl p-8
                          shadow-[0_8px_40px_rgba(0,0,0,0.5),inset_0_1px_0_rgba(255,255,255,0.06)]
                          backdrop-blur-xl">
            <div className="absolute inset-x-6 top-0 h-px bg-gradient-to-r from-transparent via-brand/50 to-transparent" />

            {sent ? (
              /* ── Success state ── */
              <div className="text-center py-2">
                <div className="w-16 h-16 rounded-full bg-green-500/10 border border-green-500/25
                                flex items-center justify-center mx-auto mb-5
                                shadow-[0_0_24px_rgba(34,197,94,0.15)]">
                  <svg className="w-8 h-8 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <h2 className="text-xl font-bold text-white mb-2">{SUCCESS_H[lang] ?? SUCCESS_H.en}</h2>
                <p className="text-sm text-zinc-400 mb-2 leading-relaxed">{SUCCESS_B[lang] ?? SUCCESS_B.en}</p>
                <p className="text-xs text-zinc-600 mb-7 leading-relaxed">{t("fp_admin_note")}</p>
                <Link href="/login"
                  className="flex items-center justify-center gap-2 w-full py-3.5 rounded-xl font-semibold text-white text-sm
                             bg-gradient-to-r from-brand to-brand-dark hover:from-brand-light hover:to-brand
                             shadow-[0_4px_16px_rgba(224,36,36,0.35)] hover:shadow-[0_6px_24px_rgba(224,36,36,0.5)]
                             hover:-translate-y-0.5 active:translate-y-0 transition-all duration-150">
                  {BTN_GOTO[lang] ?? BTN_GOTO.en}
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13 7l5 5-5 5M6 12h12" />
                  </svg>
                </Link>
              </div>
            ) : (
              /* ── Form state ── */
              <>
                {/* Icon */}
                <div className="w-12 h-12 rounded-xl bg-brand/10 border border-brand/20 flex items-center justify-center mb-5">
                  <svg className="w-6 h-6 text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8}
                      d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                  </svg>
                </div>

                <h1 className="text-2xl font-bold text-white mb-2">{HEADING[lang] ?? HEADING.en}</h1>
                <p className="text-sm text-zinc-500 mb-7 leading-relaxed">{BODY[lang] ?? BODY.en}</p>

                {error && (
                  <div className="mb-5 p-3.5 bg-brand/8 border border-brand/25 rounded-xl text-brand text-sm flex items-center gap-2.5">
                    <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                    </svg>
                    {error}
                  </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-5">
                  <div>
                    <label className="block text-[11px] font-semibold text-zinc-500 mb-2 uppercase tracking-[0.12em]">
                      {EMAIL_LBL[lang] ?? EMAIL_LBL.en}
                    </label>
                    <div className="relative">
                      <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-600 pointer-events-none">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8}
                            d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                        </svg>
                      </span>
                      <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                        placeholder="you@example.com" required autoComplete="email"
                        className="w-full pl-10 pr-4 py-3 bg-white/[0.05] border border-white/[0.09] rounded-xl
                                   text-white placeholder-zinc-600 text-sm
                                   focus:outline-none focus:border-brand/50 focus:bg-white/[0.07]
                                   focus:shadow-[0_0_0_3px_rgba(224,36,36,0.12)]
                                   transition-all duration-150" />
                    </div>
                  </div>

                  <button type="submit" disabled={loading}
                    className="w-full py-3.5 px-5 rounded-xl font-semibold text-white text-sm
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
                        {BTN_WAIT[lang] ?? BTN_WAIT.en}
                      </>
                    ) : (
                      <>
                        {BTN_SUBMIT[lang] ?? BTN_SUBMIT.en}
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13 7l5 5-5 5M6 12h12" />
                        </svg>
                      </>
                    )}
                  </button>
                </form>

                <div className="mt-6 pt-5 border-t border-white/[0.07] text-center">
                  <Link href="/login"
                    className="text-sm text-zinc-600 hover:text-zinc-400 transition-colors duration-150">
                    {BACK[lang] ?? BACK.en}
                  </Link>
                </div>
              </>
            )}
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
