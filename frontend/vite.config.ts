import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// During development the API runs on port 8000; in production FastAPI serves the built files.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://localhost:8000" } },
});
