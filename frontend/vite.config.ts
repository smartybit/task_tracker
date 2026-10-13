import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { existsSync, readFileSync } from "node:fs";
import { instanceConfig } from "./instance-config";

export default defineConfig(async ({ command }) => {
  const config = instanceConfig(process.env);
  if (existsSync(".instance-build.json")) {
    const built = JSON.parse(readFileSync(".instance-build.json", "utf8"));
    if (built.basePath !== config.basePath || built.instanceId !== config.instanceId) {
      throw new Error("Instance configuration differs from the frontend image. Rebuild it for this path and instance ID.");
    }
  }
  const target = new URL(process.env.API_PROXY_TARGET ?? "http://web:8000");
  if (!["http:", "https:"].includes(target.protocol) || target.pathname !== "/" || target.search || target.hash || target.username || target.password) {
    throw new Error("API_PROXY_TARGET must be an HTTP(S) origin without a path or credentials.");
  }
  if (command === "serve") {
    const response = await fetch(new URL("/api/v1/health/", target), { signal: AbortSignal.timeout(5000) });
    if (!response.ok || response.headers.get("X-Task-Tracker-Base-Path") !== config.basePath
        || response.headers.get("X-Task-Tracker-Instance") !== config.instanceId) {
      throw new Error("Frontend/backend instance configuration mismatch or unavailable backend.");
    }
  }
  return {
  // Navigation uses document fragments; unknown paths/assets must remain 404s.
  appType: "mpa" as const,
  base: config.basePath,
  define: { __INSTANCE_ID__: JSON.stringify(config.instanceId) },
  plugins: [react(), {
    name: "instance-metadata",
    generateBundle() { this.emitFile({ type: "asset", fileName: "instance.json", source: JSON.stringify(config) }); },
  }],
  // Generated bundles carry their mount metadata for deployment verification.
  build: { manifest: true },
  server: {
    port: 5173,
    strictPort: true,
    allowedHosts: (process.env.FRONTEND_ALLOWED_HOSTS ?? "frontend").split(","),
    proxy: {
      [`^${config.basePath}api(?:/|$)`]: {
        target: target.origin,
        changeOrigin: true,
        rewrite: (path: string) => config.basePath === "/" ? path : path.slice(config.basePath.length - 1),
      },
    },
  },
  };
});
