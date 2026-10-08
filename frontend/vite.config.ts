import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    allowedHosts: ["frontend"],
    proxy: {
      "/api": {
        target: process.env.API_PROXY_TARGET ?? "http://web:8000",
        changeOrigin: true,
      },
    },
  },
});
