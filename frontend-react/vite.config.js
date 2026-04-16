import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite dev server on 5173, proxies /api → FastAPI on 8000.
// This avoids CORS entirely in development.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
});
