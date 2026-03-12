import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  outputFileTracingRoot: path.join(__dirname),
  experimental: {
    serverActions: {
      bodySizeLimit: "500mb",
    },
  },
  async rewrites() {
    return [
      // /api/convert is handled by the Next.js route handler (src/app/api/convert/route.ts)
      {
        source: "/api/:path((?!convert$).*)",
        destination: "http://localhost:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
