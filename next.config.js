/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // API w Pythonie pod /api/* są serwowane przez Vercel z folderu api/
  // Next.js nie obsługuje tych ścieżek – wywołania idą bezpośrednio na /api/batch_search itd.
};

module.exports = nextConfig;
