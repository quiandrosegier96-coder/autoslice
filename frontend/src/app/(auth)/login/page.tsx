"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiPost, apiGet } from "@/lib/api";
import { saveAuth } from "@/lib/auth";
import { useLang } from "@/contexts/LangContext";
import { LANGS, type Lang } from "@/lib/i18n";

const NOTICE_KEY = "autoslice_notice_v3_dismissed";

const FEATURES = {
  nl: [
    { icon: "⚡", title: "Snelle conversie", desc: "Zet 3MF bestanden razendsnel om naar G-code." },
    { icon: "🛡", title: "Betrouwbaar & veilig", desc: "Je bestanden zijn beveiligd en privé." },
    { icon: "🎛", title: "Geoptimaliseerd resultaat", desc: "Consistente en hoogwaardige output." },
  ],
  en: [
    { icon: "⚡", title: "Fast conversion", desc: "Convert 3MF files to G-code in seconds." },
    { icon: "🛡", title: "Reliable & secure", desc: "Your files are protected and private." },
    { icon: "🎛", title: "Optimised output", desc: "Consistent and high-quality results." },
  ],
  fr: [
    { icon: "⚡", title: "Conversion rapide", desc: "Convertissez les fichiers 3MF en G-code rapidement." },
    { icon: "🛡", title: "Fiable & sécurisé", desc: "Vos fichiers sont protégés et privés." },
    { icon: "🎛", title: "Résultat optimisé", desc: "Sortie cohérente et de haute qualité." },
  ],
  de: [
    { icon: "⚡", title: "Schnelle Konvertierung", desc: "3MF-Dateien blitzschnell in G-Code umwandeln." },
    { icon: "🛡", title: "Zuverlässig & sicher", desc: "Ihre Dateien sind geschützt und privat." },
    { icon: "🎛", title: "Optimiertes Ergebnis", desc: "Konsistente und hochwertige Ausgabe." },
  ],
};

const TAGLINE = {
  nl: "SMART 3MF → G-CODE CONVERSIE",
  en: "SMART 3MF → G-CODE CONVERSION",
  fr: "CONVERSION SMART 3MF → G-CODE",
  de: "SMART 3MF → G-CODE KONVERTIERUNG",
};

const WELCOME = {
  nl: "Welkom terug",
  en: "Welcome back",
  fr: "Bon retour",
  de: "Willkommen zurück",
};

const SUBTITLE = {
  nl: "Meld je aan om door te gaan met AutoSlice.",
  en: "Sign in to continue with AutoSlice.",
  fr: "Connectez-vous pour continuer avec AutoSlice.",
  de: "Melden Sie sich an, um mit AutoSlice fortzufahren.",
};

const FOOTER = {
  nl: "Gebouwd voor makers & professionals",
  en: "Built for makers & professionals",
  fr: "Conçu pour les makers & professionnels",
  de: "Für Maker & Profis entwickelt",
};

