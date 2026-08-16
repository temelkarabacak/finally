import type { NextConfig } from "next";

const devApiTarget = process.env.NEXT_PUBLIC_DEV_API ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  output: "export",
  images: { unoptimized: true },
  // Dev-only: proxy /api to a running backend (or `npm run mock`).
  // Rewrites are not emitted by the static export; production is same-origin.
  ...(process.env.NODE_ENV === "development"
    ? {
        async rewrites() {
          return [{ source: "/api/:path*", destination: `${devApiTarget}/api/:path*` }];
        },
      }
    : {}),
};

export default nextConfig;
