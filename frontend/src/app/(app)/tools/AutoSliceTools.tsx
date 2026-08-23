"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  apiAnalyze,
  apiConvertDownload,
  apiDownloadReference,
  apiGet,
  apiUniversalAnalyze,
  apiUniversalConvert,
  apiUpload,
} from "@/lib/api";
import type { AnalysisResult, ConversionResult, Recommendation } from "@/lib/autoslice-types";
import { acceptsThreeMf, autoSliceFilename, canAnalyze, collectRecommendations, fallbackNotice, isConversionBlocked } from "@/lib/autoslice-flow";

type Printer = {
  id: string;
  display_name: string;
  supported_filaments: string[];
  max_colors: number;
};

type DetectedProject = {
  source?: { slicer?: string; confidence?: number };
  project?: { objects?: number; plates?: number; materials?: number };
  geometry?: { bounding_box?: { x_mm?: number; y_mm?: number; z_mm?: number } };
  universal_engine_enabled?: boolean;
};

type FlowState = "empty" | "uploading" | "detected" | "analyzing" | "ready" | "converting" | "done" | "failed";
type Mode = "preserve_source" | "autoslice";

const SELECT = "h-11 w-full rounded-xl border border-white/[0.09] bg-[#141419] px-3 text-sm font-semibold text-zinc-100 outline-none transition focus:border-brand/70 disabled:opacity-45";
const CARD = "rounded-2xl border border-white/[0.07] bg-[#101015]/95 shadow-[0_20px_55px_rgba(0,0,0,0.28)]";
const SOURCE_NAMES: Record<string, string> = {
  bambu: "Bambu", orca: "Orca", prusa: "Prusa", cura: "Cura", anycubic: "Anycubic", unknown: "Unknown",
};

function readable(value: unknown) {
  if (value === null || value === undefined || value === "") return "—";
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function sourceName(value?: string) {
  const key = (value ?? "unknown").toLowerCase();
  return SOURCE_NAMES[key] ?? value ?? "Unknown";
}

function StatusPill({ value }: { value: string }) {
  const bad = value === "blocked" || value === "failed" || value === "unsupported";
  const warn = value === "warning" || value === "unknown";
  return <span className={`rounded-full border px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.16em] ${bad ? "border-red-500/30 bg-red-500/10 text-red-300" : warn ? "border-amber-500/30 bg-amber-500/10 text-amber-300" : "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"}`}>{value}</span>;
}

function Metric({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.025] p-3">
      <p className="text-[10px] font-black uppercase tracking-[0.17em] text-zinc-500">{label}</p>
      <p className="mt-2 text-sm font-bold text-zinc-100">{value}</p>
      {detail && <p className="mt-1 text-xs text-zinc-500">{detail}</p>}
    </div>
  );
}

