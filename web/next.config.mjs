/** Same-origin /api proxy so the httpOnly session cookie works (DECISIONS D-004). */
const rawApi = (process.env.API_URL || "http://127.0.0.1:8000").trim().replace(/\/+$/, "");
const API_URL = /^https?:\/\//i.test(rawApi)
  ? rawApi
  : rawApi.includes(":") || rawApi.startsWith("localhost")
    ? `http://${rawApi}`
    : `https://${rawApi}`;

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  experimental: {
    // The /api proxy buffers request bodies and cut them at 10 MB by default, which truncated course uploads
    // (the app allows 5 files x 20 MB). Keep in sync with api config max_file_bytes x max_files_per_batch.
    middlewareClientMaxBodySize: "110mb",
    // Large uploads + extraction may take longer than the default 30 s proxy timeout.
    proxyTimeout: 180_000,
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
  async headers() {
    return [{
      source: "/:path*",
      headers: [
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "Referrer-Policy", value: "same-origin" },
        { key: "Permissions-Policy", value: "microphone=(self), camera=()" },
      ],
    }];
  },
};
export default nextConfig;
