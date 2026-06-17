import { defineConfig } from "vite";
import { resolve } from "path";

export default defineConfig({
  build: {
    outDir: resolve(__dirname, "dist"),
    emptyOutDir: true,
    rollupOptions: {
      input: resolve(__dirname, "src/main.ts"),
      output: {
        entryFileNames: "ai-dashboard.js",
        assetFileNames: (info) =>
          info.name?.endsWith(".css") ? "ai-dashboard.css" : "[name][extname]",
      },
    },
  },
});
