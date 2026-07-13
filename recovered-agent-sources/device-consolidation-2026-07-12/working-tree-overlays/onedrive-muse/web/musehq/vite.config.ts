import { defineConfig } from "vite"
import solid from "vite-plugin-solid"

// musehq.io front-end. Solid + Vite so we can compose OpenCode's vendored
// SolidJS chat renderer (vendor/opencode/*) directly, dressed in the MUSE look.
export default defineConfig({
  base: process.env.MUSEHQ_BASE || "/",
  plugins: [solid()],
  build: {
    target: "esnext",
    // Emitted into the Vercel/cockpit output by scripts/deploy/build_cockpit_vercel.sh.
    outDir: "dist",
    emptyOutDir: true,
  },
  server: {
    port: 9200,
    // Proxy the chat + gateway API to a locally running muse web server.
    proxy: {
      "/api": {
        target: process.env.MUSE_API_ORIGIN || "http://127.0.0.1:9119",
        changeOrigin: true,
      },
    },
  },
})
