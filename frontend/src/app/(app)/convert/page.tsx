"use client";

import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { isLoggedIn, getUser } from "@/lib/auth";
import { apiUpload, apiAnalyze, apiConvertDownload, apiGet, apiPost } from "@/lib/api";
import { Navbar } from "@/components/Navbar";

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

type AnalysisResult = {
  job_id: string;
  model: { part_count: number; unit: string };
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
  { value: "smooth", label: "Smooth PEI" },
  { value: "textured", label: "Textured PEI (+5°C bed)" },
  { value: "cold", label: "Cold plate (0°C bed)" },
];

const difficultyColor: Record<string, string> = {
  easy: "text-green-400",
  moderate: "text-yellow-400",
  hard: "text-red-400",
};

export default function ConvertPage() {
  const router = useRouter();
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

  useEffect(() => {
    if (!isLoggedIn()) { router.push("/login"); return; }
    setUser(getUser());
    apiGet<Printer[]>("/printers").then((ps) => {
      setPrinters(ps);
      if (ps.length > 0) {
        setSelectedPrinter(ps[0].id);
        setAvailableFilaments(ps[0].supported_filaments);
        setSelectedFilament(ps[0].supported_filaments[0] ?? "pla");
      }
    });
  }, [router]);

  function handlePrinterChange(id: string) {
    setSelectedPrinter(id);
    const p = printers.find((x) => x.id === id);
    if (p) {
      setAvailableFilaments(p.supported_filaments);
      setSelectedFilament(p.supported_filaments[0] ?? "pla");
    }
  }

  function handleMultiColorMode(mode: "none" | "ace_pro" | "ace_pro2") {
    setMultiColorMode(mode);
    if (mode === "none") { setColorCount(1); setDualUnit(false); }
    else setColorCount(dualUnit ? 8 : 4);
  }

  function handleDualUnit(checked: boolean) {
    setDualUnit(checked);
    if (multiColorMode !== "none") setColorCount(checked ? 8 : 4);
  }

  async function handleFile(file: File) {
    if (!file.name.endsWith(".3mf")) { setError("Please upload a .3mf file."); return; }
    setError("");
    setUploadedFile(file);
    setStep("uploading");
    setAnalysis(null);
    setDownloadUrl(null);
    try {
      const up = await apiUpload(file);
      setJobId(up.job_id);
      setStep("analyzing");
      const result = await apiAnalyze(up.job_id) as AnalysisResult;
      setAnalysis(result);
      setStep("ready");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed");
      setStep("idle");
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
    setStep("converting");
    setError("");
    try {
      const blob = await apiConvertDownload(
        jobId, selectedPrinter, selectedFilament, nozzleSize, nozzleType, 1.75, buildPlate, flushVolume,
        colorCount,
        slotColors.slice(0, colorCount),
        slotFilaments.slice(0, colorCount),
      );
      const url = URL.createObjectURL(blob);
      const name = `autoslice_${selectedPrinter}_${selectedFilament}.3mf`;
      setDownloadUrl(url);
      setDownloadName(name);
      setStep("done");
      // Auto-trigger download
      const a = document.createElement("a");
      a.href = url;
      a.download = name;
      a.click();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Conversion failed");
      setStep("ready");
    }
  }

  function reset() {
    setStep("idle");
    setUploadedFile(null);
    setJobId(null);
    setAnalysis(null);
    setDownloadUrl(null);
    setError("");
  }

  async function sendFeedback(outcome: string) {
    if (!jobId || feedbackSent) return;
    setFeedbackLoading(true);
    try {
      await apiPost("/feedback", { job_id: jobId, outcome }, true);
      setFeedbackSent(true);
    } catch {
      setFeedbackSent(true); // hide on any error
    } finally {
      setFeedbackLoading(false);
    }
  }

  const isWorking = step === "uploading" || step === "analyzing" || step === "converting";
  const settingsDisabled = isWorking;

  return (
    <div className="min-h-screen bg-surface">
      <Navbar showAdmin={user?.is_admin} />

      <main className="max-w-3xl mx-auto px-4 py-10">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-white mb-1">Convert 3MF File</h1>
          <p className="text-zinc-500 text-sm">
            Configure your printer settings, upload your file, then hit Generate.
          </p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-brand/10 border border-brand/30 rounded-lg text-brand text-sm">
            {error}
          </div>
        )}

        {/* ── Settings panel (always visible) ── */}
        <div className="bg-surface-card border border-surface-border rounded-xl p-5 mb-6 space-y-4">
          <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wide">Print Settings</h2>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1.5 uppercase tracking-wide">Printer</label>
              <select
                value={selectedPrinter}
                onChange={(e) => handlePrinterChange(e.target.value)}
                disabled={settingsDisabled}
              >
                {printers.map((p) => (
                  <option key={p.id} value={p.id}>{p.display_name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1.5 uppercase tracking-wide">Filament Type</label>
              <select
                value={selectedFilament}
                onChange={(e) => setSelectedFilament(e.target.value)}
                disabled={settingsDisabled}
              >
                {availableFilaments.map((f) => (
                  <option key={f} value={f}>{FILAMENT_LABELS[f] ?? f.toUpperCase()}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1.5 uppercase tracking-wide">Nozzle Size</label>
              <select
                value={nozzleSize}
                onChange={(e) => setNozzleSize(parseFloat(e.target.value))}
                disabled={settingsDisabled}
              >
                {NOZZLE_SIZES.map((n) => (
                  <option key={n.value} value={n.value}>{n.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1.5 uppercase tracking-wide">Nozzle Type</label>
              <select
                value={nozzleType}
                onChange={(e) => setNozzleType(e.target.value)}
                disabled={settingsDisabled}
              >
                {NOZZLE_TYPES.map((n) => (
                  <option key={n.value} value={n.value}>{n.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1.5 uppercase tracking-wide">Filament Diameter</label>
              <div className="w-full px-3 py-2 bg-surface-elevated border border-surface-border rounded-lg text-sm text-zinc-400 cursor-not-allowed">
                1.75 mm
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1.5 uppercase tracking-wide">Build Plate</label>
              <select
                value={buildPlate}
                onChange={(e) => setBuildPlate(e.target.value)}
                disabled={settingsDisabled}
              >
                {BUILD_PLATES.map((b) => (
                  <option key={b.value} value={b.value}>{b.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1.5 uppercase tracking-wide">Flush Volume (mm³)</label>
              <input
                type="number"
                min={0}
                max={50}
                step={0.5}
                value={flushVolume}
                onChange={(e) => setFlushVolume(parseFloat(e.target.value) || 0)}
                disabled={settingsDisabled}
                className="w-full"
              />
            </div>
          </div>
        </div>

        {/* ── Multi-Color Setup ── */}
        <div className="bg-surface-card border border-surface-border rounded-xl p-5 mb-6">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-5 h-5 rounded-sm bg-brand/20 flex items-center justify-center">
              <svg className="w-3 h-3 text-brand" viewBox="0 0 24 24" fill="currentColor">
                <circle cx="6" cy="6" r="4"/><circle cx="18" cy="6" r="4"/>
                <circle cx="6" cy="18" r="4"/><circle cx="18" cy="18" r="4"/>
              </svg>
            </div>
            <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wide">Multi-Color Setup</h2>
          </div>

          {/* Mode buttons */}
          <div className="flex gap-2 mb-5">
            {([
              { id: "none",     label: "None",       sub: "Single color",  slots: 0 },
              { id: "ace_pro",  label: "ACE Pro",    sub: "4 color slots", slots: 4 },
              { id: "ace_pro2", label: "ACE Pro 2",  sub: "4 color slots", slots: 4 },
            ] as const).map(({ id, label, sub }) => (
              <button
                key={id}
                onClick={() => handleMultiColorMode(id)}
                disabled={settingsDisabled}
                className={`flex-1 py-2.5 px-3 rounded-lg border text-left transition-colors ${
                  multiColorMode === id
                    ? "bg-brand/15 border-brand text-white"
                    : "bg-surface-elevated border-surface-border text-zinc-400 hover:border-zinc-500"
                }`}
              >
                <p className={`text-sm font-semibold ${multiColorMode === id ? "text-brand" : ""}`}>{label}</p>
                <p className="text-xs text-zinc-500 mt-0.5">{sub}</p>
              </button>
            ))}
          </div>

          {/* Dual unit toggle */}
          {multiColorMode !== "none" && (
            <label className="flex items-center gap-2 mb-4 cursor-pointer w-fit select-none">
              <input
                type="checkbox"
                checked={dualUnit}
                onChange={(e) => handleDualUnit(e.target.checked)}
                disabled={settingsDisabled}
                className="w-3.5 h-3.5 accent-brand cursor-pointer"
              />
              <span className="text-xs text-zinc-500">
                Add second {multiColorMode === "ace_pro" ? "ACE Pro" : "ACE Pro 2"}
                <span className="ml-1.5 text-zinc-600">(8 slots)</span>
              </span>
            </label>
          )}

          {/* Color slots */}
          {multiColorMode !== "none" ? (
            {dualUnit && (
              <p className="text-xs text-zinc-600 mb-1.5 -mt-1">Unit 1</p>
            )}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {Array.from({ length: Math.min(colorCount, 4) }, (_, i) => (
                <ColorSlot key={i} index={i} slotColors={slotColors} setSlotColors={setSlotColors}
                  slotFilaments={slotFilaments} setSlotFilaments={setSlotFilaments}
                  availableFilaments={availableFilaments} disabled={settingsDisabled} />
              ))}
            </div>
            {dualUnit && colorCount === 8 && (
              <>
                <p className="text-xs text-zinc-600 mt-4 mb-1.5">Unit 2</p>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {Array.from({ length: 4 }, (_, i) => (
                    <ColorSlot key={i + 4} index={i + 4} slotColors={slotColors} setSlotColors={setSlotColors}
                      slotFilaments={slotFilaments} setSlotFilaments={setSlotFilaments}
                      availableFilaments={availableFilaments} disabled={settingsDisabled} />
                  ))}
                </div>
              </>
            )}
          ) : (
            <p className="text-xs text-zinc-600 italic">
              Kies ACE Pro of ACE Pro 2 om multi-color printen in te schakelen.
            </p>
          )}
        </div>

        {/* ── Upload zone ── */}
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => !isWorking && step !== "done" && fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-xl p-10 text-center transition-all duration-150 mb-6
            ${dragging ? "border-brand bg-brand/5" : "border-surface-border bg-surface-card"}
            ${step === "idle" || step === "ready" ? "cursor-pointer hover:border-zinc-600" : ""}
            ${isWorking ? "cursor-not-allowed opacity-70" : ""}
            ${step === "done" ? "border-green-700/50 bg-green-950/10 cursor-default" : ""}
          `}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".3mf"
            className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
          />

          {step === "idle" && (
            <>
              <div className="w-12 h-12 rounded-full bg-surface-elevated border border-surface-border flex items-center justify-center mx-auto mb-4">
                <svg className="w-6 h-6 text-zinc-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/>
                </svg>
              </div>
              <p className="text-white font-medium mb-1">Drop your .3mf file here</p>
              <p className="text-zinc-500 text-sm">or click to browse</p>
            </>
          )}

          {(step === "uploading" || step === "analyzing") && (
            <div className="flex flex-col items-center gap-3">
              <div className="w-8 h-8 border-2 border-brand border-t-transparent rounded-full animate-spin"/>
              <p className="text-white text-sm font-medium">
                {step === "uploading" ? "Uploading…" : "Analysing geometry…"}
              </p>
              <p className="text-zinc-500 text-xs">{uploadedFile?.name}</p>
            </div>
          )}

          {(step === "ready" || step === "converting") && (
            <div className="flex flex-col items-center gap-2">
              <div className="w-10 h-10 rounded-full bg-brand/10 border border-brand/30 flex items-center justify-center">
                <svg className="w-5 h-5 text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7"/>
                </svg>
              </div>
              <p className="text-white text-sm font-medium">{uploadedFile?.name}</p>
              <button
                onClick={(e) => { e.stopPropagation(); reset(); }}
                className="text-xs text-zinc-500 hover:text-brand transition-colors mt-1"
              >
                Upload different file
              </button>
            </div>
          )}

          {step === "done" && (
            <div className="flex flex-col items-center gap-2">
              <div className="w-10 h-10 rounded-full bg-green-500/10 border border-green-500/30 flex items-center justify-center">
                <svg className="w-5 h-5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7"/>
                </svg>
              </div>
              <p className="text-green-400 text-sm font-medium">Conversion complete</p>
            </div>
          )}
        </div>

        {/* 3D Model Viewer */}
        {jobId && (step === "ready" || step === "converting" || step === "done") && (
          <div className="mb-6">
            <ModelViewer jobId={jobId} />
          </div>
        )}

        {/* Analysis results */}
        {analysis && (
          <div className="bg-surface-card border border-surface-border rounded-xl p-6 mb-6">
            <h2 className="text-sm font-semibold text-zinc-300 uppercase tracking-wide mb-4">
              Model Analysis
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mb-5">
              <Stat label="Size X" value={`${analysis.geometry.bounding_box.x_mm} mm`} />
              <Stat label="Size Y" value={`${analysis.geometry.bounding_box.y_mm} mm`} />
              <Stat label="Size Z" value={`${analysis.geometry.bounding_box.z_mm} mm`} />
              <Stat label="Volume" value={`${analysis.geometry.bounding_box.volume_cm3} cm³`} />
              <Stat label="Parts" value={String(analysis.geometry.part_count)} />
              <Stat label="Watertight" value={analysis.geometry.mesh_is_watertight ? "Yes" : "No"} />
            </div>

            <div className="border-t border-surface-border pt-4 grid grid-cols-2 sm:grid-cols-3 gap-3">
              <Badge
                label="Difficulty"
                value={analysis.intent.difficulty}
                className={difficultyColor[analysis.intent.difficulty] ?? "text-zinc-400"}
              />
              <Badge label="Size" value={analysis.intent.size_class} />
              <Badge
                label="Supports"
                value={analysis.intent.needs_supports ? `Yes (${analysis.intent.support_density_hint})` : "No"}
                className={analysis.intent.needs_supports ? "text-yellow-400" : "text-green-400"}
              />
              <Badge
                label="Overhangs"
                value={analysis.geometry.overhang.has_overhangs
                  ? `${analysis.geometry.overhang.max_angle_deg}°`
                  : "None"}
                className={analysis.geometry.overhang.has_overhangs ? "text-yellow-400" : "text-zinc-400"}
              />
              <Badge
                label="Bridges"
                value={analysis.geometry.bridge.has_bridges
                  ? `${analysis.geometry.bridge.max_span_mm} mm span`
                  : "None"}
                className={analysis.geometry.bridge.has_bridges ? "text-yellow-400" : "text-zinc-400"}
              />
              <Badge
                label="Brim"
                value={analysis.intent.needs_brim ? "Recommended" : "Not needed"}
              />
            </div>

            {/* Risk score bars */}
            <div className="border-t border-surface-border pt-4 mt-4 space-y-2.5">
              <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wide mb-3">Risk Assessment</p>
              <RiskBar label="Support risk"   value={analysis.intent.support_risk}   />
              <RiskBar label="Adhesion risk"  value={analysis.intent.adhesion_risk}  />
              <RiskBar label="Stability risk" value={analysis.intent.stability_risk} />
              <RiskBar label="Detail risk"    value={analysis.intent.detail_risk}    />
            </div>
          </div>
        )}

        {/* Action buttons */}
        {step === "ready" && (
          <button
            onClick={handleConvert}
            className="w-full py-3 bg-brand hover:bg-brand-dark text-white font-semibold rounded-lg
                       transition-colors duration-150 text-sm flex items-center justify-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
            </svg>
            Generate Anycubic 3MF
          </button>
        )}

        {step === "converting" && (
          <button disabled className="w-full py-3 bg-brand/50 text-white font-semibold rounded-lg text-sm flex items-center justify-center gap-2">
            <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"/>
            Generating…
          </button>
        )}

        {step === "done" && downloadUrl && (
          <div className="flex flex-col gap-3">
            <a
              href={downloadUrl}
              download={downloadName}
              className="w-full py-3 bg-green-700 hover:bg-green-600 text-white font-semibold rounded-lg
                         transition-colors duration-150 text-sm flex items-center justify-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l4 4m0 0l4-4m-4 4V4"/>
              </svg>
              Download {downloadName}
            </a>
            <button
              onClick={reset}
              className="w-full py-3 bg-surface-card hover:bg-surface-elevated border border-surface-border
                         text-white font-semibold rounded-lg transition-colors duration-150 text-sm
                         flex items-center justify-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M12 4v16m8-8H4"/>
              </svg>
              Convert New Project
            </button>

            {/* Feedback card */}
            <div className="mt-2 p-4 bg-surface-card border border-surface-border rounded-xl">
              {feedbackSent ? (
                <p className="text-center text-sm text-green-400">Thanks for your feedback!</p>
              ) : (
                <>
                  <p className="text-xs text-zinc-500 mb-3 text-center">How did your print turn out?</p>
                  <div className="grid grid-cols-3 gap-2">
                    {[
                      { outcome: "printed_ok",         label: "Printed well",      color: "text-green-400 border-green-500/30 hover:bg-green-500/10" },
                      { outcome: "supports_unneeded",  label: "Supports excess",   color: "text-yellow-400 border-yellow-500/30 hover:bg-yellow-500/10" },
                      { outcome: "supports_missing",   label: "Supports missing",  color: "text-orange-400 border-orange-500/30 hover:bg-orange-500/10" },
                      { outcome: "detached_from_bed",  label: "Detached",          color: "text-red-400 border-red-500/30 hover:bg-red-500/10" },
                      { outcome: "weak_part",          label: "Too weak",          color: "text-orange-400 border-orange-500/30 hover:bg-orange-500/10" },
                      { outcome: "details_lost",       label: "Details lost",      color: "text-blue-400 border-blue-500/30 hover:bg-blue-500/10" },
                    ].map(({ outcome, label, color }) => (
                      <button
                        key={outcome}
                        onClick={() => sendFeedback(outcome)}
                        disabled={feedbackLoading}
                        className={`py-1.5 px-2 rounded-lg border text-xs font-medium transition-colors disabled:opacity-50 ${color} bg-transparent`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
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
  return (
    <div className="rounded-lg border p-3"
      style={{ borderColor: slotColors[index] + "66", backgroundColor: slotColors[index] + "11" }}>
      <div className="flex items-center gap-2 mb-2">
        <div className="w-4 h-4 rounded-full border border-white/20 shrink-0"
          style={{ backgroundColor: slotColors[index] }} />
        <span className="text-xs font-medium text-zinc-400">Slot {index + 1}</span>
      </div>
      <input
        type="color"
        value={slotColors[index]}
        onChange={(e) => {
          const next = [...slotColors];
          next[index] = e.target.value;
          setSlotColors(next);
        }}
        disabled={disabled}
        className="w-full h-7 rounded cursor-pointer border-0 bg-transparent mb-2"
      />
      <select
        value={slotFilaments[index]}
        onChange={(e) => {
          const next = [...slotFilaments];
          next[index] = e.target.value;
          setSlotFilaments(next);
        }}
        disabled={disabled}
        className="text-xs py-1"
      >
        {availableFilaments.map((f) => (
          <option key={f} value={f}>{FILAMENT_LABELS[f] ?? f.toUpperCase()}</option>
        ))}
      </select>
    </div>
  );
}

function RiskBar({ label, value }: { label: string; value: number }) {
  const color =
    value >= 60 ? "bg-red-500" :
    value >= 35 ? "bg-yellow-500" :
    value >= 15 ? "bg-blue-400" :
    "bg-green-500";
  const textColor =
    value >= 60 ? "text-red-400" :
    value >= 35 ? "text-yellow-400" :
    value >= 15 ? "text-blue-400" :
    "text-green-400";
  const riskLabel =
    value >= 60 ? "High" :
    value >= 35 ? "Medium" :
    value >= 15 ? "Low" :
    "None";

  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-zinc-500 w-28 shrink-0">{label}</span>
      <div className="flex-1 h-1.5 bg-surface-elevated rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${color}`}
          style={{ width: `${Math.min(value, 100)}%` }}
        />
      </div>
      <span className={`text-xs font-mono w-12 text-right ${textColor}`}>{riskLabel}</span>
    </div>
  );
}
