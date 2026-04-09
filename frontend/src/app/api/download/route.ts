import { NextResponse } from "next/server";

const OWNER = "quiandrosegier96-coder";
const REPO  = "autoslice";

export async function GET() {
  try {
    const res = await fetch(
      `https://api.github.com/repos/${OWNER}/${REPO}/releases/latest`,
      {
        headers: { Accept: "application/vnd.github+json" },
        next: { revalidate: 300 },   // cache 5 min
      }
    );

    if (!res.ok) throw new Error(`GitHub API ${res.status}`);

    const data = await res.json();

    // Find the Windows installer (.exe) asset
    const asset = (data.assets as { name: string; browser_download_url: string }[])
      .find((a) => a.name.endsWith(".exe") && a.name.includes("Setup"));

    if (!asset) throw new Error("No installer asset found in latest release");

    return NextResponse.redirect(asset.browser_download_url, { status: 302 });
  } catch {
    // Fallback: send user to the releases page
    return NextResponse.redirect(
      `https://github.com/${OWNER}/${REPO}/releases/latest`,
      { status: 302 }
    );
  }
}
