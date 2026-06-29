/** @type {import('next').NextConfig} */
const nextConfig = {
  // Standalone output keeps the air-gapped Docker image small and self-contained.
  output: "standalone",
  reactStrictMode: true,
};

module.exports = nextConfig;
