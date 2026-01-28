import { defineConfig, PluginOption } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";

export default defineConfig(({ mode }) => ({
  base: mode === "production" ? "/iss-simulator/" : "/",
  server: {
    host: "::",
    port: 8080,
    proxy: {
      "/iss-simulator/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/iss-simulator/ws": {
        target: "ws://127.0.0.1:8000",
        ws: true,
        changeOrigin: true,
      },
    },
  },
  plugins: [react()] as PluginOption[],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
    dedupe: ["react", "react-dom"],
  },
}));