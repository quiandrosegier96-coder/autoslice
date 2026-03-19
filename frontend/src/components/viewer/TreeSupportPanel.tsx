"use client";

/**
 * AutoSlice — Tree Support Analysis Panel
 *
 * Sidebar sections for the tree support viewer:
 *   1. Support Decision card
 *   2. Tree Structure Stats card
 *   3. Overhang Analysis card
 *   4. Viewer Controls card (mode, animation, reset)
 *   5. Debug Graph legend card
 */

import type { TreeSupportResult, SupportStats, OverhangCluster } from "@/lib/tree-support/types";
import { getAnimPhaseLabel } from "./SupportGrowthAnimation";
import { DEBUG_LEGEND } from "./DebugGraphOverlay";

// ── Viewer mode type ───────────────────────────────────────────────────────────

export type ExtendedViewMode =
  | "model"
  | "model+supports"
  | "supports"
  | "transparent+supports"
  | "heatmap"
  | "heatmap+supports"
  | "debug-graph";

// ── Shared card wrapper ────────────────────────────────────────────────────────

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-surface-card border border-surface-border rounded-2xl p-4 ${className}`}>
      {children}
    </div>
  );
}

function CardTitle({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="text-[11px] font-semibold tracking-widest uppercase text-zinc-500 mb-3">
      {children}
    </h3>
  );
}

function StatRow({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-surface-border last:border-0">
      <span className="text-xs text-zinc-400">{label}</span>
      <div className="text-right">
        <span className="text-xs font-mono font-semibold text-white">{value}</span>
        {sub && <span className="text-[10px] text-zinc-600 ml-1">{sub}</span>}
      </div>
    </div>
  );
}

// ── 1. Support Decision Card ───────────────────────────────────────────────────

interface SupportDecisionProps {
  stats:        SupportStats;
  hasOverhangs: boolean;
  needsSupport: boolean;
}

export function SupportDecisionCard({ stats, hasOverhangs, needsSupport }: SupportDecisionProps) {
  const icon = needsSupport ? "🌳" : hasOverhangs ? "⚠️" : "✅";
  const title = needsSupport
    ? "Tree supports selected"
    : hasOverhangs
    ? "Minor overhangs detected"
    : "No supports needed";

  const reasons = [
    needsSupport && stats.clusterCount > 0
      ? `${stats.clusterCount} unsupported overhang island${stats.clusterCount > 1 ? "s" : ""} detected`
      : null,
    needsSupport && stats.trunkCount > 0
      ? `Tree structure uses ${stats.trunkCount} trunk${stats.trunkCount > 1 ? "s" : ""} to minimise material`
      : null,
    needsSupport
      ? "Organic tree form prevents model scarring and reduces stringing"
      : !hasOverhangs
      ? "All faces are within printable overhang limits"
      : "Small overhangs can bridge without dedicated supports",
  ].filter(Boolean);

  return (
    <Card>
      <CardTitle>Support Decision</CardTitle>
      <div className="flex items-start gap-3">
        <span className="text-2xl">{icon}</span>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-white mb-1">{title}</p>
          <ul className="space-y-0.5">
            {reasons.map((r, i) => (
              <li key={i} className="text-xs text-zinc-400 flex items-start gap-1.5">
                <span className="text-zinc-600 shrink-0 mt-0.5">—</span>
                {r}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {needsSupport && (
        <div className="mt-3 pt-3 border-t border-surface-border grid grid-cols-3 gap-2">
          {[
            { label: "Type",      value: "Tree" },
            { label: "Trunks",   value: stats.trunkCount },
            { label: "Contacts", value: stats.contactCount },
          ].map(({ label, value }) => (
            <div key={label} className="text-center">
              <div className="text-sm font-bold text-blue-400">{value}</div>
              <div className="text-[10px] text-zinc-600">{label}</div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

// ── 2. Tree Structure Stats Card ───────────────────────────────────────────────

interface TreeStatsProps {
  stats: SupportStats;
}

export function TreeStatsCard({ stats }: TreeStatsProps) {
  const volCm3  = (stats.estimatedVolumeMm3 / 1000).toFixed(2);
  const riskPct = Math.min(100, Math.round((stats.clusterCount / Math.max(1, stats.tipCount)) * 100));

  return (
    <Card>
      <CardTitle>Tree Support Analysis</CardTitle>

      <StatRow label="Trunk columns"   value={stats.trunkCount} />
      <StatRow label="Branch tips"     value={stats.tipCount} />
      <StatRow label="Contact points"  value={stats.contactCount} />
      <StatRow label="Total nodes"     value={stats.nodeCount} />
      <StatRow label="Segments"        value={stats.segmentCount} />
      <StatRow label="Est. volume"     value={volCm3} sub="cm³" />
      <StatRow label="Overhang clusters" value={stats.clusterCount} />

      <div className="mt-3 pt-3 border-t border-surface-border">
        <div className="flex justify-between items-center mb-1.5">
          <span className="text-[10px] text-zinc-500">Support risk (if disabled)</span>
          <span className={`text-[10px] font-semibold ${riskPct >= 70 ? "text-red-400" : riskPct >= 40 ? "text-yellow-400" : "text-green-400"}`}>
            {riskPct >= 70 ? "High" : riskPct >= 40 ? "Medium" : "Low"}
          </span>
        </div>
        <div className="h-1.5 rounded-full bg-surface-elevated overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${riskPct >= 70 ? "bg-red-500" : riskPct >= 40 ? "bg-yellow-500" : "bg-green-500"}`}
            style={{ width: `${riskPct}%` }}
          />
        </div>
      </div>
    </Card>
  );
}

