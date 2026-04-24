/** @type {import('next').NextConfig} */
const API_UPSTREAM =
  process.env.API_UPSTREAM ?? "http://localhost:8000"

const nextConfig = {
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },

  // Proxy /api/* to the FastAPI backend during `next dev`.
  // In production, set NEXT_PUBLIC_API_URL on the client instead.
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${API_UPSTREAM}/api/:path*`,
      },
    ]
  },
}

export default nextConfig
