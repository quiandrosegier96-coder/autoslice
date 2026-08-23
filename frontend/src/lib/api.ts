// In the Electron/web app API calls go through the Next.js rewrite proxy (/api → backend).
// In the Android app there is no proxy — calls go directly to the backend server.
// NEXT_PUBLIC_API_BASE is set at build time for the mobile export.
const BASE = (process.env.NEXT_PUBLIC_API_BASE ?? "") + "/api";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("autoslice_token") ?? sessionStorage.getItem("autoslice_token");
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function parseResponse<T>(res: Response): Promise<T> {
  const contentType = res.headers.get("content-type") ?? "";
  const isJson = contentType.includes("application/json");
  if (!res.ok) {
    if (isJson) {
      const data = await res.json();
      const detail = data.detail;
      throw new Error(typeof detail === "string" ? detail : detail?.message || data.error?.message || `Request failed (${res.status})`);
    }
    throw new Error(`Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export async function apiPost<T>(path: string, body: unknown, auth = false): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(auth ? authHeaders() : {}),
    },
    body: JSON.stringify(body),
  });
  return parseResponse<T>(res);
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  return parseResponse<T>(res);
}

export async function apiGet<T>(path: string, auth = false): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: auth ? authHeaders() : {},
  });
  return parseResponse<T>(res);
}

export async function apiUpload(file: File): Promise<{ job_id: string; filename: string; has_model_file: boolean; archive_file_count: number }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/upload`, {
    method: "POST",
    headers: authHeaders(),
    body: form,
  });
  if (!res.ok) {
    const contentType = res.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      const data = await res.json();
      throw new Error(data.detail || `Upload failed (${res.status})`);
    }
    throw new Error(`Upload failed (${res.status})`);
  }
  return res.json();
}

export async function apiAnalyze(jobId: string) {
  return apiGet(`/analyze/${jobId}`, true);
}

export type UniversalConversionResult = {
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
  };
  output_filename: string;
  download_reference: string;
  validation_passed: boolean;
  fallback_used: boolean;
};

export function apiUniversalConvert(body: {
  job_id: string;
  target_slicer: string;
  target_printer: string;
  nozzle_size_mm: number;
  material: string;
  mode: "autoslice" | "preserve_source";
}): Promise<UniversalConversionResult> {
  return apiPost<UniversalConversionResult>("/universal-convert", body, true);
}

export type AutoSliceAnalysis = {
  source: { slicer: string; confidence: number; version?: string | null };
  project: { dimensions_mm: number[]; build_volume_status: string; object_count: number };
  target: { slicer: string; printer: { display_name: string }; nozzle: { diameter_mm: number }; filament: { material_id: string } };
  optimization_plan: {
    changes: Array<{ setting: string; old_value: unknown; new_value: unknown; reason: string; rule: string; confidence: string }>;
    unchanged: string[];
    warnings: Array<{ code: string; message: string }>;
    blocked: Array<{ code: string; message: string }>;
    geometry_changes: Array<{
      object_id: string;
      current_transform: number[];
      recommended_transform: number[];
      rotation_degrees: number[];
      reason: string;
      confidence: string;
      score_improvement: number;
      applied: boolean;
    }>;
    support_changes: Array<{
      setting: string;
      old_value: unknown;
      new_value: unknown;
      reason: string;
      rule: string;
      confidence: string;
      applied: boolean;
    }>;
    compatibility: { final_compatibility: number };
  };
  printability: {
    status: "good" | "warning" | "blocked" | "unknown";
    project_build_volume: string;
    collisions: Array<{ first_object_id: string; second_object_id: string; kind: string }>;
    support_recommendations: string[];
    debug: unknown[];
  };
  orientation: {
    recommended_transform: number[];
    rotation_degrees: number[];
    score: number;
    current_score: number;
    confidence: string;
    estimated_support_reduction_percent: number;
    candidates: unknown[];
  } | null;
  support_plan: {
    strategy: "none" | "build_plate_only" | "normal" | "tree" | "organic" | "auto";
    required_regions: unknown[];
    optional_regions: unknown[];
    blocked_regions: unknown[];
    estimated_support_volume_mm3: number | null;
    confidence: string;
    diagnostics: Array<{ code: string; message: string }>;
    applied: boolean;
    preserves_source_supports: boolean;
  };
  dry_run: boolean;
};

export function apiUniversalAnalyze(body: {
  job_id: string;
  target_slicer: string;
  target_printer: string;
  nozzle_size_mm: number;
  nozzle_material: string;
  material: string;
  mode: "autoslice" | "preserve_source";
}): Promise<AutoSliceAnalysis> {
  return apiPost<AutoSliceAnalysis>("/universal-analyze", body, true);
}

