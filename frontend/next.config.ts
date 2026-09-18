import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Pin the tracing root to this package so a stray lockfile in a parent directory
  // cannot change the standalone layout (server.js must stay at .next/standalone/).
  outputFileTracingRoot: __dirname,
  reactStrictMode: true,
  poweredByHeader: false,
};

export default nextConfig;
