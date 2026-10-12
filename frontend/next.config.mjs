/** @type {import('next').NextConfig} */
const nextConfig = {
  // The browser always calls /api/* on the same origin.
  // - On Vercel, the top-level rewrite in /vercel.json sends /api/* to the backend service.
  // - Locally (npm run dev), Next.js proxies /api/* to the FastAPI server instead.
  async rewrites() {
    if (process.env.VERCEL) return [];
    const backend = process.env.BACKEND_URL || "http://127.0.0.1:8000";
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
