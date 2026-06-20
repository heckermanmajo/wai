import type { NextConfig } from "next";

const BACKEND_URL = process.env.WAI_BACKEND_URL ?? "http://localhost:8500";

// Alle Backend-Aufrufe laufen ueber Next.js als Same-Origin-Proxy.
// Damit ist das wai_session-Cookie aus Browser-Sicht von localhost:3000
// gesetzt — kein Cross-Site-Cookie-Tanz noetig.
const nextConfig: NextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      // Auth + Globale Service-Endpoints
      { source: "/api/me", destination: `${BACKEND_URL}/me` },
      { source: "/api/login", destination: `${BACKEND_URL}/login` },
      { source: "/api/login/pick", destination: `${BACKEND_URL}/login/pick` },
      { source: "/api/dev-users", destination: `${BACKEND_URL}/api/dev-users` },
      { source: "/api/traces", destination: `${BACKEND_URL}/api/traces` },
      { source: "/api/traces/:uid", destination: `${BACKEND_URL}/api/traces/:uid` },
      // Plan 06 — Debug-View API
      { source: "/api/debug/me", destination: `${BACKEND_URL}/api/debug/me` },
      { source: "/api/debug/traces", destination: `${BACKEND_URL}/api/debug/traces` },
      { source: "/api/debug/traces/:uid", destination: `${BACKEND_URL}/api/debug/traces/:uid` },
      { source: "/api/debug/mcps", destination: `${BACKEND_URL}/api/debug/mcps` },
      { source: "/api/debug/mcps/:name", destination: `${BACKEND_URL}/api/debug/mcps/:name` },
      { source: "/api/debug/mcps/:name/calls", destination: `${BACKEND_URL}/api/debug/mcps/:name/calls` },
      { source: "/api/debug/stream", destination: `${BACKEND_URL}/api/debug/stream` },
      { source: "/api/errors/report", destination: `${BACKEND_URL}/errors/report` },
      // Tenant-Endpoints (alle /<slug>/* Backend-Routen)
      { source: "/api/backend/:slug/:path*", destination: `${BACKEND_URL}/:slug/:path*` },
      { source: "/api/backend/:slug", destination: `${BACKEND_URL}/:slug/` },
      // Logout (gleicher Pfad wie Backend, weil Cookie-Loeschen praktisch dieselbe URL braucht)
      { source: "/api/logout/:slug", destination: `${BACKEND_URL}/:slug/logout` },
    ];
  },
};

export default nextConfig;
