import type { NextConfig } from "next";
import { createMDX } from "fumadocs-mdx/next";

// Next injects inline bootstrap scripts, so script-src keeps 'unsafe-inline'; everything else is locked down.
export const CSP = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${process.env.NODE_ENV === "production" ? "" : " 'unsafe-eval'"}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  "connect-src 'self'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  async redirects() {
    return [
      { source: "/docs", destination: "/", permanent: true },
      // Hide account entry points during the workspace preview.
      { source: "/auth/sign-in", destination: "/app", permanent: false },
      { source: "/auth/sign-up", destination: "/app", permanent: false },
    ];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "same-origin" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Content-Security-Policy", value: CSP },
        ],
      },
    ];
  },
};

export default createMDX()(nextConfig);
