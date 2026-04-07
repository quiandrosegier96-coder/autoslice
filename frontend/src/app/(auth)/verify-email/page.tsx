"use client";

import { useState, useEffect, useRef, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { apiPost } from "@/lib/api";
import { saveAuth } from "@/lib/auth";

function VerifyEmailContent() {
  const router = useRouter();
  const params = useSearchParams();
  const email    = params.get("email") ?? "";
  const username = params.get("username") ?? "";

  const [code, setCode]       = useState(["", "", "", "", "", ""]);
  const [error, setError]     = useState("");
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [resendMsg, setResendMsg] = useState("");
  const [resendCooldown, setResendCooldown] = useState(0);
  const inputs = useRef<(HTMLInputElement | null)[]>([]);

  useEffect(() => {
    inputs.current[0]?.focus();
  }, []);

  useEffect(() => {
    if (resendCooldown <= 0) return;
    const t = setTimeout(() => setResendCooldown((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [resendCooldown]);

  function handleDigit(i: number, val: string) {
    const digit = val.replace(/\D/g, "").slice(-1);
    const next = [...code];
    next[i] = digit;
    setCode(next);
    setError("");
    if (digit && i < 5) inputs.current[i + 1]?.focus();
    if (next.every((d) => d !== "")) submitCode(next.join(""));
  }

  function handleKeyDown(i: number, e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Backspace" && !code[i] && i > 0) {
      inputs.current[i - 1]?.focus();
    }
  }

  function handlePaste(e: React.ClipboardEvent) {
    e.preventDefault();
    const digits = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6).split("");
    if (digits.length === 6) {
      setCode(digits);
      inputs.current[5]?.focus();
      submitCode(digits.join(""));
    }
  }

  async function submitCode(fullCode: string) {
    setLoading(true);
    setError("");
    try {
      const res = await apiPost<{ access_token: string; username: string; email: string; is_admin: boolean }>(
        "/auth/verify-email",
        { email, code: fullCode }
      );
      saveAuth({ token: res.access_token, username: res.username, email: res.email, is_admin: res.is_admin });
      router.push("/convert");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Ongeldige code.");
      setCode(["", "", "", "", "", ""]);
      setTimeout(() => inputs.current[0]?.focus(), 50);
    } finally {
      setLoading(false);
    }
  }

  async function resend() {
    if (resendCooldown > 0 || resending) return;
    setResending(true);
    setResendMsg("");
    setError("");
    try {
      await apiPost("/auth/resend-verification", { email });
      setResendMsg("Nieuwe code verstuurd! Controleer je e-mail.");
      setResendCooldown(60);
    } catch (err: unknown) {
      setResendMsg(err instanceof Error ? err.message : "Probeer opnieuw.");
    } finally {
      setResending(false);
    }
  }

  const filled = code.filter(Boolean).length;

  return (
    <div className="min-h-screen bg-[#0a0a0d] flex items-center justify-center p-4">

      {/* Background glow */}
      <div className="pointer-events-none fixed inset-0">
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[600px] h-[600px] rounded-full bg-brand/10 blur-[120px]" />
      </div>

      <div className="relative w-full max-w-[400px]">
        {/* Card */}
        <div className="bg-[#0e0e14] border border-white/[0.08] rounded-2xl p-8
                        shadow-[0_24px_80px_rgba(0,0,0,0.6)]">

          {/* Icon */}
          <div className="w-14 h-14 rounded-2xl bg-brand/15 flex items-center justify-center mx-auto mb-6">
            <svg className="w-7 h-7 text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8}
                d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
            </svg>
          </div>

          <h1 className="text-[22px] font-bold text-white text-center mb-1">Verifieer je e-mail</h1>
          <p className="text-[13px] text-zinc-500 text-center mb-1">
            We hebben een 6-cijferige code gestuurd naar
          </p>
          <p className="text-[13px] font-medium text-zinc-300 text-center mb-7 break-all">{email}</p>

          {/* Code input */}
          <div className="flex gap-2 justify-center mb-6" onPaste={handlePaste}>
            {code.map((digit, i) => (
              <input
                key={i}
                ref={(el) => { inputs.current[i] = el; }}
                type="text"
                inputMode="numeric"
                maxLength={1}
                value={digit}
                onChange={(e) => handleDigit(i, e.target.value)}
                onKeyDown={(e) => handleKeyDown(i, e)}
                disabled={loading}
                className="w-11 h-13 text-center text-xl font-bold rounded-xl border transition-all duration-150
                           focus:outline-none disabled:opacity-50"
                style={{
                  height: "52px",
                  background: digit ? "rgba(224,36,36,0.1)" : "#1a1a1f",
                  border: `1.5px solid ${digit ? "rgba(224,36,36,0.5)" : error ? "rgba(239,68,68,0.4)" : "rgba(255,255,255,0.1)"}`,
                  color: "#ffffff",
                  WebkitAppearance: "none",
                }}
              />
            ))}
          </div>

          {/* Progress bar */}
          <div className="h-0.5 bg-white/[0.06] rounded-full mb-5 overflow-hidden">
            <div
              className="h-full bg-brand rounded-full transition-all duration-300"
              style={{ width: `${(filled / 6) * 100}%` }}
            />
          </div>

          {/* Error */}
          {error && (
            <div className="flex items-center gap-2 px-3 py-2.5 bg-red-500/10 border border-red-500/20
                            rounded-lg mb-4 text-[13px] text-red-400">
              <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
              {error}
            </div>
          )}

          {/* Submit button — shown when all digits filled but not auto-submitted yet */}
          {filled === 6 && loading && (
            <div className="flex items-center justify-center gap-2 h-10 text-[13px] text-zinc-400 mb-4">
              <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
              </svg>
              Verificeren…
            </div>
          )}

          {/* Resend */}
          <div className="text-center mt-2">
            {resendMsg && (
              <p className={`text-[12px] mb-3 ${resendMsg.includes("verstuurd") ? "text-green-400" : "text-red-400"}`}>
                {resendMsg}
              </p>
            )}
            <button
              type="button"
              onClick={resend}
              disabled={resendCooldown > 0 || resending}
              className="text-[13px] text-zinc-500 hover:text-zinc-300 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {resendCooldown > 0
                ? `Opnieuw versturen (${resendCooldown}s)`
                : resending ? "Versturen…" : "Code niet ontvangen? Opnieuw versturen"}
            </button>
          </div>

          {/* Back to login */}
          <div className="text-center mt-5 pt-5 border-t border-white/[0.06]">
            <a href="/login" className="text-[12px] text-zinc-600 hover:text-zinc-400 transition-colors">
              Terug naar inloggen
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense>
      <VerifyEmailContent />
    </Suspense>
  );
}