export async function apiDownloadReference(reference: string): Promise<Blob> {
  const path = reference.startsWith("/api/") ? reference.slice(4) : reference;
  const res = await fetch(`${BASE}${path}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`Download failed (${res.status})`);
  return res.blob();
}

export type SiteConfig = {
  landing_features: boolean;
  landing_how: boolean;
  landing_pricing: boolean;
  landing_apppreview: boolean;
  landing_multicolor: boolean;
  landing_trustbar: boolean;
  landing_downloadcta: boolean;
  landing_blog: boolean;
  nav_history: boolean;
  nav_community: boolean;
  nav_settings: boolean;
  registration_open: boolean;
  maintenance_mode: boolean;
};

export async function getSiteConfig(): Promise<SiteConfig> {
  return apiGet<SiteConfig>("/site-config");
}

export async function adminSetSiteConfig(updates: Partial<SiteConfig>): Promise<SiteConfig> {
  const res = await fetch(`${BASE}/admin/site-config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(updates),
  });
  return parseResponse<SiteConfig>(res);
}

export async function apiScoringReport(jobId: string) {
  return apiGet(`/scoring/report/${jobId}`, true);
}

export async function apiSupportPreview(jobId: string) {
  return apiGet(`/analyze/${jobId}/support-preview`, true);
}

export async function apiValidateGcode(gcode: string): Promise<{
  status: string;
  has_m83: boolean;
  has_m82: boolean;
  g92_e0_count: number;
  layer_count: number;
  line_count: number;
  issues: string[];
  fixes_applied: string[];
  fixed_gcode: string | null;
}> {
  return apiPost("/gcode/validate", { gcode }, true);
}

export async function apiCommunityList(): Promise<CommunityPrint[]> {
  return apiGet<CommunityPrint[]>("/community", true);
}

export async function apiCommunityUpload(
  title: string,
  description: string,
  filamentType: string,
  printerName: string,
  file: File,
  photo: File,
): Promise<{ id: number; message: string }> {
  const form = new FormData();
  form.append("title", title);
  form.append("description", description);
  form.append("filament_type", filamentType);
  form.append("printer_name", printerName);
  form.append("file", file);
  form.append("photo", photo);
  const res = await fetch(`${BASE}/community/upload`, {
    method: "POST",
    headers: authHeaders(),
    body: form,
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Upload failed (${res.status})`);
  }
  return res.json();
}

export async function apiCommunityRate(
  printId: number,
  stars: number,
): Promise<{ avg_rating: number; rating_count: number }> {
  return apiPost(`/community/${printId}/rate`, { stars }, true);
}

export interface CommunityPrint {
  id: number;
  user_id: number;
  username: string;
  title: string;
  description: string;
  filament_type: string;
  printer_name: string;
  photo_filename: string;
  download_count: number;
  created_at: string;
  avg_rating: number | null;
  rating_count: number;
  user_rating: number | null;
}

export async function apiConvertDownload(
  jobId: string,
  printerId: string,
  filamentType: string,
  nozzleSizeMm: number,
  nozzleType: string,
  filamentDiameterMm: number,
  buildPlate: string,
  flushVolume: number,
  colorCount = 1,
  filamentColors: string[] = [],
  filamentTypes: string[] = [],
  orientationEulerDeg: number[] = [],
  scaleFactor = 1.0,
  fuzzySkin = "none",
  fuzzyThicknessMm = 0.3,
  fuzzyPointDistMm = 0.8,
): Promise<Blob> {
  const res = await fetch(`${BASE}/convert`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
    },
    body: JSON.stringify({
      job_id: jobId,
      printer_id: printerId,
      filament_type: filamentType,
      nozzle_size_mm: nozzleSizeMm,
      nozzle_type: nozzleType,
      filament_diameter_mm: filamentDiameterMm,
      build_plate: buildPlate,
      flush_volume_mm3: flushVolume,
      color_count: colorCount,
      filament_colors: filamentColors,
      filament_types: filamentTypes,
      orientation_euler_deg: orientationEulerDeg,
      scale_factor: scaleFactor,
      fuzzy_skin: fuzzySkin,
      fuzzy_skin_thickness_mm: fuzzyThicknessMm,
      fuzzy_skin_point_dist_mm: fuzzyPointDistMm,
    }),
  });
  if (!res.ok) {
    const contentType = res.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      const data = await res.json();
      throw new Error(data.detail || `Conversion failed (${res.status})`);
    }
    const text = await res.text().catch(() => "");
    const preview = text.slice(0, 200).replace(/<[^>]+>/g, "").trim();
    throw new Error(preview || `Conversion failed (${res.status})`);
  }
  return res.blob();
}
