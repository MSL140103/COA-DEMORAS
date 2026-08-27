import type { NextConfig } from "next";

// In production (e.g. on Render) the browser only ever talks to this Next.js
// server, same-origin, at /api/*. This server then proxies to the FastAPI
// backend using plain (non-NEXT_PUBLIC_) env vars, which are only resolved at
// container start — not at build time. That sidesteps the usual "the other
// service's URL isn't known yet when this one builds" problem you'd hit baking
// a NEXT_PUBLIC_API_URL in at build time.
//
// BACKEND_URL: a full URL, if you already have one (e.g. a manual deploy).
// BACKEND_HOST: just a hostname (e.g. Render's private-network service name,
//   via render.yaml's `fromService: { property: host }`) — combined here with
//   the backend's known container port (see backend/Dockerfile, EXPOSE 8000).
const BACKEND_URL =
  process.env.BACKEND_URL ??
  (process.env.BACKEND_HOST ? `http://${process.env.BACKEND_HOST}:8000` : "http://localhost:8000");

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND_URL}/:path*` }];
  },
};

export default nextConfig;
