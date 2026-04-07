"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { isLoggedIn, getUser, getToken, saveAuth } from "@/lib/auth";
import { useLang } from "@/contexts/LangContext";
import { useTheme, type Theme } from "@/contexts/ThemeContext";
import { useUnits, type Unit } from "@/contexts/UnitsContext";
import { LANGS, type Lang } from "@/lib/i18n";
import { apiGet, apiPatch } from "@/lib/api";

// ── Section wrapper ────────────────────────────────────────────────────────

function Section({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="bg-surface-card border border-white/[0.07] rounded-2xl overflow-hidden
                    shadow-[0_4px_24px_rgba(0,0,0,0.3)]">
      <div className="px-6 py-4 border-b border-white/[0.07] flex items-center gap-3">
        <div className="w-7 h-7 rounded-lg bg-brand/15 flex items-center justify-center shrink-0">
          {icon}
        </div>
        <h2 className="text-xs font-bold text-zinc-300 uppercase tracking-[0.12em]">{title}</h2>
      </div>
      <div className="p-6">{children}</div>
    </div>
  );
}

// ── Toggle ─────────────────────────────────────────────────────────────────

function Toggle({ checked, onChange, disabled }: { checked: boolean; onChange: (v: boolean) => void; disabled?: boolean }) {
  return (
    <button
      type="button"
      onClick={() => !disabled && onChange(!checked)}
      disabled={disabled}
      className={`relative w-11 h-6 rounded-full transition-all duration-200 shrink-0 ${
        checked ? "bg-brand shadow-[0_0_12px_rgba(224,36,36,0.4)]" : "bg-white/10"
      } ${disabled ? "opacity-40 cursor-not-allowed" : "cursor-pointer"}`}
    >
      <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform duration-200 ${
        checked ? "translate-x-5" : "translate-x-0"
      }`} />
    </button>
  );
}

// ── Option card ─────────────────────────────────────────────────────────────

function OptionCard({ selected, onClick, icon, label, sub }: {
  selected: boolean; onClick: () => void;
  icon: React.ReactNode; label: string; sub?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex-1 flex flex-col items-center gap-2 py-4 px-3 rounded-xl border transition-all duration-150 ${
        selected
          ? "bg-brand/[0.12] border-brand/60 shadow-[0_0_16px_rgba(224,36,36,0.12)]"
          : "bg-white/[0.03] border-white/[0.07] hover:border-white/[0.15]"
      }`}
    >
      <span className={selected ? "text-brand" : "text-zinc-500"}>{icon}</span>
      <span className={`text-sm font-semibold ${selected ? "text-white" : "text-zinc-400"}`}>{label}</span>
      {sub && <span className="text-[10px] text-zinc-600">{sub}</span>}
    </button>
  );
}

// ── Input ──────────────────────────────────────────────────────────────────

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-[10px] font-bold text-zinc-500 uppercase tracking-[0.12em] mb-1.5">{label}</label>
      {children}
    </div>
  );
}

function Input({ value, onChange, type = "text", placeholder, disabled }: {
  value: string; onChange: (v: string) => void;
  type?: string; placeholder?: string; disabled?: boolean;
}) {
  return (
    <input
      type={type}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      disabled={disabled}
      className="w-full !px-3 h-10 bg-white/[0.05] border border-white/[0.09] rounded-xl
                 text-white text-sm focus:outline-none focus:border-brand/50
                 focus:bg-white/[0.07] transition-all duration-150
                 disabled:opacity-40 disabled:cursor-not-allowed"
    />
  );
}

// ── Main page ──────────────────────────────────────────────────────────────

