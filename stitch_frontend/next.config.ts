import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  turbopack: {
    // The repository also has an empty root lockfile. Keep module resolution
    // scoped to the actual Next.js application instead of auto-detecting it.
    root: process.cwd(),
  },
};

export default nextConfig;
