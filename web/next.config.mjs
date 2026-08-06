/** @type {import('next').NextConfig} */
const nextConfig = {
  // Static export: no server, no runtime data access, nothing that could log a
  // user's search server-side (plan.md §1.5). Deploys to any static host.
  output: 'export',
  trailingSlash: true,
  images: { unoptimized: true },
};
export default nextConfig;
