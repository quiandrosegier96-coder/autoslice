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
        async headers() {
          return [
            {
              source: "/tools/hinged-box",
              headers: [
                { key: "Cache-Control", value: "no-store, no-cache, must-revalidate" },
                { key: "Pragma", value: "no-cache" },
                { key: "Expires", value: "0" },
              ],
            },
            {
              source: "/(login|register|forgot-password|reset-password)",
              headers: [
                { key: "Cache-Control", value: "no-store, no-cache, must-revalidate" },
              ],
            },
          ];
        },
      }),
};

export default nextConfig;
