import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server runs on :5173 per the Docker Compose topology (design.md).
// Requests to /api are proxied to the Backend_API (:8000) so the
// Frontend_App can call relative paths like `/api/auth/login` in both
// local dev and the Compose stack without hardcoding the backend origin.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": "/src",
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    globals: true,
  },
});
