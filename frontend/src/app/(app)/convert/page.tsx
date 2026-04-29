"use client";

import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { isLoggedIn, getUser } from "@/lib/auth";
import { useLang } from "@/contexts/LangContext";
import { apiUpload, apiAnalyze, apiConvertDownload, apiGet, apiPost } from "@/lib/api";
import { useToast, ToastContainer } from "@/components/Toast";

const ModelViewer = dynamic(
  () => import("@/components/ModelViewer").then((m) => m.ModelViewer),
  {
    ssr: false,
    loading: () => (
      <div className="w-full h-72 bg-surface-card rounded-xl border border-surface-border flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-brand border-t-transparent rounded-full animate-spin" />
      </div>
    ),
  }
);

type PrintabilityScore = {
  total: number;
  support_score: number;
  adhesion_score: number;
  stability_score: number;
  detail_score: number;
  bridge_score: number;
  difficulty_label: string;
  warnings: string[];
};

type SettingExplanation = {
  setting: string;
  value: string;
  reason: string;
  icon: "check" | "warning" | "info";
};

type ExplanationReport = {
  summary: string;
  items: SettingExplanation[];
};

type OrientationCandidate = {
  label: string;
  rotation_euler_deg: number[];
  overhang_area_ratio: number;
  contact_area_mm2: number;
  height_to_base_ratio: number;
  height_mm: number;
  support_score: number;
  adhesion_score: number;
  stability_score: number;
  total_score: number;
};

type OrientationReport = {
  recommended: OrientationCandidate;
  original: OrientationCandidate;
  all_candidates: OrientationCandidate[];
  improvement: number;
  should_rotate: boolean;
  support_reduction_pct: number;
  reasons: string[];
};

type SourceFilaments = {
  colors: string[];
  types: string[];
  count: number;
};

type AnalysisResult = {
  job_id: string;
  model: { part_count: number; unit: string };
  source_filaments?: SourceFilaments;
  geometry: {
    bounding_box: { x_mm: number; y_mm: number; z_mm: number; volume_cm3: number };
    part_count: number;
    mesh_is_watertight: boolean;
    overhang: { has_overhangs: boolean; max_angle_deg: number; overhang_area_ratio: number };
    bridge: { has_bridges: boolean; max_span_mm: number };
    thin_wall: { has_thin_walls: boolean };
  };
  intent: {
    difficulty: string;
    needs_supports: boolean;
    support_density_hint: string;
    needs_brim: boolean;
    size_class: string;
    is_structurally_risky: boolean;
    support_risk: number;
    adhesion_risk: number;
    stability_risk: number;
    detail_risk: number;
  };
  printability: PrintabilityScore;
  explanations: ExplanationReport;
  orientation: OrientationReport;
};

type Printer = { id: string; display_name: string; supported_filaments: string[]; max_colors: number };

const FILAMENT_LABELS: Record<string, string> = { pla: "PLA", petg: "PETG", tpu: "TPU" };

const NOZZLE_SIZES = [
  { value: 0.2, label: "0.2 mm — Fine detail" },
  { value: 0.4, label: "0.4 mm — Standard" },
  { value: 0.6, label: "0.6 mm — Fast / thick" },
  { value: 0.8, label: "0.8 mm — Draft / vase" },
  { value: 1.0, label: "1.0 mm — Extra thick" },
];

const NOZZLE_TYPES = [
  { value: "brass", label: "Brass" },
  { value: "hardened_steel", label: "Hardened Steel" },
  { value: "stainless_steel", label: "Stainless Steel" },
  { value: "ruby_tip", label: "Ruby Tip" },
  { value: "ceramic", label: "Ceramic" },
];

const BUILD_PLATES = [
  { value: "smooth",    label: "Smooth PEI" },
  { value: "textured",  label: "Textured PEI (+5°C bed)" },
  { value: "high_temp", label: "High Temp Plate (+10°C bed)" },
  { value: "glass",     label: "Glass" },
  { value: "cold",      label: "Cold plate (0°C bed)" },
];

const difficultyColor: Record<string, string> = {
  easy: "text-green-400",
  moderate: "text-yellow-400",
  hard: "text-red-400",
};

// ── Shared select style ────────────────────────────────────────────────────────
const SEL = "w-full h-10 pl-9 pr-3 bg-white/[0.05] border border-white/[0.09] rounded-xl text-white text-sm focus:outline-none focus:border-brand/50 focus:bg-white/[0.07] transition-all duration-150 disabled:opacity-50 disabled:cursor-not-allowed";

