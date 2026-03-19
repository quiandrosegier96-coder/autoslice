"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { isLoggedIn } from "@/lib/auth";
import { apiAnalyze, apiScoringReport, apiSupportPreview } from "@/lib/api";
import type { TreeSupportResult } from "@/lib/tree-support/types";
import type { ExtendedViewMode } from "@/components/viewer/TreeSupportPanel";
import {
  SupportDecisionCard,
  TreeStatsCard,
  OverhangAnalysisCard,
  ViewerControlsCard as TreeViewerControlsCard,
  DebugLegendCard,
} from "@/components/viewer/TreeSupportPanel";

const ModelViewer = dynamic(
  () => import("@/components/ModelViewer").then((m) => m.ModelViewer),
  {
    ssr: false,
    loading: () => (
      <div className="w-full h-full bg-[#111] flex items-center justify-center">
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

type NozzleRiskItem = {
  type:           string;
  severity:       "low" | "medium" | "high";
  reason:         string;
  recommendation: string;
};

type NozzleRiskReport = {
  has_risks:            boolean;
  risks:                NozzleRiskItem[];
  recommended_z_hop_mm: number;
  recommended_combing:  string;
  recommended_flow_pct: number;
};

type AnalysisResult = {
  job_id: string;
  archive: { filename: string; size_bytes: number };
  model: { part_count: number; unit: string };
  nozzle_risk: NozzleRiskReport;
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

// Scoring report (from /api/scoring/report/{jobId})
type ScoringDecisions = {
  support: {
    enabled: boolean;
    type: string;
    placement: string;
    density_percent: number;
    angle_threshold_deg: number;
    interface_enabled: boolean;
    interface_layers: number;
    top_z_distance_mm: number;
    xy_distance_mm: number;
  };
  brim: { enabled: boolean; width_mm: number };
  layer: { height_mm: number };
  walls: { count: number; top_layers: number; bottom_layers: number };
  infill: { percent: number; pattern: string };
  speed: { print_mm_s: number; fan_percent: number; min_layer_time_s: number };
  quality: { ironing_enabled: boolean; top_surface_pattern: string; seam_position: string };
  line_width: { line_width_mm: number; first_layer_width_mm: number; infill_width_mm: number };
};

type ScoringReport = {
  job_id: string;
  printer_id: string;
  filament: string;
  nozzle_mm: number;
  decisions: ScoringDecisions;
};

// Support preview (from /api/analyze/{jobId}/support-preview)
type SupportPreview = {
  job_id:           string;
  needs_supports:   boolean;
  support_type:     string;  // "none" | "normal" | "tree"
  placement:        string;
  overhang_area_mm2: number;
  column_count:     number;
  trunk_count:      number;  // tree: root trunk count
  tip_count:        number;  // tree: contact point count
};

// Viewer display mode — now unified with ExtendedViewMode
type ViewMode = ExtendedViewMode;

// Client-side G-code validation
type GcodeValidationResult = {
  status: "ok" | "warning" | "fixed" | "error" | "idle";
  hasM83: boolean;
  hasM82: boolean;
  g92e0Count: number;
  layerCount: number;
  lineCount: number;
  issues: string[];
  fixesApplied: string[];
  fixedGcode: string | null;
};

// ─── Score helpers ─────────────────────────────────────────────────────────────

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
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  const rem = m % 60;
  return rem === 0 ? `${h}h` : `${h}h ${rem}m`;
}

// ─── Client-side G-code validator ─────────────────────────────────────────────

const LAYER_MARKER_RE = /^\s*;(?:\s*LAYER[:\s_]|layer_change|LAYER_CHANGE|Z\s+CHANGE)/i;

function validateGcodeClientSide(text: string): GcodeValidationResult {
  const lines = text.split("\n");

  function stripComment(l: string) { const i = l.indexOf(";"); return i === -1 ? l : l.slice(0, i); }
  function hasCmd(cmd: string) { const re = new RegExp(`\\b${cmd}\\b`, "i"); return lines.some(l => re.test(stripComment(l))); }

  const hasM83 = hasCmd("M83");
  const hasM82 = hasCmd("M82");
  const layerIndices = lines.reduce<number[]>((acc, l, i) => { if (LAYER_MARKER_RE.test(l)) acc.push(i); return acc; }, []);
  const g92re = /\bG92\s+E0\b/i;
  const g92e0Count = lines.filter(l => g92re.test(stripComment(l))).length;

  const eRe = /\bE(-?\d+(?:\.\d+)?)\b/gi;
  let maxE = 0;
  for (const l of lines) {
    const code = stripComment(l);
    if (!(/^g[01]\b/i.test(code))) continue;
    let m: RegExpExecArray | null;
    while ((m = eRe.exec(code)) !== null) { const v = parseFloat(m[1]); if (v > maxE) maxE = v; }
  }

  const issues: string[] = [];
  const fixes: string[] = [];
  let fixedGcode: string | null = null;
  let status: GcodeValidationResult["status"] = "ok";

  if (hasM83) {
    if (g92e0Count === 0) {
      issues.push("Relative extruder mode (M83) detected — no G92 E0 reset found. Progressive extrusion drift will occur across every layer.");

      // Auto-fix: insert G92 E0 before each layer marker (reverse to preserve indices)
      const working = [...lines];
      const inject = "G92 E0 ; auto-injected — relative extrusion safety reset";
      for (let i = layerIndices.length - 1; i >= 0; i--) working.splice(layerIndices[i], 0, inject);
      // Also insert after M83
      const m83Idx = working.findIndex(l => /\bM83\b/i.test(stripComment(l)));
      if (m83Idx !== -1) {
        working.splice(m83Idx + 1, 0, "G92 E0 ; auto-injected after M83 — initial extruder reset");
        fixes.push("Inserted G92 E0 immediately after M83 (initial reset)");
      }
      fixes.push(`Inserted G92 E0 before ${layerIndices.length} layer change(s)`);
      fixedGcode = working.join("\n");
      status = "fixed";

    } else if (layerIndices.length > 10 && g92e0Count < layerIndices.length * 0.5) {
      issues.push(`M83 active: only ${g92e0Count} G92 E0 resets for ${layerIndices.length} layer changes — coverage < 50%.`);
      status = "warning";
    } else {
      issues.push(`Relative extrusion (M83) with ${g92e0Count} G92 E0 resets — coverage looks adequate.`);
    }
  } else if (hasM82) {
    if (g92e0Count > Math.max(layerIndices.length * 2, 10)) {
      issues.push(`Absolute extrusion (M82) with ${g92e0Count} resets — unusually high, may indicate duplicate post-processing scripts.`);
      status = "warning";
    }
    if (maxE > 100) {
      issues.push(`Very high absolute E value (E${maxE.toFixed(2)}) — possible missing reset after filament change.`);
      if (status === "ok") status = "warning";
    }
  } else if (lines.length > 50) {
    issues.push("No extrusion mode (M82 / M83) found — printer firmware default will be assumed.");
    status = "warning";
  }

  return { status, hasM83, hasM82, g92e0Count, layerCount: layerIndices.length, lineCount: lines.length, issues, fixesApplied: fixes, fixedGcode };
}

// ─── Shared atoms ──────────────────────────────────────────────────────────────

function SectionLabel({ children }: { children: React.ReactNode }) {
  return <p className="text-[10px] font-semibold text-zinc-600 uppercase tracking-widest mb-3">{children}</p>;
}

function ScoreBar({ label, value, compact = false }: { label: string; value: number; compact?: boolean }) {
  return (
    <div className="flex items-center gap-2">
      <span className={`text-zinc-500 shrink-0 ${compact ? "text-[10px] w-12" : "text-xs w-16"}`}>{label}</span>
      <div className="flex-1 h-1 bg-surface-elevated rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-500 ${scoreTrack(value)}`} style={{ width: `${value}%` }} />
      </div>
      <span className={`font-mono tabular-nums text-right ${compact ? "text-[10px] w-5" : "text-xs w-6"} ${scoreColor(value)}`}>{value}</span>
    </div>
  );
}

function IconCheck() {
  return <svg className="w-3.5 h-3.5 text-green-400 shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414L8.414 15 3.293 9.879a1 1 0 111.414-1.414L8.414 12.172l6.879-6.879a1 1 0 011.414 0z" clipRule="evenodd"/></svg>;
}
function IconWarn() {
  return <svg className="w-3.5 h-3.5 text-yellow-400 shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd"/></svg>;
}
function IconInfo() {
  return <svg className="w-3.5 h-3.5 text-blue-400 shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd"/></svg>;
}

// ─── Toggle switch ─────────────────────────────────────────────────────────────

function Toggle({
  label, sublabel, checked, onChange, accent = "brand", disabled = false,
}: { label: string; sublabel?: string; checked: boolean; onChange: (v: boolean) => void; accent?: "orange" | "blue" | "green" | "brand"; disabled?: boolean }) {
  const trackOn = accent === "orange" ? "bg-orange-500" : accent === "blue" ? "bg-blue-500" : accent === "green" ? "bg-green-500" : "bg-brand";
  return (
    <div className={`flex items-center justify-between py-2.5 select-none ${disabled ? "opacity-40 cursor-not-allowed" : "cursor-pointer"}`} onClick={() => !disabled && onChange(!checked)}>
      <div>
        <p className="text-xs text-zinc-300">{label}</p>
        {sublabel && <p className="text-[10px] text-zinc-600 mt-0.5">{sublabel}</p>}
      </div>
      <button role="switch" aria-checked={checked} disabled={disabled} onClick={e => { e.stopPropagation(); !disabled && onChange(!checked); }}
        className={`w-9 h-5 rounded-full transition-all duration-200 relative shrink-0 ml-3 ${checked ? trackOn : "bg-surface-elevated border border-surface-border"}`}>
        <span className={`absolute top-0.5 w-4 h-4 rounded-full shadow-sm transition-transform duration-200 ${checked ? "translate-x-[17px] bg-white" : "translate-x-0.5 bg-zinc-500"}`} />
      </button>
    </div>
  );
}

// ─── Card: Printability ───────────────────────────────────────────────────────

function PrintabilityCard({ score }: { score: PrintabilityScore }) {
  const diffColor =
    score.difficulty_label === "Easy"        ? "text-green-400  bg-green-500/10  border-green-500/20"  :
    score.difficulty_label === "Moderate"    ? "text-yellow-400 bg-yellow-500/10 border-yellow-500/20" :
    score.difficulty_label === "Challenging" ? "text-orange-400 bg-orange-500/10 border-orange-500/20" :
    "text-red-400 bg-red-500/10 border-red-500/20";

  return (
    <div className="bg-surface-card border border-surface-border rounded-2xl p-4">
      <SectionLabel>Printability Score</SectionLabel>
      <div className="flex items-end gap-2 mb-3">
        <span className={`text-5xl font-bold tabular-nums leading-none ${scoreColor(score.total)}`}>{score.total}</span>
        <span className="text-zinc-600 text-sm mb-1">/ 100</span>
        <span className={`ml-auto text-[10px] font-semibold px-2.5 py-1 rounded-full border ${diffColor}`}>{score.difficulty_label}</span>
      </div>
      <div className="w-full h-1.5 bg-surface-elevated rounded-full overflow-hidden mb-4">
        <div className={`h-full rounded-full transition-all duration-700 ${scoreTrack(score.total)}`} style={{ width: `${score.total}%` }} />
      </div>
      <div className="space-y-2">
        <ScoreBar label="Support"   value={score.support_score}   />
        <ScoreBar label="Adhesion"  value={score.adhesion_score}  />
        <ScoreBar label="Stability" value={score.stability_score} />
        <ScoreBar label="Detail"    value={score.detail_score}    />
        <ScoreBar label="Bridge"    value={score.bridge_score}    />
      </div>
      {score.warnings.length > 0 && (
        <div className="mt-3.5 pt-3.5 border-t border-surface-border space-y-2">
          {score.warnings.map((w, i) => (
            <div key={i} className="flex items-start gap-2"><IconWarn /><span className="text-xs text-zinc-500 leading-relaxed">{w}</span></div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Card: Generated Print Settings ──────────────────────────────────────────

function SettingRow({ label, value, mono = true }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-surface-border/30 last:border-0">
      <span className="text-[11px] text-zinc-500">{label}</span>
      <span className={`text-[11px] font-medium ${mono ? "font-mono text-zinc-200" : "text-zinc-300"}`}>{value}</span>
    </div>
  );
}

const FILAMENT_TEMPS: Record<string, { nozzle: number; bed: number }> = {
  pla:  { nozzle: 205, bed: 60  },
  petg: { nozzle: 235, bed: 70  },
  tpu:  { nozzle: 220, bed: 40  },
  abs:  { nozzle: 240, bed: 100 },
};

function GeneratedSettingsCard({
  decisions, filament, nozzleMm, explanations,
}: {
  decisions: ScoringDecisions;
  filament: string;
  nozzleMm: number;
  explanations: ExplanationReport;
}) {
  const [showExplanations, setShowExplanations] = useState(false);
  const temps = FILAMENT_TEMPS[filament?.toLowerCase()] ?? FILAMENT_TEMPS.pla;
  const d = decisions;
  const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

  const rows = [
    { label: "Layer Height",     value: `${d.layer.height_mm} mm`                                                  },
    { label: "Wall Count",       value: `${d.walls.count} perimeters`                                              },
    { label: "Top / Bottom",     value: `${d.walls.top_layers} / ${d.walls.bottom_layers} layers`                  },
    { label: "Infill",           value: `${d.infill.percent}% — ${cap(d.infill.pattern)}`                          },
    { label: "Supports",         value: d.support.enabled ? `${cap(d.support.type)} · ${d.support.density_percent}% · ${d.support.angle_threshold_deg}°` : "None" },
    { label: "Support placement",value: d.support.enabled ? cap(d.support.placement.replace("_", " ")) : "—"       },
    { label: "Brim",             value: d.brim.enabled ? `${d.brim.width_mm} mm` : "None"                          },
    { label: "Print Speed",      value: `${d.speed.print_mm_s} mm/s`                                               },
    { label: "Fan",              value: `${d.speed.fan_percent}%`                                                   },
    { label: "Min layer time",   value: `${d.speed.min_layer_time_s}s`                                             },
    { label: "Nozzle Temp",      value: `${temps.nozzle}°C`                                                        },
    { label: "Bed Temp",         value: `${temps.bed}°C`                                                           },
    { label: "Nozzle Diameter",  value: `${nozzleMm} mm`                                                           },
    { label: "Line Width",       value: `${d.line_width.line_width_mm} mm`                                         },
    { label: "Infill Width",     value: `${d.line_width.infill_width_mm} mm`                                       },
    { label: "First Layer Width",value: `${d.line_width.first_layer_width_mm} mm`                                  },
    { label: "Top Surface",      value: cap(d.quality.top_surface_pattern)                                         },
    { label: "Seam",             value: cap(d.quality.seam_position)                                               },
    { label: "Ironing",          value: d.quality.ironing_enabled ? "On" : "Off"                                   },
    { label: "Z gap (support)",  value: d.support.enabled ? `${d.support.top_z_distance_mm} mm` : "—"             },
    { label: "XY gap (support)", value: d.support.enabled ? `${d.support.xy_distance_mm} mm` : "—"                },
  ];

  const COLLAPSE_AT = 10;
  const visible = showExplanations ? explanations.items : explanations.items.slice(0, 3);

  return (
    <div className="bg-surface-card border border-surface-border rounded-2xl overflow-hidden">
      <div className="p-4">
        <div className="flex items-center justify-between mb-3">
          <SectionLabel>Generated Print Settings</SectionLabel>
          <span className="text-[9px] font-semibold text-brand/70 bg-brand/10 border border-brand/20 px-1.5 py-0.5 rounded-full uppercase tracking-wide -mt-1">
            AI · rule-based
          </span>
        </div>

        {/* Settings grid */}
        <div className="mb-4">
          {rows.slice(0, COLLAPSE_AT).map(r => <SettingRow key={r.label} {...r} />)}
          <details className="group">
            <summary className="text-[10px] text-zinc-600 hover:text-zinc-400 cursor-pointer py-1.5 select-none list-none flex items-center gap-1.5">
              <svg className="w-3 h-3 transition-transform group-open:rotate-90" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7"/>
              </svg>
              {rows.length - COLLAPSE_AT} more settings
            </summary>
            <div>
              {rows.slice(COLLAPSE_AT).map(r => <SettingRow key={r.label} {...r} />)}
            </div>
          </details>
        </div>

        {/* AI explanations */}
        {explanations.items.length > 0 && (
          <div className="pt-3.5 border-t border-surface-border">
            <p className="text-[10px] font-semibold text-zinc-600 uppercase tracking-widest mb-2.5">Why these settings</p>
            <div className="space-y-2.5">
              {visible.map(item => (
                <div key={item.setting} className="flex gap-2.5">
                  {item.icon === "check" ? <IconCheck /> : item.icon === "warning" ? <IconWarn /> : <IconInfo />}
                  <div className="min-w-0">
                    <div className="flex items-baseline gap-1.5 flex-wrap mb-0.5">
                      <span className="text-xs font-medium text-zinc-300">{item.setting}</span>
                      <span className="text-[10px] font-mono text-brand">{item.value}</span>
                    </div>
                    <p className="text-[11px] text-zinc-500 leading-relaxed">{item.reason}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
      {explanations.items.length > 3 && (
        <button onClick={() => setShowExplanations(e => !e)}
          className="w-full text-xs text-zinc-600 hover:text-zinc-400 py-2.5 border-t border-surface-border transition-colors hover:bg-surface-elevated/20">
          {showExplanations ? "Show fewer explanations" : `+${explanations.items.length - 3} more explanations`}
        </button>
      )}
    </div>
  );
}

// ─── Card: Support Analysis ────────────────────────────────────────────────────

function SupportAnalysisCard({ jobId, showSupports, onShowSupports }: {
  jobId: string;
  showSupports: boolean;
  onShowSupports: (v: boolean) => void;
}) {
  const [data, setData] = useState<SupportPreview | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiSupportPreview(jobId)
      .then(d => setData(d as SupportPreview))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [jobId]);

  if (loading) {
    return (
      <div className="bg-surface-card border border-surface-border rounded-2xl p-4 animate-pulse">
        <div className="h-2.5 rounded-full bg-surface-elevated w-28 mb-4" />
        <div className="space-y-2">
          {[80, 60, 70].map(w => <div key={w} className="h-2 rounded-full bg-surface-elevated" style={{ width: `${w}%` }} />)}
        </div>
      </div>
    );
  }

  if (!data) return null;

  const riskLevel = data.overhang_area_mm2 > 500 ? "high" : data.overhang_area_mm2 > 100 ? "medium" : "low";
  const riskColor = riskLevel === "high" ? "text-red-400 bg-red-500/10 border-red-500/20" :
                    riskLevel === "medium" ? "text-yellow-400 bg-yellow-500/10 border-yellow-500/20" :
                    "text-green-400 bg-green-500/10 border-green-500/20";

  const isTree = data.support_type === "tree";

  return (
    <div className="bg-surface-card border border-surface-border rounded-2xl p-4">
      <div className="flex items-center justify-between mb-3">
        <SectionLabel>Support Analysis</SectionLabel>
        <div className="flex items-center gap-1.5 -mt-1">
          {isTree && (
            <span className="text-[9px] font-bold px-2 py-0.5 rounded-full border text-amber-400 bg-amber-500/10 border-amber-500/20 uppercase tracking-wide">
              Tree
            </span>
          )}
          <span className={`text-[9px] font-semibold px-2 py-0.5 rounded-full border ${riskColor}`}>
            {riskLevel === "high" ? "High need" : riskLevel === "medium" ? "Moderate" : "Low need"}
          </span>
        </div>
      </div>

      {!data.needs_supports ? (
        <div className="flex items-center gap-2.5 py-2">
          <div className="w-7 h-7 rounded-full bg-green-500/10 border border-green-500/20 flex items-center justify-center shrink-0">
            <IconCheck />
          </div>
          <div>
            <p className="text-xs font-medium text-green-400">No supports needed</p>
            <p className="text-[11px] text-zinc-600">This model can print without support structures.</p>
          </div>
        </div>
      ) : (
        <div className="space-y-2 mb-3">
          {/* Stats grid */}
          {isTree ? (
            <div className="grid grid-cols-3 gap-1.5">
              {[
                { label: "Trunks",       value: String(data.trunk_count) },
                { label: "Contact tips", value: String(data.tip_count)   },
                { label: "Overhang",     value: `${data.overhang_area_mm2.toFixed(0)} mm²` },
              ].map(s => (
                <div key={s.label} className="bg-surface-elevated rounded-xl p-2 text-center">
                  <p className="text-[10px] text-zinc-600 mb-0.5">{s.label}</p>
                  <p className="text-xs font-bold font-mono text-zinc-200">{s.value}</p>
                </div>
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-2">
              <div className="bg-surface-elevated rounded-xl p-2.5">
                <p className="text-[10px] text-zinc-600 mb-1">Columns</p>
                <p className="text-sm font-bold text-zinc-200 tabular-nums">{data.column_count}</p>
              </div>
              <div className="bg-surface-elevated rounded-xl p-2.5">
                <p className="text-[10px] text-zinc-600 mb-1">Overhang area</p>
                <p className="text-sm font-bold text-zinc-200 tabular-nums">{data.overhang_area_mm2.toFixed(0)} mm²</p>
              </div>
            </div>
          )}

          <div className="space-y-0">
            {[
              { label: "Support type", value: isTree ? "Tree (organic branching)" : "Normal (buildplate columns)" },
              { label: "Placement",    value: data.placement.replace("_", " ") },
            ].map(r => (
              <div key={r.label} className="flex items-center justify-between py-1.5 border-b border-surface-border/30 last:border-0">
                <span className="text-[11px] text-zinc-500">{r.label}</span>
                <span className="text-[11px] font-medium text-zinc-300 capitalize">{r.value}</span>
              </div>
            ))}
          </div>

          {/* Tree support explanation */}
          {isTree && (
            <div className="mt-1 p-2.5 bg-amber-500/5 border border-amber-500/15 rounded-xl space-y-1.5">
              <p className="text-[10px] font-semibold text-amber-400/80 uppercase tracking-wide">Why tree supports?</p>
              {[
                "Isolated overhang islands detected — organic branches reach them more efficiently than columns.",
                "Reduced contact surface minimises scarring on visible faces.",
                "Branching trunks share material, lowering overall support volume.",
              ].map((t, i) => (
                <div key={i} className="flex items-start gap-1.5">
                  <svg className="w-3 h-3 text-amber-500/60 shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414L8.414 15 3.293 9.879a1 1 0 111.414-1.414L8.414 12.172l6.879-6.879a1 1 0 011.414 0z" clipRule="evenodd"/>
                  </svg>
                  <p className="text-[10px] text-zinc-500 leading-relaxed">{t}</p>
                </div>
              ))}
            </div>
          )}

          {/* Risk warning if supports disabled */}
          {!showSupports && (
            <div className="mt-2 flex items-start gap-2 p-2.5 bg-yellow-500/5 border border-yellow-500/20 rounded-xl">
              <IconWarn />
              <p className="text-[11px] text-yellow-300/80 leading-relaxed">
                Support preview is off. The model has unsupported overhangs that may fail without supports.
              </p>
            </div>
          )}
        </div>
      )}

      {/* Toggle */}
      <div className="pt-3 border-t border-surface-border/50">
        <Toggle
          label="Support preview"
          sublabel="Show overhang regions in viewer"
          checked={showSupports}
          onChange={onShowSupports}
          accent="orange"
        />
      </div>
    </div>
  );
}

// ─── Card: G-code Validator ───────────────────────────────────────────────────

function GcodeValidationCard({ onResult }: { onResult: (r: GcodeValidationResult | null) => void }) {
  const [open, setOpen]         = useState(false);
  const [gcode, setGcode]       = useState("");
  const [running, setRunning]   = useState(false);
  const [result, setResult]     = useState<GcodeValidationResult | null>(null);
  const fileRef                 = useRef<HTMLInputElement>(null);

  function handleValidate() {
    if (!gcode.trim()) return;
    setRunning(true);
    // Client-side — synchronous, but wrap in setTimeout to allow spinner render
    setTimeout(() => {
      const r = validateGcodeClientSide(gcode);
      setResult(r);
      onResult(r);
      setRunning(false);
    }, 80);
  }

  function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = ev => { setGcode(ev.target?.result as string ?? ""); setResult(null); };
    reader.readAsText(file);
  }

  function downloadFixed() {
    if (!result?.fixedGcode) return;
    const blob = new Blob([result.fixedGcode], { type: "text/plain" });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href = url; a.download = "validated_fixed.gcode"; a.click();
    URL.revokeObjectURL(url);
  }

  const statusMeta: Record<string, { label: string; cls: string }> = {
    ok:      { label: "Valid — safe to export",     cls: "text-green-400  bg-green-500/10  border-green-500/20"  },
    warning: { label: "Warnings — review before export", cls: "text-yellow-400 bg-yellow-500/10 border-yellow-500/20" },
    fixed:   { label: "Auto-corrected — safe to export", cls: "text-blue-400   bg-blue-500/10   border-blue-500/20"   },
    error:   { label: "Critical error — export blocked", cls: "text-red-400    bg-red-500/10    border-red-500/20"    },
  };

  return (
    <div className="bg-surface-card border border-surface-border rounded-2xl overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between p-4 text-left hover:bg-surface-elevated/20 transition-colors"
      >
        <div>
          <p className="text-[10px] font-semibold text-zinc-600 uppercase tracking-widest mb-0.5">G-code Validator</p>
          <p className="text-xs text-zinc-500">Check &amp; auto-fix M83 / G92 E0 issues</p>
        </div>
        <div className="flex items-center gap-2">
          {result && (
            <span className={`text-[9px] font-semibold px-2 py-0.5 rounded-full border ${statusMeta[result.status]?.cls ?? ""}`}>
              {result.status.toUpperCase()}
            </span>
          )}
          <svg className={`w-4 h-4 text-zinc-600 transition-transform ${open ? "rotate-180" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7"/>
          </svg>
        </div>
      </button>

      {open && (
        <div className="border-t border-surface-border">
          {/* Input area */}
          <div className="p-4 space-y-3">
            <div className="flex items-center gap-2 mb-1">
              <p className="text-xs text-zinc-400 flex-1">Paste G-code or upload a .gcode file</p>
              <button
                onClick={() => fileRef.current?.click()}
                className="text-[10px] text-zinc-500 hover:text-zinc-300 border border-surface-border rounded-lg px-2 py-1 transition-colors hover:border-zinc-500"
              >
                Upload file
              </button>
              <input ref={fileRef} type="file" accept=".gcode,.gco,.nc" className="hidden" onChange={handleFileUpload} />
            </div>

            <textarea
              value={gcode}
              onChange={e => { setGcode(e.target.value); setResult(null); }}
              placeholder="; Generated by OrcaSlicer&#10;M83&#10;G28&#10;; LAYER:0&#10;G1 X10 Y10 E1.2..."
              rows={7}
              className="w-full text-[11px] font-mono text-zinc-300 bg-surface-elevated border border-surface-border rounded-xl
                         p-3 resize-none focus:outline-none focus:border-zinc-500 placeholder:text-zinc-700
                         leading-relaxed scrollbar-thin"
            />

            <div className="flex items-center gap-2">
              <button
                onClick={handleValidate}
                disabled={!gcode.trim() || running}
                className="flex-1 py-2 rounded-xl bg-brand hover:bg-red-700 disabled:opacity-40 disabled:cursor-not-allowed
                           text-white text-xs font-semibold transition-colors flex items-center justify-center gap-2"
              >
                {running ? (
                  <><div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" /> Analyzing…</>
                ) : (
                  <><svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>Validate &amp; Fix</>
                )}
              </button>
              {gcode && (
                <button onClick={() => { setGcode(""); setResult(null); }}
                  className="px-3 py-2 rounded-xl border border-surface-border text-zinc-500 text-xs hover:text-zinc-300 hover:border-zinc-500 transition-colors">
                  Clear
                </button>
              )}
            </div>
          </div>

          {/* Results */}
          {result && (
            <div className="border-t border-surface-border p-4 space-y-3">
              {/* Status banner */}
              <div className={`flex items-center gap-2.5 p-3 rounded-xl border ${statusMeta[result.status]?.cls ?? ""}`}>
                <svg className="w-4 h-4 shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  {result.status === "ok" || result.status === "fixed" ? (
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd"/>
                  ) : (
                    <path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd"/>
                  )}
                </svg>
                <p className="text-xs font-semibold">{statusMeta[result.status]?.label}</p>
              </div>

              {/* File stats */}
              <div className="grid grid-cols-3 gap-1.5">
                {[
                  { label: "Lines",    value: result.lineCount.toLocaleString() },
                  { label: "Layers",   value: result.layerCount.toLocaleString() },
                  { label: "G92 E0",   value: result.g92e0Count.toLocaleString() },
                ].map(s => (
                  <div key={s.label} className="bg-surface-elevated rounded-xl p-2 text-center">
                    <p className="text-[10px] text-zinc-600 mb-0.5">{s.label}</p>
                    <p className="text-xs font-bold font-mono text-zinc-300">{s.value}</p>
                  </div>
                ))}
              </div>

              {/* Extrusion mode badges */}
              <div className="flex gap-2">
                <span className={`text-[10px] font-semibold px-2.5 py-1 rounded-full border ${result.hasM83 ? "text-yellow-400 bg-yellow-500/10 border-yellow-500/20" : "text-zinc-600 border-surface-border"}`}>
                  M83 {result.hasM83 ? "detected" : "absent"}
                </span>
                <span className={`text-[10px] font-semibold px-2.5 py-1 rounded-full border ${result.hasM82 ? "text-green-400 bg-green-500/10 border-green-500/20" : "text-zinc-600 border-surface-border"}`}>
                  M82 {result.hasM82 ? "detected" : "absent"}
                </span>
              </div>

              {/* Issues */}
              {result.issues.length > 0 && (
                <div className="space-y-1.5">
                  <p className="text-[10px] font-semibold text-zinc-600 uppercase tracking-wide">Issues found</p>
                  {result.issues.map((issue, i) => (
                    <div key={i} className="flex items-start gap-2">
                      <IconWarn />
                      <p className="text-[11px] text-zinc-400 leading-relaxed">{issue}</p>
                    </div>
                  ))}
                </div>
              )}

              {/* Fixes */}
              {result.fixesApplied.length > 0 && (
                <div className="space-y-1.5">
                  <p className="text-[10px] font-semibold text-zinc-600 uppercase tracking-wide">Auto-fixes applied</p>
                  {result.fixesApplied.map((fix, i) => (
                    <div key={i} className="flex items-start gap-2">
                      <IconCheck />
                      <p className="text-[11px] text-zinc-300 leading-relaxed">{fix}</p>
                    </div>
                  ))}
                  <div className="mt-1 p-2.5 bg-surface-elevated border border-surface-border rounded-xl">
                    <code className="text-[10px] text-green-400 font-mono">
                      G92 E0 ; auto-injected — relative extrusion safety reset
                    </code>
                  </div>
                </div>
              )}

              {/* Download fixed */}
              {result.fixedGcode && (
                <button
                  onClick={downloadFixed}
                  className="w-full py-2 rounded-xl bg-green-500/10 border border-green-500/30 text-green-400 text-xs font-semibold
                             hover:bg-green-500/15 transition-colors flex items-center justify-center gap-2"
                >
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
                  </svg>
                  Download corrected G-code
                </button>
              )}

              {/* Clean state */}
              {result.status === "ok" && result.issues.length === 0 && (
                <p className="text-center text-xs text-green-400/70">No issues detected — this G-code is safe to export.</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Card: Model Info ─────────────────────────────────────────────────────────

function ModelInfoCard({ analysis }: { analysis: AnalysisResult }) {
  const geo = analysis.geometry;
  const bb  = geo.bounding_box;
  return (
    <div className="bg-surface-card border border-surface-border rounded-2xl p-4">
      <SectionLabel>Model Info</SectionLabel>

      {/* Dimension chips */}
      <div className="grid grid-cols-3 gap-1.5 mb-3">
        {([
          { label: "Width",  value: `${bb.x_mm}` },
          { label: "Depth",  value: `${bb.y_mm}` },
          { label: "Height", value: `${bb.z_mm}` },
        ] as { label: string; value: string }[]).map(s => (
          <div key={s.label} className="bg-surface-elevated rounded-xl p-2 text-center">
            <p className="text-[10px] text-zinc-600 mb-0.5">{s.label}</p>
            <p className="text-xs font-bold font-mono text-zinc-200">{s.value}<span className="text-zinc-600 text-[9px] ml-0.5">mm</span></p>
          </div>
        ))}
      </div>

      {/* Detail rows */}
      <div className="space-y-0">
        {([
          { label: "Volume",       value: `${geo.estimated_volume_cm3.toFixed(1)} cm³`                     },
          { label: "Surface area", value: `${(geo.surface_area_mm2 / 100).toFixed(0)} cm²`                 },
          { label: "Parts",        value: `${geo.part_count}`                                               },
          { label: "Overhangs",    value: geo.overhang.has_overhangs ? `${geo.overhang.max_angle_deg.toFixed(0)}° max` : "None" },
          { label: "Bridges",      value: geo.bridge.has_bridges ? `${geo.bridge.max_span_mm.toFixed(1)} mm span` : "None"     },
          { label: "Thin walls",   value: geo.thin_wall.has_thin_walls ? `${geo.thin_wall.min_thickness_mm.toFixed(1)} mm min` : "None" },
        ] as { label: string; value: string }[]).map(r => (
          <div key={r.label} className="flex items-center justify-between py-1.5 border-b border-surface-border/30 last:border-0">
            <span className="text-[11px] text-zinc-500">{r.label}</span>
            <span className="text-[11px] font-mono font-medium text-zinc-200">{r.value}</span>
          </div>
        ))}
      </div>

      {/* Mesh quality */}
      <div className="mt-3 pt-3 border-t border-surface-border flex items-center gap-2">
        <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${geo.mesh_is_watertight ? "bg-green-500" : "bg-yellow-500"}`} />
        <span className="text-[10px] text-zinc-500 leading-snug">
          {geo.mesh_is_watertight ? "Watertight mesh — slicing will be reliable" : "Non-watertight mesh — may affect slicing accuracy"}
        </span>
      </div>
    </div>
  );
}

// ─── Card: Export Preflight ────────────────────────────────────────────────────

function ExportPreflightCard({
  scoring, gcodeResult, onConvert,
}: {
  scoring:     ScoringReport | null;
  gcodeResult: GcodeValidationResult | null;
  onConvert:   () => void;
}) {
  const gcodeBlocked = gcodeResult?.status === "error";
  const gcodeFixed   = gcodeResult?.status === "fixed";
  const gcodeWarn    = gcodeResult?.status === "warning";
  const gcodeOk      = gcodeResult?.status === "ok";

  const steps = [
    {
      label:   "Geometry analyzed",
      done:    true,
      warning: false,
      pending: false,
    },
    {
      label:   scoring ? "Print settings generated" : "Print settings — convert to generate",
      done:    !!scoring,
      warning: false,
      pending: !scoring,
    },
    {
      label:   gcodeResult
        ? gcodeFixed   ? "G-code auto-corrected — safe to export"
        : gcodeOk      ? "G-code validated — no issues"
        : gcodeWarn    ? "G-code warnings — review before export"
        : gcodeBlocked ? "G-code error — export blocked"
        : "G-code status unknown"
        : "G-code not validated",
      done:    gcodeOk || gcodeFixed,
      warning: gcodeWarn,
      pending: !gcodeResult,
      error:   gcodeBlocked,
    },
  ];

  const bannerCls = gcodeBlocked ? "text-red-400 bg-red-500/10 border-red-500/20" :
    gcodeFixed                   ? "text-blue-400 bg-blue-500/10 border-blue-500/20" :
    gcodeWarn                    ? "text-yellow-400 bg-yellow-500/10 border-yellow-500/20" :
    gcodeOk                      ? "text-green-400 bg-green-500/10 border-green-500/20" :
    "text-zinc-500 bg-surface-elevated border-surface-border";

  const bannerLabel = gcodeBlocked ? "Export blocked — fix G-code errors first" :
    gcodeFixed                     ? "Export with auto-fix applied" :
    gcodeWarn                      ? "Export with warnings — review recommended" :
    gcodeOk                        ? "Ready to export" :
    "Validate G-code below before exporting";

  return (
    <div className="bg-surface-card border border-surface-border rounded-2xl p-4">
      <SectionLabel>Export Readiness</SectionLabel>

      {/* Checklist */}
      <div className="space-y-2.5 mb-4">
        {steps.map((step, i) => {
          const dotCls = step.error   ? "bg-red-500/10 border-red-500/20"
            : step.done              ? "bg-green-500/10 border-green-500/20"
            : step.warning           ? "bg-yellow-500/10 border-yellow-500/20"
            : "bg-surface-elevated border-surface-border";
          const textCls = step.error  ? "text-red-400/80"
            : step.done              ? "text-zinc-300"
            : step.warning           ? "text-yellow-400/80"
            : "text-zinc-600";
          return (
            <div key={i} className="flex items-center gap-2.5">
              <div className={`w-5 h-5 rounded-full flex items-center justify-center shrink-0 border ${dotCls}`}>
                {step.done    ? <IconCheck /> :
                 step.warning ? <IconWarn /> :
                 step.error   ? <svg className="w-3.5 h-3.5 text-red-400" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd"/></svg> :
                 <span className="w-1.5 h-1.5 rounded-full bg-zinc-600" />}
              </div>
              <span className={`text-xs leading-snug ${textCls}`}>{step.label}</span>
            </div>
          );
        })}
      </div>

      {/* Status banner */}
      <div className={`flex items-center gap-2 p-2.5 rounded-xl border mb-3 text-xs font-medium ${bannerCls}`}>
        {bannerLabel}
      </div>

      {/* CTA */}
      <button
        onClick={onConvert}
        disabled={gcodeBlocked}
        className={`w-full py-3 font-semibold rounded-xl transition-colors duration-150 text-sm flex items-center justify-center gap-2 ${
          gcodeBlocked
            ? "bg-red-500/10 border border-red-500/20 text-red-400/60 cursor-not-allowed"
            : "bg-brand hover:bg-red-700 active:bg-red-800 text-white shadow-lg shadow-brand/20"
        }`}
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
        </svg>
        {gcodeBlocked ? "Export blocked" : gcodeFixed ? "Convert (auto-fix applied)" : "Convert this file"}
      </button>

      {!scoring && (
        <p className="text-center text-[10px] text-zinc-600 mt-2">Converting also generates your final print settings</p>
      )}
    </div>
  );
}

// ─── Card: Nozzle Collision Risk ──────────────────────────────────────────────

const RISK_TYPE_LABELS: Record<string, string> = {
  overhang_curl:  "Overhang Curl",
  bridge_droop:   "Bridge Droop",
  tower_sway:     "Tower Sway",
  travel_scrape:  "Travel Scrape",
};

function NozzleRiskCard({ report }: { report: NozzleRiskReport }) {
  const [expanded, setExpanded] = useState<string | null>(null);

  if (!report.has_risks) {
    return (
      <div className="bg-surface-card border border-surface-border rounded-2xl p-4">
        <SectionLabel>Nozzle Collision Risk</SectionLabel>
        <div className="flex items-center gap-2.5 py-1">
          <div className="w-7 h-7 rounded-full bg-green-500/10 border border-green-500/20 flex items-center justify-center shrink-0">
            <IconCheck />
          </div>
          <div>
            <p className="text-xs font-medium text-green-400">Low nozzle collision risk</p>
            <p className="text-[11px] text-zinc-600">No significant scraping risks detected.</p>
          </div>
        </div>
      </div>
    );
  }

  const maxSev = report.risks.some(r => r.severity === "high") ? "high"
    : report.risks.some(r => r.severity === "medium") ? "medium" : "low";

  const headerCls = maxSev === "high"   ? "text-red-400    bg-red-500/10    border-red-500/20"
    : maxSev === "medium" ? "text-yellow-400 bg-yellow-500/10 border-yellow-500/20"
    : "text-zinc-400 bg-surface-elevated border-surface-border";

  const sevDot = (s: "low" | "medium" | "high") =>
    s === "high"   ? "bg-red-500"    :
    s === "medium" ? "bg-yellow-500" : "bg-zinc-500";

  return (
    <div className="bg-surface-card border border-surface-border rounded-2xl overflow-hidden">
      <div className="p-4">
        <div className="flex items-center justify-between mb-3">
          <SectionLabel>Nozzle Collision Risk</SectionLabel>
          <span className={`text-[9px] font-semibold px-2 py-0.5 rounded-full border -mt-1 ${headerCls}`}>
            {maxSev.charAt(0).toUpperCase() + maxSev.slice(1)}
          </span>
        </div>

        {/* Risk list */}
        <div className="space-y-1.5 mb-3">
          {report.risks.map(risk => (
            <div key={risk.type}>
              <button
                onClick={() => setExpanded(expanded === risk.type ? null : risk.type)}
                className="w-full flex items-center gap-2.5 py-2 px-2.5 rounded-xl hover:bg-surface-elevated transition-colors text-left"
              >
                <span className={`w-2 h-2 rounded-full shrink-0 ${sevDot(risk.severity)}`} />
                <span className="text-xs text-zinc-300 flex-1">{RISK_TYPE_LABELS[risk.type] ?? risk.type}</span>
                <svg className={`w-3.5 h-3.5 text-zinc-600 transition-transform ${expanded === risk.type ? "rotate-180" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7"/>
                </svg>
              </button>
              {expanded === risk.type && (
                <div className="mx-2 mb-1.5 px-3 py-2.5 bg-surface-elevated rounded-xl space-y-2">
                  <p className="text-[11px] text-zinc-400 leading-relaxed">{risk.reason}</p>
                  <div className="flex items-start gap-1.5 pt-1 border-t border-surface-border/40">
                    <svg className="w-3 h-3 text-brand shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd"/>
                    </svg>
                    <p className="text-[11px] text-zinc-500 leading-relaxed">{risk.recommendation}</p>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Auto-fix recommendations */}
        <div className="pt-3 border-t border-surface-border space-y-1.5">
          <p className="text-[10px] font-semibold text-zinc-600 uppercase tracking-widest mb-2">Recommended fixes</p>
          {[
            report.recommended_z_hop_mm > 0 && {
              label: "Z-hop",
              value: `${report.recommended_z_hop_mm} mm`,
              cls:   "text-blue-400  bg-blue-500/10  border-blue-500/20",
            },
            report.recommended_combing !== "off" && {
              label: "Combing",
              value: report.recommended_combing === "not_in_skin" ? "Not in skin" : "All",
              cls:   "text-purple-400 bg-purple-500/10 border-purple-500/20",
            },
            report.recommended_flow_pct < 100 && {
              label: "Flow",
              value: `${report.recommended_flow_pct}%`,
              cls:   "text-orange-400 bg-orange-500/10 border-orange-500/20",
            },
          ].filter(Boolean).map(fix => fix && (
            <div key={fix.label} className="flex items-center justify-between">
              <span className="text-[11px] text-zinc-500">{fix.label}</span>
              <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${fix.cls}`}>{fix.value}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Card: Viewer Controls ─────────────────────────────────────────────────────

function ViewerControlsCard({
  showSupports, onShowSupports,
  wireframe, onWireframe,
  showOverhangZones, onShowOverhangZones,
  hasOverhangs,
  onApplyOrientation, orientationFeedback, shouldRotate,
}: {
  showSupports: boolean; onShowSupports: (v: boolean) => void;
  wireframe: boolean; onWireframe: (v: boolean) => void;
  showOverhangZones: boolean; onShowOverhangZones: (v: boolean) => void;
  hasOverhangs: boolean;
  onApplyOrientation: () => void; orientationFeedback: "idle" | "applied"; shouldRotate: boolean;
}) {
  return (
    <div className="bg-surface-card border border-surface-border rounded-2xl p-4">
      <SectionLabel>Viewer Controls</SectionLabel>
      <div className="divide-y divide-surface-border/40">
        {hasOverhangs && (
          <Toggle label="Support preview" sublabel="Highlight unsupported regions" checked={showSupports} onChange={onShowSupports} accent="orange" />
        )}
        <Toggle label="Wireframe mode" checked={wireframe} onChange={onWireframe} accent="blue" />
        {hasOverhangs && (
          <Toggle label="Show overhang zones" sublabel="Blue overlay on overhang faces" checked={showOverhangZones} onChange={onShowOverhangZones} />
        )}
        <Toggle label="Show bounding box" sublabel="Coming soon" checked={false} onChange={() => {}} disabled />
      </div>
      <div className="mt-4 pt-4 border-t border-surface-border">
        <button
          onClick={onApplyOrientation}
          disabled={!shouldRotate || orientationFeedback === "applied"}
          className={`w-full py-2.5 rounded-xl text-xs font-medium transition-all duration-200 flex items-center justify-center gap-2 ${
            orientationFeedback === "applied"
              ? "bg-green-500/10 border border-green-500/30 text-green-400"
              : shouldRotate
              ? "bg-surface-elevated border border-surface-border text-zinc-300 hover:border-green-500/40 hover:text-green-400 hover:bg-green-500/5"
              : "bg-surface-elevated border border-surface-border text-zinc-600 cursor-not-allowed opacity-50"
          }`}
        >
          {orientationFeedback === "applied" ? (
            <><IconCheck /> Orientation applied</>
          ) : (
            <><svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>Apply optimized orientation</>
          )}
        </button>
        {!shouldRotate && <p className="text-center text-[10px] text-zinc-600 mt-2">Already in optimal orientation</p>}
      </div>
    </div>
  );
}

// ─── Orientation strip ─────────────────────────────────────────────────────────

function OrientationCard({ candidate, isBest, isOriginal, mins, timeSaved }: {
  candidate: OrientationCandidate; isBest: boolean; isOriginal: boolean; mins: number; timeSaved: number;
}) {
  return (
    <div className={`w-[185px] shrink-0 rounded-2xl border flex flex-col p-3.5 transition-all duration-200 ${
      isBest ? "border-green-500/50 bg-green-500/[0.04] shadow-[0_0_0_1px_rgba(34,197,94,0.12),0_4px_24px_rgba(34,197,94,0.06)]"
             : "border-surface-border bg-surface-card"
    }`}>
      <div className="flex items-start justify-between mb-2">
        <div>
          <p className={`text-xs font-semibold leading-none mb-1 ${isBest ? "text-green-400" : "text-zinc-300"}`}>{candidate.label}</p>
          {isOriginal && !isBest && <span className="text-[9px] text-zinc-600 font-medium">current</span>}
        </div>
        <span className={`text-xl font-bold tabular-nums leading-none ${scoreColor(candidate.total_score)}`}>{candidate.total_score}</span>
      </div>
      {isBest && (
        <div className="mb-2.5">
          <span className="inline-flex items-center gap-1 text-[9px] font-bold text-green-400 bg-green-500/10 border border-green-500/20 px-2 py-0.5 rounded-full uppercase tracking-wide">
            <svg className="w-2.5 h-2.5" fill="currentColor" viewBox="0 0 20 20"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/></svg>
            Best choice
          </span>
        </div>
      )}
      <div className="space-y-1.5 flex-1 mb-3">
        <ScoreBar label="Support"   value={candidate.support_score}   compact />
        <ScoreBar label="Adhesion"  value={candidate.adhesion_score}  compact />
        <ScoreBar label="Stability" value={candidate.stability_score} compact />
      </div>
      <div className="pt-2.5 border-t border-surface-border/50 space-y-1.5">
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-zinc-600">
            {candidate.overhang_area_ratio === 0 ? "No overhangs" : `${(candidate.overhang_area_ratio * 100).toFixed(0)}% overhang`}
          </span>
          <span className="text-[10px] text-zinc-500">{candidate.height_mm.toFixed(0)} mm</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-medium text-zinc-400">~{fmtMins(mins)}</span>
          {isBest && timeSaved > 5 && <span className="text-[10px] font-medium text-green-500">saves {fmtMins(timeSaved)}</span>}
        </div>
      </div>
    </div>
  );
}

function OrientationStrip({ report }: { report: OrientationReport }) {
  const candidates = report.all_candidates ?? [];
  if (candidates.length === 0) return null;
  const times    = candidates.map(estimatePrintMins);
  const worstTime = Math.max(...times);
  return (
    <div className="h-full overflow-x-auto">
      <div className="flex items-stretch gap-3 px-4 py-3 h-full min-w-max">
        <div className="flex flex-col justify-center pr-4 border-r border-surface-border shrink-0 min-w-[100px]">
          <p className="text-[10px] font-semibold text-zinc-600 uppercase tracking-widest mb-1">Orientation</p>
          <p className="text-[10px] text-zinc-500">Comparison</p>
          {report.should_rotate && (
            <div className="mt-2">
              <span className="text-[9px] font-semibold text-brand bg-brand/10 border border-brand/20 px-1.5 py-0.5 rounded-full">
                Rotation suggested
              </span>
            </div>
          )}
        </div>
        {candidates.map((c, i) => (
          <OrientationCard key={c.label} candidate={c}
            isBest={c.label === report.recommended.label && report.should_rotate}
            isOriginal={c.label === report.original.label}
            mins={times[i]} timeSaved={worstTime - times[i]} />
        ))}
      </div>
    </div>
  );
}

// ─── Loading skeleton ──────────────────────────────────────────────────────────

function Skeleton() {
  return (
    <div className="p-4 space-y-3 animate-pulse">
      {[[80, 100, 60, 70], [70, 100, 50], [60, 80]].map((widths, i) => (
        <div key={i} className="bg-surface-card border border-surface-border rounded-2xl p-4 space-y-2.5">
          {widths.map((w, j) => <div key={j} className="h-2.5 rounded-full bg-surface-elevated" style={{ width: `${w}%` }} />)}
        </div>
      ))}
    </div>
  );
}

// ─── Viewer overlay button ─────────────────────────────────────────────────────

function ViewerBtn({ onClick, active = false, activeClass = "bg-orange-500/20 border-orange-500/40 text-orange-300", children }: {
  onClick: () => void; active?: boolean; activeClass?: string; children: React.ReactNode;
}) {
  return (
    <button onClick={onClick} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs transition-all backdrop-blur-sm ${
      active ? activeClass : "bg-black/60 border-white/10 text-zinc-400 hover:text-zinc-200 hover:border-white/20 hover:bg-black/80"
    }`}>{children}</button>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function ViewerPage() {
  const params = useParams<{ jobId: string }>();
  const jobId  = params.jobId;
  const router = useRouter();

  const [analysis,     setAnalysis]     = useState<AnalysisResult | null>(null);
  const [scoring,      setScoring]      = useState<ScoringReport | null>(null);
  const [loading,      setLoading]      = useState(true);
  const [error,        setError]        = useState("");
  const [viewMode,          setViewMode]          = useState<ViewMode>("model");
  const [wireframe,         setWireframe]         = useState(false);
  const [showOverhangZones, setShowOverhangZones] = useState(false);
  const [resetKey,          setResetKey]          = useState(0);
  const [orientationFeedback, setOrientationFeedback] = useState<"idle" | "applied">("idle");
  const [gcodeResult, setGcodeResult]                 = useState<GcodeValidationResult | null>(null);

  // Tree support state
  const [treeResult,        setTreeResult]        = useState<TreeSupportResult | null>(null);
  const [animPlaying,       setAnimPlaying]       = useState(false);
  const [animProgress,      setAnimProgress]      = useState(0);
  const [animSpeed,         setAnimSpeed]         = useState(1);
  const [selectedSegmentId, setSelectedSegmentId] = useState<number | null>(null);
  const [selectedNodeId,    setSelectedNodeId]    = useState<number | null>(null);

  // Derived viewer props from viewMode (kept for legacy backend viz)
  const showSupports   = viewMode !== "model" && viewMode !== "debug-graph";
  const modelOpacity   = viewMode === "supports" ? 0.0 : viewMode === "transparent+supports" ? 0.18 : 1.0;
  const heatmapOnly    = viewMode === "heatmap";

  // Sync overhang zone debug toggle with view mode
  useEffect(() => { if (showOverhangZones) setViewMode(v => v === "model" ? "model+supports" : v); }, [showOverhangZones]);

  // Animation auto-stop at end
  useEffect(() => { if (animProgress >= 1) setAnimPlaying(false); }, [animProgress]);

  const debugMode = typeof window !== "undefined" && new URLSearchParams(window.location.search).get("debug") === "1";
  const debugLayers = { showAllOverhangs: showOverhangZones, showActiveCandidates: false, showFilteredCandidates: false };

  useEffect(() => {
    if (!isLoggedIn()) { router.push("/login"); return; }
    // Fetch analysis + scoring in parallel
    Promise.all([
      apiAnalyze(jobId),
      apiScoringReport(jobId).catch(() => null),
    ]).then(([a, s]) => {
      setAnalysis(a as AnalysisResult);
      if (s) setScoring(s as ScoringReport);
      setLoading(false);
    }).catch((e: unknown) => {
      setError(e instanceof Error ? e.message : "Analysis failed");
      setLoading(false);
    });
  }, [jobId, router]);

  const handleApplyOrientation = useCallback(() => {
    setOrientationFeedback("applied");
    setTimeout(() => setOrientationFeedback("idle"), 2500);
  }, []);

  const filename   = analysis?.archive.filename ?? "model.3mf";
  const geo        = analysis?.geometry;
  const intent     = analysis?.intent;
  const hasOrient  = (analysis?.orientation?.all_candidates?.length ?? 0) > 1;

  const diffColor =
    intent?.difficulty === "easy"     ? "text-green-400  bg-green-500/10  border-green-500/20"  :
    intent?.difficulty === "moderate" ? "text-yellow-400 bg-yellow-500/10 border-yellow-500/20" :
    intent?.difficulty               ? "text-red-400    bg-red-500/10    border-red-500/20"    : "";

  const statusBadge = analysis
    ? geo?.overhang.has_overhangs
      ? { label: "Supports analyzed",  cls: "text-yellow-400 bg-yellow-500/10 border-yellow-500/20" }
      : { label: "No supports needed", cls: "text-green-400  bg-green-500/10  border-green-500/20"  }
    : loading
    ? { label: "Analyzing…",           cls: "text-zinc-500 border-surface-border" }
    : null;

  const gcodeStatusBadge = gcodeResult
    ? gcodeResult.status === "ok"    ? { label: "G-code valid",         cls: "text-green-400 bg-green-500/10 border-green-500/20" }
    : gcodeResult.status === "fixed" ? { label: "G-code auto-corrected",cls: "text-blue-400  bg-blue-500/10  border-blue-500/20"  }
    : gcodeResult.status === "error" ? { label: "G-code error",         cls: "text-red-400   bg-red-500/10   border-red-500/20"  }
    : null
    : null;

  return (
    <div className="h-screen flex flex-col bg-surface overflow-hidden">

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header className="h-14 shrink-0 flex items-center px-4 gap-3 border-b border-surface-border bg-surface-card">
        <button onClick={() => router.push("/convert")}
          className="flex items-center gap-1.5 text-zinc-500 hover:text-zinc-300 transition-colors shrink-0">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7"/>
          </svg>
          <span className="text-xs">Back</span>
        </button>

        <div className="w-px h-5 bg-surface-border shrink-0" />

        <div className="flex items-center gap-2 min-w-0 flex-1">
          <svg className="w-4 h-4 text-zinc-600 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z"/>
          </svg>
          <span className="text-sm font-medium text-white truncate max-w-[200px]">{filename}</span>
          {geo && (
            <span className="text-xs text-zinc-600 font-mono shrink-0 hidden md:block">
              {geo.bounding_box.x_mm} × {geo.bounding_box.y_mm} × {geo.bounding_box.z_mm} mm
            </span>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {/* TODO: replace with user printer/filament preferences */}
          <span className="hidden lg:inline-flex items-center gap-1.5 text-[10px] text-zinc-500 px-2.5 py-1 rounded-full border border-surface-border">
            <svg className="w-3 h-3 opacity-60" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M6.75 7.5l3 2.25-3 2.25m4.5 0h3m-9 8.25h13.5A2.25 2.25 0 0021 18V6a2.25 2.25 0 00-2.25-2.25H5.25A2.25 2.25 0 003 6v12a2.25 2.25 0 002.25 2.25z"/>
            </svg>
            {scoring?.printer_id && scoring.printer_id !== "unknown" ? scoring.printer_id : "FDM Printer"}
          </span>
          <span className="hidden lg:inline-flex items-center gap-1.5 text-[10px] text-zinc-500 px-2.5 py-1 rounded-full border border-surface-border">
            <span className="w-2 h-2 rounded-full bg-zinc-500 opacity-70" />
            {scoring?.filament && scoring.filament !== "unknown" ? scoring.filament.toUpperCase() : "PLA"}
          </span>
          {statusBadge && (
            <span className={`text-[10px] font-semibold px-2.5 py-1 rounded-full border ${statusBadge.cls}`}>{statusBadge.label}</span>
          )}
          {gcodeStatusBadge && (
            <span className={`hidden lg:inline-flex text-[10px] font-semibold px-2.5 py-1 rounded-full border ${gcodeStatusBadge.cls}`}>{gcodeStatusBadge.label}</span>
          )}
          {intent && diffColor && (
            <span className={`text-[10px] font-semibold px-2.5 py-1 rounded-full border ${diffColor}`}>
              {intent.difficulty.charAt(0).toUpperCase() + intent.difficulty.slice(1)}
            </span>
          )}
          {loading && <div className="w-3.5 h-3.5 border-2 border-brand border-t-transparent rounded-full animate-spin" />}
        </div>
      </header>

      {/* ── Main ───────────────────────────────────────────────────────────── */}
      <div className="flex-1 flex overflow-hidden">

        {/* ── Left column ──────────────────────────────────────────────────── */}
        <div className="flex-1 flex flex-col overflow-hidden">

          {/* 3D Viewer */}
          <div className="flex-1 relative bg-[#111]">
            <ModelViewer
              jobId={jobId}
              viewMode={viewMode}
              showSupports={showSupports}
              wireframe={wireframe}
              modelOpacity={modelOpacity}
              heatmapOnly={heatmapOnly}
              className="w-full h-full absolute inset-0"
              resetKey={resetKey}
              debugMode={debugMode}
              debugLayers={debugLayers}
              // Client-side tree support
              showClientTreeSupport={!!geo?.overhang.has_overhangs}
              onClientSupportGenerated={(result) => {
                setTreeResult(result);
                if (viewMode === "model") setViewMode("model+supports");
              }}
              // Tree result + animation
              treeResult={treeResult}
              animPlaying={animPlaying}
              animProgress={animProgress}
              animSpeed={animSpeed}
              onAnimProgress={setAnimProgress}
              selectedSegmentId={selectedSegmentId}
              selectedNodeId={selectedNodeId}
              onSegmentClick={setSelectedSegmentId}
              onNodeClick={setSelectedNodeId}
            />

            {/* Top-left controls */}
            <div className="absolute top-3 left-3 z-10 flex gap-2">
              <ViewerBtn onClick={() => setResetKey(k => k + 1)}>
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                </svg>
                Reset View
              </ViewerBtn>
            </div>

            {/* Top-right view mode selector */}
            <div className="absolute top-3 right-3 z-10 flex gap-1.5 flex-wrap justify-end max-w-xs">
              {(geo?.overhang.has_overhangs ? (
                [
                  { mode: "model"                as ViewMode, label: "Model",        activeClass: "bg-white/10 border-white/30 text-white"              },
                  { mode: "model+supports"       as ViewMode, label: "+ Tree",        activeClass: "bg-orange-500/20 border-orange-500/40 text-orange-300" },
                  { mode: "transparent+supports" as ViewMode, label: "X-ray",         activeClass: "bg-purple-500/20 border-purple-500/40 text-purple-300"  },
                  { mode: "supports"             as ViewMode, label: "Tree only",     activeClass: "bg-amber-500/20 border-amber-500/40 text-amber-300"    },
                  { mode: "heatmap"              as ViewMode, label: "Heatmap",       activeClass: "bg-red-500/20 border-red-500/40 text-red-300"          },
                  { mode: "heatmap+supports"     as ViewMode, label: "Heat + Tree",   activeClass: "bg-rose-500/20 border-rose-500/40 text-rose-300"        },
                  { mode: "debug-graph"          as ViewMode, label: "Debug",         activeClass: "bg-cyan-500/20 border-cyan-500/40 text-cyan-300"        },
                ] satisfies { mode: ViewMode; label: string; activeClass: string }[]
              ) : (
                [
                  { mode: "model" as ViewMode, label: "Model", activeClass: "bg-white/10 border-white/30 text-white" },
                ] satisfies { mode: ViewMode; label: string; activeClass: string }[]
              )).map(({ mode, label, activeClass }) => (
                <ViewerBtn key={mode} onClick={() => setViewMode(mode)} active={viewMode === mode} activeClass={activeClass}>
                  {label}
                </ViewerBtn>
              ))}
              <ViewerBtn onClick={() => setWireframe(w => !w)} active={wireframe} activeClass="bg-blue-500/20 border-blue-500/40 text-blue-300">
                Wireframe
              </ViewerBtn>
            </div>

            <p className="absolute bottom-3 right-3 z-10 text-[10px] text-zinc-700 pointer-events-none select-none">
              drag · scroll · right-drag to pan
            </p>

            {/* Debug layer panel (?debug=1 only) */}
            {debugMode && showSupports && (
              <div className="absolute bottom-8 left-3 z-10 flex flex-col gap-1.5 bg-black/70 backdrop-blur-sm border border-white/10 rounded-xl p-3">
                <p className="text-[10px] font-semibold text-zinc-500 uppercase tracking-widest mb-1">Debug layers</p>
                {([
                  { key: "showAllOverhangs" as const, label: "All overhangs",     color: "text-blue-400"  },
                  { key: "showActiveCandidates" as const,   label: "Active candidates", color: "text-green-400" },
                  { key: "showFilteredCandidates" as const, label: "Filtered regions",  color: "text-red-400"   },
                ]).map(({ key, label, color }) => (
                  <label key={key} className="flex items-center gap-2 cursor-pointer select-none">
                    <input type="checkbox" checked={debugLayers[key]}
                      onChange={() => key === "showAllOverhangs" ? setShowOverhangZones(v => !v) : undefined}
                      className="w-3 h-3 accent-brand" />
                    <span className={`text-xs ${color}`}>{label}</span>
                  </label>
                ))}
              </div>
            )}
          </div>

          {/* Orientation strip */}
          {hasOrient && analysis && (
            <div className="h-[220px] shrink-0 border-t border-surface-border bg-surface">
              <OrientationStrip report={analysis.orientation} />
            </div>
          )}
        </div>

        {/* ── Right sidebar ─────────────────────────────────────────────────── */}
        <aside className="w-80 shrink-0 border-l border-surface-border overflow-y-auto bg-surface">
          {error && (
            <div className="m-4 p-3.5 bg-brand/10 border border-brand/30 rounded-xl text-brand text-xs leading-relaxed">{error}</div>
          )}

          {loading && <Skeleton />}

          {analysis && (
            <div className="p-4 space-y-3 pb-6">

              {/* 0. Model Info */}
              <ModelInfoCard analysis={analysis} />

              {/* 1. Printability Score */}
              <PrintabilityCard score={analysis.printability} />

              {/* 2. Generated Print Settings (needs scoring report) */}
              {scoring?.decisions ? (
                <GeneratedSettingsCard
                  decisions={scoring.decisions}
                  filament={scoring.filament}
                  nozzleMm={scoring.nozzle_mm}
                  explanations={analysis.explanations}
                />
              ) : (
                <div className="bg-surface-card border border-surface-border rounded-2xl p-4 animate-pulse">
                  <div className="h-2.5 rounded-full bg-surface-elevated w-36 mb-4" />
                  <div className="space-y-2">
                    {[85, 70, 75, 65, 80].map(w => <div key={w} className="h-2 rounded-full bg-surface-elevated" style={{ width: `${w}%` }} />)}
                  </div>
                </div>
              )}

              {/* 3. Support Analysis (backend summary) */}
              <SupportAnalysisCard
                jobId={jobId}
                showSupports={showSupports}
                onShowSupports={(v) => setViewMode(v ? "model+supports" : "model")}
              />

              {/* 3b. Tree Support Decision + Stats (client-side result) */}
              {treeResult && (
                <>
                  <SupportDecisionCard
                    stats={treeResult.stats}
                    hasOverhangs={!!geo?.overhang.has_overhangs}
                    needsSupport={treeResult.stats.tipCount > 0}
                  />
                  <TreeStatsCard stats={treeResult.stats} />
                  <OverhangAnalysisCard clusters={treeResult.clusters} />
                </>
              )}

              {/* 4. Nozzle Collision Risk */}
              {analysis.nozzle_risk && (
                <NozzleRiskCard report={analysis.nozzle_risk} />
              )}

              {/* 5. G-code Validator */}
              <GcodeValidationCard onResult={setGcodeResult} />

              {/* 6. Tree Viewer Controls (replaces old viewer controls when tree result available) */}
              {treeResult ? (
                <TreeViewerControlsCard
                  mode={viewMode}
                  onMode={setViewMode}
                  hasOverhangs={!!geo?.overhang.has_overhangs}
                  treeResult={treeResult}
                  animPlaying={animPlaying}
                  animProgress={animProgress}
                  animSpeed={animSpeed}
                  onAnimPlay={() => {
                    if (animProgress >= 1) setAnimProgress(0);
                    setAnimPlaying(true);
                  }}
                  onAnimPause={() => setAnimPlaying(false)}
                  onAnimReset={() => { setAnimPlaying(false); setAnimProgress(0); }}
                  onAnimScrub={(p) => { setAnimPlaying(false); setAnimProgress(p); }}
                  onAnimSpeedChange={setAnimSpeed}
                  onCameraReset={() => setResetKey(k => k + 1)}
                />
              ) : (
                <ViewerControlsCard
                  showSupports={showSupports}     onShowSupports={(v) => setViewMode(v ? "model+supports" : "model")}
                  wireframe={wireframe}           onWireframe={setWireframe}
                  showOverhangZones={showOverhangZones} onShowOverhangZones={setShowOverhangZones}
                  hasOverhangs={!!geo?.overhang.has_overhangs}
                  onApplyOrientation={handleApplyOrientation}
                  orientationFeedback={orientationFeedback}
                  shouldRotate={analysis.orientation.should_rotate}
                />
              )}

              {/* Debug graph legend (only in debug mode) */}
              {treeResult && viewMode === "debug-graph" && (
                <DebugLegendCard
                  result={treeResult}
                  selectedNodeId={selectedNodeId}
                  selectedSegmentId={selectedSegmentId}
                />
              )}

              {/* 7. Export Preflight + CTA */}
              <ExportPreflightCard
                scoring={scoring}
                gcodeResult={gcodeResult}
                onConvert={() => router.push("/convert")}
              />
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
