import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: path.join(__dirname),
  experimental: {
    serverActions: {
      bodySizeLimit: "500mb",
    },
  },
  async headers() {
    return [
      {
        // Prevent CDN/proxy caching of all auth pages
        source: "/(login|register|forgot-password|reset-password)",
        headers: [
          { key: "Cache-Control", value: "no-store, no-cache, must-revalidate" },
        ],
      },
    ];
  },
  async rewrites() {
    return [
      // /api/convert is handled by the Next.js route handler (src/app/api/convert/route.ts)
      {
        source: "/api/:path((?!convert$).*)",
        destination: `${process.env.BACKEND_URL ?? "http://localhost:8000"}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