export default function AutoSliceTools() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [state, setState] = useState<FlowState>("empty");
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [jobId, setJobId] = useState("");
  const [detected, setDetected] = useState<DetectedProject | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [result, setResult] = useState<ConversionResult | null>(null);
  const [printers, setPrinters] = useState<Printer[]>([]);
  const [printer, setPrinter] = useState("");
  const [target] = useState("anycubic");
  const [nozzle, setNozzle] = useState(0.4);
  const [nozzleMaterial, setNozzleMaterial] = useState("brass");
  const [material, setMaterial] = useState("pla");
  const [mode, setMode] = useState<Mode>("autoslice");
  const [error, setError] = useState("");
  const [legacyUsed, setLegacyUsed] = useState(false);
  const [downloaded, setDownloaded] = useState(false);

  useEffect(() => {
    apiGet<Printer[]>("/printers", true).then((items) => {
      setPrinters(items);
      if (items[0]) {
        setPrinter(items[0].id);
        setMaterial(items[0].supported_filaments[0] ?? "pla");
      }
    }).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Printers konden niet worden geladen."));
  }, []);

  const selectedPrinter = printers.find((item) => item.id === printer);
  const recommendations = useMemo<Recommendation[]>(() => analysis ? collectRecommendations(analysis) : [], [analysis]);

  const resetOutput = useCallback(() => {
    setAnalysis(null); setResult(null); setLegacyUsed(false); setDownloaded(false); setError("");
  }, []);

  const upload = useCallback(async (next: File) => {
    if (!acceptsThreeMf(next.name)) { setError("Selecteer een geldig .3mf-bestand."); return; }
    resetOutput(); setFile(next); setState("uploading");
    try {
      const uploaded = await apiUpload(next);
      setJobId(uploaded.job_id);
      const project = await apiAnalyze(uploaded.job_id) as DetectedProject;
      setDetected(project);
      setState("detected");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Upload of detectie mislukt."); setState("failed");
    }
  }, [resetOutput]);

  async function analyze() {
    if (!canAnalyze(jobId, printer)) return;
    setState("analyzing"); setError(""); setResult(null); setLegacyUsed(false);
    try {
      setAnalysis(await apiUniversalAnalyze({
        job_id: jobId, target_slicer: target, target_printer: printer, nozzle_size_mm: nozzle,
        nozzle_material: nozzleMaterial, material, mode,
      }));
      setState("ready");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "AutoSlice-analyse mislukt."); setState("failed");
    }
  }

  async function convert() {
    if (!jobId || !printer || !file) return;
    setState("converting"); setError(""); setDownloaded(false);
    try {
      const converted = await apiUniversalConvert({
        job_id: jobId, target_slicer: target, target_printer: printer, nozzle_size_mm: nozzle,
        nozzle_material: nozzleMaterial, material, mode,
      });
      if (!converted.validation_passed) throw new Error("De uitvoer heeft de validatie niet doorstaan.");
      setResult(converted); setLegacyUsed(converted.fallback_used); setState("done");
    } catch (universalError) {
      try {
        const blob = await apiConvertDownload(jobId, printer, material, nozzle, nozzleMaterial, 1.75, "smooth", 3);
        const name = autoSliceFilename(file.name);
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement("a"); anchor.href = url; anchor.download = name; anchor.click(); URL.revokeObjectURL(url);
        setLegacyUsed(true); setDownloaded(true); setState("done");
      } catch {
        setError(universalError instanceof Error ? universalError.message : "Conversie mislukt."); setState("failed");
      }
    }
  }

  async function download() {
    if (!result?.validation_passed) return;
    try {
      const blob = await apiDownloadReference(result.download_reference);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a"); anchor.href = url; anchor.download = result.output_filename; anchor.click(); URL.revokeObjectURL(url);
      setDownloaded(true);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Download mislukt."); }
  }

  const blocked = analysis ? isConversionBlocked(analysis) : false;
  const outputName = result?.output_filename ?? (file ? autoSliceFilename(file.name) : "project_AutoSlice.3mf");

  return (
    <main className="min-h-full p-4 sm:p-6 lg:p-7">
      <header className="mb-6 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div><p className="text-[11px] font-black uppercase tracking-[0.24em] text-brand">Tools / AutoSlice</p><h1 className="mt-1 text-3xl font-black tracking-tight text-white">AutoSlice</h1><p className="mt-1 text-sm font-bold tracking-[0.18em] text-zinc-500">ONE FILE. ANY SLICE.</p></div>
        <Link href="/tools/hinged-box" className="rounded-xl border border-white/[0.09] bg-white/[0.035] px-4 py-2.5 text-sm font-bold text-zinc-300 transition hover:border-brand/50 hover:text-white">Hinged Box Generator →</Link>
      </header>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.1fr)_minmax(360px,.9fr)]">
        <section className="space-y-5">
          <div className={`${CARD} p-5`}>
            <div className="mb-4 flex items-center justify-between"><div><p className="text-xs font-black uppercase tracking-[0.18em] text-zinc-400">1 · Upload 3MF</p><p className="mt-1 text-xs text-zinc-600">Bambu · Orca · Prusa · Cura · Anycubic · Core 3MF</p></div>{detected && <StatusPill value="detected" />}</div>
            <button type="button" onClick={() => inputRef.current?.click()} onDragEnter={() => setDragging(true)} onDragLeave={() => setDragging(false)} onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); setDragging(false); const next = event.dataTransfer.files[0]; if (next) void upload(next); }} className={`flex min-h-44 w-full flex-col items-center justify-center rounded-2xl border border-dashed px-5 text-center transition ${dragging ? "border-brand bg-brand/10" : "border-white/[0.12] bg-black/20 hover:border-brand/55"}`}>
              <span className="mb-3 grid h-12 w-12 place-items-center rounded-2xl bg-brand/12 text-2xl text-brand">↥</span>
              <span className="text-sm font-bold text-white">{file?.name ?? "Drop je 3MF hier"}</span>
              <span className="mt-1 text-xs text-zinc-500">of klik om een bestand te kiezen</span>
            </button>
            <input ref={inputRef} type="file" accept=".3mf,model/3mf,application/vnd.ms-package.3dmanufacturing-3dmodel+xml" className="hidden" onChange={(event) => { const next = event.target.files?.[0]; if (next) void upload(next); }} />
            {state === "uploading" && <p className="mt-3 animate-pulse text-xs font-bold text-brand">Uploaden en project detecteren…</p>}
            {detected && <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4"><Metric label="Source" value={sourceName(detected.source?.slicer)} detail={`${Math.round((detected.source?.confidence ?? 0) * 100)}% confidence`} /><Metric label="Objects" value={String(detected.project?.objects ?? "—")} /><Metric label="Plates" value={String(detected.project?.plates ?? "—")} /><Metric label="Materials" value={String(detected.project?.materials ?? "—")} /></div>}
          </div>

          <div className={`${CARD} p-5 ${!detected ? "opacity-55" : ""}`}>
            <p className="mb-4 text-xs font-black uppercase tracking-[0.18em] text-zinc-400">2 · Target & mode</p>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <label><span className="mb-1.5 block text-[10px] font-bold uppercase tracking-widest text-zinc-500">Target</span><select className={SELECT} value={target} disabled={!detected}><option value="anycubic">Anycubic</option></select></label>
              <label><span className="mb-1.5 block text-[10px] font-bold uppercase tracking-widest text-zinc-500">Printer</span><select className={SELECT} value={printer} disabled={!detected} onChange={(event) => { const id = event.target.value; setPrinter(id); const item = printers.find((p) => p.id === id); setMaterial(item?.supported_filaments[0] ?? "pla"); setAnalysis(null); setState("detected"); }}>{printers.map((item) => <option key={item.id} value={item.id}>{item.display_name}</option>)}</select></label>
              <label><span className="mb-1.5 block text-[10px] font-bold uppercase tracking-widest text-zinc-500">Nozzle</span><select className={SELECT} value={nozzle} disabled={!detected} onChange={(event) => { setNozzle(Number(event.target.value)); setAnalysis(null); setState("detected"); }}>{[0.2, 0.4, 0.6, 0.8, 1].map((size) => <option key={size} value={size}>{size.toFixed(1)} mm</option>)}</select></label>
              <label><span className="mb-1.5 block text-[10px] font-bold uppercase tracking-widest text-zinc-500">Nozzle type</span><select className={SELECT} value={nozzleMaterial} disabled={!detected} onChange={(event) => setNozzleMaterial(event.target.value)}><option value="brass">Brass</option><option value="hardened_steel">Hardened steel</option><option value="stainless_steel">Stainless steel</option></select></label>
              <label className="sm:col-span-2"><span className="mb-1.5 block text-[10px] font-bold uppercase tracking-widest text-zinc-500">Material</span><select className={SELECT} value={material} disabled={!detected} onChange={(event) => { setMaterial(event.target.value); setAnalysis(null); setState("detected"); }}>{(selectedPrinter?.supported_filaments ?? ["pla"]).map((item) => <option key={item} value={item}>{item.toUpperCase()}</option>)}</select></label>
              <div className="sm:col-span-2"><span className="mb-1.5 block text-[10px] font-bold uppercase tracking-widest text-zinc-500">Mode</span><div className="grid grid-cols-2 gap-2">{(["preserve_source", "autoslice"] as Mode[]).map((item) => <button key={item} disabled={!detected} onClick={() => { setMode(item); setAnalysis(null); setState("detected"); }} className={`h-11 rounded-xl border text-xs font-black uppercase tracking-wider transition disabled:opacity-45 ${mode === item ? "border-brand bg-brand/15 text-white" : "border-white/[0.08] bg-white/[0.03] text-zinc-500"}`}>{item === "preserve_source" ? "Preserve" : "AutoSlice"}</button>)}</div></div>
            </div>
            <button onClick={() => void analyze()} disabled={!detected || !printer || state === "analyzing"} className="mt-4 h-12 w-full rounded-xl bg-brand text-sm font-black text-white shadow-[0_0_28px_rgba(224,36,36,0.22)] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40">{state === "analyzing" ? "AutoSlice analyzing…" : "Run AutoSlice analysis"}</button>
          </div>

          {analysis && <div className={`${CARD} p-5`}><div className="mb-4 flex items-center justify-between"><p className="text-xs font-black uppercase tracking-[0.18em] text-zinc-400">3 · Analysis</p><StatusPill value={blocked ? "blocked" : analysis.printability.status} /></div><div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <Metric label="Compatibility" value={`${Math.round(analysis.optimization_plan.compatibility.final_compatibility)}%`} />
            <Metric label="Printability" value={analysis.printability.status} detail={analysis.printability.project_build_volume} />
            <Metric label="Geometry" value={`${analysis.project.object_count} object${analysis.project.object_count === 1 ? "" : "s"}`} detail={analysis.project.dimensions_mm.map((v) => `${v.toFixed(1)}`).join(" × ") + " mm"} />
            <Metric label="Supports" value={analysis.support_plan.strategy} detail={`${analysis.support_plan.required_regions.length} required regions`} />
            <Metric label="Orientation" value={analysis.orientation ? `${analysis.orientation.rotation_degrees.map((v) => Math.round(v)).join("° / ")}°` : "Preserved"} detail={analysis.orientation ? `${analysis.orientation.confidence} confidence` : undefined} />
            <Metric label="Placement" value={analysis.placement_plan.applied ? "Will change" : "Preserved"} detail={`${analysis.placement_plan.plate_assignments.length || 1} plate assignment(s)`} />
          </div></div>}

          {analysis && <div className={`${CARD} overflow-hidden`}><div className="flex items-center justify-between border-b border-white/[0.07] p-5"><div><p className="text-xs font-black uppercase tracking-[0.18em] text-zinc-400">Recommendations</p><p className="mt-1 text-xs text-zinc-600">Directly from the backend OptimizationPlan</p></div><span className="text-xs font-bold text-zinc-500">{recommendations.length} changes</span></div>
            {recommendations.length ? <div className="divide-y divide-white/[0.06]">{recommendations.map((item, index) => <div key={`${item.setting}-${index}`} className="grid gap-3 p-4 md:grid-cols-[1fr_1fr_1fr_2fr_auto]"><div><p className="text-[10px] uppercase tracking-widest text-zinc-600">Setting</p><p className="mt-1 break-all text-xs font-bold text-white">{item.setting}</p></div><div><p className="text-[10px] uppercase tracking-widest text-zinc-600">Old</p><p className="mt-1 break-all text-xs text-zinc-400">{readable(item.old_value)}</p></div><div><p className="text-[10px] uppercase tracking-widest text-zinc-600">New</p><p className="mt-1 break-all text-xs text-emerald-300">{readable(item.new_value)}</p></div><div><p className="text-[10px] uppercase tracking-widest text-zinc-600">Reason</p><p className="mt-1 text-xs leading-relaxed text-zinc-400">{item.reason}</p></div><StatusPill value={item.confidence} /></div>)}</div> : <div className="p-8 text-center text-sm text-zinc-500">No changes recommended. The current project already fits this target.</div>}
          </div>}
        </section>

        <aside className="space-y-5">
          {(error || analysis?.optimization_plan.warnings.length || blocked) && <div className={`${CARD} border-amber-500/20 p-5`}><p className={`text-xs font-black uppercase tracking-[0.18em] ${blocked ? "text-red-400" : "text-amber-400"}`}>{blocked ? "Blocked" : "Warnings"}</p>{error && <p className="mt-3 text-sm text-red-300">{error}</p>}{analysis?.optimization_plan.blocked.map((item) => <p key={item.code} className="mt-3 text-sm text-red-300"><b>{item.code}</b> — {item.message}</p>)}{analysis?.optimization_plan.warnings.map((item) => <p key={item.code} className="mt-3 text-sm text-amber-200"><b>{item.code}</b> — {item.message}</p>)}{state === "failed" && <button onClick={() => jobId ? void analyze() : inputRef.current?.click()} className="mt-4 rounded-lg border border-white/[0.1] px-3 py-2 text-xs font-bold text-white">Opnieuw proberen</button>}</div>}

          <div className={`${CARD} p-5`}><p className="mb-4 text-xs font-black uppercase tracking-[0.18em] text-zinc-400">Pipeline</p><div className="space-y-2">{["Analyzing", "Optimizing", "Exporting", "Validating"].map((label, index) => { const backendStage = result?.compatibility.pipeline_stages[index]; const complete = state === "done" || Boolean(backendStage); const active = state === "converting" && index === 0; return <div key={label} className="flex items-center gap-3 rounded-xl border border-white/[0.06] bg-white/[0.025] px-3 py-3"><span className={`h-2.5 w-2.5 rounded-full ${complete ? "bg-emerald-400" : active ? "animate-pulse bg-brand" : "bg-zinc-700"}`} /><div className="min-w-0 flex-1"><p className="text-xs font-bold text-zinc-300">{label}</p>{backendStage && <p className="truncate text-[10px] text-zinc-600">{backendStage.name} · {backendStage.duration_ms.toFixed(1)} ms · {backendStage.status}</p>}</div></div>; })}</div>
            <button onClick={() => void convert()} disabled={!analysis || blocked || state === "converting"} className="mt-4 h-12 w-full rounded-xl bg-brand text-sm font-black text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40">{state === "converting" ? "Converting…" : blocked ? "Conversion blocked" : "Convert 3MF"}</button>
          </div>

          {(result || legacyUsed) && <div className={`${CARD} border-emerald-500/20 p-5`}><div className="flex items-center justify-between"><p className="text-xs font-black uppercase tracking-[0.18em] text-emerald-400">Download ready</p><StatusPill value={result?.validation_passed ? "validated" : "legacy"} /></div><p className="mt-4 break-all text-base font-black text-white">{outputName}</p><p className="mt-1 text-xs text-zinc-500">{downloaded ? "Download gestart." : "Validated conversion output."}</p>{legacyUsed && <div className="mt-4 rounded-xl border border-amber-500/25 bg-amber-500/8 p-3 text-xs leading-relaxed text-amber-200">{fallbackNotice(legacyUsed)}</div>}{result && <button onClick={() => void download()} className="mt-4 h-12 w-full rounded-xl bg-emerald-500 text-sm font-black text-black transition hover:bg-emerald-400">Download {outputName}</button>}</div>}

          {!file && <div className={`${CARD} p-8 text-center`}><p className="text-sm font-bold text-zinc-400">Start with one 3MF file.</p><p className="mt-2 text-xs leading-relaxed text-zinc-600">AutoSlice detects the source and only asks for choices the backend needs.</p></div>}
        </aside>
      </div>
    </main>
  );
}
