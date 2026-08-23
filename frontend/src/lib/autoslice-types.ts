export type Confidence = "low" | "medium" | "high" | string;

export type Diagnostics = {
  code: string;
  message: string;
  object_ids?: string[];
};

export type Recommendation = {
  setting: string;
  old_value: unknown;
  new_value: unknown;
  reason: string;
  rule: string;
  confidence: Confidence;
  applied?: boolean;
};

export type Compatibility = {
  final_compatibility: number;
};

export type Printability = {
  status: "good" | "warning" | "blocked" | "unknown";
  project_build_volume: string;
  collisions: Array<{ first_object_id: string; second_object_id: string; kind: string }>;
  support_recommendations: string[];
  debug: unknown[];
};

export type OptimizationPlan = {
  changes: Recommendation[];
  unchanged: string[];
  warnings: Diagnostics[];
  blocked: Diagnostics[];
  geometry_changes: Array<{
    object_id: string;
    current_transform: number[];
    recommended_transform: number[];
    rotation_degrees: number[];
    reason: string;
    confidence: Confidence;
    score_improvement: number;
    applied: boolean;
  }>;
  support_changes: Recommendation[];
  placement_changes: Array<{
    item_index: number;
    object_id: string;
    old_transform: number[];
    new_transform: number[];
    old_position_mm: number[];
    new_position_mm: number[];
    reason: string;
    rule: string;
    confidence: Confidence;
    applied: boolean;
  }>;
  compatibility: Compatibility;
};

export type AnalysisResult = {
  source: { slicer: string; confidence: number; version?: string | null };
  project: { dimensions_mm: number[]; build_volume_status: string; object_count: number };
  target: { slicer: string; printer: { display_name: string }; nozzle: { diameter_mm: number }; filament: { material_id: string } };
  optimization_plan: OptimizationPlan;
  printability: Printability;
  orientation: {
    recommended_transform: number[];
    rotation_degrees: number[];
    score: number;
    current_score: number;
    confidence: Confidence;
    estimated_support_reduction_percent: number;
    candidates: unknown[];
  } | null;
  support_plan: {
    strategy: "none" | "build_plate_only" | "normal" | "tree" | "organic" | "auto";
    required_regions: unknown[];
    optional_regions: unknown[];
    blocked_regions: unknown[];
    estimated_support_volume_mm3: number | null;
    confidence: Confidence;
    diagnostics: Diagnostics[];
    applied: boolean;
    preserves_source_supports: boolean;
  };
  placement_plan: {
    current: unknown;
    recommended: unknown;
    candidates: unknown[];
    plate_assignments: unknown[];
    diagnostics: Diagnostics[];
    confidence: Confidence;
    applied: boolean;
    reanalysis_required: boolean;
  };
  optimization_preview: {
    profile: "balanced" | "quality" | "fast" | "material_saving";
    weights: { values: Array<[string, number]> };
    selected: unknown;
    candidates: unknown[];
    explanations: unknown[];
    analyze_only: boolean;
    benchmark_ms: number;
  };
  dry_run: boolean;
};

export type ConversionResult = {
  success: boolean;
  source: { slicer: string; confidence: number; evidence: string[] };
  target: { slicer: string; printer: string | null };
  compatibility: {
    compatibility_score: number;
    translated: unknown[];
    modified: unknown[];
    preserved: unknown[];
    approximated: unknown[];
    unsupported: unknown[];
    warnings: string[];
    pipeline_stages: Array<{ name: string; duration_ms: number; status: string }>;
  };
  output_filename: string;
  download_reference: string;
  validation_passed: boolean;
  fallback_used: boolean;
};
