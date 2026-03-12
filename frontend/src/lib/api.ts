const BASE = "/api";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("autoslice_token");
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
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
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Request failed");
  return data as T;
}

export async function apiGet<T>(path: string, auth = false): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: auth ? authHeaders() : {},
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Request failed");
  return data as T;
}

export async function apiUpload(file: File): Promise<{ job_id: string; filename: string; has_model_file: boolean; archive_file_count: number }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/upload`, {
    method: "POST",
    headers: authHeaders(),
    body: form,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Upload failed");
  return data;
}

export async function apiAnalyze(jobId: string) {
  return apiGet(`/analyze/${jobId}`, true);
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
    }),
  });
  if (!res.ok) {
    try {
      const data = await res.json();
      throw new Error(data.detail || `Conversion failed (${res.status})`);
    } catch {
      throw new Error(`Conversion failed (${res.status})`);
    }
  }
  return res.blob();
}
