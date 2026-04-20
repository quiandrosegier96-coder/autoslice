"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";

// ── Design tokens ────────────────────────────────────────────────────────────
const BG      = "#050508";
const SURFACE = "#0c0c10";
const BRAND   = "#e02424";

// ── Scroll-fade hook ─────────────────────────────────────────────────────────
function useFadeIn() {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setVisible(true); obs.disconnect(); } }, { threshold: 0.12 });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);
  return { ref, visible };
}

// ── Reusable atoms ───────────────────────────────────────────────────────────
function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full border text-[11px] font-semibold uppercase tracking-[0.1em]"
      style={{ borderColor: "rgba(224,36,36,0.3)", background: "rgba(224,36,36,0.08)", color: BRAND }}>
      {children}
    </span>
  );
}

function GradBtn({ href, children, outline, download }: { href: string; children: React.ReactNode; outline?: boolean; download?: boolean }) {
  const base = "inline-flex items-center gap-2 px-6 h-11 rounded-xl font-semibold text-sm transition-all duration-150 active:scale-[0.97]";
  const isExternal = href.startsWith("http");
  const extraProps = isExternal ? { target: "_blank", rel: "noopener noreferrer" } : {};
  if (outline) return (
    <Link href={href} {...extraProps} className={`${base} border text-zinc-300 hover:text-white hover:bg-white/[0.05]`}
      style={{ borderColor: "rgba(255,255,255,0.12)" }}>
      {children}
    </Link>
  );
  return (
    <Link href={href} {...extraProps} className={`${base} text-white shadow-[0_0_24px_rgba(224,36,36,0.4)] hover:shadow-[0_0_36px_rgba(224,36,36,0.6)] hover:-translate-y-0.5`}
      style={{ background: "linear-gradient(135deg,#e02424,#b81c1c)" }}>
      {children}
    </Link>
  );
}

// ── Navbar ────────────────────────────────────────────────────────────────────
function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const fn = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", fn, { passive: true });
    return () => window.removeEventListener("scroll", fn);
  }, []);

  return (
    <header className={`fixed top-0 inset-x-0 z-50 transition-all duration-300 ${scrolled ? "border-b" : ""}`}
      style={{ background: scrolled ? "rgba(5,5,8,0.85)" : "transparent", backdropFilter: scrolled ? "blur(16px)" : "none", borderColor: "rgba(255,255,255,0.06)" }}>
      <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">

        {/* Logo */}
        <Link href="/landing" className="flex items-center gap-2.5 group">
          <div className="w-8 h-8 rounded-xl flex items-center justify-center transition-shadow duration-200 group-hover:shadow-[0_0_20px_rgba(224,36,36,0.5)]"
            style={{ background: BRAND, boxShadow: "0 0 14px rgba(224,36,36,0.35)" }}>
            <svg viewBox="0 0 24 24" fill="white" className="w-4 h-4">
              <path d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <span className="text-[15px] font-bold text-white tracking-tight">
            Auto<span style={{ color: BRAND }}>Slice</span>
          </span>
        </Link>

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center gap-7">
          {[["#features","Features"],["#how","Hoe het werkt"],["#pricing","Prijzen"]].map(([href,label]) => (
            <a key={href} href={href} className="text-sm text-zinc-500 hover:text-white transition-colors duration-150">{label}</a>
          ))}
        </nav>

        {/* Desktop CTA */}
        <div className="hidden md:flex items-center gap-3">
          <Link href="/login" className="text-sm text-zinc-400 hover:text-white transition-colors">Inloggen</Link>
          <GradBtn href="/register">Gratis starten</GradBtn>
        </div>

        {/* Mobile hamburger */}
        <button onClick={() => setOpen(!open)} className="md:hidden text-zinc-400 hover:text-white transition-colors">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={open ? "M6 18L18 6M6 6l12 12" : "M4 6h16M4 12h16M4 18h16"} />
          </svg>
        </button>
      </div>

      {/* Mobile menu */}
      {open && (
        <div className="md:hidden border-t px-6 py-4 space-y-3" style={{ background: "rgba(5,5,8,0.95)", borderColor: "rgba(255,255,255,0.07)" }}>
          {[["#features","Features"],["#how","Hoe het werkt"],["#pricing","Prijzen"]].map(([href,label]) => (
            <a key={href} href={href} onClick={() => setOpen(false)} className="block text-sm text-zinc-400 hover:text-white py-1 transition-colors">{label}</a>
          ))}
          <div className="flex flex-col gap-2 pt-2 border-t" style={{ borderColor: "rgba(255,255,255,0.06)" }}>
            <Link href="/login" className="text-sm text-zinc-400 py-1">Inloggen</Link>
            <GradBtn href="/register">Gratis starten</GradBtn>
          </div>
        </div>
      )}
    </header>
  );
}

