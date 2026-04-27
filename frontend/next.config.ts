import type { NextConfig } from "next";
import path from "path";

const isMobile = process.env.NEXT_MOBILE === "1";

const nextConfig: NextConfig = {
  output: isMobile ? "export" : "standalone",
  outputFileTracingRoot: path.join(__dirname),
  ...(isMobile
    ? {
        // Static export for Android/Capacitor
        trailingSlash: true,
        images: { unoptimized: true },
      }
    : {
        // Electron / web server build
        experimental: {
          serverActions: { bodySizeLimit: "500mb" },
        },
        async headers() {
          return [
            {
              source: "/(login|register|forgot-password|reset-password)",
              headers: [
                { key: "Cache-Control", value: "no-store, no-cache, must-revalidate" },
              ],
            },
          ];
        },
        async rewrites() {
          return [
            {
              source: "/api/:path((?!convert$|download$).*)",
              destination: `${process.env.BACKEND_URL ?? "http://localhost:8000"}/api/:path*`,
            },
          ];
        },
      }),
};

export default nextConfig;
