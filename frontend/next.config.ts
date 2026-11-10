import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  devIndicators: false,
  poweredByHeader: false,
  async headers() {
    const api = new URL(process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1");
    if (!["http:", "https:"].includes(api.protocol) || api.username || api.password) {
      throw new Error("NEXT_PUBLIC_API_URL must be an HTTP(S) URL without credentials");
    }
    const development = process.env.NODE_ENV === "development";
    const csp = [
      "default-src 'self'",
      "base-uri 'none'",
      "frame-ancestors 'none'",
      "form-action 'self'",
      "object-src 'none'",
      `script-src 'self' 'unsafe-inline'${development ? " 'unsafe-eval'" : ""}`,
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob:",
      "font-src 'self'",
      `connect-src 'self' ${api.origin}${development ? " ws://localhost:3000" : ""}`,
      "frame-src 'self' blob:",
    ].join("; ");
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "no-referrer" },
        ],
      },
    ];
  },
};

export default nextConfig;
