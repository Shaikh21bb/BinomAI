import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The repository also carries a root lockfile for workspace tooling. Tell
  // Turbopack which directory owns this Next.js app so builds are deterministic.
  turbopack: {
    root: process.cwd(),
  },
};

export default nextConfig;
