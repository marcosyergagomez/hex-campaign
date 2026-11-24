import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"

// The browser stays on this origin. /api is forwarded to uvicorn, so the
// session cookie is first-party. API_ORIGIN must be http://localhost:5173.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: false,
      },
    },
  },
})
