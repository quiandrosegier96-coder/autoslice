const BASE = "/api";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("autoslice_token");
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
      throw new Error(data.detail || `Request failed (${res.status})`);
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