export default function LoginPage() {
  const router = useRouter();
  const { lang, setLang, t } = useLang();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showNotice, setShowNotice] = useState(false);
  const [showPw, setShowPw] = useState(false);
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

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
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

  const features = FEATURES[lang] ?? FEATURES.en;

  return (
    <div className="relative min-h-screen bg-[#0a0a0d] overflow-hidden flex flex-col">

      {/* ── Background glows ── */}
      <div className="pointer-events-none select-none absolute inset-0">
        {/* top-left big glow */}
        <div className="absolute -top-32 -left-32 w-[600px] h-[600px] rounded-full bg-brand/20 blur-[120px]" />
        {/* bottom-right glow */}
        <div className="absolute bottom-0 right-0 w-[400px] h-[400px] rounded-full bg-brand/15 blur-[100px]" />
        {/* center subtle */}
        <div className="absolute top-1/2 left-1/3 w-[300px] h-[300px] -translate-y-1/2 rounded-full bg-brand/8 blur-[80px]" />

        {/* Grid overlay */}
        <svg className="absolute inset-0 w-full h-full opacity-[0.04]" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id="grid" width="48" height="48" patternUnits="userSpaceOnUse">
              <path d="M 48 0 L 0 0 0 48" fill="none" stroke="#e02424" strokeWidth="0.5"/>
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" />
        </svg>

        {/* Perspective grid bottom-left */}
        <svg className="absolute bottom-0 left-0 w-[55%] h-[45%] opacity-[0.12]" viewBox="0 0 800 400" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
          {Array.from({ length: 12 }).map((_, i) => (
            <line key={`h${i}`} x1="0" y1={400 - i * 36} x2="800" y2={400 - i * 6} stroke="#e02424" strokeWidth="0.8"/>
          ))}
          {Array.from({ length: 16 }).map((_, i) => (
            <line key={`v${i}`} x1={i * 54} y1="400" x2={400 + i * 26} y2="0" stroke="#e02424" strokeWidth="0.8"/>
          ))}
        </svg>
      </div>

      {/* ── Notice modal ── */}
      {showNotice && (
        <div className="fixed inset-0 z-50 flex items-center justify-center px-4 bg-black/75 backdrop-blur-md">
          <div className="w-full max-w-md bg-[#131316] border border-white/8 rounded-2xl p-7 shadow-[0_24px_64px_rgba(0,0,0,0.7)]">
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

      {/* ── Language switcher — top right ── */}
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

      {/* ── Main split layout ── */}
      <div className="relative z-10 flex flex-1 items-center justify-center px-6 py-10 gap-8 lg:gap-16 max-w-[1200px] mx-auto w-full">

        {/* ══ LEFT: Branding + Features ══ */}
        <div className="hidden lg:flex flex-col flex-1 max-w-[480px]">

          {/* Logo */}
          <div className="flex items-center gap-4 mb-4">
            <div className="w-16 h-16 bg-brand rounded-2xl flex items-center justify-center shadow-[0_0_32px_rgba(224,36,36,0.5)] shrink-0">
              <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-8 h-8">
                <polygon points="12 2 22 8.5 22 15.5 12 22 2 15.5 2 8.5 12 2"/>
                <line x1="12" y1="22" x2="12" y2="15.5"/>
                <polyline points="22 8.5 12 15.5 2 8.5"/>
              </svg>
            </div>
            <div>
              <h1 className="text-4xl font-bold text-white tracking-tight leading-none">
                Auto<span className="text-brand">Slice</span>
              </h1>
              <p className="text-[11px] font-semibold text-zinc-500 tracking-[0.18em] mt-1 uppercase">
                {TAGLINE[lang] ?? TAGLINE.en}
              </p>
            </div>
          </div>

          {/* Rating badge */}
          {avgRating && avgRating.total > 0 && (
            <div className="inline-flex items-center gap-2 mb-10 bg-white/4 border border-white/8 rounded-full px-4 py-1.5 w-fit">
              <span className="text-yellow-400 text-xs tracking-tight">
                {"★".repeat(Math.round(avgRating.average))}{"☆".repeat(5 - Math.round(avgRating.average))}
              </span>
              <span className="text-zinc-400 text-xs font-medium">{avgRating.average.toFixed(1)}</span>
              <span className="text-zinc-700 text-xs">·</span>
              <span className="text-zinc-500 text-xs">{avgRating.total} reviews</span>
            </div>
          )}
          {(!avgRating || avgRating.total === 0) && <div className="mb-10" />}

          {/* Feature list */}
          <div className="space-y-5">
            {features.map((f, i) => (
              <div key={i} className="flex items-start gap-4 group">
                <div className="w-11 h-11 rounded-xl bg-brand/10 border border-brand/20 flex items-center justify-center shrink-0
                                group-hover:bg-brand/15 group-hover:border-brand/30 transition-colors duration-200">
                  <span className="text-lg leading-none">{f.icon}</span>
                </div>
                <div className="pt-0.5">
                  <p className="text-[15px] font-semibold text-white leading-snug">{f.title}</p>
                  <p className="text-sm text-zinc-500 mt-0.5 leading-relaxed">{f.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* ══ RIGHT: Login card ══ */}
        <div className="w-full max-w-[440px] shrink-0">
          {/* Glassmorphism card */}
          <div className="relative bg-white/[0.04] border border-white/[0.09] rounded-2xl p-8
                          shadow-[0_8px_40px_rgba(0,0,0,0.5),inset_0_1px_0_rgba(255,255,255,0.06)]
                          backdrop-blur-xl">

            {/* Subtle red top border glow */}
            <div className="absolute inset-x-6 top-0 h-px bg-gradient-to-r from-transparent via-brand/50 to-transparent" />

            {/* Mobile logo */}
            <div className="flex lg:hidden items-center gap-3 mb-7">
              <div className="w-9 h-9 bg-brand rounded-xl flex items-center justify-center shadow-[0_0_16px_rgba(224,36,36,0.4)]">
                <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
                  <polygon points="12 2 22 8.5 22 15.5 12 22 2 15.5 2 8.5 12 2"/>
                  <line x1="12" y1="22" x2="12" y2="15.5"/>
                  <polyline points="22 8.5 12 15.5 2 8.5"/>
                </svg>
              </div>
              <span className="text-xl font-bold text-white tracking-tight">
                Auto<span className="text-brand">Slice</span>
              </span>
            </div>

            <h2 className="text-2xl font-bold text-white mb-1">{WELCOME[lang] ?? WELCOME.en}</h2>
            <p className="text-sm text-zinc-500 mb-7">{SUBTITLE[lang] ?? SUBTITLE.en}</p>

            {/* Error */}
            {error && (
              <div className="mb-5 p-3.5 bg-brand/8 border border-brand/25 rounded-xl text-brand text-sm flex items-center gap-2.5">
                <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
                </svg>
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-5">

              {/* Email */}
              <div>
                <label className="block text-[11px] font-semibold text-zinc-500 mb-2 uppercase tracking-[0.12em]">
                  {t("login_email")}
                </label>
                <div className="relative">
                  <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-600 pointer-events-none">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8}
                        d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
                    </svg>
                  </span>
                  <input
                    type="text"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@example.com"
                    required
                    autoComplete="username"
                    className="w-full pl-10 pr-4 py-3 bg-white/[0.05] border border-white/[0.09] rounded-xl
                               text-white placeholder-zinc-600 text-sm
                               focus:outline-none focus:border-brand/50 focus:bg-white/[0.07]
                               focus:shadow-[0_0_0_3px_rgba(224,36,36,0.12)]
                               transition-all duration-150"
                  />
                </div>
              </div>

              {/* Password */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="block text-[11px] font-semibold text-zinc-500 uppercase tracking-[0.12em]">
                    {t("login_password")}
                  </label>
                  <Link href="/forgot-password"
                    className="text-[11px] text-zinc-600 hover:text-brand transition-colors duration-150">
                    {t("login_forgot")}
                  </Link>
                </div>
                <div className="relative">
                  <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-600 pointer-events-none">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8}
                        d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/>
                    </svg>
                  </span>
                  <input
                    type={showPw ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    required
                    autoComplete="current-password"
                    className="w-full pl-10 pr-11 py-3 bg-white/[0.05] border border-white/[0.09] rounded-xl
                               text-white placeholder-zinc-600 text-sm
                               focus:outline-none focus:border-brand/50 focus:bg-white/[0.07]
                               focus:shadow-[0_0_0_3px_rgba(224,36,36,0.12)]
                               transition-all duration-150"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPw(!showPw)}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 text-zinc-600 hover:text-zinc-400 transition-colors"
                    tabIndex={-1}
                  >
                    {showPw ? (
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8}
                          d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"/>
                      </svg>
                    ) : (
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8}
                          d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8}
                          d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
                      </svg>
                    )}
                  </button>
                </div>
              </div>

              {/* Remember me */}
              <label className="flex items-center gap-3 cursor-pointer group w-fit">
                <div className={`w-4.5 h-4.5 rounded-md border flex items-center justify-center transition-all duration-150 ${
                  remember
                    ? "bg-brand border-brand shadow-[0_0_8px_rgba(224,36,36,0.35)]"
                    : "border-white/15 bg-white/5 group-hover:border-white/25"
                }`}
                  style={{ width: "18px", height: "18px" }}
                  onClick={() => setRemember(!remember)}
                >
                  {remember && (
                    <svg className="w-2.5 h-2.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7"/>
                    </svg>
                  )}
                </div>
                <input type="checkbox" className="sr-only" checked={remember} onChange={() => setRemember(!remember)} />
                <span className="text-sm text-zinc-400 group-hover:text-zinc-300 transition-colors select-none">
                  {lang === "nl" ? "Onthoud mij" : lang === "fr" ? "Se souvenir de moi" : lang === "de" ? "Angemeldet bleiben" : "Remember me"}
                </span>
              </label>

              {/* Submit */}
              <button
                type="submit"
                disabled={loading}
                className="w-full py-3.5 px-5 mt-1 rounded-xl font-semibold text-white text-sm
                           bg-gradient-to-r from-brand to-brand-dark
                           hover:from-brand-light hover:to-brand
                           disabled:opacity-40 disabled:cursor-not-allowed
                           shadow-[0_4px_16px_rgba(224,36,36,0.35)]
                           hover:shadow-[0_6px_24px_rgba(224,36,36,0.5)]
                           hover:-translate-y-0.5 active:translate-y-0
                           transition-all duration-150
                           flex items-center justify-center gap-2"
              >
                {loading ? (
                  <>
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    {t("login_submitting")}
                  </>
                ) : (
                  <>
                    {t("login_submit")}
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13 7l5 5-5 5M6 12h12"/>
                    </svg>
                  </>
                )}
              </button>
            </form>

            {/* Register link */}
            <div className="mt-6 pt-5 border-t border-white/[0.07] text-center">
              <p className="text-sm text-zinc-500">
                {t("login_no_account")}{" "}
                <Link href="/register"
                  className="text-brand hover:text-brand-light font-semibold transition-colors duration-150">
                  {t("login_create")}
                </Link>
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* ── Footer ── */}
      <div className="relative z-10 pb-6 text-center">
        <p className="text-[11px] text-zinc-700 tracking-wide">
          © {new Date().getFullYear()} AutoSlice v1.3.44
          <span className="mx-2 text-zinc-800">•</span>
          {FOOTER[lang] ?? FOOTER.en}
        </p>
      </div>
    </div>
  );
}
