import type { AnalysisResult, Recommendation } from "./autoslice-types";

export function acceptsThreeMf(filename: string) {
  return filename.trim().toLowerCase().endsWith(".3mf");
}

export function canAnalyze(jobId: string, targetPrinter: string) {
  return Boolean(jobId && targetPrinter);
}

export function collectRecommendations(analysis: AnalysisResult): Recommendation[] {
  const orientation: Recommendation[] = analysis.optimization_plan.geometry_changes.map((item) => ({
    setting: `orientation:${item.object_id}`,
    old_value: item.current_transform,
    new_value: item.recommended_transform,
    reason: item.reason,
    rule: "orientation_analysis",
    confidence: item.confidence,
    applied: item.applied,
  }));
  const placement: Recommendation[] = analysis.optimization_plan.placement_changes.map((item) => ({
    setting: `placement:${item.object_id}`,
    old_value: item.old_position_mm,
    new_value: item.new_position_mm,
    reason: item.reason,
    rule: item.rule,
    confidence: item.confidence,
    applied: item.applied,
  }));
  return [
    ...analysis.optimization_plan.changes,
    ...analysis.optimization_plan.support_changes,
    ...orientation,
    ...placement,
  ];
}

export function isConversionBlocked(analysis: AnalysisResult) {
  return analysis.printability.status === "blocked" || analysis.optimization_plan.blocked.length > 0;
}

export function autoSliceFilename(original: string) {
  return `${original.replace(/\.3mf$/i, "")}_AutoSlice.3mf`;
}

export function fallbackNotice(used: boolean) {
  return used ? "Universal conversion unavailable — legacy compatibility route used." : "";
}
