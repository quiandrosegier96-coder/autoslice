"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { isLoggedIn } from "@/lib/auth";
import { apiAnalyze } from "@/lib/api";

const ModelViewer = dynamic(
  () => import("@/components/ModelViewer").then((m) => m.ModelViewer),
  {
    ssr: false,
    loading: () => (
      <div className="w-full h-full bg-[#191919] flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-brand border-t-transparent rounded-full animate-spin" />
      </div>
    ),
  }
);

// ─── Types ────────────────────────────────────────────────────────────────────

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

type AnalysisResult = {
  job_id: string;
  archive: {
    filename: string;
    size_bytes: number;
  };
  model: { part_count: number; unit: string };
  geometry: {
    bounding_box: { x_mm: number; y_mm: number; z_mm: number; volume_cm3: number };
    part_count: number;
    mesh_is_watertight: boolean;
    estimated_volume_cm3: number;
    surface_area_mm2: number;
    overhang: { has_overhangs: boolean; max_angle_deg: number; overhang_area_ratio: number };
    bridge: { has_bridges: boolean; max_span_mm: number };
    thin_wall: { has_thin_walls: boolean; min_thickness_mm: number };
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

// ─── Helpers ──────────────────────────────────────────────────────────────────

function scoreColor(v: number) {
  return v >= 75 ? "text-green-400" : v >= 55 ? "text-yellow-400" : v >= 35 ? "text-orange-400" : "text-red-400";
}

function scoreTrack(v: number) {
  return v >= 75 ? "bg-green-500" : v >= 55 ? "bg-yellow-500" : v >= 35 ? "bg-orange-500" : "bg-red-500";
}

function estimatePrintMins(c: OrientationCandidate): number {
  return Math.round(c.height_mm * 1.8 + c.overhang_area_ratio * 90 + 8);
}

function fmtMins(m: number): string {
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  const rem = m % 60;
  return rem === 0 ? `${h}h` : `${h}h ${rem}m`;
}

// ─── Small sub-components ─────────────────────────────────────────────────────

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[10px] font-semibold text-zinc-600 uppercase tracking-widest mb-2.5">
      {children}
    </p>
  );
}

function ScoreBar({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-zinc-500 shrink-0 w-16">{label}</span>
      <div className="flex-1 h-1 bg-surface-elevated rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${scoreTrack(value)}`} style={{ width: `${value}%` }} />
      </div>
      <span className={`text-xs font-mono w-6 text-right tabular-nums ${scoreColor(value)}`}>{value}</span>
    </div>
  );
}

function InfoRow({ label, value, accent = false }: { label: string; value: string; accent?: boolean }) {
  return (
    <div>
      <p className="text-[10px] text-zinc-600 mb-0.5">{label}</p>
      <p className={`text-xs font-mono font-medium ${accent ? "text-yellow-400" : "text-zinc-300"}`}>{value}</p>
    </div>
  );
}

// ─── Icon helpers ─────────────────────────────────────────────────────────────

function IconCheck() {
  return (
    <svg className="w-3.5 h-3.5 text-green-400 shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414L8.414 15 3.293 9.879a1 1 0 111.414-1.414L8.414 12.172l6.879-6.879a1 1 0 011.414 0z" clipRule="evenodd"/>
    </svg>
  );
}

function IconWarn() {
  return (
    <svg className="w-3.5 h-3.5 text-yellow-400 shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
      <path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd"/>
    </svg>
  );
}

function IconInfo() {
  return (
    <svg className="w-3.5 h-3.5 text-blue-400 shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
      <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd"/>
    </svg>
  );
}

// ─── Card: Printability ───────────────────────────────────────────────────────