export default function ConvertPage() {
  const router = useRouter();
  const { t } = useLang();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [user, setUser] = useState<{ username: string; email: string; is_admin: boolean } | null>(null);
  const [printers, setPrinters] = useState<Printer[]>([]);
  const [selectedPrinter, setSelectedPrinter] = useState("");
  const [selectedFilament, setSelectedFilament] = useState("pla");
  const [availableFilaments, setAvailableFilaments] = useState<string[]>(["pla"]);
  const [nozzleSize, setNozzleSize] = useState(0.4);
  const [nozzleType, setNozzleType] = useState("brass");
  const [buildPlate, setBuildPlate] = useState("smooth");
  const [flushVolume, setFlushVolume] = useState(3.0);
  const [multiColorMode, setMultiColorMode] = useState<"none" | "ace_pro" | "ace_pro2">("none");
  const [dualUnit, setDualUnit] = useState(false);
  const [colorCount, setColorCount] = useState(1);
  const [slotColors, setSlotColors] = useState<string[]>(["#FF0000", "#00AA00", "#0000FF", "#FF8800", "#AA00AA", "#00AAAA", "#FFFFFF", "#111111"]);
  const [slotFilaments, setSlotFilaments] = useState<string[]>(Array(8).fill("pla"));

  const [dragging, setDragging] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);

  const [step, setStep] = useState<"idle" | "uploading" | "analyzing" | "ready" | "converting" | "done">("idle");
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState("");
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [feedbackSent, setFeedbackSent] = useState(false);
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const [downloadName, setDownloadName] = useState("");
  const [ratingGiven, setRatingGiven] = useState(0);
  const [ratingLoading, setRatingLoading] = useState(false);
  const [ratingDone, setRatingDone] = useState(false);
  const [applyOrientation, setApplyOrientation] = useState(false);
  const [showSupports, setShowSupports] = useState(false);
  const [manualEuler, setManualEuler] = useState<number[]>([]);

  // Scale & fuzzy skin
  const [scalePct, setScalePct] = useState(100);
  const [fuzzySkin, setFuzzySkin] = useState<"none" | "outer" | "all" | "allwalls">("none");
  const [fuzzyThickness, setFuzzyThickness] = useState(0.3);
  const [fuzzyDist, setFuzzyDist] = useState(0.8);

  // Progress simulation
  const [progress, setProgress] = useState(0);
  const [progressText, setProgressText] = useState("");
  const [conversionStart, setConversionStart] = useState<number | null>(null);
  const [conversionTime, setConversionTime] = useState<number | null>(null);
  const [resultSize, setResultSize] = useState<number | null>(null);
  const progressIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Preset system
  const [presets, setPresets] = useState<Record<string, object>>({});
  const [presetName, setPresetName] = useState("");
  const [showPresetInput, setShowPresetInput] = useState(false);
  const [confirmDeletePreset, setConfirmDeletePreset] = useState<string | null>(null);
  const [defaultPreset, setDefaultPreset] = useState<string | null>(null);
  const [lastUsedPreset, setLastUsedPreset] = useState<string | null>(null);
  const [showPresetsMenu, setShowPresetsMenu] = useState(false);
  const [renamingPreset, setRenamingPreset] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [didAutoLoad, setDidAutoLoad] = useState(false);
  const presetsMenuRef = useRef<HTMLDivElement>(null);
  const importInputRef = useRef<HTMLInputElement>(null);

  // Toast
  const { toasts, push: pushToast, dismiss: dismissToast } = useToast();

  useEffect(() => {
    if (!isLoggedIn()) { router.push("/login"); return; }
    setUser(getUser());
    try {
      const saved = JSON.parse(localStorage.getItem("autoslice_presets") ?? "{}");
      setPresets(saved);
      setDefaultPreset(localStorage.getItem("autoslice_preset_default") ?? null);
      setLastUsedPreset(localStorage.getItem("autoslice_preset_last_used") ?? null);
    } catch { /* ignore */ }
    apiGet<Printer[]>("/printers").then((ps) => {
      setPrinters(ps);
      if (ps.length > 0) {
        const first = ps[0];
        const firstFil = first.supported_filaments[0] ?? "pla";
        setSelectedPrinter(first.id);
        setAvailableFilaments(first.supported_filaments);
        setSelectedFilament(firstFil);
        setSlotFilaments(prev => { const a = [...prev]; a[0] = firstFil; return a; });
        if (first.max_colors > 1) {
          const dual = first.max_colors >= 8;
          setColorCount(first.max_colors);
          setMultiColorMode(dual ? "ace_pro2" : "ace_pro");
          setDualUnit(dual);
        }
      }
    });
  }, [router]);

  // ── Keyboard shortcuts ──────────────────────────────────────────────────────
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement).tagName;
      const inInput = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
      const working = step === "uploading" || step === "analyzing" || step === "converting";

      // Ctrl+O — open file picker
      if (e.ctrlKey && e.key === "o" && !inInput) {
        e.preventDefault();
        if (!working && step !== "done") fileInputRef.current?.click();
      }
      // Ctrl+S — save preset (opens name input)
      if (e.ctrlKey && e.key === "s" && !inInput) {
        e.preventDefault();
        if (!working) setShowPresetInput(true);
      }
      // Enter — generate if ready
      if (e.key === "Enter" && !inInput && step === "ready") {
        e.preventDefault();
        handleConvert();
      }
      // Esc — close modals / preset input
      if (e.key === "Escape") {
        setShowPresetInput(false);
        setPresetName("");
        setConfirmDeletePreset(null);
        setShowPresetsMenu(false);
        setRenamingPreset(null);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step]);

  // Auto-load default preset once printers are ready
  useEffect(() => {
    if (didAutoLoad || printers.length === 0) return;
    setDidAutoLoad(true);
    const defName = localStorage.getItem("autoslice_preset_default");
    if (!defName) return;
    try {
      const saved = JSON.parse(localStorage.getItem("autoslice_presets") ?? "{}") as Record<string, object>;
      const p = saved[defName] as Record<string, unknown> | undefined;
      if (p) applyPresetValues(p);
    } catch { /* ignore */ }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [printers, didAutoLoad]);

  // Close presets menu on outside click
  useEffect(() => {
    if (!showPresetsMenu) return;
    function onDown(e: MouseEvent) {
      if (presetsMenuRef.current && !presetsMenuRef.current.contains(e.target as Node)) {
        setShowPresetsMenu(false);
        setRenamingPreset(null);
      }
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [showPresetsMenu]);

  function handlePrinterChange(id: string) {
    setSelectedPrinter(id);
    const p = printers.find((x) => x.id === id);
    if (p) {
      setAvailableFilaments(p.supported_filaments);
      const firstFil = p.supported_filaments[0] ?? "pla";
      setSelectedFilament(firstFil);
      setSlotFilaments(prev => { const a = [...prev]; a[0] = firstFil; return a; });
      if (p.max_colors > 1) {
        const dual = p.max_colors >= 8;
        setColorCount(p.max_colors);
        setMultiColorMode(dual ? "ace_pro2" : "ace_pro");
        setDualUnit(dual);
      } else {
        setColorCount(1);
        setMultiColorMode("none");
        setDualUnit(false);
      }
    }
  }

  function handleMultiColorMode(mode: "none" | "ace_pro" | "ace_pro2") {
    setMultiColorMode(mode);
    if (mode === "none") {
      setColorCount(1);
      setDualUnit(false);
    } else {
      setColorCount(dualUnit ? 8 : 4);
    }
  }

  function handleDualUnit(checked: boolean) {
    setDualUnit(checked);
    if (multiColorMode !== "none") {
      setColorCount(checked ? 8 : 4);
    }
  }

  async function handleFile(file: File) {
    if (!file.name.endsWith(".3mf")) { setError("Please upload a .3mf file."); return; }
    setError("");
    setUploadedFile(file);
    setStep("uploading");
    setAnalysis(null);
    setDownloadUrl(null);
    setApplyOrientation(false);
    setManualEuler([]);
    try {
      const up = await apiUpload(file);
      setJobId(up.job_id);
      setStep("analyzing");
      const result = await apiAnalyze(up.job_id) as AnalysisResult;
      setAnalysis(result);
      const sf = result.source_filaments;
      if (sf && sf.count > 1) {
        const dual = sf.count >= 8;
        setColorCount(sf.count);
        setMultiColorMode(dual ? "ace_pro2" : "ace_pro");
        setDualUnit(dual);
        if (sf.colors.length > 0) {
          setSlotColors(prev => {
            const a = [...prev];
            sf.colors.forEach((c, i) => { if (i < a.length) a[i] = c; });
            return a;
          });
        }
        if (sf.types.length > 0) {
          setSlotFilaments(prev => {
            const a = [...prev];
            sf.types.forEach((ty, i) => { if (i < a.length) a[i] = ty; });
            return a;
          });
        }
      }
      setStep("ready");
      pushToast("success", `${file.name} geladen en geanalyseerd`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed");
      setStep("idle");
      pushToast("error", "Upload mislukt. Probeer opnieuw.");
    }
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }

  async function handleConvert() {
    if (!jobId || !selectedPrinter) return;
    if (multiColorMode !== "none" && dualUnit && colorCount !== 8) {
      setColorCount(8);
      setError("Second ACE unit enabled, but 8 filament slots were not generated. Slot configuration was rebuilt automatically.");
      return;
    }
    setStep("converting");
    setError("");
    setProgress(0);
    setConversionStart(Date.now());
    setConversionTime(null);

    // Smooth progress simulation — advances toward each target gradually
    const phases = [
      { target: 18, text: "Model analyseren..." },
      { target: 42, text: "Toolpaths voorbereiden..." },
      { target: 68, text: "G-code genereren..." },
      { target: 88, text: "Finaliseren..." },
    ];
    let phaseIdx = 0;
    let currentPct = 0;
    setProgressText(phases[0].text);
    progressIntervalRef.current = setInterval(() => {
      const phase = phases[phaseIdx];
      if (!phase) return;
      const gap = phase.target - currentPct;
      const step = Math.max(1, Math.round(gap * 0.18)); // ease toward target
      currentPct = Math.min(phase.target, currentPct + step);
      setProgress(currentPct);
      if (currentPct >= phase.target) {
        phaseIdx++;
        if (phases[phaseIdx]) setProgressText(phases[phaseIdx].text);
      }
    }, 160);

    try {
      const orientEuler =
        manualEuler.length === 3 && manualEuler.some(v => Math.abs(v) > 0.5)
          ? manualEuler
          : applyOrientation && analysis?.orientation?.should_rotate
            ? analysis.orientation.recommended.rotation_euler_deg
            : [];
      const blob = await apiConvertDownload(
        jobId, selectedPrinter, selectedFilament, nozzleSize, nozzleType, 1.75, buildPlate, flushVolume,
        colorCount,
        slotColors.slice(0, colorCount),
        slotFilaments.slice(0, colorCount),
        orientEuler,
        scalePct / 100,
        fuzzySkin,
        fuzzyThickness,
        fuzzyDist,
      );
      if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
      setProgress(100);
      setProgressText("Klaar!");
      // Persist last-used settings for "Reuse" feature
      localStorage.setItem("autoslice_last_settings", JSON.stringify({
        selectedPrinter, selectedFilament, nozzleSize, nozzleType,
        buildPlate, flushVolume, multiColorMode, dualUnit,
      }));
      const elapsed = conversionStart ? Math.round((Date.now() - conversionStart) / 1000) : null;
      setConversionTime(elapsed);
      setResultSize(blob.size);

      const url = URL.createObjectURL(blob);
      const name = `autoslice_${selectedPrinter}_${selectedFilament}.3mf`;
      setDownloadUrl(url);
      setDownloadName(name);
      setStep("done");
      pushToast("success", "G-code succesvol gegenereerd!");
      const a = document.createElement("a");
      a.href = url;
      a.download = name;
      a.click();
    } catch (e: unknown) {
      if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
      setProgress(0);
      setProgressText("");
      setError(e instanceof Error ? e.message : "Conversion failed");
      setStep("ready");
      pushToast("error", "Conversie mislukt. Probeer opnieuw.");
    }
  }

  function reset() {
    if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
    setStep("idle");
    setUploadedFile(null);
    setJobId(null);
    setAnalysis(null);
    setDownloadUrl(null);
    setError("");
    setFeedbackSent(false);
    setFeedbackLoading(false);
    setRatingGiven(0);
    setRatingDone(false);
    setRatingLoading(false);
    setApplyOrientation(false);
    setShowSupports(false);
    setManualEuler([]);
    setProgress(0);
    setProgressText("");
    setConversionStart(null);
    setConversionTime(null);
    setResultSize(null);
  }

  function applyPresetValues(p: Record<string, unknown>) {
    if (p.selectedPrinter) handlePrinterChange(p.selectedPrinter as string);
    if (p.selectedFilament) setSelectedFilament(p.selectedFilament as string);
    if (p.nozzleSize !== undefined) setNozzleSize(p.nozzleSize as number);
    if (p.nozzleType) setNozzleType(p.nozzleType as string);
    if (p.buildPlate) setBuildPlate(p.buildPlate as string);
    if (p.flushVolume !== undefined) setFlushVolume(p.flushVolume as number);
    if (p.multiColorMode) handleMultiColorMode(p.multiColorMode as "none" | "ace_pro" | "ace_pro2");
    if (p.scalePct !== undefined) setScalePct(p.scalePct as number);
    if (p.fuzzySkin) setFuzzySkin(p.fuzzySkin as "none" | "outer" | "all" | "allwalls");
    if (p.fuzzyThickness !== undefined) setFuzzyThickness(p.fuzzyThickness as number);
    if (p.fuzzyDist !== undefined) setFuzzyDist(p.fuzzyDist as number);
  }

  function savePreset(name: string) {
    const trimmed = name.trim();
    if (!trimmed) return;
    const preset = {
      selectedPrinter, selectedFilament, nozzleSize, nozzleType,
      buildPlate, flushVolume, multiColorMode, dualUnit,
      scalePct, fuzzySkin, fuzzyThickness, fuzzyDist,
    };
    const next = { ...presets, [trimmed]: preset };
    setPresets(next);
    localStorage.setItem("autoslice_presets", JSON.stringify(next));
    setPresetName("");
    setShowPresetInput(false);
    pushToast("success", `Preset "${trimmed}" opgeslagen`);
  }

  function loadPreset(name: string) {
    const p = presets[name] as Record<string, unknown> | undefined;
    if (!p) return;
    applyPresetValues(p);
    setLastUsedPreset(name);
    localStorage.setItem("autoslice_preset_last_used", name);
    setShowPresetsMenu(false);
    pushToast("info", `Preset "${name}" geladen`);
  }

  function deletePreset(name: string) {
    const next = { ...presets };
    delete next[name];
    setPresets(next);
    localStorage.setItem("autoslice_presets", JSON.stringify(next));
    if (defaultPreset === name) {
      setDefaultPreset(null);
      localStorage.removeItem("autoslice_preset_default");
    }
    if (lastUsedPreset === name) {
      setLastUsedPreset(null);
      localStorage.removeItem("autoslice_preset_last_used");
    }
    setConfirmDeletePreset(null);
    pushToast("info", `Preset "${name}" verwijderd`);
  }

  function renamePreset(oldName: string, newName: string) {
    const trimmed = newName.trim();
    if (!trimmed || trimmed === oldName) { setRenamingPreset(null); setRenameValue(""); return; }
    const next: Record<string, object> = {};
    for (const k of Object.keys(presets)) {
      next[k === oldName ? trimmed : k] = presets[k];
    }
    setPresets(next);
    localStorage.setItem("autoslice_presets", JSON.stringify(next));
    if (defaultPreset === oldName) {
      setDefaultPreset(trimmed);
      localStorage.setItem("autoslice_preset_default", trimmed);
    }
    if (lastUsedPreset === oldName) {
      setLastUsedPreset(trimmed);
      localStorage.setItem("autoslice_preset_last_used", trimmed);
    }
    setRenamingPreset(null);
    setRenameValue("");
    pushToast("success", `Preset hernoemd naar "${trimmed}"`);
  }

  function toggleDefaultPreset(name: string) {
    if (defaultPreset === name) {
      setDefaultPreset(null);
      localStorage.removeItem("autoslice_preset_default");
    } else {
      setDefaultPreset(name);
      localStorage.setItem("autoslice_preset_default", name);
    }
  }

  function exportPresets() {
    const blob = new Blob([JSON.stringify(presets, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "autoslice-presets.json";
    a.click();
    URL.revokeObjectURL(url);
    pushToast("success", "Presets geëxporteerd");
  }

  function importPresets(file: File) {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const data = JSON.parse(e.target?.result as string) as Record<string, object>;
        if (typeof data !== "object" || Array.isArray(data)) throw new Error();
        const merged = { ...presets, ...data };
        setPresets(merged);
        localStorage.setItem("autoslice_presets", JSON.stringify(merged));
        pushToast("success", `${Object.keys(data).length} preset(s) geïmporteerd`);
      } catch {
        pushToast("error", "Ongeldig bestand. Gebruik een geldig autoslice-presets.json");
      }
    };
    reader.readAsText(file);
  }

  function reuseLastSettings() {
    try {
      const raw = localStorage.getItem("autoslice_last_settings");
      if (!raw) return;
      applyPresetValues(JSON.parse(raw) as Record<string, unknown>);
      pushToast("info", "Vorige instellingen geladen");
    } catch { /* ignore */ }
  }

  const hasLastSettings = typeof window !== "undefined" && !!localStorage.getItem("autoslice_last_settings");

  async function submitRating(stars: number) {
    if (!jobId || ratingDone) return;
    setRatingGiven(stars);
    setRatingLoading(true);
    try {
      await apiPost("/ratings", { job_id: jobId, stars }, true);
      setRatingDone(true);
    } catch {
      setRatingDone(true);
    } finally {
      setRatingLoading(false);
    }
  }

  async function sendFeedback(outcome: string) {
    if (!jobId || feedbackSent) return;
    setFeedbackLoading(true);
    try {
      await apiPost("/feedback", { job_id: jobId, outcome }, true);
      setFeedbackSent(true);
    } catch {
      setFeedbackSent(true);
    } finally {
      setFeedbackLoading(false);
    }
  }

  const isWorking = step === "uploading" || step === "analyzing" || step === "converting";
  const settingsDisabled = isWorking;
  const aceName = multiColorMode === "ace_pro" ? "ACE Pro" : "ACE Pro 2";

  return (
    <main className="px-8 py-7 max-w-[1200px] mx-auto">

      {/* ── Page header ── */}
      <div className="flex items-center gap-4 pb-6 border-b border-white/[0.07] mb-6">
        <div className="w-10 h-10 rounded-xl bg-brand/[0.12] border border-brand/[0.25] flex items-center justify-center shrink-0
                        shadow-[0_0_20px_rgba(224,36,36,0.2)]">
          <svg className="w-5 h-5 text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </div>
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight">{t("conv_title")}</h1>
          <p className="text-sm text-zinc-500 mt-0.5">{t("conv_subtitle")}</p>
        </div>
      </div>

      {/* ── Step indicators ── */}
      <div className="flex items-center gap-1 mb-6">
        {([
          { n: 1, label: "Instellingen", done: true },
          { n: 2, label: "Bestand",      done: step !== "idle" },
          { n: 3, label: "Genereren",    done: step === "done" },
        ] as { n: number; label: string; done: boolean }[]).map(({ n, label, done }, i) => (
          <div key={n} className="flex items-center gap-1">
            <div className={`flex items-center gap-2 px-3 py-1 rounded-full text-[11px] font-semibold transition-all duration-300 ${
              done
                ? "bg-brand/[0.15] border border-brand/40 text-brand"
                : "bg-white/[0.04] border border-white/[0.07] text-zinc-600"
            }`}>
              <span className={`w-4 h-4 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 ${
                done ? "bg-brand text-white" : "bg-white/[0.08] text-zinc-600"
              }`}>{n}</span>
              {label}
            </div>
            {i < 2 && (
              <svg className="w-3 h-3 text-zinc-700 mx-0.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7"/>
              </svg>
            )}
          </div>
        ))}
      </div>

      {/* ── Error card ── */}
      {error && (
        <div className="mb-5 bg-red-500/[0.07] border border-red-500/25 rounded-2xl p-4 flex items-start gap-3">
          <div className="w-8 h-8 rounded-lg bg-red-500/15 flex items-center justify-center shrink-0">
            <svg className="w-4 h-4 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
            </svg>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-red-400 mb-0.5">Conversie mislukt</p>
            <p className="text-xs text-zinc-500 leading-relaxed">{error}</p>
          </div>
          <button onClick={() => setError("")} className="text-zinc-600 hover:text-zinc-300 transition-colors shrink-0">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>
      )}

      {/* ── Preset manager ── */}
      <div className="flex items-center gap-2 mb-4" ref={presetsMenuRef}>

        {/* Trigger button */}
        <div className="relative">
          <button
            onClick={() => { if (!settingsDisabled) setShowPresetsMenu((v) => !v); }}
            disabled={settingsDisabled}
            className="flex items-center gap-2 h-8 px-3 bg-white/[0.04] border border-white/[0.08]
                       rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.07]
                       text-[11px] font-medium transition-all disabled:opacity-40"
          >
            <svg className="w-3 h-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01"/>
            </svg>
            Presets
            {Object.keys(presets).length > 0 && (
              <span className="text-[9px] bg-brand/20 text-brand px-1.5 py-0.5 rounded-full font-bold leading-none">
                {Object.keys(presets).length}
              </span>
            )}
            <svg className={`w-3 h-3 shrink-0 transition-transform duration-150 ${showPresetsMenu ? "rotate-180" : ""}`}
              fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7"/>
            </svg>
          </button>

          {/* Dropdown panel */}
          {showPresetsMenu && (
            <div className="absolute left-0 top-full mt-1.5 w-[300px] z-50
                            bg-[#0e0e14] border border-white/[0.09] rounded-2xl overflow-hidden
                            shadow-[0_16px_48px_rgba(0,0,0,0.65)] collapse-enter">

              {/* Header */}
              <div className="flex items-center justify-between px-4 pt-3.5 pb-2.5 border-b border-white/[0.06]">
                <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-[0.14em]">Presets</span>
                <button onClick={() => setShowPresetsMenu(false)}
                  className="text-zinc-700 hover:text-zinc-400 transition-colors">
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12"/>
                  </svg>
                </button>
              </div>

              {/* Preset rows */}
              {Object.keys(presets).length === 0 ? (
                <p className="px-4 py-4 text-[11px] text-zinc-600 italic">Nog geen presets opgeslagen.</p>
              ) : (
                <div className="max-h-[200px] overflow-y-auto py-1">
                  {Object.keys(presets).map((name) => (
                    <div key={name}
                      className="flex items-center gap-1.5 px-2.5 py-1.5 hover:bg-white/[0.03] transition-colors group">

                      {/* Star = default */}
                      <button onClick={() => toggleDefaultPreset(name)}
                        title={defaultPreset === name ? "Standaard (klik om te verwijderen)" : "Instellen als standaard"}
                        className={`shrink-0 w-6 h-6 flex items-center justify-center rounded transition-colors
                                    ${defaultPreset === name ? "text-yellow-400" : "text-zinc-700 hover:text-yellow-500"}`}>
                        <svg className="w-3.5 h-3.5" fill={defaultPreset === name ? "currentColor" : "none"} stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                            d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"/>
                        </svg>
                      </button>

                      {/* Name or rename input */}
                      {renamingPreset === name ? (
                        <input autoFocus type="text" value={renameValue}
                          onChange={(e) => setRenameValue(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") renamePreset(name, renameValue);
                            if (e.key === "Escape") { setRenamingPreset(null); setRenameValue(""); }
                          }}
                          onBlur={() => renamePreset(name, renameValue)}
                          className="flex-1 h-6 px-2 bg-white/[0.07] border border-brand/40 rounded
                                     text-white text-[11px] focus:outline-none focus:border-brand/70"
                        />
                      ) : (
                        <div className="flex-1 flex items-center gap-1.5 min-w-0">
                          <span className="text-[12px] text-zinc-200 font-medium truncate">{name}</span>
                          {lastUsedPreset === name && (
                            <span className="text-[9px] text-zinc-600 bg-white/[0.04] px-1.5 py-0.5 rounded-full shrink-0 leading-none">
                              laatste
                            </span>
                          )}
                        </div>
                      )}

                      {/* Actions */}
                      {renamingPreset !== name && (
                        <div className="flex items-center gap-0.5 shrink-0">
                          <button onClick={() => loadPreset(name)}
                            className="h-6 px-2 rounded text-[10px] font-semibold text-brand/70
                                       hover:text-brand hover:bg-brand/[0.12] transition-colors">
                            Laden
                          </button>
                          <button onClick={() => { setRenamingPreset(name); setRenameValue(name); }}
                            title="Hernoemen"
                            className="w-6 h-6 flex items-center justify-center rounded
                                       text-zinc-700 hover:text-zinc-300 hover:bg-white/[0.06] transition-colors">
                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
                            </svg>
                          </button>
                          {confirmDeletePreset === name ? (
                            <div className="flex items-center gap-1 px-1">
                              <button onClick={() => deletePreset(name)}
                                className="text-[10px] font-bold text-red-400 hover:text-red-300 transition-colors">Ja</button>
                              <button onClick={() => setConfirmDeletePreset(null)}
                                className="text-[10px] text-zinc-600 hover:text-zinc-400 transition-colors">Nee</button>
                            </div>
                          ) : (
                            <button onClick={() => setConfirmDeletePreset(name)}
                              title="Verwijderen"
                              className="w-6 h-6 flex items-center justify-center rounded
                                         text-zinc-700 hover:text-red-400 hover:bg-red-500/[0.08] transition-colors">
                              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                  d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                              </svg>
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Save new preset */}
              <div className="px-3 py-2.5 border-t border-white/[0.06]">
                {showPresetInput ? (
                  <div className="flex items-center gap-1.5">
                    <input autoFocus type="text" value={presetName}
                      onChange={(e) => setPresetName(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") savePreset(presetName);
                        if (e.key === "Escape") { setShowPresetInput(false); setPresetName(""); }
                      }}
                      placeholder="Naam preset…"
                      className="flex-1 h-7 px-2.5 bg-white/[0.05] border border-brand/40 rounded-lg
                                 text-white text-[11px] focus:outline-none focus:border-brand/70"
                    />
                    <button onClick={() => savePreset(presetName)}
                      className="h-7 px-3 bg-brand/[0.18] border border-brand/40 rounded-lg
                                 text-brand text-[11px] font-semibold hover:bg-brand/[0.28] transition-colors">
                      Opslaan
                    </button>
                    <button onClick={() => { setShowPresetInput(false); setPresetName(""); }}
                      className="text-zinc-600 hover:text-zinc-300 transition-colors text-base leading-none px-1">×</button>
                  </div>
                ) : (
                  <button onClick={() => setShowPresetInput(true)}
                    className="flex items-center gap-1.5 w-full h-7 px-2 rounded-lg text-[11px] font-medium
                               text-zinc-500 hover:text-zinc-200 hover:bg-white/[0.05] transition-all">
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4"/>
                    </svg>
                    Opslaan als nieuwe preset
                  </button>
                )}
              </div>

              {/* Import / Export / Last settings */}
              <div className="px-3 pb-3 pt-1 border-t border-white/[0.06] flex flex-col gap-1.5">
                <div className="flex gap-1.5">
                  <input ref={importInputRef} type="file" accept=".json" className="hidden"
                    onChange={(e) => { const f = e.target.files?.[0]; if (f) importPresets(f); e.target.value = ""; }} />
                  <button onClick={() => importInputRef.current?.click()}
                    className="flex-1 flex items-center justify-center gap-1.5 h-7 rounded-lg
                               bg-white/[0.04] hover:bg-white/[0.07] border border-white/[0.07]
                               text-zinc-500 hover:text-zinc-200 text-[11px] font-medium transition-all">
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"/>
                    </svg>
                    Importeren
                  </button>
                  <button onClick={exportPresets} disabled={Object.keys(presets).length === 0}
                    className="flex-1 flex items-center justify-center gap-1.5 h-7 rounded-lg
                               bg-white/[0.04] hover:bg-white/[0.07] border border-white/[0.07]
                               text-zinc-500 hover:text-zinc-200 text-[11px] font-medium transition-all
                               disabled:opacity-40 disabled:cursor-not-allowed">
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
                    </svg>
                    Exporteren
                  </button>
                </div>
                {hasLastSettings && (
                  <button onClick={() => { reuseLastSettings(); setShowPresetsMenu(false); }}
                    className="flex items-center gap-1.5 w-full h-7 px-2 rounded-lg text-[11px] font-medium
                               text-zinc-500 hover:text-zinc-200 hover:bg-white/[0.05] transition-all">
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
                    </svg>
                    Vorige instellingen laden
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ══════════════════════════════════════════════════════
          PRINTER SETTINGS CARD
      ══════════════════════════════════════════════════════ */}
      <div className="bg-surface-card border border-white/[0.07] rounded-2xl mb-4 overflow-hidden
                      shadow-[0_4px_24px_rgba(0,0,0,0.4),0_0_0_1px_rgba(255,255,255,0.02)]">

        {/* Card header */}
        <div className="px-6 py-[14px] border-b border-white/[0.07] flex items-center gap-3
                        bg-gradient-to-r from-white/[0.02] to-transparent">
          <div className="w-7 h-7 rounded-lg bg-brand/15 border border-brand/[0.2] flex items-center justify-center shrink-0">
            <svg className="w-3.5 h-3.5 text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </div>
          <span className="text-[11px] font-bold text-zinc-300 uppercase tracking-[0.14em]">
            {t("conv_settings")}
          </span>
        </div>

        <div className="px-6 py-5 space-y-4">

          {/* Row 1 — 3 columns: Printer · Filamenttype · Laaghoogte */}
          <div className="grid grid-cols-3 gap-4">

            {/* Printer */}
            <div>
              <label className="block text-[10px] font-semibold text-zinc-500 uppercase tracking-[0.12em] mb-2">
                {t("conv_printer")}
              </label>
              <div className="relative">
                <div className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-600 pointer-events-none">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8}
                      d="M17 17H7a2 2 0 01-2-2V9a2 2 0 012-2h10a2 2 0 012 2v6a2 2 0 01-2 2zM5 9V7a2 2 0 012-2h10a2 2 0 012 2v2M7 13h.01M10 13h.01" />
                  </svg>
                </div>
                <select value={selectedPrinter} onChange={(e) => handlePrinterChange(e.target.value)}
                  disabled={settingsDisabled} className={SEL}>
                  {printers.map((p) => (
                    <option key={p.id} value={p.id}>{p.display_name}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Filamenttype */}
            <div>
              <label className="block text-[10px] font-semibold text-zinc-500 uppercase tracking-[0.12em] mb-2">
                {t("conv_filament")}
              </label>
              <div className="relative">
                <div className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-600 pointer-events-none">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <circle cx="12" cy="12" r="4" strokeWidth={1.8}/>
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8}
                      d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/>
                  </svg>
                </div>
                <select value={selectedFilament}
                  onChange={(e) => {
                    setSelectedFilament(e.target.value);
                    setSlotFilaments(prev => { const a = [...prev]; a[0] = e.target.value; return a; });
                  }}
                  disabled={settingsDisabled} className={SEL}>
                  {availableFilaments.map((f) => (
                    <option key={f} value={f}>{FILAMENT_LABELS[f] ?? f.toUpperCase()}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Laaghoogte */}
            <div>
              <label className="block text-[10px] font-semibold text-zinc-500 uppercase tracking-[0.12em] mb-2">
                {t("conv_nozzle_size")}
              </label>
              <div className="relative">
                <div className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-600 pointer-events-none">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8}
                      d="M4 6h16M4 10h16M4 14h10M4 18h6"/>
                  </svg>
                </div>
                <select value={nozzleSize} onChange={(e) => setNozzleSize(parseFloat(e.target.value))}
                  disabled={settingsDisabled} className={SEL}>
                  {NOZZLE_SIZES.map((n) => (
                    <option key={n.value} value={n.value}>{n.label}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Row 2 — 4 columns: Spuitstuktype · Filamentdiameter · Bouwplaat · Spoelvolume */}
          <div className="grid grid-cols-4 gap-4">

            {/* Spuitstuktype */}
            <div>
              <label className="block text-[10px] font-semibold text-zinc-500 uppercase tracking-[0.12em] mb-2">
                {t("conv_nozzle_type")}
              </label>
              <div className="relative">
                <div className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-600 pointer-events-none">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8}
                      d="M9 3h6l2 6-4 2-4-2 2-6zm0 0L7 9m10-6l2 6M12 11v10M9 21h6"/>
                  </svg>
                </div>
                <select value={nozzleType} onChange={(e) => setNozzleType(e.target.value)}
                  disabled={settingsDisabled} className={SEL}>
                  {NOZZLE_TYPES.map((n) => (
                    <option key={n.value} value={n.value}>{n.label}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Filamentdiameter — static */}
            <div>
              <label className="block text-[10px] font-semibold text-zinc-500 uppercase tracking-[0.12em] mb-2">
                {t("conv_diameter")}
              </label>
              <div className="relative">
                <div className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-600 pointer-events-none">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <circle cx="12" cy="12" r="3" strokeWidth={1.8}/>
                    <circle cx="12" cy="12" r="8" strokeWidth={1.8} strokeDasharray="2 3"/>
                  </svg>
                </div>
                <div className="w-full h-10 pl-9 pr-3 flex items-center bg-white/[0.03] border border-white/[0.06]
                                rounded-xl text-sm text-zinc-500 cursor-not-allowed select-none">
                  1.75 mm
                </div>
              </div>
            </div>

            {/* Bouwplaat */}
            <div>
              <label className="block text-[10px] font-semibold text-zinc-500 uppercase tracking-[0.12em] mb-2">
                {t("conv_plate")}
              </label>
              <div className="relative">
                <div className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-600 pointer-events-none">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <rect x="3" y="14" width="18" height="4" rx="1" strokeWidth={1.8}/>
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8}
                      d="M7 14V10m4 4V8m4 6V6"/>
                  </svg>
                </div>
                <select value={buildPlate} onChange={(e) => setBuildPlate(e.target.value)}
                  disabled={settingsDisabled} className={SEL}>
                  {BUILD_PLATES.map((b) => (
                    <option key={b.value} value={b.value}>{b.label}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Spoelvolume */}
            <div>
              <label className="block text-[10px] font-semibold text-zinc-500 uppercase tracking-[0.12em] mb-2">
                {t("conv_flush")}
              </label>
              <div className="relative">
                <div className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-600 pointer-events-none">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8}
                      d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                  </svg>
                </div>
                <input type="number" min={0} max={50} step={0.5} value={flushVolume}
                  onChange={(e) => setFlushVolume(parseFloat(e.target.value) || 0)}
                  disabled={settingsDisabled}
                  className="w-full h-10 pl-9 pr-3 bg-white/[0.05] border border-white/[0.09] rounded-xl text-white text-sm
                             focus:outline-none focus:border-brand/50 focus:bg-white/[0.07] transition-all duration-150
                             disabled:opacity-50 disabled:cursor-not-allowed" />
              </div>
            </div>
          </div>

          {/* Row 3 — Scale · Fuzzy skin */}
          <div className="grid grid-cols-4 gap-4 pt-1">

            {/* Schaal */}
            <div>
              <label className="block text-[10px] font-semibold text-zinc-500 uppercase tracking-[0.12em] mb-2">
                Schaal (%)
              </label>
              <div className="relative">
                <div className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-600 pointer-events-none">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8}
                      d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"/>
                  </svg>
                </div>
                <input type="number" min={10} max={500} step={1} value={scalePct}
                  onChange={(e) => setScalePct(Math.max(10, Math.min(500, parseFloat(e.target.value) || 100)))}
                  disabled={settingsDisabled}
                  className="w-full h-10 pl-9 pr-3 bg-white/[0.05] border border-white/[0.09] rounded-xl text-white text-sm
                             focus:outline-none focus:border-brand/50 focus:bg-white/[0.07] transition-all duration-150
                             disabled:opacity-50 disabled:cursor-not-allowed" />
              </div>
            </div>

            {/* Fuzzy skin modus */}
            <div>
              <label className="block text-[10px] font-semibold text-zinc-500 uppercase tracking-[0.12em] mb-2">
                Fuzzy skin
              </label>
              <div className="relative">
                <div className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-600 pointer-events-none">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8}
                      d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01"/>
                  </svg>
                </div>
                <select value={fuzzySkin} onChange={(e) => setFuzzySkin(e.target.value as "none" | "outer" | "all" | "allwalls")}
                  disabled={settingsDisabled} className={SEL}>
                  <option value="none">Uit</option>
                  <option value="outer">Buitenwand</option>
                  <option value="all">Alle wanden</option>
                  <option value="allwalls">Alle + infill</option>
                </select>
              </div>
            </div>

            {/* Fuzzy dikte */}
            <div className={fuzzySkin === "none" ? "opacity-40 pointer-events-none" : ""}>
              <label className="block text-[10px] font-semibold text-zinc-500 uppercase tracking-[0.12em] mb-2">
                Fuzzy dikte (mm)
              </label>
              <div className="relative">
                <div className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-600 pointer-events-none">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M4 12h16M4 6h16M4 18h7"/>
                  </svg>
                </div>
                <input type="number" min={0.1} max={2} step={0.05} value={fuzzyThickness}
                  onChange={(e) => setFuzzyThickness(parseFloat(e.target.value) || 0.3)}
                  disabled={settingsDisabled}
                  className="w-full h-10 pl-9 pr-3 bg-white/[0.05] border border-white/[0.09] rounded-xl text-white text-sm
                             focus:outline-none focus:border-brand/50 focus:bg-white/[0.07] transition-all duration-150
                             disabled:opacity-50 disabled:cursor-not-allowed" />
              </div>
            </div>

            {/* Fuzzy punt-afstand */}
            <div className={fuzzySkin === "none" ? "opacity-40 pointer-events-none" : ""}>
              <label className="block text-[10px] font-semibold text-zinc-500 uppercase tracking-[0.12em] mb-2">
                Fuzzy puntafstand (mm)
              </label>
              <div className="relative">
                <div className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-600 pointer-events-none">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <circle cx="5" cy="12" r="1.5" strokeWidth={1.8}/>
                    <circle cx="12" cy="12" r="1.5" strokeWidth={1.8}/>
                    <circle cx="19" cy="12" r="1.5" strokeWidth={1.8}/>
                  </svg>
                </div>
                <input type="number" min={0.2} max={5} step={0.1} value={fuzzyDist}
                  onChange={(e) => setFuzzyDist(parseFloat(e.target.value) || 0.8)}
                  disabled={settingsDisabled}
                  className="w-full h-10 pl-9 pr-3 bg-white/[0.05] border border-white/[0.09] rounded-xl text-white text-sm
                             focus:outline-none focus:border-brand/50 focus:bg-white/[0.07] transition-all duration-150
                             disabled:opacity-50 disabled:cursor-not-allowed" />
              </div>
            </div>

          </div>
        </div>
      </div>

      {/* ══════════════════════════════════════════════════════
          MULTI-COLOR SETTINGS CARD
      ══════════════════════════════════════════════════════ */}
      <div className="bg-surface-card border border-white/[0.07] rounded-2xl mb-4
                      shadow-[0_4px_24px_rgba(0,0,0,0.4),0_0_0_1px_rgba(255,255,255,0.02)]">

        {/* Card header */}
        <div className="px-6 py-[14px] border-b border-white/[0.07] flex items-center gap-3
                        bg-gradient-to-r from-white/[0.02] to-transparent rounded-t-2xl">
          <div className="w-7 h-7 rounded-lg bg-brand/15 border border-brand/[0.2] flex items-center justify-center shrink-0">
            <svg className="w-3.5 h-3.5 text-brand" viewBox="0 0 24 24" fill="currentColor">
              <circle cx="6"  cy="6"  r="3.2"/>
              <circle cx="18" cy="6"  r="3.2"/>
              <circle cx="6"  cy="18" r="3.2"/>
              <circle cx="18" cy="18" r="3.2"/>
            </svg>
          </div>
          <span className="text-[11px] font-bold text-zinc-300 uppercase tracking-[0.14em]">
            {t("conv_multicolor")}
          </span>

          {/* Toggle + label — right side */}
          <div className="ml-auto flex items-center gap-3">
            <span className="text-sm text-zinc-400">
              {multiColorMode !== "none"
                ? `${aceName} ingeschakeld (${colorCount} slots)`
                : "Uitgeschakeld"}
            </span>
            <button
              type="button"
              onClick={() => {
                if (multiColorMode !== "none") handleMultiColorMode("none");
                else handleMultiColorMode("ace_pro");
              }}
              disabled={settingsDisabled}
              className={`relative w-11 h-6 rounded-full shrink-0 transition-all duration-200 disabled:opacity-40 ${
                multiColorMode !== "none"
                  ? "bg-brand shadow-[0_0_14px_rgba(224,36,36,0.45)]"
                  : "bg-white/[0.12]"
              }`}
            >
              <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow-sm
                                transition-transform duration-200 ${
                multiColorMode !== "none" ? "translate-x-5" : "translate-x-0"
              }`} />
            </button>
          </div>
        </div>

        <div className="px-6 py-5">

          {/* Mode selection tabs */}
          <div className="grid grid-cols-3 gap-3 mb-5">

            {/* Enkel */}
            <button
              onClick={() => handleMultiColorMode("none")}
              disabled={settingsDisabled}
              className={`flex items-center gap-3 px-4 py-3.5 rounded-xl border text-left transition-all duration-150 disabled:opacity-50 ${
                multiColorMode === "none"
                  ? "bg-brand/[0.16] border-brand/50 shadow-[0_0_20px_rgba(224,36,36,0.14)]"
                  : "bg-white/[0.03] border-white/[0.07] hover:border-white/[0.15]"
              }`}
            >
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${
                multiColorMode === "none" ? "bg-brand/20" : "bg-white/[0.06]"
              }`}>
                <svg className={`w-4 h-4 ${multiColorMode === "none" ? "text-brand" : "text-zinc-500"}`}
                  fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h8M4 18h6"/>
                </svg>
              </div>
              <div>
                <p className={`text-sm font-semibold leading-tight ${multiColorMode === "none" ? "text-white" : "text-zinc-400"}`}>
                  {t("conv_single")}
                </p>
                <p className="text-[11px] text-zinc-600 mt-0.5">Één kleur</p>
              </div>
            </button>

            {/* ACE Pro */}
            <button
              onClick={() => handleMultiColorMode("ace_pro")}
              disabled={settingsDisabled}
              className={`flex items-center gap-3 px-4 py-3.5 rounded-xl border text-left transition-all duration-150 disabled:opacity-50 ${
                multiColorMode === "ace_pro"
                  ? "bg-brand/[0.16] border-brand/50 shadow-[0_0_20px_rgba(224,36,36,0.14)]"
                  : "bg-white/[0.03] border-white/[0.07] hover:border-white/[0.15]"
              }`}
            >
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${
                multiColorMode === "ace_pro" ? "bg-brand/20" : "bg-white/[0.06]"
              }`}>
                <svg className={`w-4 h-4 ${multiColorMode === "ace_pro" ? "text-brand" : "text-zinc-500"}`}
                  fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M5 3l1.5 4.5L12 5l5.5 2.5L19 3M5 3L3 12l9 9 9-9-2-9M12 5v16"/>
                </svg>
              </div>
              <div>
                <p className={`text-sm font-semibold leading-tight ${multiColorMode === "ace_pro" ? "text-white" : "text-zinc-400"}`}>
                  ACE Pro
                </p>
                <p className="text-[11px] text-zinc-600 mt-0.5">4 kleurenloten</p>
              </div>
            </button>

            {/* ACE Pro 2 */}
            <button
              onClick={() => handleMultiColorMode("ace_pro2")}
              disabled={settingsDisabled}
              className={`flex items-center gap-3 px-4 py-3.5 rounded-xl border text-left transition-all duration-150 disabled:opacity-50 ${
                multiColorMode === "ace_pro2"
                  ? "bg-brand/[0.16] border-brand/50 shadow-[0_0_20px_rgba(224,36,36,0.14)]"
                  : "bg-white/[0.03] border-white/[0.07] hover:border-white/[0.15]"
              }`}
            >
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${
                multiColorMode === "ace_pro2" ? "bg-brand/20" : "bg-white/[0.06]"
              }`}>
                <svg className={`w-4 h-4 ${multiColorMode === "ace_pro2" ? "text-brand" : "text-zinc-500"}`}
                  fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <circle cx="12" cy="12" r="9" strokeWidth={2}/>
                  <circle cx="12" cy="12" r="4" strokeWidth={2}/>
                </svg>
              </div>
              <div>
                <p className={`text-sm font-semibold leading-tight ${multiColorMode === "ace_pro2" ? "text-white" : "text-zinc-400"}`}>
                  ACE Pro 2
                </p>
                <p className="text-[11px] text-zinc-600 mt-0.5">4 kleurentorens</p>
              </div>
            </button>
          </div>

          {/* Dual unit toggle */}
          {multiColorMode !== "none" && (
            <label className="flex items-center gap-2 mb-4 cursor-pointer select-none w-fit">
              <input
                type="checkbox"
                checked={dualUnit}
                onChange={(e) => handleDualUnit(e.target.checked)}
                disabled={settingsDisabled}
                className="w-3.5 h-3.5 accent-brand cursor-pointer"
              />
              <span className="text-xs text-zinc-500">
                {t("conv_add_second")} {aceName}
                <span className="ml-1.5 text-zinc-600">{t("conv_8slots")}</span>
              </span>
            </label>
          )}

          {/* Color slots */}
          {multiColorMode !== "none" ? (
            <>
              {dualUnit && (
                <p className="text-[10px] font-semibold text-zinc-600 uppercase tracking-widest mb-2.5">
                  {t("conv_unit1")}
                </p>
              )}
              <div className="grid grid-cols-4 gap-3">
                {Array.from({ length: Math.min(colorCount, 4) }, (_, i) => (
                  <ColorSlot key={i} index={i} slotColors={slotColors} setSlotColors={setSlotColors}
                    slotFilaments={slotFilaments} setSlotFilaments={setSlotFilaments}
                    availableFilaments={availableFilaments} disabled={settingsDisabled} />
                ))}
              </div>
              {dualUnit && colorCount === 8 && (
                <>
                  <p className="text-[10px] font-semibold text-zinc-600 uppercase tracking-widest mt-5 mb-2.5">
                    {t("conv_unit2")}
                  </p>
                  <div className="grid grid-cols-4 gap-3">
                    {Array.from({ length: 4 }, (_, i) => (
                      <ColorSlot key={i + 4} index={i + 4} slotColors={slotColors} setSlotColors={setSlotColors}
                        slotFilaments={slotFilaments} setSlotFilaments={setSlotFilaments}
                        availableFilaments={availableFilaments} disabled={settingsDisabled} />
                    ))}
                  </div>
                </>
              )}
            </>
          ) : (
            <p className="text-xs text-zinc-600 italic">{t("conv_multicolor_hint")}</p>
          )}
        </div>
      </div>

      {/* ══════════════════════════════════════════════════════
          UPLOAD AREA
      ══════════════════════════════════════════════════════ */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => !isWorking && step !== "done" && fileInputRef.current?.click()}
        className={[
          "relative rounded-2xl border-2 border-dashed transition-all duration-200 mb-4",
          dragging
            ? "border-brand bg-brand/[0.08] shadow-[0_0_48px_rgba(224,36,36,0.2),0_0_0_1px_rgba(224,36,36,0.18)]"
            : step === "done"
              ? "border-green-700/50 bg-green-950/10 cursor-default"
              : "border-brand/[0.3] bg-surface-card hover:border-brand/[0.55] hover:bg-brand/[0.03] shadow-[0_4px_32px_rgba(0,0,0,0.5)] hover:shadow-[0_0_40px_rgba(224,36,36,0.1)]",
          step === "idle" || step === "ready" ? "cursor-pointer" : "",
          isWorking ? "cursor-not-allowed opacity-70" : "",
        ].join(" ")}
      >
        <input ref={fileInputRef} type="file" accept=".3mf" className="hidden"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }} />

        <div className="flex flex-col items-center justify-center py-16 px-8 text-center">

          {step === "idle" && (
            <>
              <div className={`w-16 h-16 rounded-full flex items-center justify-center mb-5 transition-all duration-200 ${
                dragging
                  ? "bg-brand/25 border border-brand/50 shadow-[0_0_36px_rgba(224,36,36,0.4)]"
                  : "bg-brand/[0.1] border border-brand/[0.25] shadow-[0_0_24px_rgba(224,36,36,0.15)]"
              }`}>
                <svg className={`w-7 h-7 transition-colors ${dragging ? "text-brand" : "text-brand/70"}`}
                  fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8}
                    d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/>
                </svg>
              </div>
              <p className="text-lg font-bold text-white mb-1.5">{t("conv_drop")}</p>
              <p className="text-sm text-zinc-500 mb-5">{t("conv_or_browse")}</p>
              <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full
                               bg-brand/[0.08] border border-brand/[0.22] text-xs text-zinc-300 font-medium">
                <svg className="w-3.5 h-3.5 text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M13 10V3L4 14h7v7l9-11h-7z"/>
                </svg>
                Ondersteunt .3mf bestanden tot 100MB
                <svg className="w-3 h-3 text-zinc-600" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd"/>
                </svg>
              </span>
            </>
          )}

          {(step === "uploading" || step === "analyzing") && (
            <>
              <div className="w-14 h-14 rounded-full border-2 border-brand/30 border-t-brand flex items-center justify-center mb-5 animate-spin" />
              <p className="text-base font-semibold text-white mb-1">
                {step === "uploading" ? t("conv_uploading") : t("conv_analyzing")}
              </p>
              <p className="text-sm text-zinc-500">{uploadedFile?.name}</p>
            </>
          )}

          {(step === "ready" || step === "converting") && uploadedFile && (
            <div className="w-full max-w-md" onClick={(e) => e.stopPropagation()}>
              <div className="bg-white/[0.04] border border-white/[0.09] rounded-2xl p-4 mb-3 text-left">
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-xl bg-brand/10 border border-brand/25 flex items-center justify-center shrink-0">
                    <svg className="w-5 h-5 text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                    </svg>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-white truncate">{uploadedFile.name}</p>
                    <p className="text-xs text-zinc-500 mt-0.5">
                      {uploadedFile.size < 1024 * 1024
                        ? `${(uploadedFile.size / 1024).toFixed(1)} KB`
                        : `${(uploadedFile.size / (1024 * 1024)).toFixed(2)} MB`}
                      {analysis?.geometry && (
                        <> · {analysis.geometry.bounding_box.x_mm}×{analysis.geometry.bounding_box.y_mm}×{analysis.geometry.bounding_box.z_mm} mm</>
                      )}
                      {analysis?.geometry?.part_count && (
                        <> · {analysis.geometry.part_count} {analysis.geometry.part_count === 1 ? "onderdeel" : "onderdelen"}</>
                      )}
                    </p>
                  </div>
                  <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-green-500/10 border border-green-500/20 text-[10px] font-semibold text-green-400 shrink-0">
                    <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                    Ready
                  </span>
                </div>
              </div>
              <button onClick={() => reset()} className="text-xs text-zinc-500 hover:text-brand transition-colors">
                {t("conv_change_file")}
              </button>
            </div>
          )}

          {step === "done" && (
            <>
              <div className="w-14 h-14 rounded-full bg-green-500/10 border border-green-500/30 flex items-center justify-center mb-5
                              shadow-[0_0_24px_rgba(34,197,94,0.15)]">
                <svg className="w-7 h-7 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7"/>
                </svg>
              </div>
              <p className="text-base font-semibold text-green-400">{t("conv_done")}</p>
            </>
          )}
        </div>
      </div>

      {/* ── Conversion progress bar ── */}
      {step === "converting" && (
        <div className="bg-surface-card border border-white/[0.07] rounded-2xl mb-4 px-6 py-4
                        shadow-[0_4px_24px_rgba(0,0,0,0.4)]">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 border-2 border-brand/40 border-t-brand rounded-full animate-spin shrink-0"/>
              <span className="text-sm font-medium text-zinc-300">{progressText || "Verwerken…"}</span>
            </div>
            <div className="flex items-center gap-3">
              {conversionStart && (
                <ElapsedTimer startMs={conversionStart} />
              )}
              <span className="text-sm font-bold text-brand tabular-nums">{progress}%</span>
            </div>
          </div>
          <div className="w-full h-2 bg-white/[0.06] rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-[#e02424] to-[#ff4444]
                         shadow-[0_0_12px_rgba(224,36,36,0.5)] transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {/* ── Result panel (after done) ── */}
      {step === "done" && downloadUrl && (
        <div className="bg-green-500/[0.06] border border-green-500/25 rounded-2xl mb-4 p-5
                        shadow-[0_4px_24px_rgba(0,0,0,0.4)]">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-9 h-9 rounded-xl bg-green-500/15 border border-green-500/25 flex items-center justify-center shrink-0">
              <svg className="w-4.5 h-4.5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" style={{width:18,height:18}}>
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7"/>
              </svg>
            </div>
            <div className="flex-1">
              <p className="text-sm font-bold text-green-400">Conversie geslaagd</p>
              <p className="text-xs text-zinc-500 mt-0.5 truncate">{downloadName}</p>
            </div>
            <div className="flex gap-3 text-right shrink-0">
              {resultSize && (
                <div>
                  <p className="text-[10px] text-zinc-600 uppercase tracking-wider">Bestand</p>
                  <p className="text-xs font-semibold text-zinc-300">
                    {resultSize < 1024*1024 ? `${(resultSize/1024).toFixed(0)} KB` : `${(resultSize/1024/1024).toFixed(2)} MB`}
                  </p>
                </div>
              )}
              {conversionTime !== null && (
                <div>
                  <p className="text-[10px] text-zinc-600 uppercase tracking-wider">Tijd</p>
                  <p className="text-xs font-semibold text-zinc-300">{conversionTime}s</p>
                </div>
              )}
            </div>
          </div>
          <div className="flex gap-2">
            <a href={downloadUrl} download={downloadName}
              className="flex-1 flex items-center justify-center gap-2 h-9 rounded-xl
                         bg-green-500/[0.15] border border-green-500/30 text-green-400
                         text-xs font-semibold hover:bg-green-500/[0.25] transition-colors">
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4 4m0 0l-4-4m4 4V4"/>
              </svg>
              {t("conv_download")}
            </a>
            <button onClick={reset}
              className="flex-1 flex items-center justify-center gap-2 h-9 rounded-xl
                         bg-white/[0.04] border border-white/[0.08] text-zinc-400
                         text-xs font-semibold hover:bg-white/[0.08] hover:text-white transition-colors">
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4"/>
              </svg>
              {t("conv_new")}
            </button>
          </div>
        </div>
      )}

      {/* ── 3D Model Viewer ── */}
      {jobId && (step === "ready" || step === "converting" || step === "done") && (
        <div className="relative bg-surface-card border border-white/[0.07] rounded-2xl overflow-hidden mb-4
                        shadow-[0_0_0_1px_rgba(255,255,255,0.02),0_4px_32px_rgba(0,0,0,0.5)]">
          <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/[0.09] to-transparent" />
          <div className="px-5 py-3.5 border-b border-white/[0.06] flex items-center justify-between
                          bg-gradient-to-r from-white/[0.025] to-transparent">
            <span className="text-xs font-semibold text-zinc-300 uppercase tracking-[0.1em]">3D Preview</span>
            <div className="flex items-center gap-1.5 flex-wrap justify-end">
              {([
                { label: "Default", euler: [] },
                { label: "Flat",    euler: [-90, 0, 0] },
                { label: "Flip",    euler: [180, 0, 0] },
                { label: "Side L",  euler: [0, 0, 90]  },
                { label: "Side R",  euler: [0, 0, -90] },
              ] as { label: string; euler: number[] }[]).map(({ label, euler }) => {
                const isActive = JSON.stringify(manualEuler) === JSON.stringify(euler);
                return (
                  <button key={label} onClick={() => setManualEuler(euler)}
                    className={`px-2 py-0.5 rounded-md text-[10px] font-medium border transition-colors ${
                      isActive
                        ? "bg-brand/20 border-brand/50 text-brand"
                        : "bg-surface-elevated border-surface-border text-zinc-500 hover:text-white hover:border-zinc-500"
                    }`}>
                    {label}
                  </button>
                );
              })}
            </div>
          </div>
          <div className="p-4">
            <ModelViewer jobId={jobId} showSupports={showSupports}
              rotationEuler={manualEuler.length === 3 ? manualEuler : undefined} />
            {analysis?.geometry.overhang.has_overhangs && (
              <label className="flex items-center gap-2 text-sm text-zinc-400 cursor-pointer select-none w-fit mt-3">
                <input type="checkbox" checked={showSupports} onChange={(e) => setShowSupports(e.target.checked)}
                  className="w-4 h-4 rounded accent-orange-500" />
                <span>Show support regions</span>
                {showSupports && analysis.geometry.overhang.overhang_area_ratio > 0 && (
                  <span className="text-xs text-zinc-600">
                    ({(analysis.geometry.overhang.overhang_area_ratio * 100).toFixed(0)}% of surface)
                  </span>
                )}
              </label>
            )}
          </div>
        </div>
      )}

      {/* ── Analysis results ── */}
      {analysis && (
        <div className="relative bg-surface-card border border-white/[0.07] rounded-2xl overflow-hidden mb-4
                        shadow-[0_0_0_1px_rgba(255,255,255,0.02),0_4px_32px_rgba(0,0,0,0.5)]">
          <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/[0.09] to-transparent" />
          <div className="px-5 py-4 border-b border-white/[0.06] bg-gradient-to-r from-white/[0.025] to-transparent">
            <h2 className="text-xs font-semibold text-zinc-300 uppercase tracking-[0.1em]">{t("conv_analysis")}</h2>
          </div>
          <div className="p-5">
            <div className="grid grid-cols-3 sm:grid-cols-6 gap-3 mb-5">
              <Stat label={t("conv_size") + " X"} value={`${analysis.geometry.bounding_box.x_mm} mm`} />
              <Stat label={t("conv_size") + " Y"} value={`${analysis.geometry.bounding_box.y_mm} mm`} />
              <Stat label={t("conv_size") + " Z"} value={`${analysis.geometry.bounding_box.z_mm} mm`} />
              <Stat label="Volume" value={`${analysis.geometry.bounding_box.volume_cm3} cm³`} />
              <Stat label="Parts" value={String(analysis.geometry.part_count)} />
              <Stat label={t("conv_watertight")} value={analysis.geometry.mesh_is_watertight ? t("conv_yes") : t("conv_no")} />
            </div>
            <div className="border-t border-surface-border pt-4 grid grid-cols-3 sm:grid-cols-6 gap-3 mb-5">
              <Badge label={t("conv_difficulty")} value={analysis.intent.difficulty}
                className={difficultyColor[analysis.intent.difficulty] ?? "text-zinc-400"} />
              <Badge label={t("conv_size")} value={analysis.intent.size_class} />
              <Badge label={t("conv_supports")}
                value={analysis.intent.needs_supports ? `Yes (${analysis.intent.support_density_hint})` : t("conv_no")}
                className={analysis.intent.needs_supports ? "text-yellow-400" : "text-green-400"} />
              <Badge label={t("conv_overhangs")}
                value={analysis.geometry.overhang.has_overhangs ? `${analysis.geometry.overhang.max_angle_deg}°` : "None"}
                className={analysis.geometry.overhang.has_overhangs ? "text-yellow-400" : "text-zinc-400"} />
              <Badge label={t("conv_bridges")}
                value={analysis.geometry.bridge.has_bridges ? `${analysis.geometry.bridge.max_span_mm} mm span` : "None"}
                className={analysis.geometry.bridge.has_bridges ? "text-yellow-400" : "text-zinc-400"} />
              <Badge label={t("conv_brim")} value={analysis.intent.needs_brim ? t("conv_brim_rec") : t("conv_brim_no")} />
            </div>
            <div className="border-t border-surface-border pt-4 space-y-2.5">
              <p className="text-[10px] font-semibold text-zinc-500 uppercase tracking-[0.12em] mb-3">{t("conv_risk")}</p>
              <RiskBar label={t("conv_risk_support")}   value={analysis.intent.support_risk} />
              <RiskBar label={t("conv_risk_adhesion")}  value={analysis.intent.adhesion_risk} />
              <RiskBar label={t("conv_risk_stability")} value={analysis.intent.stability_risk} />
              <RiskBar label={t("conv_risk_detail")}    value={analysis.intent.detail_risk} />
            </div>
          </div>
        </div>
      )}

      {analysis?.orientation && (
        <OrientationCard report={analysis.orientation} apply={applyOrientation}
          onToggle={setApplyOrientation} disabled={isWorking} />
      )}
      {analysis?.printability && <PrintabilityCard score={analysis.printability} />}
      {analysis?.explanations && <ExplanationsCard report={analysis.explanations} />}

      {/* Done: download + feedback + rating */}
      {step === "done" && downloadUrl && (
        <div className="space-y-3 mt-4">
          <a href={downloadUrl} download={downloadName}
            className="w-full h-14 rounded-2xl font-bold text-white text-base
                       bg-gradient-to-r from-green-700 to-green-600
                       hover:from-green-600 hover:to-green-500
                       shadow-[0_4px_20px_rgba(34,197,94,0.25)] hover:shadow-[0_6px_32px_rgba(34,197,94,0.35)]
                       hover:-translate-y-0.5 active:translate-y-0 transition-all duration-150
                       flex items-center justify-center gap-3">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l4 4m0 0l4-4m-4 4V4"/>
            </svg>
            {t("conv_download")} {downloadName}
          </a>
          <div className="p-5 bg-surface-card border border-white/[0.07] rounded-2xl
                          shadow-[0_0_0_1px_rgba(255,255,255,0.02),0_4px_24px_rgba(0,0,0,0.4)]">
            {feedbackSent ? (
              <p className="text-center text-sm text-green-400">{t("conv_fb_thanks")}</p>
            ) : (
              <>
                <p className="text-xs text-zinc-500 mb-3 text-center">{t("conv_feedback_q")}</p>
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { outcome: "printed_ok",        label: t("conv_fb_ok"),        color: "text-green-400 border-green-500/30 hover:bg-green-500/10" },
                    { outcome: "supports_unneeded", label: t("conv_fb_sup_excess"), color: "text-yellow-400 border-yellow-500/30 hover:bg-yellow-500/10" },
                    { outcome: "supports_missing",  label: t("conv_fb_sup_miss"),   color: "text-orange-400 border-orange-500/30 hover:bg-orange-500/10" },
                    { outcome: "detached_from_bed", label: t("conv_fb_detach"),     color: "text-red-400 border-red-500/30 hover:bg-red-500/10" },
                    { outcome: "weak_part",         label: t("conv_fb_weak"),       color: "text-orange-400 border-orange-500/30 hover:bg-orange-500/10" },
                    { outcome: "details_lost",      label: t("conv_fb_detail"),     color: "text-blue-400 border-blue-500/30 hover:bg-blue-500/10" },
                  ].map(({ outcome, label, color }) => (
                    <button key={outcome} onClick={() => sendFeedback(outcome)} disabled={feedbackLoading}
                      className={`py-2 px-2 rounded-xl border text-xs font-medium transition-colors disabled:opacity-50 ${color} bg-transparent`}>
                      {label}
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
          <div className="p-5 bg-surface-card border border-white/[0.07] rounded-2xl
                          shadow-[0_0_0_1px_rgba(255,255,255,0.02),0_4px_24px_rgba(0,0,0,0.4)]">
            {ratingDone ? (
              <p className="text-center text-sm text-green-400">{t("rating_thanks")}</p>
            ) : (
              <>
                <p className="text-xs text-zinc-500 mb-3 text-center">{t("rating_title")}</p>
                <div className="flex items-center justify-center gap-2">
                  {[1, 2, 3, 4, 5].map((star) => (
                    <button key={star} onClick={() => submitRating(star)} disabled={ratingLoading}
                      className={`text-2xl transition-transform hover:scale-110 disabled:opacity-50 ${
                        star <= ratingGiven ? "text-yellow-400" : "text-zinc-600 hover:text-yellow-300"
                      }`}>★</button>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* ── Toast container ── */}
      <ToastContainer toasts={toasts} dismiss={dismissToast} />

      {/* ══════════════════════════════════════════════════════
          FOOTER ACTION ROW — sticky
      ══════════════════════════════════════════════════════ */}
      <div className="sticky bottom-0 z-20 -mx-8 px-8 py-4 mt-6
                      bg-[#070709]/90 backdrop-blur-md border-t border-white/[0.06]
                      flex items-center justify-between gap-4">

        {/* Reset button */}
        <button
          onClick={reset}
          className="flex items-center gap-2.5 px-5 h-11 rounded-xl border border-white/[0.1]
                     bg-white/[0.04] hover:bg-white/[0.07] text-zinc-400 hover:text-white
                     text-sm font-medium transition-all duration-150"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
          </svg>
          Instellingen resetten
        </button>

        {/* Generate button */}
        {step === "ready" && (
          <button
            onClick={handleConvert}
            className="flex items-center gap-3 px-8 h-11 rounded-xl font-bold text-white text-sm
                       bg-gradient-to-r from-[#e02424] via-[#d42020] to-[#c41f1f]
                       shadow-[0_4px_24px_rgba(224,36,36,0.5),inset_0_1px_0_rgba(255,255,255,0.1)]
                       hover:shadow-[0_6px_36px_rgba(224,36,36,0.7)] hover:-translate-y-0.5 active:translate-y-0
                       transition-all duration-150"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5}
                d="M13 10V3L4 14h7v7l9-11h-7z"/>
            </svg>
            {t("conv_generate")}
            <svg className="w-4 h-4 opacity-70" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3"/>
            </svg>
          </button>
        )}

        {step === "converting" && (
          <button disabled
            className="flex items-center gap-3 px-8 h-11 rounded-xl font-bold text-white text-sm
                       bg-brand/40 cursor-not-allowed">
            <div className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin"/>
            {progressText || t("conv_generating")}
          </button>
        )}

        {(step === "idle" || step === "uploading" || step === "analyzing") && (
          <button disabled
            className="flex items-center gap-3 px-8 h-11 rounded-xl font-bold text-zinc-600 text-sm
                       bg-white/[0.04] border border-white/[0.07] cursor-not-allowed opacity-50">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13 10V3L4 14h7v7l9-11h-7z"/>
            </svg>
            {step === "idle" ? "Selecteer een bestand" : step === "uploading" ? t("conv_uploading") : t("conv_analyzing")}
          </button>
        )}

        {step === "done" && (
          <button onClick={reset}
            className="flex items-center gap-3 px-8 h-11 rounded-xl font-bold text-white text-sm
                       bg-gradient-to-r from-[#e02424] via-[#d42020] to-[#c41f1f]
                       shadow-[0_4px_24px_rgba(224,36,36,0.5)] hover:shadow-[0_6px_36px_rgba(224,36,36,0.7)]
                       hover:-translate-y-0.5 active:translate-y-0 transition-all duration-150">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4"/>
            </svg>
            {t("conv_new")}
          </button>
        )}
      </div>

    </main>
  );
}

// ── Helper components ──────────────────────────────────────────────────────────

function ElapsedTimer({ startMs }: { startMs: number }) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - startMs) / 1000)), 500);
    return () => clearInterval(id);
  }, [startMs]);
  return <span className="text-xs text-zinc-600 tabular-nums">{elapsed}s</span>;
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-zinc-500 mb-0.5">{label}</p>
      <p className="text-sm font-mono text-white">{value}</p>
    </div>
  );
}

function Badge({ label, value, className = "text-zinc-400" }: { label: string; value: string; className?: string }) {
  return (
    <div>
      <p className="text-xs text-zinc-600 mb-0.5">{label}</p>
      <p className={`text-xs font-medium ${className}`}>{value}</p>
    </div>
  );
}

function SlotSelect({
  value, options, onChange, disabled,
}: {
  value: string;
  options: { value: string; label: string }[];
  onChange: (v: string) => void;
  disabled: boolean;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const selectedLabel = options.find((o) => o.value === value)?.label ?? value.toUpperCase();

  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  function handleKey(e: React.KeyboardEvent) {
    if (disabled) return;
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setOpen((v) => !v); }
    if (e.key === "Escape") setOpen(false);
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const idx = options.findIndex((o) => o.value === value);
      const next = e.key === "ArrowDown"
        ? options[Math.min(idx + 1, options.length - 1)]
        : options[Math.max(idx - 1, 0)];
      if (next) onChange(next.value);
    }
  }

  return (
    <div ref={ref} className="relative w-full" onKeyDown={handleKey}>
      {/* Trigger */}
      <button
        type="button"
        onClick={() => !disabled && setOpen((v) => !v)}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        className="w-full h-7 px-2 flex items-center justify-between rounded-lg text-xs
                   disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none"
        style={{
          WebkitAppearance: "none",
          appearance: "none",
          background: "#1a1a1f",
          border: `1px solid ${open ? "rgba(224,36,36,0.5)" : "rgba(255,255,255,0.1)"}`,
          boxShadow: open ? "0 0 0 3px rgba(224,36,36,0.08)" : undefined,
          color: "#e4e4e8",
        }}
      >
        <span className="truncate" style={{ color: "#e4e4e8" }}>{selectedLabel || "\u00A0"}</span>
        <svg
          className="shrink-0 ml-1 opacity-50"
          style={{ transform: open ? "rotate(180deg)" : undefined, transition: "transform 0.15s" }}
          width="10" height="10" viewBox="0 0 10 10" fill="none"
        >
          <path d="M2 3.5L5 6.5L8 3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </button>

      {/* Dropdown */}
      {open && (
        <div
          role="listbox"
          className="absolute z-[9999] left-0 right-0 mt-1 rounded-lg overflow-hidden py-0.5"
          style={{
            background: "#1a1a1f",
            border: "1px solid rgba(255,255,255,0.1)",
            boxShadow: "0 8px 24px rgba(0,0,0,0.6)",
          }}
        >
          {options.map((o) => (
            <div
              key={o.value}
              role="option"
              aria-selected={o.value === value}
              onMouseDown={(e) => { e.preventDefault(); onChange(o.value); setOpen(false); }}
              className="px-2 py-1.5 text-xs cursor-pointer transition-colors duration-75"
              style={{
                color: o.value === value ? "#ffffff" : "#a1a1aa",
                background: o.value === value ? "rgba(224,36,36,0.15)" : undefined,
              }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.background = "rgba(255,255,255,0.07)"; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.background = o.value === value ? "rgba(224,36,36,0.15)" : ""; }}
            >
              {o.label}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ColorSlot({
  index, slotColors, setSlotColors, slotFilaments, setSlotFilaments, availableFilaments, disabled,
}: {
  index: number;
  slotColors: string[];
  setSlotColors: (v: string[]) => void;
  slotFilaments: string[];
  setSlotFilaments: (v: string[]) => void;
  availableFilaments: string[];
  disabled: boolean;
}) {
  const color = slotColors[index];
  const colorInputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="rounded-2xl border p-3 flex flex-col gap-2.5 select-none"
      style={{
        borderColor: color + "45",
        background: "rgba(10,10,14,0.7)",
        boxShadow: `0 0 16px ${color}18`,
      }}>

      {/* Top: label + dot */}
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-semibold text-zinc-400">Slot {index + 1}</span>
        <div className="w-3 h-3 rounded-full shrink-0"
          style={{ background: color, boxShadow: `0 0 6px ${color}99` }} />
      </div>

      {/* Clickable color bar */}
      <div
        className={`h-9 rounded-xl relative overflow-hidden transition-all duration-150 ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer hover:brightness-110"}`}
        style={{ background: color, boxShadow: `0 2px 14px ${color}55` }}
        onClick={() => !disabled && colorInputRef.current?.click()}
      >
        <input
          ref={colorInputRef}
          type="color"
          value={color}
          onChange={(e) => {
            const next = [...slotColors];
            next[index] = e.target.value;
            setSlotColors(next);
          }}
          disabled={disabled}
          className="absolute opacity-0 w-0 h-0 pointer-events-none"
        />
      </div>

      {/* Filament select */}
      <SlotSelect
        value={slotFilaments[index]}
        options={availableFilaments.map((f) => ({ value: f, label: FILAMENT_LABELS[f] ?? f.toUpperCase() }))}
        onChange={(v) => {
          const next = [...slotFilaments];
          next[index] = v;
          setSlotFilaments(next);
        }}
        disabled={disabled}
      />
    </div>
  );
}

function OrientationCard({
  report, apply, onToggle, disabled,
}: {
  report: OrientationReport;
  apply: boolean;
  onToggle: (v: boolean) => void;
  disabled: boolean;
}) {
  const { t } = useLang();
  const [open, setOpen] = useState(false);

  const scoreColor = (v: number) =>
    v >= 75 ? "text-green-400" : v >= 55 ? "text-yellow-400" : v >= 35 ? "text-orange-400" : "text-red-400";

  const ScoreBar = ({ label, value }: { label: string; value: number }) => {
    const color = value >= 75 ? "bg-green-500" : value >= 55 ? "bg-yellow-500" : value >= 35 ? "bg-orange-500" : "bg-red-500";
    return (
      <div className="flex items-center gap-2">
        <span className="text-xs text-zinc-500 w-16 shrink-0">{label}</span>
        <div className="flex-1 h-1 bg-surface-elevated rounded-full overflow-hidden">
          <div className={`h-full rounded-full ${color}`} style={{ width: `${value}%` }} />
        </div>
        <span className={`text-xs font-mono w-6 text-right ${scoreColor(value)}`}>{value}</span>
      </div>
    );
  };

  const CandidateRow = ({ c, highlight }: { c: OrientationCandidate; highlight?: boolean }) => (
    <div className={`rounded-lg border p-3 ${highlight ? "border-brand/40 bg-brand/5" : "border-surface-border"}`}>
      <div className="flex items-center justify-between mb-2">
        <span className={`text-xs font-semibold ${highlight ? "text-brand" : "text-zinc-300"}`}>{c.label}</span>
        <span className={`text-xs font-bold tabular-nums ${scoreColor(c.total_score)}`}>{c.total_score}</span>
      </div>
      <div className="space-y-1">
        <ScoreBar label={t("orient_support")}   value={c.support_score} />
        <ScoreBar label={t("orient_adhesion")}  value={c.adhesion_score} />
        <ScoreBar label={t("orient_stability")} value={c.stability_score} />
      </div>
      <div className="flex gap-3 mt-2">
        <span className="text-xs text-zinc-600">{c.overhang_area_ratio === 0 ? "No overhangs" : `${(c.overhang_area_ratio * 100).toFixed(0)}% overhang`}</span>
        <span className="text-xs text-zinc-600">{c.height_mm.toFixed(0)} mm tall</span>
      </div>
    </div>
  );

  return (
    <div className="relative bg-surface-card border border-white/[0.07] rounded-2xl mb-4 overflow-hidden
                    shadow-[0_0_0_1px_rgba(255,255,255,0.02),0_4px_32px_rgba(0,0,0,0.5)]">
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/[0.09] to-transparent" />
      <div className="p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-zinc-300 uppercase tracking-wide">{t("orient_title")}</h2>
          {report.should_rotate ? (
            <span className="text-xs font-semibold px-2.5 py-1 rounded-full border text-brand bg-brand/10 border-brand/20">
              {t("orient_suggested")}
            </span>
          ) : (
            <span className="text-xs font-semibold px-2.5 py-1 rounded-full border text-green-400 bg-green-500/10 border-green-500/20">
              {t("orient_optimal")}
            </span>
          )}
        </div>
        {report.should_rotate ? (
          <>
            <div className="grid grid-cols-2 gap-3 mb-3">
              <div>
                <p className="text-xs text-zinc-600 mb-1.5">Original</p>
                <div className="flex items-baseline gap-2">
                  <span className={`text-2xl font-bold tabular-nums ${scoreColor(report.original.total_score)}`}>{report.original.total_score}</span>
                  <span className="text-xs text-zinc-600">/ 100</span>
                </div>
              </div>
              <div>
                <p className="text-xs text-zinc-600 mb-1.5">Recommended — {report.recommended.label}</p>
                <div className="flex items-baseline gap-2">
                  <span className={`text-2xl font-bold tabular-nums ${scoreColor(report.recommended.total_score)}`}>{report.recommended.total_score}</span>
                  <span className="text-xs text-zinc-500">+{report.improvement} pts</span>
                </div>
              </div>
            </div>
            <div className="space-y-1.5 mb-3">
              {report.reasons.map((r, i) => (
                <div key={i} className="flex items-start gap-2">
                  <svg className="w-3.5 h-3.5 text-brand shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd"/>
                  </svg>
                  <span className="text-xs text-zinc-400">{r}</span>
                </div>
              ))}
            </div>
            <label className="flex items-center gap-2.5 cursor-pointer select-none w-fit">
              <input type="checkbox" checked={apply} onChange={(e) => onToggle(e.target.checked)}
                disabled={disabled} className="w-3.5 h-3.5 accent-brand cursor-pointer disabled:opacity-50" />
              <span className={`text-xs font-medium ${apply ? "text-brand" : "text-zinc-400"}`}>{t("orient_apply")}</span>
            </label>
          </>
        ) : (
          <div className="flex items-center gap-3">
            <span className={`text-3xl font-bold tabular-nums ${scoreColor(report.original.total_score)}`}>{report.original.total_score}</span>
            <span className="text-xs text-zinc-500 leading-relaxed">{report.reasons[0]}</span>
          </div>
        )}
      </div>
      <button onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-5 py-3 border-t border-surface-border text-left hover:bg-surface-elevated/40 transition-colors">
        <span className="text-xs text-zinc-500">
          {open ? t("orient_hide_all") : t("orient_show_all").replace("{n}", String(report.all_candidates.length))}
        </span>
        <svg className={`w-4 h-4 text-zinc-600 transition-transform ${open ? "rotate-180" : ""}`}
          fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7"/>
        </svg>
      </button>
      {open && (
        <div className="px-5 pb-5 grid grid-cols-2 sm:grid-cols-3 gap-3">
          {report.all_candidates.map((c) => (
            <CandidateRow key={c.label} c={c} highlight={c.label === report.recommended.label && report.should_rotate} />
          ))}
        </div>
      )}
    </div>
  );
}

function ExplanationsCard({ report }: { report: ExplanationReport }) {
  const { t } = useLang();
  const [open, setOpen] = useState(false);

  const iconEl = (icon: SettingExplanation["icon"]) => {
    if (icon === "check") return (
      <svg className="w-3.5 h-3.5 text-green-400 shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414L8.414 15 3.293 9.879a1 1 0 111.414-1.414L8.414 12.172l6.879-6.879a1 1 0 011.414 0z" clipRule="evenodd"/>
      </svg>
    );
    if (icon === "warning") return (
      <svg className="w-3.5 h-3.5 text-yellow-400 shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
        <path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd"/>
      </svg>
    );
    return (
      <svg className="w-3.5 h-3.5 text-blue-400 shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
        <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd"/>
      </svg>
    );
  };

  return (
    <div className="relative bg-surface-card border border-white/[0.07] rounded-2xl mb-4 overflow-hidden
                    shadow-[0_0_0_1px_rgba(255,255,255,0.02),0_4px_32px_rgba(0,0,0,0.5)]">
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/[0.09] to-transparent" />
      <button onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between p-5 text-left hover:bg-white/[0.02] transition-colors">
        <div>
          <h2 className="text-sm font-semibold text-zinc-300 uppercase tracking-wide mb-1">{t("explain_title")}</h2>
          <p className="text-xs text-zinc-500 line-clamp-1">{report.summary}</p>
        </div>
        <svg className={`w-4 h-4 text-zinc-500 shrink-0 ml-4 transition-transform ${open ? "rotate-180" : ""}`}
          fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7"/>
        </svg>
      </button>
      {open && (
        <div className="px-5 pb-5 border-t border-surface-border">
          <p className="text-xs text-zinc-400 leading-relaxed pt-4 pb-3 border-b border-surface-border/50 mb-4">{report.summary}</p>
          <div className="space-y-4">
            {report.items.map((item) => (
              <div key={item.setting} className="flex gap-3">
                {iconEl(item.icon)}
                <div className="min-w-0">
                  <div className="flex items-baseline gap-2 flex-wrap mb-0.5">
                    <span className="text-xs font-semibold text-zinc-300">{item.setting}</span>
                    <span className="text-xs font-mono text-brand">{item.value}</span>
                  </div>
                  <p className="text-xs text-zinc-500 leading-relaxed">{item.reason}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function PrintabilityCard({ score }: { score: PrintabilityScore }) {
  const { t } = useLang();
  const totalColor = score.total >= 80 ? "text-green-400" : score.total >= 60 ? "text-yellow-400" : score.total >= 40 ? "text-orange-400" : "text-red-400";
  const trackColor = score.total >= 80 ? "bg-green-500" : score.total >= 60 ? "bg-yellow-500" : score.total >= 40 ? "bg-orange-500" : "bg-red-500";
  const difficultyKey = score.difficulty_label === "Easy" ? "print_easy" : score.difficulty_label === "Moderate" ? "print_moderate" : score.difficulty_label === "Challenging" ? "print_challenging" : "print_difficult";
  const labelColor = score.difficulty_label === "Easy" ? "text-green-400 bg-green-500/10 border-green-500/20" : score.difficulty_label === "Moderate" ? "text-yellow-400 bg-yellow-500/10 border-yellow-500/20" : score.difficulty_label === "Challenging" ? "text-orange-400 bg-orange-500/10 border-orange-500/20" : "text-red-400 bg-red-500/10 border-red-500/20";
  const subs = [
    { label: t("print_support"),   value: score.support_score },
    { label: t("print_adhesion"),  value: score.adhesion_score },
    { label: t("print_stability"), value: score.stability_score },
    { label: t("print_detail"),    value: score.detail_score },
    { label: t("print_bridge"),    value: score.bridge_score },
  ];

  return (
    <div className="relative bg-surface-card border border-white/[0.07] rounded-2xl p-6 mb-4
                    shadow-[0_0_0_1px_rgba(255,255,255,0.02),0_4px_32px_rgba(0,0,0,0.5)]">
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/[0.09] to-transparent" />
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-zinc-300 uppercase tracking-wide">{t("print_title")}</h2>
        <span className={`text-xs font-semibold px-2.5 py-1 rounded-full border ${labelColor}`}>{t(difficultyKey)}</span>
      </div>
      <div className="flex items-end gap-3 mb-4">
        <span className={`text-5xl font-bold tabular-nums ${totalColor}`}>{score.total}</span>
        <span className="text-zinc-600 text-xl mb-1">/ 100</span>
      </div>
      <div className="w-full h-2 bg-surface-elevated rounded-full overflow-hidden mb-5">
        <div className={`h-full rounded-full transition-all duration-700 ${trackColor}`} style={{ width: `${score.total}%` }} />
      </div>
      <div className="space-y-2 mb-4">
        {subs.map(({ label, value }) => {
          const color = value >= 70 ? "bg-green-500" : value >= 50 ? "bg-yellow-500" : value >= 30 ? "bg-orange-500" : "bg-red-500";
          const textColor = value >= 70 ? "text-green-400" : value >= 50 ? "text-yellow-400" : value >= 30 ? "text-orange-400" : "text-red-400";
          return (
            <div key={label} className="flex items-center gap-3">
              <span className="text-xs text-zinc-500 w-20 shrink-0">{label}</span>
              <div className="flex-1 h-1.5 bg-surface-elevated rounded-full overflow-hidden">
                <div className={`h-full rounded-full ${color}`} style={{ width: `${value}%` }} />
              </div>
              <span className={`text-xs font-mono w-8 text-right ${textColor}`}>{value}</span>
            </div>
          );
        })}
      </div>
      {score.warnings.length > 0 && (
        <div className="border-t border-surface-border pt-3 space-y-1.5">
          {score.warnings.map((w, i) => (
            <div key={i} className="flex items-start gap-2">
              <svg className="w-3.5 h-3.5 text-yellow-500 mt-0.5 shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd"/>
              </svg>
              <span className="text-xs text-zinc-400">{w}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function RiskBar({ label, value }: { label: string; value: number }) {
  const color = value >= 60 ? "bg-red-500" : value >= 35 ? "bg-yellow-500" : value >= 15 ? "bg-blue-400" : "bg-green-500";
  const textColor = value >= 60 ? "text-red-400" : value >= 35 ? "text-yellow-400" : value >= 15 ? "text-blue-400" : "text-green-400";
  const riskLabel = value >= 60 ? "High" : value >= 35 ? "Medium" : value >= 15 ? "Low" : "None";
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-zinc-500 w-28 shrink-0">{label}</span>
      <div className="flex-1 h-1.5 bg-surface-elevated rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-500 ${color}`} style={{ width: `${Math.min(value, 100)}%` }} />
      </div>
      <span className={`text-xs font-mono w-12 text-right ${textColor}`}>{riskLabel}</span>
    </div>
  );
}
