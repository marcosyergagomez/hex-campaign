import { defineConfig, type Plugin } from "vite"
import react from "@vitejs/plugin-react"

// The browser stays on this origin. /api is forwarded to uvicorn, so the
// session cookie is first-party. API_ORIGIN must be http://localhost:5173.
// These headers are not applied to /api, so they do not replace the API policy.
const SHARED = [
  "default-src 'self'",
  "base-uri 'self'",
  "object-src 'none'",
  "frame-src 'none'",
  "frame-ancestors 'none'",
  "form-action 'self'",
  "font-src https://fonts.gstatic.com",
  "img-src 'self'",
].join("; ")

// Dev injects the stylesheet and the React Refresh preamble. The hash is the
// exact preamble from @vitejs/plugin-react 4.7; update it if that script changes.
const DEV_POLICY = [
  SHARED,
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "script-src 'self' 'sha256-Z2/iFzh9VMlVkEOar1f/oSHWwQk3ve1qk/C2WdsC4Xk='",
  "connect-src 'self' ws://localhost:5173 ws://127.0.0.1:5173 https://fonts.googleapis.com https://fonts.gstatic.com",
].join("; ")

const PREVIEW_POLICY = [
  SHARED,
  "style-src 'self' https://fonts.googleapis.com",
  "script-src 'self'",
  "connect-src 'self' https://fonts.googleapis.com https://fonts.gstatic.com",
].join("; ")

function securityHeaders(): Plugin {
  return {
    name: "security-headers",
    configureServer(server) {
      server.middlewares.use(harden(DEV_POLICY))
    },
    configurePreviewServer(server) {
      server.middlewares.use(harden(PREVIEW_POLICY))
    },
  }
}

function harden(policy: string) {
  return (
    req: { url?: string },
    res: { setHeader: (name: string, value: string) => void },
    next: () => void,
  ) => {
    const url = req.url ?? ""
    if (url === "/api" || url.startsWith("/api/") || url.startsWith("/api?")) {
      next()
      return
    }
    res.setHeader("X-Frame-Options", "DENY")
    res.setHeader("X-Content-Type-Options", "nosniff")
    res.setHeader("Referrer-Policy", "no-referrer")
    res.setHeader("Cross-Origin-Opener-Policy", "same-origin")
    res.setHeader("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    res.setHeader("Content-Security-Policy", policy)
    next()
  }
}

export default defineConfig({
  plugins: [react(), securityHeaders()],
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
  preview: {
    port: 4173,
    strictPort: true,
  },
})