// ── Hero ──────────────────────────────────────────────────────────────────────
function Hero() {
  return (
    <section className="relative min-h-screen flex items-center pt-24 pb-16 overflow-hidden">

      {/* Background glows */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[500px] rounded-full opacity-30"
          style={{ background: "radial-gradient(ellipse, rgba(224,36,36,0.18) 0%, transparent 70%)" }} />
        <div className="absolute bottom-0 right-0 w-[600px] h-[400px] opacity-20"
          style={{ background: "radial-gradient(ellipse at right bottom, rgba(224,36,36,0.15) 0%, transparent 70%)" }} />
      </div>

      <div className="relative max-w-6xl mx-auto px-6 w-full">
        <div className="flex flex-col lg:flex-row items-center gap-16">

          {/* Left: copy */}
          <div className="flex-1 text-center lg:text-left">
            <div className="mb-6">
              <Badge>
                <svg className="w-2.5 h-2.5" fill="currentColor" viewBox="0 0 8 8"><circle cx="4" cy="4" r="4"/></svg>
                Windows app — nu beschikbaar
              </Badge>
            </div>

            <h1 className="text-5xl lg:text-[62px] font-extrabold text-white leading-[1.05] tracking-tight mb-6">
              Van Bambu naar{" "}
              <span className="relative">
                <span style={{ color: BRAND }}>Anycubic</span>
                <svg className="absolute -bottom-2 left-0 w-full" viewBox="0 0 200 8" fill="none">
                  <path d="M2 6 Q100 2 198 6" stroke={BRAND} strokeWidth="2.5" strokeLinecap="round" opacity="0.5"/>
                </svg>
              </span>
              {" "}in seconden.
            </h1>

            <p className="text-lg text-zinc-400 leading-relaxed mb-8 max-w-lg mx-auto lg:mx-0">
              AutoSlice converteert elk Bambu of MakerWorld .3mf bestand automatisch naar
              een geoptimaliseerd Anycubic printprofiel — met AI-analyse, multicolor support en meer.
            </p>

            <div className="flex flex-col sm:flex-row items-center gap-3 justify-center lg:justify-start">
              <a href="/api/download" download
                className="inline-flex items-center gap-2.5 px-6 h-11 rounded-xl font-semibold text-sm text-white transition-all duration-150 active:scale-[0.97] hover:bg-white/[0.08] hover:-translate-y-0.5"
                style={{ background: "rgba(255,255,255,0.07)", border: "1px solid rgba(255,255,255,0.18)" }}>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
                </svg>
                Downloaden voor Windows
              </a>
              <GradBtn href="#features" outline>
                Bekijk features
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7"/>
                </svg>
              </GradBtn>
            </div>

            <p className="mt-3 text-xs text-zinc-600">
              Gratis te gebruiken · Geen creditcard vereist · Automatische updates
            </p>
            <p className="mt-1 text-xs text-zinc-700">
              Linux &amp; iOS — binnenkort beschikbaar
            </p>
          </div>

          {/* Right: App window mockup */}
          <div className="flex-1 w-full max-w-[600px]">
            <AppWindowMockup />
          </div>
        </div>
      </div>
    </section>
  );
}

// ── App window CSS mockup ─────────────────────────────────────────────────────
function AppWindowMockup() {
  return (
    <div className="relative w-full rounded-2xl overflow-hidden shadow-[0_32px_80px_rgba(0,0,0,0.7),0_0_0_1px_rgba(255,255,255,0.06)]">
      {/* Outer glow */}
      <div className="absolute -inset-[1px] rounded-2xl pointer-events-none"
        style={{ background: "linear-gradient(135deg, rgba(224,36,36,0.2), transparent 50%)", zIndex: -1 }} />

      {/* Title bar */}
      <div className="flex items-center justify-between px-4 h-9 shrink-0 select-none"
        style={{ background: "#030305", borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-xl flex items-center justify-center" style={{ background: BRAND }}>
            <svg viewBox="0 0 24 24" fill="white" className="w-1.5 h-1.5"><path d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
          </div>
          <span className="text-[10px] font-bold tracking-widest" style={{ color: "rgba(255,255,255,0.25)" }}>AUTOSLICE</span>
        </div>
        <div className="flex items-center gap-1.5">
          {["rgba(255,255,255,0.08)","rgba(255,255,255,0.08)","rgba(224,36,36,0.4)"].map((c,i) => (
            <div key={i} className="w-3 h-3 rounded-[3px]" style={{ background: c }} />
          ))}
        </div>
      </div>

      {/* App body */}
      <div className="flex h-[380px]" style={{ background: BG }}>

        {/* Sidebar */}
        <div className="w-[52px] shrink-0 flex flex-col items-center py-4 gap-1"
          style={{ background: "#07070b", borderRight: "1px solid rgba(255,255,255,0.05)" }}>
          {[
            { icon: "M13 10V3L4 14h7v7l9-11h-7z", active: true },
            { icon: "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z", active: false },
            { icon: "M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z", active: false },
            { icon: "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z", active: false },
          ].map((item, i) => (
            <div key={i} className="w-8 h-8 rounded-xl flex items-center justify-center"
              style={{ background: item.active ? "rgba(224,36,36,0.16)" : "transparent" }}>
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"
                style={{ color: item.active ? BRAND : "rgba(255,255,255,0.2)" }}>
                <path strokeLinecap="round" strokeLinejoin="round" d={item.icon}/>
              </svg>
            </div>
          ))}
        </div>

        {/* Main content */}
        <div className="flex-1 flex flex-col p-4 overflow-hidden">

          {/* Top bar */}
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="text-sm font-bold text-white">3MF Converter</div>
              <div className="text-[10px] mt-0.5" style={{ color: "rgba(255,255,255,0.3)" }}>Converteer Bambu naar Anycubic</div>
            </div>
            {/* Step pills */}
            <div className="flex items-center gap-1.5">
              {["Instellingen","Bestand","Genereren"].map((s,i) => (
                <div key={i} className="flex items-center gap-1">
                  <div className={`text-[9px] font-bold px-2 py-0.5 rounded-full ${i === 0 ? "text-white" : "text-zinc-700"}`}
                    style={{ background: i === 0 ? "rgba(224,36,36,0.2)" : "rgba(255,255,255,0.04)", border: `1px solid ${i===0?"rgba(224,36,36,0.35)":"rgba(255,255,255,0.07)"}` }}>
                    {i+1} {s}
                  </div>
                  {i < 2 && <div className="w-3 h-px" style={{ background: "rgba(255,255,255,0.1)" }}/>}
                </div>
              ))}
            </div>
          </div>

          {/* Upload zone */}
          <div className="rounded-xl border-2 border-dashed flex flex-col items-center justify-center py-7 mb-3"
            style={{ borderColor: "rgba(224,36,36,0.3)", background: "rgba(224,36,36,0.03)" }}>
            <div className="w-8 h-8 rounded-full flex items-center justify-center mb-2"
              style={{ background: "rgba(224,36,36,0.1)", border: "1px solid rgba(224,36,36,0.25)" }}>
              <svg className="w-4 h-4" fill="none" stroke={BRAND} viewBox="0 0 24 24" strokeWidth={1.8}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/>
              </svg>
            </div>
            <div className="text-xs font-semibold text-white mb-0.5">Sleep je .3mf bestand hier</div>
            <div className="text-[9px]" style={{ color: "rgba(255,255,255,0.3)" }}>of klik om te bladeren</div>
          </div>

          {/* Settings row */}
          <div className="grid grid-cols-3 gap-2">
            {[
              { label: "Printer", value: "Kobra 3 Combo" },
              { label: "Filament", value: "PLA · 0.4mm" },
              { label: "Buildplaat", value: "Textured PEI" },
            ].map(({ label, value }) => (
              <div key={label} className="rounded-lg px-2.5 py-2"
                style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)" }}>
                <div className="text-[8px] font-semibold uppercase tracking-wider mb-0.5" style={{ color: "rgba(255,255,255,0.3)" }}>{label}</div>
                <div className="text-[10px] font-medium text-white truncate">{value}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Animated glow bar at bottom */}
      <div className="h-[2px]" style={{ background: `linear-gradient(90deg, transparent, ${BRAND}, transparent)` }}/>
    </div>
  );
}

// ── Trust / compatibility bar ─────────────────────────────────────────────────
function TrustBar() {
  const brands = ["Bambu Lab X1C","MakerWorld","Anycubic Kobra","ACE Pro","Kobra 3 Max","MakerBot"];
  return (
    <div className="border-y py-5" style={{ borderColor: "rgba(255,255,255,0.05)", background: "rgba(255,255,255,0.015)" }}>
      <div className="max-w-6xl mx-auto px-6">
        <p className="text-center text-[10px] text-zinc-600 uppercase tracking-[0.18em] font-semibold mb-5">
          Compatibel met
        </p>
        <div className="flex flex-wrap items-center justify-center gap-x-10 gap-y-3">
          {brands.map((b) => (
            <span key={b} className="text-[13px] font-semibold" style={{ color: "rgba(255,255,255,0.2)" }}>{b}</span>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Features ──────────────────────────────────────────────────────────────────
const FEATURES = [
  {
    icon: "M13 10V3L4 14h7v7l9-11h-7z",
    title: "Directe 3MF conversie",
    desc: "Upload elk Bambu of MakerWorld .3mf bestand en ontvang binnen seconden een kant-en-klaar Anycubic printprofiel.",
    accent: BRAND,
  },
  {
    icon: "M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z",
    title: "AI-model analyse",
    desc: "AutoSlice analyseert automatisch overhangen, bruggen, dunne wanden en printbaarheid — en past instellingen aan.",
    accent: "#8b5cf6",
  },
  {
    icon: "M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z",
    title: "Multicolor support",
    desc: "Volledige ondersteuning voor ACE Pro en ACE Pro 2 met tot 8 kleurslots, filamentwissel en flush-instellingen.",
    accent: "#06b6d4",
  },
  {
    icon: "M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01",
    title: "Preset systeem",
    desc: "Sla je printerinstellingen op als preset, hernoem ze, stel een standaard in en importeer/exporteer als JSON.",
    accent: "#f59e0b",
  },
  {
    icon: "M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z",
    title: "Automatische updates",
    desc: "AutoSlice controleert op nieuwe versies bij elke start. Updates worden op de achtergrond gedownload en geïnstalleerd.",
    accent: "#10b981",
  },
  {
    icon: "M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z",
    title: "Veilig & privé",
    desc: "Alle verwerking gebeurt lokaal op jouw machine. Geen bestanden naar de cloud. Jouw 3D-modellen blijven van jou.",
    accent: "#f43f5e",
  },
];

function Features() {
  const { ref, visible } = useFadeIn();
  return (
    <section id="features" className="py-28" ref={ref}>
      <div className="max-w-6xl mx-auto px-6">
        <div className={`text-center mb-16 transition-all duration-700 ${visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"}`}>
          <Badge>Features</Badge>
          <h2 className="text-4xl font-extrabold text-white mt-5 mb-4 tracking-tight">
            Alles wat je nodig hebt
          </h2>
          <p className="text-zinc-500 text-lg max-w-xl mx-auto">
            Van conversie tot AI-analyse — AutoSlice dekt het volledige 3D-print workflow.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {FEATURES.map((f, i) => (
            <FeatureCard key={f.title} {...f} delay={i * 80} visible={visible} />
          ))}
        </div>
      </div>
    </section>
  );
}

function FeatureCard({ icon, title, desc, accent, delay, visible }: typeof FEATURES[0] & { delay: number; visible: boolean }) {
  return (
    <div className={`group rounded-2xl p-6 border transition-all duration-700 hover:-translate-y-1`}
      style={{
        background: "rgba(255,255,255,0.02)",
        borderColor: "rgba(255,255,255,0.06)",
        transitionDelay: `${delay}ms`,
        opacity: visible ? 1 : 0,
        transform: visible ? "translateY(0)" : "translateY(20px)",
      }}>
      <div className="w-10 h-10 rounded-xl flex items-center justify-center mb-4 transition-all duration-200 group-hover:scale-110"
        style={{ background: `${accent}18`, border: `1px solid ${accent}30` }}>
        <svg className="w-5 h-5" fill="none" stroke={accent} strokeWidth={1.8} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d={icon}/>
        </svg>
      </div>
      <h3 className="text-[15px] font-bold text-white mb-2">{title}</h3>
      <p className="text-sm text-zinc-500 leading-relaxed">{desc}</p>
    </div>
  );
}

// ── How it works ──────────────────────────────────────────────────────────────
const STEPS = [
  { n: "01", title: "Upload je bestand", desc: "Sleep een .3mf bestand van Bambu Studio of MakerWorld in het uploadvenster." },
  { n: "02", title: "AI analyseert het model", desc: "AutoSlice berekent printbaarheid, detecteert overhangen, optimaliseert oriëntatie en kiest de beste instellingen." },
  { n: "03", title: "Download en print", desc: "Ontvang een geoptimaliseerd .3mf profiel voor jouw Anycubic printer. Direct starten met printen." },
];

function HowItWorks() {
  const { ref, visible } = useFadeIn();
  return (
    <section id="how" className="py-28" ref={ref}
      style={{ background: "linear-gradient(180deg, transparent, rgba(224,36,36,0.02) 50%, transparent)" }}>
      <div className="max-w-6xl mx-auto px-6">
        <div className={`text-center mb-16 transition-all duration-700 ${visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"}`}>
          <Badge>Hoe het werkt</Badge>
          <h2 className="text-4xl font-extrabold text-white mt-5 mb-4 tracking-tight">
            Drie stappen naar de perfecte print
          </h2>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {STEPS.map((s, i) => (
            <div key={s.n}
              className="relative transition-all duration-700"
              style={{ transitionDelay: `${i * 120}ms`, opacity: visible ? 1 : 0, transform: visible ? "translateY(0)" : "translateY(24px)" }}>
              {/* Connector line */}
              {i < 2 && (
                <div className="hidden lg:block absolute top-7 left-full w-full h-px -translate-x-8 -translate-y-0"
                  style={{ background: "linear-gradient(90deg, rgba(224,36,36,0.3), transparent)" }}/>
              )}

              <div className="rounded-2xl p-7 h-full border"
                style={{ background: "rgba(255,255,255,0.02)", borderColor: "rgba(255,255,255,0.06)" }}>
                <div className="text-5xl font-black mb-5 leading-none"
                  style={{ background: `linear-gradient(135deg, ${BRAND}, rgba(224,36,36,0.3))`, WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
                  {s.n}
                </div>
                <h3 className="text-lg font-bold text-white mb-3">{s.title}</h3>
                <p className="text-sm text-zinc-500 leading-relaxed">{s.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ── Screenshot / app preview ──────────────────────────────────────────────────
function AppPreview() {
  const { ref, visible } = useFadeIn();
  return (
    <section className="py-28 overflow-hidden" ref={ref}>
      <div className="max-w-6xl mx-auto px-6">
        <div className={`transition-all duration-700 ${visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"}`}>
          <div className="flex flex-col lg:flex-row items-center gap-16">

            {/* Left: text */}
            <div className="flex-1 lg:max-w-[420px]">
              <Badge>AI Analyse</Badge>
              <h2 className="text-4xl font-extrabold text-white mt-5 mb-5 tracking-tight leading-tight">
                Slimmere prints door diepgaande modelanalyse
              </h2>
              <p className="text-zinc-500 leading-relaxed mb-8">
                AutoSlice verwerkt elk model door een uitgebreide analyse-engine die printbaarheid beoordeelt,
                overhangende geometrie detecteert en automatisch de beste printoriëntatie berekent.
              </p>

              <div className="space-y-4">
                {[
                  { label: "Printbaarheidscore", color: "#10b981", val: 88 },
                  { label: "Overhang risico",    color: BRAND,    val: 23 },
                  { label: "Support aanwezigheid", color: "#f59e0b", val: 45 },
                ].map(({ label, color, val }) => (
                  <div key={label}>
                    <div className="flex justify-between text-xs mb-1.5">
                      <span className="text-zinc-400 font-medium">{label}</span>
                      <span className="font-bold" style={{ color }}>{val}%</span>
                    </div>
                    <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.06)" }}>
                      <div className="h-full rounded-full transition-all duration-1000"
                        style={{ width: visible ? `${val}%` : "0%", background: color, transitionDelay: "400ms" }}/>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Right: analysis mockup */}
            <div className="flex-1 w-full max-w-[520px]">
              <AnalysisMockup />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function AnalysisMockup() {
  const items = [
    { icon: "M9 12l2 2 4-4", label: "Mesh is waterdicht", ok: true },
    { icon: "M12 9v2m0 4h.01", label: "Matige overhangen gedetecteerd", ok: false },
    { icon: "M9 12l2 2 4-4", label: "Brim aanbevolen", ok: true },
    { icon: "M9 12l2 2 4-4", label: "Oriëntatie geoptimaliseerd (−34% support)", ok: true },
    { icon: "M12 9v2m0 4h.01", label: "Dunne wanden: 1 zone", ok: false },
  ];
  return (
    <div className="rounded-2xl overflow-hidden shadow-[0_24px_60px_rgba(0,0,0,0.6),0_0_0_1px_rgba(255,255,255,0.06)]">
      {/* Window chrome */}
      <div className="px-4 h-9 flex items-center gap-2" style={{ background: "#030305", borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
        {[BRAND,"rgba(255,255,255,0.08)","rgba(255,255,255,0.08)"].map((c,i) => (
          <div key={i} className="w-2.5 h-2.5 rounded-full" style={{ background: c }}/>
        ))}
        <span className="ml-2 text-[10px] font-medium" style={{ color: "rgba(255,255,255,0.2)" }}>Analyse resultaten — vase_mode_pot.3mf</span>
      </div>

      <div className="p-5" style={{ background: SURFACE }}>
        {/* Score ring */}
        <div className="flex items-center gap-5 mb-5 p-4 rounded-xl" style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
          <div className="relative w-16 h-16 shrink-0">
            <svg viewBox="0 0 36 36" className="w-16 h-16 -rotate-90">
              <circle cx="18" cy="18" r="14" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="3"/>
              <circle cx="18" cy="18" r="14" fill="none" stroke="#10b981" strokeWidth="3"
                strokeDasharray="88 100" strokeLinecap="round"/>
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-lg font-black text-white">88</span>
            </div>
          </div>
          <div>
            <p className="text-[11px] text-zinc-500 uppercase tracking-wider font-semibold mb-0.5">Printbaarheid</p>
            <p className="text-xl font-black" style={{ color: "#10b981" }}>Goed</p>
            <p className="text-[11px] text-zinc-600 mt-0.5">4 van 5 criteria geslaagd</p>
          </div>
        </div>

        {/* Check items */}
        <div className="space-y-2">
          {items.map(({ icon, label, ok }) => (
            <div key={label} className="flex items-center gap-3 px-3 py-2 rounded-lg"
              style={{ background: ok ? "rgba(16,185,129,0.05)" : "rgba(224,36,36,0.05)", border: `1px solid ${ok ? "rgba(16,185,129,0.12)" : "rgba(224,36,36,0.12)"}` }}>
              <div className="w-5 h-5 rounded-full flex items-center justify-center shrink-0"
                style={{ background: ok ? "rgba(16,185,129,0.15)" : "rgba(224,36,36,0.15)" }}>
                <svg className="w-3 h-3" fill="none" stroke={ok ? "#10b981" : BRAND} strokeWidth={2.5} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d={icon}/>
                </svg>
              </div>
              <span className="text-[12px] font-medium" style={{ color: ok ? "#a7f3d0" : "#fca5a5" }}>{label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Multicolor showcase ───────────────────────────────────────────────────────
function MultiColorSection() {
  const { ref, visible } = useFadeIn();
  const colors = ["#e02424","#3b82f6","#10b981","#f59e0b","#8b5cf6","#f43f5e","#ffffff","#1a1a2e"];
  return (
    <section className="py-28" ref={ref}
      style={{ background: "linear-gradient(180deg, transparent, rgba(6,182,212,0.02) 50%, transparent)" }}>
      <div className="max-w-6xl mx-auto px-6">
        <div className={`flex flex-col lg:flex-row items-center gap-16 transition-all duration-700 ${visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"}`}>

          {/* Left: color slot mockup */}
          <div className="flex-1 max-w-[480px] w-full">
            <div className="rounded-2xl p-6 border shadow-[0_24px_60px_rgba(0,0,0,0.5)]"
              style={{ background: SURFACE, borderColor: "rgba(255,255,255,0.07)" }}>
              <div className="flex items-center justify-between mb-5">
                <div>
                  <p className="text-xs font-bold text-zinc-400 uppercase tracking-wider">ACE Pro 2 — 8 slots</p>
                  <p className="text-[11px] text-zinc-600 mt-0.5">Dubbele unit actief</p>
                </div>
                <div className="px-2 py-1 rounded-full text-[9px] font-bold" style={{ background: "rgba(6,182,212,0.12)", color: "#06b6d4", border: "1px solid rgba(6,182,212,0.25)" }}>
                  ACTIEF
                </div>
              </div>
              <div className="grid grid-cols-4 gap-3">
                {colors.map((c, i) => (
                  <div key={i} className="rounded-xl p-2.5 flex flex-col gap-2"
                    style={{ background: "rgba(255,255,255,0.02)", border: `1px solid ${c}30` }}>
                    <div className="flex items-center justify-between">
                      <span className="text-[9px] font-bold" style={{ color: "rgba(255,255,255,0.4)" }}>Slot {i+1}</span>
                      <div className="w-2 h-2 rounded-full" style={{ background: c, boxShadow: `0 0 5px ${c}80` }}/>
                    </div>
                    <div className="h-7 rounded-lg" style={{ background: c, boxShadow: `0 2px 10px ${c}40` }}/>
                    <div className="h-5 rounded text-[8px] font-medium flex items-center justify-center"
                      style={{ background: "rgba(255,255,255,0.05)", color: "rgba(255,255,255,0.5)" }}>
                      PLA
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Right: text */}
          <div className="flex-1">
            <Badge>Multicolor</Badge>
            <h2 className="text-4xl font-extrabold text-white mt-5 mb-5 tracking-tight leading-tight">
              Volledig multicolor<br/>zonder compromissen
            </h2>
            <p className="text-zinc-500 leading-relaxed mb-8">
              Werk met ACE Pro en ACE Pro 2 configuraties tot 8 kleurslots. AutoSlice vertaalt
              Bambu-kleurinformatie automatisch naar de juiste Anycubic filamentslots.
            </p>
            <ul className="space-y-3">
              {[
                "Automatische kleurdetectie uit .3mf bronbestand",
                "Instelbare flush-volumes per filamentwissel",
                "Dubbele unit ondersteuning (8 slots)",
                "Aangepaste filamenttypes per slot (PLA, PETG, TPU)",
              ].map((item) => (
                <li key={item} className="flex items-start gap-3">
                  <div className="w-5 h-5 rounded-full flex items-center justify-center mt-0.5 shrink-0"
                    style={{ background: "rgba(6,182,212,0.12)", border: "1px solid rgba(6,182,212,0.25)" }}>
                    <svg className="w-2.5 h-2.5" fill="none" stroke="#06b6d4" strokeWidth={2.5} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/>
                    </svg>
                  </div>
                  <span className="text-sm text-zinc-400">{item}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}

// ── Pricing ───────────────────────────────────────────────────────────────────
const PLANS = [
  {
    name: "Starter",
    price: "Gratis",
    sub: "Voor altijd",
    color: "rgba(255,255,255,0.08)",
    border: "rgba(255,255,255,0.08)",
    badge: null,
    features: [
      "15 conversies per maand",
      "Basisprinter instellingen",
      "3 opgeslagen presets",
      "Community support",
      "Automatische updates",
    ],
    cta: "Gratis starten",
    ctaHref: "/register",
    highlight: false,
  },
  {
    name: "Pro",
    price: "€7,99",
    sub: "per maand",
    color: "rgba(224,36,36,0.08)",
    border: "rgba(224,36,36,0.35)",
    badge: "Meest populair",
    features: [
      "Onbeperkte conversies",
      "AI-model analyse",
      "Onbeperkte presets",
      "Prioriteit support",
      "Geavanceerde oriëntatie-optimalisatie",
      "Import / export presets",
    ],
    cta: "Pro proberen",
    ctaHref: "/register",
    highlight: true,
  },
  {
    name: "Team",
    price: "€24,99",
    sub: "per maand",
    color: "rgba(139,92,246,0.06)",
    border: "rgba(139,92,246,0.25)",
    badge: null,
    features: [
      "Alles in Pro",
      "Tot 5 gebruikers",
      "Gedeelde presets",
      "Centraal gebruikersbeheer",
      "Prioriteit support",
    ],
    cta: "Contact opnemen",
    ctaHref: "/register",
    highlight: false,
  },
];

function Pricing() {
  const { ref, visible } = useFadeIn();
  return (
    <section id="pricing" className="py-28" ref={ref}>
      <div className="max-w-6xl mx-auto px-6">
        <div className={`text-center mb-16 transition-all duration-700 ${visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"}`}>
          <Badge>Prijzen</Badge>
          <h2 className="text-4xl font-extrabold text-white mt-5 mb-4 tracking-tight">
            Simpele, eerlijke prijzen
          </h2>
          <p className="text-zinc-500 text-lg max-w-md mx-auto">
            Begin gratis. Upgrade wanneer je klaar bent.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {PLANS.map((plan, i) => (
            <div key={plan.name}
              className={`relative rounded-2xl p-7 flex flex-col transition-all duration-700 ${plan.highlight ? "scale-[1.02]" : ""}`}
              style={{
                background: plan.color,
                border: `1px solid ${plan.border}`,
                boxShadow: plan.highlight ? "0 0 48px rgba(224,36,36,0.15)" : "none",
                transitionDelay: `${i * 80}ms`,
                opacity: visible ? 1 : 0,
                transform: visible ? (plan.highlight ? "scale(1.02)" : "translateY(0)") : "translateY(20px)",
              }}>

              {plan.badge && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full text-[10px] font-bold text-white"
                  style={{ background: BRAND, boxShadow: "0 4px 16px rgba(224,36,36,0.4)" }}>
                  {plan.badge}
                </div>
              )}

              <div className="mb-7">
                <p className="text-sm font-bold text-zinc-300 mb-3">{plan.name}</p>
                <div className="flex items-baseline gap-1.5">
                  <span className="text-4xl font-extrabold text-white">{plan.price}</span>
                  <span className="text-sm text-zinc-500">{plan.sub}</span>
                </div>
              </div>

              <ul className="space-y-3 flex-1 mb-8">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-start gap-2.5">
                    <svg className="w-4 h-4 mt-0.5 shrink-0" fill="none" stroke={plan.highlight ? BRAND : "#6b7280"} strokeWidth={2.5} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/>
                    </svg>
                    <span className="text-sm text-zinc-400">{f}</span>
                  </li>
                ))}
              </ul>

              <Link href={plan.ctaHref}
                className="w-full flex items-center justify-center h-11 rounded-xl font-semibold text-sm transition-all duration-150 active:scale-[0.97]"
                style={plan.highlight
                  ? { background: "linear-gradient(135deg,#e02424,#b81c1c)", color: "#fff", boxShadow: "0 4px 20px rgba(224,36,36,0.4)" }
                  : { background: "rgba(255,255,255,0.05)", color: "#a1a1aa", border: "1px solid rgba(255,255,255,0.08)" }}>
                {plan.cta}
              </Link>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ── Download CTA ──────────────────────────────────────────────────────────────
function DownloadCTA() {
  const { ref, visible } = useFadeIn();
  return (
    <section ref={ref} className="py-28">
      <div className="max-w-6xl mx-auto px-6">
        <div className={`relative rounded-3xl overflow-hidden p-14 text-center transition-all duration-700 ${visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"}`}
          style={{ background: "linear-gradient(135deg, rgba(224,36,36,0.12) 0%, rgba(224,36,36,0.04) 60%, rgba(255,255,255,0.02) 100%)", border: "1px solid rgba(224,36,36,0.2)" }}>

          {/* BG glow */}
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[300px] pointer-events-none"
            style={{ background: "radial-gradient(ellipse, rgba(224,36,36,0.15) 0%, transparent 70%)" }}/>

          <div className="relative">
            <div className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-6"
              style={{ background: BRAND, boxShadow: "0 0 40px rgba(224,36,36,0.5)" }}>
              <svg viewBox="0 0 24 24" fill="white" className="w-8 h-8">
                <path d="M13 10V3L4 14h7v7l9-11h-7z"/>
              </svg>
            </div>
            <h2 className="text-4xl font-extrabold text-white mb-4 tracking-tight">
              Klaar om te starten?
            </h2>
            <p className="text-zinc-400 text-lg mb-8 max-w-lg mx-auto">
              Download AutoSlice gratis voor Windows en begin vandaag nog met het converteren van je Bambu-modellen.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
              <a href="/api/download" download
                className="inline-flex items-center gap-2.5 px-6 h-11 rounded-xl font-semibold text-sm text-white transition-all duration-150 active:scale-[0.97] hover:bg-white/[0.08] hover:-translate-y-0.5"
                style={{ background: "rgba(255,255,255,0.07)", border: "1px solid rgba(255,255,255,0.18)" }}>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
                </svg>
                Downloaden voor Windows
              </a>
              <GradBtn href="/login" outline>Al een account? Inloggen</GradBtn>
            </div>
            <p className="mt-4 text-xs text-zinc-600">Windows 10/11 · 64-bit · ~180 MB · Automatische updates inbegrepen</p>
            <p className="mt-1 text-xs text-zinc-700">Linux &amp; iOS — binnenkort beschikbaar</p>
          </div>
        </div>
      </div>
    </section>
  );
}

// ── Footer ────────────────────────────────────────────────────────────────────
function LandingFooter() {
  return (
    <footer className="border-t py-14" style={{ borderColor: "rgba(255,255,255,0.06)" }}>
      <div className="max-w-6xl mx-auto px-6">
        <div className="flex flex-col lg:flex-row gap-12 mb-10">

          {/* Brand */}
          <div className="lg:w-[260px] shrink-0">
            <div className="flex items-center gap-2.5 mb-4">
              <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: BRAND }}>
                <svg viewBox="0 0 24 24" fill="white" className="w-3.5 h-3.5"><path d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
              </div>
              <span className="font-bold text-white">Auto<span style={{ color: BRAND }}>Slice</span></span>
            </div>
            <p className="text-sm text-zinc-600 leading-relaxed">
              De slimste manier om Bambu 3MF-bestanden te converteren naar Anycubic-printprofielen.
            </p>
          </div>

          {/* Links */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-10 flex-1">
            {[
              { heading: "Product", items: [["#features","Features"],["#how","Hoe het werkt"],["#pricing","Prijzen"]] },
              { heading: "Account", items: [["/register","Registreren"],["/login","Inloggen"]] },
              { heading: "Meer", items: [["mailto:support@autoslice.be","Support"],["https://github.com/quiandrosegier96-coder/autoslice","GitHub"]] },
            ].map(({ heading, items }) => (
              <div key={heading}>
                <p className="text-[11px] font-bold text-zinc-500 uppercase tracking-[0.12em] mb-4">{heading}</p>
                <ul className="space-y-2.5">
                  {items.map(([href, label]) => (
                    <li key={label}>
                      <a href={href} className="text-sm text-zinc-600 hover:text-zinc-300 transition-colors">{label}</a>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-8 border-t text-xs text-zinc-700"
          style={{ borderColor: "rgba(255,255,255,0.05)" }}>
          <p>© {new Date().getFullYear()} AutoSlice. Gemaakt door Quiandro Segier &amp; Yoni Smets.</p>
          <div className="flex items-center gap-5">
            <a href="#" className="hover:text-zinc-400 transition-colors">Privacy</a>
            <a href="#" className="hover:text-zinc-400 transition-colors">Voorwaarden</a>
          </div>
        </div>
      </div>
    </footer>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function LandingPage() {
  return (
    <div className="min-h-screen overflow-x-hidden" style={{ background: BG, color: "#e4e4e8", fontFamily: "Inter, system-ui, sans-serif" }}>
      <Navbar />
      <Hero />
      <TrustBar />
      <Features />
      <HowItWorks />
      <AppPreview />
      <MultiColorSection />
      <Pricing />
      <DownloadCTA />
      <LandingFooter />
    </div>
  );
}