// ── 3. Overhang Analysis Card ──────────────────────────────────────────────────

interface OverhangAnalysisProps {
  clusters: OverhangCluster[];
}

export function OverhangAnalysisCard({ clusters }: OverhangAnalysisProps) {
  const totalArea = clusters.reduce((s, c) => s + c.area, 0);
  const sorted    = [...clusters].sort((a, b) => b.area - a.area).slice(0, 5);

  function severity(area: number): { label: string; cls: string } {
    if (area > 200) return { label: "Critical", cls: "text-red-400 bg-red-500/10 border-red-500/30" };
    if (area > 80)  return { label: "Major",    cls: "text-orange-400 bg-orange-500/10 border-orange-500/30" };
    if (area > 25)  return { label: "Moderate", cls: "text-yellow-400 bg-yellow-500/10 border-yellow-500/30" };
    return               { label: "Minor",     cls: "text-green-400 bg-green-500/10 border-green-500/30" };
  }

  return (
    <Card>
      <CardTitle>Overhang Analysis</CardTitle>

      <div className="grid grid-cols-2 gap-2 mb-3">
        <div className="bg-surface-elevated rounded-xl p-2.5 text-center">
          <div className="text-lg font-bold text-orange-400">{clusters.length}</div>
          <div className="text-[10px] text-zinc-500">Islands</div>
        </div>
        <div className="bg-surface-elevated rounded-xl p-2.5 text-center">
          <div className="text-lg font-bold text-red-400">{totalArea.toFixed(0)}</div>
          <div className="text-[10px] text-zinc-500">mm² total</div>
        </div>
      </div>

      <p className="text-[10px] font-semibold text-zinc-500 uppercase tracking-widest mb-2">
        Top overhang zones
      </p>
      <div className="space-y-1.5">
        {sorted.map((cl, i) => {
          const sev = severity(cl.area);
          return (
            <div key={cl.id} className="flex items-center gap-2">
              <span className="text-[10px] text-zinc-600 font-mono w-3">{i + 1}</span>
              <div className="flex-1 h-1.5 rounded-full bg-surface-elevated overflow-hidden">
                <div
                  className="h-full rounded-full bg-orange-500"
                  style={{ width: `${Math.min(100, (cl.area / (sorted[0]?.area || 1)) * 100)}%` }}
                />
              </div>
              <span className="text-[10px] font-mono text-zinc-400 w-10 text-right">{cl.area.toFixed(0)}mm²</span>
              <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded-full border ${sev.cls}`}>
                {sev.label}
              </span>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

// ── 4. Viewer Controls Card ────────────────────────────────────────────────────

interface ViewerControlsProps {
  mode:              ExtendedViewMode;
  onMode:            (m: ExtendedViewMode) => void;
  hasOverhangs:      boolean;
  treeResult:        TreeSupportResult | null;
  // Animation
  animPlaying:       boolean;
  animProgress:      number;
  animSpeed:         number;
  onAnimPlay:        () => void;
  onAnimPause:       () => void;
  onAnimReset:       () => void;
  onAnimScrub:       (p: number) => void;
  onAnimSpeedChange: (s: number) => void;
  // Camera
  onCameraReset:     () => void;
}

const MODE_BUTTONS: { mode: ExtendedViewMode; label: string; icon: string; needsTree?: boolean; needsOverhang?: boolean }[] = [
  { mode: "model",                label: "Model",           icon: "◻" },
  { mode: "model+supports",       label: "+ Supports",      icon: "🌳", needsTree: true },
  { mode: "supports",             label: "Supports only",   icon: "⬡",  needsTree: true },
  { mode: "transparent+supports", label: "X-ray",           icon: "◎",  needsTree: true },
  { mode: "heatmap",              label: "Heatmap",         icon: "🔥", needsOverhang: true },
  { mode: "heatmap+supports",     label: "Heatmap + Tree",  icon: "🔥🌳", needsTree: true },
  { mode: "debug-graph",          label: "Debug graph",     icon: "⋯",  needsTree: true },
];

export function ViewerControlsCard({
  mode, onMode, hasOverhangs, treeResult,
  animPlaying, animProgress, animSpeed,
  onAnimPlay, onAnimPause, onAnimReset, onAnimScrub, onAnimSpeedChange,
  onCameraReset,
}: ViewerControlsProps) {
  const phaseInfo = treeResult ? getAnimPhaseLabel(animProgress) : null;

  return (
    <Card>
      <CardTitle>Viewer Controls</CardTitle>

      {/* Mode grid */}
      <div className="grid grid-cols-2 gap-1 mb-4">
        {MODE_BUTTONS.map(btn => {
          const disabled = (btn.needsTree && !treeResult) || (btn.needsOverhang && !hasOverhangs);
          const active   = mode === btn.mode;
          return (
            <button
              key={btn.mode}
              disabled={disabled}
              onClick={() => onMode(btn.mode)}
              className={`text-[11px] px-2.5 py-2 rounded-lg border transition-all text-left
                ${disabled ? "opacity-30 cursor-not-allowed border-surface-border text-zinc-600" :
                  active   ? "bg-blue-500/20 border-blue-500/40 text-blue-300 font-semibold" :
                             "border-surface-border text-zinc-400 hover:border-zinc-600 hover:text-zinc-200"}`}
            >
              <span className="mr-1">{btn.icon}</span>{btn.label}
            </button>
          );
        })}
      </div>

      {/* Animation controls */}
      {treeResult && (
        <div className="border-t border-surface-border pt-3">
          <p className="text-[10px] font-semibold text-zinc-500 uppercase tracking-widest mb-2">
            Growth Animation
          </p>

          {/* Phase indicator */}
          {phaseInfo && (
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-semibold text-blue-400">{phaseInfo.label}</span>
              <span className="text-[10px] text-zinc-500">{phaseInfo.desc}</span>
            </div>
          )}

          {/* Progress scrubber */}
          <input
            type="range" min={0} max={1} step={0.001}
            value={animProgress}
            onChange={e => onAnimScrub(parseFloat(e.target.value))}
            className="w-full h-1.5 rounded-full appearance-none bg-surface-elevated accent-blue-500 mb-2 cursor-pointer"
          />

          {/* Phase tick marks */}
          <div className="flex justify-between mb-3">
            {["P1","P2","P3","P4","P5","P6"].map((p, i) => {
              const thresholds = [0, 0.15, 0.28, 0.52, 0.80, 0.92];
              const active = animProgress >= thresholds[i];
              return (
                <span key={p} className={`text-[9px] font-mono ${active ? "text-blue-400" : "text-zinc-700"}`}>{p}</span>
              );
            })}
          </div>

          {/* Playback controls */}
          <div className="flex items-center gap-2">
            <button
              onClick={onAnimReset}
              className="text-zinc-500 hover:text-zinc-300 p-1.5 rounded-lg hover:bg-white/5 transition-colors"
              title="Reset"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M3 12a9 9 0 019-9 9 9 0 110 18 9 9 0 01-9-9zM3 12h2m7-9v2"/>
              </svg>
            </button>
            <button
              onClick={animPlaying ? onAnimPause : onAnimPlay}
              className="flex-1 flex items-center justify-center gap-1.5 text-[11px] font-semibold
                bg-blue-500/20 hover:bg-blue-500/30 border border-blue-500/40 text-blue-300
                px-3 py-2 rounded-lg transition-colors"
            >
              {animPlaying ? (
                <>
                  <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
                    <rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/>
                  </svg>
                  Pause
                </>
              ) : (
                <>
                  <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M8 5v14l11-7z"/>
                  </svg>
                  {animProgress >= 0.99 ? "Replay" : "Play"}
                </>
              )}
            </button>

            {/* Speed selector */}
            <div className="flex gap-1">
              {[0.5, 1, 2].map(s => (
                <button
                  key={s}
                  onClick={() => onAnimSpeedChange(s)}
                  className={`text-[10px] font-mono px-1.5 py-1 rounded border transition-colors
                    ${animSpeed === s
                      ? "bg-blue-500/20 border-blue-500/40 text-blue-300"
                      : "border-surface-border text-zinc-600 hover:text-zinc-400"}`}
                >
                  {s}×
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Camera reset */}
      <div className="border-t border-surface-border pt-3 mt-3">
        <button
          onClick={onCameraReset}
          className="w-full text-[11px] text-zinc-500 hover:text-zinc-300 border border-surface-border
            hover:border-zinc-600 rounded-lg py-2 px-3 transition-colors flex items-center justify-center gap-2"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
          </svg>
          Reset Camera
        </button>
      </div>
    </Card>
  );
}

// ── 5. Debug Graph Legend Card ─────────────────────────────────────────────────

interface DebugLegendProps {
  selectedNodeId:    number | null;
  selectedSegmentId: number | null;
  result:            TreeSupportResult;
}

export function DebugLegendCard({ selectedNodeId, selectedSegmentId, result }: DebugLegendProps) {
  const selectedNode = selectedNodeId !== null ? result.nodes.get(selectedNodeId) : null;

  return (
    <Card>
      <CardTitle>Debug Graph</CardTitle>

      <div className="space-y-1.5 mb-3">
        {DEBUG_LEGEND.map(entry => (
          <div key={entry.type} className="flex items-center gap-2">
            <span
              className="w-2.5 h-2.5 rounded-full shrink-0"
              style={{ background: entry.color }}
            />
            <span className="text-xs text-zinc-400">{entry.label}</span>
          </div>
        ))}
      </div>

      {selectedNode && (
        <div className="border-t border-surface-border pt-3">
          <p className="text-[10px] font-semibold text-zinc-500 uppercase tracking-widest mb-2">
            Selected Node #{selectedNode.id}
          </p>
          <div className="space-y-1 text-[11px] font-mono text-zinc-400">
            <div>Type: <span className="text-white">{selectedNode.type}</span></div>
            <div>Radius: <span className="text-white">{selectedNode.radius.toFixed(2)} mm</span></div>
            <div>X: <span className="text-white">{selectedNode.position.x.toFixed(1)}</span></div>
            <div>Y: <span className="text-white">{selectedNode.position.y.toFixed(1)}</span></div>
            <div>Z: <span className="text-white">{selectedNode.position.z.toFixed(1)}</span></div>
            <div>Children: <span className="text-white">{selectedNode.childIds.length}</span></div>
          </div>
        </div>
      )}

      {selectedSegmentId !== null && (
        <div className="border-t border-surface-border pt-3 mt-2">
          <p className="text-[10px] font-semibold text-zinc-500 uppercase tracking-widest mb-1">
            Selected Segment #{selectedSegmentId}
          </p>
          {(() => {
            const seg = result.segments.find(s => s.id === selectedSegmentId);
            if (!seg) return null;
            return (
              <div className="space-y-1 text-[11px] font-mono text-zinc-400">
                <div>r₀: <span className="text-white">{seg.radiusStart.toFixed(2)} mm</span></div>
                <div>r₁: <span className="text-white">{seg.radiusEnd.toFixed(2)} mm</span></div>
              </div>
            );
          })()}
        </div>
      )}
    </Card>
  );
}
