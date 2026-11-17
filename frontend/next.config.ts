import type { NextConfig } from "next";

// Locally, /api goes to the FastAPI server on this machine (CHANGE 2026-11-12 A).
// On Vercel, vercel.json routes /api to the backend service, so this is
// development only. Set API_DEV_URL to use another address.
const apiDevUrl = process.env.API_DEV_URL ?? "http://127.0.0.1:8000";

export async function devRewrites(nodeEnv: string | undefined) {
  return nodeEnv === "development"
    ? [{ source: "/api/:path*", destination: `${apiDevUrl}/api/:path*` }]
    : [];
}

const nextConfig: NextConfig = {
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  rewrites: () => devRewrites(process.env.NODE_ENV),
};

export default nextConfig;
