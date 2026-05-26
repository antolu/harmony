import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: [],
  },
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 3001,
    proxy: {
      "/api": {
        target:
          process.env.API_PROXY_URL ||
          process.env.VITE_API_URL ||
          "http://harmony-api:8000",
        changeOrigin: true,
      },
    },
  },
});
