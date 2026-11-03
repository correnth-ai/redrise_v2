// Build-only bundler for the Tauri UI (no web server is shipped).
import path from "node:path";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

export default defineConfig({
  base: "./",
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "src") } },
  build: { outDir: "dist", emptyOutDir: true, target: "es2022", chunkSizeWarningLimit: 1500 },
  server: { port: 5174, strictPort: true },
});
