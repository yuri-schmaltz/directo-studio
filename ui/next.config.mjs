// Directo UI — Next.js 14 configuration.
// The `directo` brand replaces the previous "maestro" identity.
// Backend API URL is inlined at build time via NEXT_PUBLIC_DIRECTO_API_URL.

const backend = process.env.DIRECTO_API_URL || "http://localhost:8000";

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  env: {
    NEXT_PUBLIC_DIRECTO_API_URL: backend,
  },
  experimental: {
    serverActions: {
      bodySizeLimit: "10mb",
    },
  },
};

export default nextConfig;
