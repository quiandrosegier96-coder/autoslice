/**
 * Next.js config for the Android/mobile static export.
 *
 * Key differences from next.config.ts:
 *   - output: "export"   → generates static HTML/JS in /out (Capacitor webDir)
 *   - No rewrites        → API calls go directly to the backend (see NEXT_PUBLIC_API_BASE)
 *   - No server actions  → not supported in static export
 *
 * Build with:
 *   npm run build:mobile
 */

import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  output: "export",
  outputFileTracingRoot: path.join(__dirname),
  trailingSlash: true,    // required for static export routing
  images: {
    unoptimized: true,    // static export can't use Next.js image optimisation
  },
};

export default nextConfig;
