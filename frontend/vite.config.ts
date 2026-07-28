import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// StarPulse's frontend and backend are two separate apps. In development,
// proxy /api to the FastAPI server so the browser never needs to deal
// with cross-origin requests; in production, point VITE_API_BASE_URL at
// wherever the backend actually lives (see src/api/client.ts).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
