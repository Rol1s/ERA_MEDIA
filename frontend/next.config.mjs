import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const appDir = dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  outputFileTracingRoot: appDir,
  async rewrites() {
    const backendUrl = process.env.INTERNAL_API_URL || "http://backend:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`
      },
      {
        source: "/health",
        destination: `${backendUrl}/health`
      }
    ];
  },
  typescript: {
    ignoreBuildErrors: true
  },
  experimental: {
    cpus: 1,
    workerThreads: false
  },
  turbopack: {
    root: appDir
  }
};

export default nextConfig;