export default function SettingsPage() {
  const router = useRouter();
  const { lang, setLang } = useLang();
  const { theme, setTheme } = useTheme();
  const { unit, setUnit } = useUnits();

  // Profile state
  const [appVersion, setAppVersion] = useState("…");
  const [username, setUsername]       = useState("");
  const [email, setEmail]             = useState("");
  const [currentPw, setCurrentPw]     = useState("");
  const [newPw, setNewPw]             = useState("");
  const [confirmPw, setConfirmPw]     = useState("");
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileMsg, setProfileMsg]   = useState<{ type: "ok" | "err"; text: string } | null>(null);
  const [memberSince, setMemberSince] = useState("");
  const [lastLogin, setLastLogin]     = useState("");

  // Preference state
  const [showUpdatePopup, setShowUpdatePopup] = useState(true);
  const [defaultFlush, setDefaultFlush] = useState("3");

  // Server-synced user settings
  type UserSettings = {
    viewer_support_preview: boolean;
    viewer_wireframe: boolean;
    viewer_bounding_box: boolean;
    viewer_contact_area: boolean;
    viewer_quality: string;
    viewer_bed_type: string;
    default_filament: string;
    default_nozzle: number;
    speed_quality: string;
    expert_mode: boolean;
    beta_features: boolean;
    debug_overlays: boolean;
  };
  const [userSettings, setUserSettings] = useState<UserSettings>({
    viewer_support_preview: true,
    viewer_wireframe: false,
    viewer_bounding_box: false,
    viewer_contact_area: false,
    viewer_quality: "medium",
    viewer_bed_type: "smooth",
    default_filament: "pla",
    default_nozzle: 0.4,
    speed_quality: "balanced",
    expert_mode: false,
    beta_features: false,
    debug_overlays: false,
  });
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [settingsMsg, setSettingsMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  useEffect(() => {
    window.autoslice?.getVersion?.().then((v) => setAppVersion(`v${v}`)).catch(() => {});
  }, []);

  useEffect(() => {
    if (!isLoggedIn()) { router.push("/login"); return; }
    const u = getUser();
    if (u) { setUsername(u.username); setEmail(u.email); }
    setShowUpdatePopup(localStorage.getItem("autoslice_update_popup") !== "false");
    setDefaultFlush(localStorage.getItem("autoslice_default_flush") ?? "3");

    apiGet<{ username: string; email: string; created_at?: string; last_login?: string }>("/auth/me", true)
      .then((data) => {
        setUsername(data.username);
        setEmail(data.email);
        if (data.created_at) setMemberSince(new Date(data.created_at).toLocaleDateString());
        if (data.last_login) setLastLogin(new Date(data.last_login).toLocaleDateString());
      })
      .catch(() => {});

    apiGet<UserSettings>("/auth/settings", true)
      .then((data) => setUserSettings((prev) => ({ ...prev, ...data })))
      .catch(() => {});
  }, [router]);

  async function saveUserSettings() {
    setSettingsSaving(true);
    setSettingsMsg(null);
    try {
      const updated = await apiPatch<UserSettings>("/auth/settings", { settings: userSettings });
      setUserSettings((prev) => ({ ...prev, ...updated }));
      setSettingsMsg({ type: "ok", text: "Instellingen opgeslagen." });
    } catch {
      setSettingsMsg({ type: "err", text: "Opslaan mislukt." });
    } finally {
      setSettingsSaving(false);
    }
  }

  function patchSetting<K extends keyof UserSettings>(key: K, value: UserSettings[K]) {
    setUserSettings((prev) => ({ ...prev, [key]: value }));
  }

  async function saveProfile() {
    setProfileMsg(null);
    if (newPw && newPw !== confirmPw) {
      setProfileMsg({ type: "err", text: "New passwords do not match." });
      return;
    }
    if (newPw && newPw.length < 8) {
      setProfileMsg({ type: "err", text: "Password must be at least 8 characters." });
      return;
    }
    setProfileSaving(true);
    try {
      const body: Record<string, string> = { username, email };
      if (newPw) { body.current_password = currentPw; body.new_password = newPw; }
      const res = await apiPatch<{ username: string; email: string }>("/auth/me", body);
      const cur = getUser();
      const tok = getToken();
      if (cur && tok) saveAuth({ ...cur, token: tok, username: res.username, email: res.email });
      setProfileMsg({ type: "ok", text: "Profile updated successfully." });
      setCurrentPw(""); setNewPw(""); setConfirmPw("");
    } catch (e: unknown) {
      setProfileMsg({ type: "err", text: e instanceof Error ? e.message : "Update failed." });
    } finally {
      setProfileSaving(false);
    }
  }

  function savePreferences() {
    localStorage.setItem("autoslice_update_popup", String(showUpdatePopup));
    localStorage.setItem("autoslice_default_flush", defaultFlush);
  }

  return (
    <div className="max-w-3xl mx-auto px-6 py-8 space-y-6">

      {/* Header */}
      <div className="mb-2">
        <h1 className="text-2xl font-bold text-white tracking-tight">Instellingen</h1>
        <p className="text-sm text-zinc-500 mt-1">Beheer je account, uiterlijk en voorkeuren.</p>
      </div>

      {/* ── Profile ── */}
      <Section title="Profiel" icon={
        <svg className="w-4 h-4 text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
        </svg>
      }>
        <div className="grid grid-cols-2 gap-4 mb-4">
          <Field label="Gebruikersnaam">
            <Input value={username} onChange={setUsername} placeholder="username" />
          </Field>
          <Field label="E-mailadres">
            <Input value={email} onChange={setEmail} type="email" placeholder="you@example.com" />
          </Field>
        </div>

        <div className="border-t border-white/[0.06] pt-4 mb-4">
          <p className="text-[11px] font-bold text-zinc-500 uppercase tracking-[0.12em] mb-3">Wachtwoord wijzigen</p>
          <div className="grid grid-cols-3 gap-3">
            <Field label="Huidig wachtwoord">
              <Input value={currentPw} onChange={setCurrentPw} type="password" placeholder="••••••••" />
            </Field>
            <Field label="Nieuw wachtwoord">
              <Input value={newPw} onChange={setNewPw} type="password" placeholder="Min. 8 tekens" />
            </Field>
            <Field label="Bevestig wachtwoord">
              <Input value={confirmPw} onChange={setConfirmPw} type="password" placeholder="Herhaal nieuw" />
            </Field>
          </div>
        </div>

        {profileMsg && (
          <div className={`mb-4 p-3 rounded-xl text-sm ${
            profileMsg.type === "ok"
              ? "bg-green-500/10 border border-green-500/20 text-green-400"
              : "bg-brand/8 border border-brand/20 text-brand"
          }`}>
            {profileMsg.text}
          </div>
        )}

        <div className="flex items-center justify-between">
          <div className="text-xs text-zinc-600 space-y-0.5">
            {memberSince && <p>Lid sinds: <span className="text-zinc-500">{memberSince}</span></p>}
            {lastLogin   && <p>Laatst ingelogd: <span className="text-zinc-500">{lastLogin}</span></p>}
          </div>
          <button
            onClick={saveProfile}
            disabled={profileSaving}
            className="px-5 py-2 rounded-xl bg-gradient-to-r from-brand to-brand-dark
                       text-white text-sm font-semibold
                       shadow-[0_4px_16px_rgba(224,36,36,0.35)]
                       hover:shadow-[0_6px_24px_rgba(224,36,36,0.5)]
                       hover:-translate-y-0.5 active:translate-y-0
                       transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {profileSaving ? "Opslaan…" : "Opslaan"}
          </button>
        </div>
      </Section>

      {/* ── Appearance ── */}
      <Section title="Uiterlijk" icon={
        <svg className="w-4 h-4 text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" />
        </svg>
      }>
        <p className="text-xs text-zinc-500 mb-4">Kies het thema voor de applicatie.</p>
        <div className="flex gap-3">
          <OptionCard
            selected={theme === "dark"}
            onClick={() => setTheme("dark" as Theme)}
            icon={
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
              </svg>
            }
            label="Donker"
            sub="Standaard"
          />
          <OptionCard
            selected={theme === "light"}
            onClick={() => setTheme("light" as Theme)}
            icon={
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707M17.657 17.657l.707.707M6.343 6.343l.707.707M12 8a4 4 0 100 8 4 4 0 000-8z" />
              </svg>
            }
            label="Licht"
          />
        </div>
      </Section>

      {/* ── Language ── */}
      <Section title="Taal" icon={
        <svg className="w-4 h-4 text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129" />
        </svg>
      }>
        <p className="text-xs text-zinc-500 mb-4">Kies de taal van de interface.</p>
        <div className="flex gap-3">
          {LANGS.map(({ code, label }) => (
            <OptionCard
              key={code}
              selected={lang === code}
              onClick={() => setLang(code as Lang)}
              icon={
                <span className="text-2xl leading-none">
                  {code === "nl" ? "🇳🇱" : code === "en" ? "🇬🇧" : code === "fr" ? "🇫🇷" : "🇩🇪"}
                </span>
              }
              label={label}
              sub={code === "nl" ? "Nederlands" : code === "en" ? "English" : code === "fr" ? "Français" : "Deutsch"}
            />
          ))}
        </div>
      </Section>

      {/* ── Units ── */}
      <Section title="Eenheden" icon={
        <svg className="w-4 h-4 text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3" />
        </svg>
      }>
        <p className="text-xs text-zinc-500 mb-4">Kies de maateenheid voor afmetingen in de app.</p>
        <div className="flex gap-3">
          <OptionCard
            selected={unit === "mm"}
            onClick={() => setUnit("mm" as Unit)}
            icon={<span className="text-xl font-bold">mm</span>}
            label="Millimeter"
            sub="Standaard"
          />
          <OptionCard
            selected={unit === "inch"}
            onClick={() => setUnit("inch" as Unit)}
            icon={<span className="text-xl font-bold">&quot;</span>}
            label="Inch"
            sub="Imperial"
          />
        </div>
      </Section>

      {/* ── Preferences ── */}
      <Section title="Voorkeuren" icon={
        <svg className="w-4 h-4 text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
        </svg>
      }>
        <div className="space-y-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-zinc-200">Update-meldingen</p>
              <p className="text-xs text-zinc-500 mt-0.5">Toon een popup wanneer een nieuwe versie beschikbaar is.</p>
            </div>
            <Toggle checked={showUpdatePopup} onChange={setShowUpdatePopup} />
          </div>

          <div className="border-t border-white/[0.06] pt-5 flex items-end gap-4">
            <div className="flex-1">
              <Field label="Standaard spoelvolume (mm³)">
                <Input value={defaultFlush} onChange={setDefaultFlush} type="number" placeholder="3.0" />
              </Field>
              <p className="text-[10px] text-zinc-600 mt-1">Standaardwaarde voor het spoelvolume bij nieuwe conversies.</p>
            </div>
            <button
              onClick={savePreferences}
              className="px-5 py-2 rounded-xl bg-white/[0.06] border border-white/[0.09]
                         text-white text-sm font-semibold hover:bg-white/[0.09]
                         transition-all duration-150 shrink-0"
            >
              Opslaan
            </button>
          </div>
        </div>
      </Section>

      {/* ── Viewer defaults ── */}
      <Section title="Viewer instellingen" icon={
        <svg className="w-4 h-4 text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M15 12a3 3 0 11-6 0 3 3 0 016 0z M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
        </svg>
      }>
        <div className="space-y-4">
          {([
            ["viewer_support_preview", "Ondersteuningspreview"],
            ["viewer_wireframe",       "Wireframe-modus"],
            ["viewer_bounding_box",    "Bounding box tonen"],
            ["viewer_contact_area",    "Contactoppervlak tonen"],
          ] as const).map(([key, label]) => (
            <div key={key} className="flex items-center justify-between">
              <p className="text-sm text-zinc-300">{label}</p>
              <Toggle
                checked={userSettings[key]}
                onChange={(v) => patchSetting(key, v)}
              />
            </div>
          ))}
          <div className="border-t border-white/[0.06] pt-4 grid grid-cols-2 gap-4">
            <Field label="Viewer kwaliteit">
              <select
                value={userSettings.viewer_quality}
                onChange={(e) => patchSetting("viewer_quality", e.target.value)}
                className="w-full h-9 px-3 rounded-lg text-sm focus:outline-none"
                style={{ background: "#1a1a1f", border: "1px solid rgba(255,255,255,0.1)", color: "#e4e4e8", colorScheme: "dark" }}
              >
                <option value="low">Laag</option>
                <option value="medium">Middel</option>
                <option value="high">Hoog</option>
              </select>
            </Field>
            <Field label="Standaard bedplaat">
              <select
                value={userSettings.viewer_bed_type}
                onChange={(e) => patchSetting("viewer_bed_type", e.target.value)}
                className="w-full h-9 px-3 rounded-lg text-sm focus:outline-none"
                style={{ background: "#1a1a1f", border: "1px solid rgba(255,255,255,0.1)", color: "#e4e4e8", colorScheme: "dark" }}
              >
                <option value="smooth">Glad PEI</option>
                <option value="textured">Getextureerd PEI</option>
                <option value="high_temp">Hoge temperatuur</option>
              </select>
            </Field>
          </div>
        </div>
      </Section>

      {/* ── Print defaults ── */}
      <Section title="Print standaardwaarden" icon={
        <svg className="w-4 h-4 text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" />
        </svg>
      }>
        <div className="grid grid-cols-2 gap-4 mb-5">
          <Field label="Standaard filament">
            <select
              value={userSettings.default_filament}
              onChange={(e) => patchSetting("default_filament", e.target.value)}
              className="w-full h-9 px-3 rounded-lg text-sm focus:outline-none"
              style={{ background: "#1a1a1f", border: "1px solid rgba(255,255,255,0.1)", color: "#e4e4e8", colorScheme: "dark" }}
            >
              <option value="pla">PLA</option>
              <option value="petg">PETG</option>
              <option value="tpu">TPU</option>
            </select>
          </Field>
          <Field label="Standaard nozzle (mm)">
            <select
              value={userSettings.default_nozzle}
              onChange={(e) => patchSetting("default_nozzle", parseFloat(e.target.value))}
              className="w-full h-9 px-3 rounded-lg text-sm focus:outline-none"
              style={{ background: "#1a1a1f", border: "1px solid rgba(255,255,255,0.1)", color: "#e4e4e8", colorScheme: "dark" }}
            >
              {[0.2, 0.4, 0.6, 0.8].map((n) => (
                <option key={n} value={n}>{n} mm</option>
              ))}
            </select>
          </Field>
        </div>
        <div className="mb-5">
          <p className="text-[11px] font-bold text-zinc-500 uppercase tracking-[0.12em] mb-3">Snelheid vs. kwaliteit</p>
          <div className="flex gap-3">
            {([["speed", "Snel"], ["balanced", "Gebalanceerd"], ["quality", "Kwaliteit"]] as const).map(([val, label]) => (
              <button
                key={val}
                type="button"
                onClick={() => patchSetting("speed_quality", val)}
                className={`flex-1 py-2.5 rounded-xl text-sm font-medium border transition-all duration-150
                  ${userSettings.speed_quality === val
                    ? "bg-brand/15 border-brand/50 text-white shadow-[0_0_16px_rgba(224,36,36,0.12)]"
                    : "bg-white/[0.03] border-white/[0.07] text-zinc-400 hover:text-zinc-200"}`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        <div className="flex items-center justify-between pt-4 border-t border-white/[0.06]">
          <div>
            <p className="text-sm text-zinc-300">Expertmodus</p>
            <p className="text-xs text-zinc-600 mt-0.5">Toon geavanceerde opties in het conversiescherm.</p>
          </div>
          <Toggle checked={userSettings.expert_mode} onChange={(v) => patchSetting("expert_mode", v)} />
        </div>
      </Section>

      {/* ── Advanced ── */}
      <Section title="Geavanceerd" icon={
        <svg className="w-4 h-4 text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      }>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-zinc-300">Beta-functies</p>
              <p className="text-xs text-zinc-600 mt-0.5">Schakel experimentele functies in die nog in ontwikkeling zijn.</p>
            </div>
            <Toggle checked={userSettings.beta_features} onChange={(v) => patchSetting("beta_features", v)} />
          </div>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-zinc-300">Debug-overlays</p>
              <p className="text-xs text-zinc-600 mt-0.5">Toon technische debug-informatie in de viewer.</p>
            </div>
            <Toggle checked={userSettings.debug_overlays} onChange={(v) => patchSetting("debug_overlays", v)} />
          </div>
        </div>
      </Section>

      {/* Save server settings */}
      <div className="flex items-center justify-between p-4 bg-white/[0.02] border border-white/[0.06] rounded-2xl">
        <div>
          {settingsMsg && (
            <p className={`text-sm ${settingsMsg.type === "ok" ? "text-green-400" : "text-red-400"}`}>
              {settingsMsg.text}
            </p>
          )}
        </div>
        <button
          onClick={saveUserSettings}
          disabled={settingsSaving}
          className="px-5 py-2 rounded-xl bg-gradient-to-r from-brand to-brand-dark
                     text-white text-sm font-semibold shadow-[0_4px_16px_rgba(224,36,36,0.35)]
                     hover:shadow-[0_6px_24px_rgba(224,36,36,0.5)] hover:-translate-y-0.5 active:translate-y-0
                     transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {settingsSaving ? "Opslaan…" : "Instellingen opslaan"}
        </button>
      </div>

      {/* ── Keyboard shortcuts ── */}
      <Section title="Sneltoetsen" icon={
        <svg className="w-4 h-4 text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
        </svg>
      }>
        <div className="grid grid-cols-2 gap-2 text-sm">
          {[
            ["Converteren",        "Ctrl + Enter"],
            ["Nieuw bestand",      "Ctrl + O"],
            ["Instellingen",       "Ctrl + ,"],
            ["Uitloggen",          "Ctrl + Shift + Q"],
            ["Geschiedenis",       "Ctrl + H"],
            ["Community",          "Ctrl + Shift + C"],
          ].map(([action, key]) => (
            <div key={action} className="flex items-center justify-between py-2 px-3
                                         bg-white/[0.03] rounded-lg border border-white/[0.05]">
              <span className="text-zinc-400 text-xs">{action}</span>
              <kbd className="text-[10px] font-mono font-bold text-zinc-500 bg-white/[0.06]
                              border border-white/[0.08] px-2 py-0.5 rounded-md">
                {key}
              </kbd>
            </div>
          ))}
        </div>
      </Section>

      {/* ── About ── */}
      <Section title="Over AutoSlice" icon={
        <svg className="w-4 h-4 text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M13 16h-1v-4h-1m1-4h.01M12 2a10 10 0 100 20A10 10 0 0012 2z" />
        </svg>
      }>
        <div className="grid grid-cols-3 gap-4 text-sm">
          {[
            ["Versie",         appVersion],
            ["Gemaakt door",   "Quiandro Segier"],
            ["Design",         "YoyoDesign"],
            ["Powered by",     "Network-it"],
            ["Technologie",    "Next.js + Electron"],
            ["Platform",       "Windows x64"],
          ].map(([label, val]) => (
            <div key={label} className="bg-white/[0.03] border border-white/[0.05] rounded-xl p-3">
              <p className="text-[10px] font-bold text-zinc-600 uppercase tracking-widest mb-1">{label}</p>
              <p className="text-sm font-medium text-zinc-300">{val}</p>
            </div>
          ))}
        </div>
      </Section>
    </div>
  );
}