function PrintabilityCard({ score }: { score: PrintabilityScore }) {
  const diffColor =
    score.difficulty_label === "Easy"        ? "text-green-400 bg-green-500/10 border-green-500/20" :
    score.difficulty_label === "Moderate"    ? "text-yellow-400 bg-yellow-500/10 border-yellow-500/20" :
    score.difficulty_label === "Challenging" ? "text-orange-400 bg-orange-500/10 border-orange-500/20" :
    "text-red-400 bg-red-500/10 border-red-500/20";

  return (
    <div className="bg-surface-card border border-surface-border rounded-xl p-4">
      <SectionLabel>Printability Score</SectionLabel>

      <div className="flex items-end gap-2 mb-3">
        <span className={`text-4xl font-bold tabular-nums leading-none ${scoreColor(score.total)}`}>
          {score.total}
        </span>
        <span className="text-zinc-600 text-sm mb-0.5">/ 100</span>
        <span className={`ml-auto text-[10px] font-semibold px-2 py-0.5 rounded-full border ${diffColor}`}>
          {score.difficulty_label}
        </span>
      </div>

      <div className="w-full h-1.5 bg-surface-elevated rounded-full overflow-hidden mb-4">
        <div
          className={`h-full rounded-full transition-all duration-700 ${scoreTrack(score.total)}`}
          style={{ width: `${score.total}%` }}
        />
      </div>

      <div className="space-y-1.5">
        <ScoreBar label="Support"   value={score.support_score} />
        <ScoreBar label="Adhesion"  value={score.adhesion_score} />
        <ScoreBar label="Stability" value={score.stability_score} />
        <ScoreBar label="Detail"    value={score.detail_score} />
        <ScoreBar label="Bridge"    value={score.bridge_score} />
      </div>

      {score.warnings.length > 0 && (
        <div className="mt-3 pt-3 border-t border-surface-border space-y-1.5">
          {score.warnings.map((w, i) => (
            <div key={i} className="flex items-start gap-2">
              <IconWarn />
              <span className="text-xs text-zinc-500">{w}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Card: Model Info ─────────────────────────────────────────────────────────

function ModelInfoCard({ analysis }: { analysis: AnalysisResult }) {
  const geo = analysis.geometry;
  const intent = analysis.intent;

  const diffColor =
    intent.difficulty === "easy"     ? "text-green-400 bg-green-500/10 border-green-500/20" :
    intent.difficulty === "moderate" ? "text-yellow-400 bg-yellow-500/10 border-yellow-500/20" :
    "text-red-400 bg-red-500/10 border-red-500/20";

  return (
    <div className="bg-surface-card border border-surface-border rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <SectionLabel>Model Info</SectionLabel>
        <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border -mt-1 ${diffColor}`}>
          {intent.difficulty.charAt(0).toUpperCase() + intent.difficulty.slice(1)}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-x-4 gap-y-2.5 mb-3">
        <InfoRow label="Size X" value={`${geo.bounding_box.x_mm} mm`} />
        <InfoRow label="Size Y" value={`${geo.bounding_box.y_mm} mm`} />
        <InfoRow label="Size Z" value={`${geo.bounding_box.z_mm} mm`} />
        <InfoRow label="Volume" value={`${geo.bounding_box.volume_cm3} cm³`} />
        <InfoRow label="Parts"  value={String(geo.part_count)} />
        <InfoRow label="Watertight" value={geo.mesh_is_watertight ? "Yes" : "No"} />
        {geo.overhang.has_overhangs && (
          <InfoRow label="Max overhang" value={`${geo.overhang.max_angle_deg}°`} accent />
        )}
        {geo.bridge.has_bridges && (
          <InfoRow label="Bridge span" value={`${geo.bridge.max_span_mm} mm`} accent />
        )}
      </div>

      {/* Intent tags */}
      <div className="flex gap-1.5 flex-wrap pt-2.5 border-t border-surface-border">
        {intent.needs_supports && (
          <span className="text-[10px] font-medium px-2 py-0.5 rounded-full border text-yellow-400 border-yellow-500/30 bg-yellow-500/5">
            Supports ({intent.support_density_hint})
          </span>
        )}
        {intent.needs_brim && (
          <span className="text-[10px] font-medium px-2 py-0.5 rounded-full border text-blue-400 border-blue-500/30 bg-blue-500/5">
            Brim
          </span>
        )}
        {geo.thin_wall.has_thin_walls && (
          <span className="text-[10px] font-medium px-2 py-0.5 rounded-full border text-orange-400 border-orange-500/30 bg-orange-500/5">
            Thin walls
          </span>
        )}
        {intent.is_structurally_risky && (
          <span className="text-[10px] font-medium px-2 py-0.5 rounded-full border text-red-400 border-red-500/30 bg-red-500/5">
            Structural risk
          </span>
        )}
        <span className="text-[10px] font-medium px-2 py-0.5 rounded-full border text-zinc-500 border-surface-border">
          {intent.size_class}
        </span>
      </div>
    </div>
  );
}

// ─── Card: Explanations ───────────────────────────────────────────────────────

function ExplanationsCard({ report }: { report: ExplanationReport }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="bg-surface-card border border-surface-border rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between p-4 text-left hover:bg-surface-elevated/30 transition-colors"
      >
        <div className="min-w-0 flex-1">
          <SectionLabel>Settings & Explanations</SectionLabel>
          <p className="text-xs text-zinc-500 line-clamp-1">{report.summary}</p>
        </div>
        <svg
          className={`w-4 h-4 text-zinc-600 shrink-0 ml-3 transition-transform ${open ? "rotate-180" : ""}`}
          fill="none" stroke="currentColor" viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7"/>
        </svg>
      </button>

      {open && (
        <div className="px-4 pb-4 border-t border-surface-border">
          <p className="text-xs text-zinc-500 leading-relaxed pt-3 pb-3 border-b border-surface-border/50 mb-3">
            {report.summary}
          </p>
          <div className="space-y-3.5">
            {report.items.map((item) => (
              <div key={item.setting} className="flex gap-2.5">
                {item.icon === "check" ? <IconCheck /> : item.icon === "warning" ? <IconWarn /> : <IconInfo />}
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

// ─── Card: Orientation ────────────────────────────────────────────────────────

function OrientationCard({ report }: { report: OrientationReport }) {
  const [showAll, setShowAll] = useState(false);

  const times = report.all_candidates.map(estimatePrintMins);
  const bestTime = Math.min(...times);
  const worstTime = Math.max(...times);

  return (
    <div className="bg-surface-card border border-surface-border rounded-xl overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-surface-border">
        <div className="flex items-center justify-between mb-3">
          <SectionLabel>Orientation</SectionLabel>
          {report.should_rotate ? (
            <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full border text-brand bg-brand/10 border-brand/20 -mt-1">
              Rotation suggested
            </span>
          ) : (
            <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full border text-green-400 bg-green-500/10 border-green-500/20 -mt-1">
              Already optimal
            </span>
          )}
        </div>

        {report.should_rotate ? (
          <>
            <div className="grid grid-cols-2 gap-3 mb-3">
              <div className="bg-surface-elevated rounded-lg p-3">
                <p className="text-[10px] text-zinc-600 mb-1">Original</p>
                <p className={`text-2xl font-bold tabular-nums ${scoreColor(report.original.total_score)}`}>
                  {report.original.total_score}
                </p>
                <p className="text-[10px] text-zinc-600 mt-1">
                  ~{fmtMins(estimatePrintMins(report.original))}
                </p>
              </div>
              <div className="bg-brand/5 border border-brand/20 rounded-lg p-3">
                <p className="text-[10px] text-brand/70 mb-1">Recommended</p>
                <p className={`text-2xl font-bold tabular-nums ${scoreColor(report.recommended.total_score)}`}>
                  {report.recommended.total_score}
                  <span className="text-xs font-normal text-zinc-500 ml-1">+{report.improvement}</span>
                </p>
                <p className="text-[10px] text-zinc-600 mt-1">
                  ~{fmtMins(estimatePrintMins(report.recommended))}
                  {worstTime > bestTime && (
                    <span className="text-green-500 ml-1">
                      (saves ~{fmtMins(worstTime - bestTime)})
                    </span>
                  )}
                </p>
              </div>
            </div>
            <div className="space-y-1.5">
              {report.reasons.map((r, i) => (
                <div key={i} className="flex items-start gap-2">
                  <svg className="w-3.5 h-3.5 text-brand shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd"/>
                  </svg>
                  <span className="text-xs text-zinc-500">{r}</span>
                </div>
              ))}
            </div>
          </>
        ) : (
          <div className="flex items-center gap-3">
            <span className={`text-3xl font-bold tabular-nums ${scoreColor(report.original.total_score)}`}>
              {report.original.total_score}
            </span>
            <span className="text-xs text-zinc-500">{report.reasons[0]}</span>
          </div>
        )}
      </div>

      {/* All candidates toggle */}
      <button
        onClick={() => setShowAll((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-2.5 text-left hover:bg-surface-elevated/30 transition-colors"
      >
        <span className="text-xs text-zinc-600">
          {showAll ? "Hide all orientations" : `Show all ${report.all_candidates.length} orientations`}
        </span>
        <svg
          className={`w-3.5 h-3.5 text-zinc-600 transition-transform ${showAll ? "rotate-180" : ""}`}
          fill="none" stroke="currentColor" viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7"/>
        </svg>
      </button>

      {showAll && (
        <div className="px-4 pb-4 grid grid-cols-2 gap-2">
          {report.all_candidates.map((c) => {
            const isRecommended = c.label === report.recommended.label && report.should_rotate;
            const mins = estimatePrintMins(c);
            return (
              <div
                key={c.label}
                className={`rounded-lg border p-3 ${
                  isRecommended
                    ? "border-green-500/40 bg-green-500/5"
                    : "border-surface-border bg-surface-elevated/30"
                }`}
              >
                <div className="flex items-start justify-between mb-1.5">
                  <span className={`text-xs font-semibold ${isRecommended ? "text-green-400" : "text-zinc-300"}`}>
                    {c.label}
                  </span>
                  <span className={`text-xs font-bold tabular-nums ${scoreColor(c.total_score)}`}>
                    {c.total_score}
                  </span>
                </div>
                {isRecommended && (
                  <div className="flex items-center gap-1 mb-2">
                    <svg className="w-3 h-3 text-green-400" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd"/>
                    </svg>
                    <span className="text-[10px] font-semibold text-green-400">Best choice</span>
                  </div>
                )}
                <div className="space-y-1 mb-2">
                  <ScoreBar label="Support"  value={c.support_score} />
                  <ScoreBar label="Adhesion" value={c.adhesion_score} />
                  <ScoreBar label="Stability" value={c.stability_score} />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-zinc-600">
                    {c.overhang_area_ratio === 0 ? "No overhangs" : `${(c.overhang_area_ratio * 100).toFixed(0)}% overhang`}
                  </span>
                  <span className="text-[10px] text-zinc-600">~{fmtMins(mins)}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── Loading skeleton ─────────────────────────────────────────────────────────

function Skeleton() {
  return (
    <div className="p-4 space-y-4 animate-pulse">
      {[["80%", "100%", "65%"], ["60%", "100%", "75%"], ["70%", "100%", "55%"]].map((widths, i) => (
        <div key={i} className="bg-surface-card border border-surface-border rounded-xl p-4 space-y-2">
          {widths.map((w, j) => (
            <div key={j} className="h-2.5 rounded bg-surface-elevated" style={{ width: w }} />
          ))}
        </div>
      ))}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function ViewerPage() {
  const params   = useParams<{ jobId: string }>();
  const jobId    = params.jobId;
  const router   = useRouter();

  const [analysis,     setAnalysis]     = useState<AnalysisResult | null>(null);
  const [loading,      setLoading]      = useState(true);
  const [error,        setError]        = useState("");
  const [showSupports, setShowSupports] = useState(false);
  const [wireframe,    setWireframe]    = useState(false);
  const [resetKey,     setResetKey]     = useState(0);

  // Debug mode: append ?debug=1 to the page URL to enable
  const debugMode = typeof window !== "undefined" &&
    new URLSearchParams(window.location.search).get("debug") === "1";
  const [debugLayers, setDebugLayers] = useState({
    showAllOverhangs:       false,
    showActiveCandidates:   false,
    showFilteredCandidates: false,
  });

  useEffect(() => {
    if (!isLoggedIn()) { router.push("/login"); return; }
    apiAnalyze(jobId)
      .then((r) => { setAnalysis(r as AnalysisResult); setLoading(false); })
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : "Analysis failed");
        setLoading(false);
      });
  }, [jobId, router]);

  const filename = analysis?.archive.filename ?? "model.3mf";
  const geo      = analysis?.geometry;
  const intent   = analysis?.intent;

  const diffColor =
    intent?.difficulty === "easy"     ? "text-green-400 bg-green-500/10 border-green-500/20" :
    intent?.difficulty === "moderate" ? "text-yellow-400 bg-yellow-500/10 border-yellow-500/20" :
    intent?.difficulty               ? "text-red-400 bg-red-500/10 border-red-500/20" : "";

  return (
    <div className="h-screen flex flex-col bg-surface overflow-hidden">

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header className="h-12 shrink-0 flex items-center px-4 gap-3 border-b border-surface-border bg-surface-card">
        <button
          onClick={() => router.push("/convert")}
          className="flex items-center gap-1.5 text-zinc-500 hover:text-zinc-300 transition-colors shrink-0"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7"/>
          </svg>
          <span className="text-xs">Convert</span>
        </button>

        <div className="w-px h-5 bg-surface-border shrink-0" />

        {/* Model name */}
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <svg className="w-4 h-4 text-zinc-600 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z"/>
          </svg>
          <span className="text-sm font-medium text-white truncate max-w-xs">{filename}</span>
          {geo && (
            <span className="text-xs text-zinc-600 font-mono shrink-0 hidden sm:block">
              {geo.bounding_box.x_mm} × {geo.bounding_box.y_mm} × {geo.bounding_box.z_mm} mm
            </span>
          )}
        </div>

        {/* Badges */}
        <div className="flex items-center gap-2 shrink-0">
          {intent && diffColor && (
            <span className={`text-[10px] font-semibold px-2.5 py-1 rounded-full border ${diffColor}`}>
              {intent.difficulty.charAt(0).toUpperCase() + intent.difficulty.slice(1)}
            </span>
          )}
          {geo && (
            <span className="text-[10px] text-zinc-500 px-2.5 py-1 rounded-full border border-surface-border">
              {geo.part_count} part{geo.part_count !== 1 ? "s" : ""}
            </span>
          )}
          {loading && (
            <div className="w-3.5 h-3.5 border-2 border-brand border-t-transparent rounded-full animate-spin" />
          )}
        </div>
      </header>

      {/* ── Main content ───────────────────────────────────────────────────── */}
      <div className="flex-1 flex overflow-hidden">

        {/* ── Left: 3D Viewer ──────────────────────────────────────────────── */}
        <div className="flex-1 relative bg-[#191919]">
          <ModelViewer
            jobId={jobId}
            showSupports={showSupports}
            wireframe={wireframe}
            className="w-full h-full absolute inset-0"
            resetKey={resetKey}
            debugMode={debugMode}
            debugLayers={debugLayers}
          />

          {/* Top-left: Reset View */}
          <div className="absolute top-3 left-3 z-10">
            <button
              onClick={() => setResetKey((k) => k + 1)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-black/60 border border-white/10 text-zinc-300 text-xs hover:bg-black/80 hover:border-white/20 transition-colors backdrop-blur-sm"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
              </svg>
              Reset View
            </button>
          </div>

          {/* Top-right: standard toggles */}
          <div className="absolute top-3 right-3 z-10 flex gap-2">
            {geo?.overhang.has_overhangs && (
              <button
                onClick={() => setShowSupports((s) => !s)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs transition-colors backdrop-blur-sm ${
                  showSupports
                    ? "bg-orange-500/20 border-orange-500/40 text-orange-300"
                    : "bg-black/60 border-white/10 text-zinc-400 hover:text-zinc-200 hover:border-white/20"
                }`}
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/>
                </svg>
                Supports
              </button>
            )}
            <button
              onClick={() => setWireframe((w) => !w)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs transition-colors backdrop-blur-sm ${
                wireframe
                  ? "bg-blue-500/20 border-blue-500/40 text-blue-300"
                  : "bg-black/60 border-white/10 text-zinc-400 hover:text-zinc-200 hover:border-white/20"
              }`}
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M4 7h16M4 12h16M4 17h16"/>
              </svg>
              Wireframe
            </button>
          </div>

          {/* Bottom-left: debug layer panel — only visible with ?debug=1 */}
          {debugMode && showSupports && (
            <div className="absolute bottom-8 left-3 z-10 flex flex-col gap-1.5 bg-black/70 backdrop-blur-sm border border-white/10 rounded-lg p-3">
              <p className="text-[10px] font-semibold text-zinc-500 uppercase tracking-widest mb-1">
                Debug layers
              </p>
              {([
                { key: "showAllOverhangs",       label: "All overhangs",        color: "text-blue-400" },
                { key: "showActiveCandidates",   label: "Active candidates",    color: "text-green-400" },
                { key: "showFilteredCandidates", label: "Filtered regions",     color: "text-red-400" },
              ] as const).map(({ key, label, color }) => (
                <label key={key} className="flex items-center gap-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={debugLayers[key]}
                    onChange={(e) =>
                      setDebugLayers((l) => ({ ...l, [key]: e.target.checked }))
                    }
                    className="w-3 h-3 accent-brand"
                  />
                  <span className={`text-xs ${color}`}>{label}</span>
                </label>
              ))}
            </div>
          )}
        </div>

        {/* ── Right: Sidebar ────────────────────────────────────────────────── */}
        <aside className="w-80 shrink-0 border-l border-surface-border overflow-y-auto bg-surface">

          {error && (
            <div className="m-4 p-3 bg-brand/10 border border-brand/30 rounded-lg text-brand text-xs">
              {error}
            </div>
          )}

          {loading && <Skeleton />}

          {analysis && (
            <div className="p-4 space-y-3">
              <PrintabilityCard score={analysis.printability} />
              <ModelInfoCard analysis={analysis} />
              <ExplanationsCard report={analysis.explanations} />
              <OrientationCard report={analysis.orientation} />

              {/* Convert CTA */}
              <button
                onClick={() => router.push("/convert")}
                className="w-full py-2.5 bg-brand hover:bg-red-700 text-white font-semibold rounded-lg
                           transition-colors duration-150 text-sm flex items-center justify-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
                </svg>
                Convert this file
              </button>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
