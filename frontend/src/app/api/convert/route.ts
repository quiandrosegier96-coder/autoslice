import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function POST(req: NextRequest) {
  const body = await req.text();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  const auth = req.headers.get("Authorization");
  if (auth) headers["Authorization"] = auth;

  const upstream = await fetch(`${BACKEND}/api/convert`, {
    method: "POST",
    headers,
    body,
  });

  if (!upstream.ok) {
    const text = await upstream.text();
    let detail = `Conversion failed (${upstream.status})`;
    try {
      detail = JSON.parse(text).detail ?? detail;
    } catch { /* not JSON */ }
    return NextResponse.json({ detail }, { status: upstream.status });
  }

  const blob = await upstream.arrayBuffer();
  const filename = upstream.headers.get("content-disposition")
    ?.match(/filename="?([^"]+)"?/)?.[1] ?? "output.3mf";

  return new NextResponse(blob, {
    status: 200,
    headers: {
      "Content-Type": "application/zip",
      "Content-Disposition": `attachment; filename="${filename}"`,
    },
  });
}
