import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  server: {
    port: 5173,
    strictPort: true,
    // Vite 6 rejects requests whose Host header it does not recognise, which
    // blocks every tunnel URL (Cloudflare, ngrok) with "Blocked request".
    //
    // '.app.github.dev' is allowed by default so a Codespace works with no
    // manual step: that domain is GitHub's, the port is only reachable once
    // explicitly forwarded, and the alternative is every Codespace user
    // hitting an unexplained blank page.
    //
    // Ad-hoc tunnels stay opt-in via VITE_ALLOWED_HOSTS. Blanket-allowing
    // '.trycloudflare.com' would let any tunnel host reach this dev server,
    // and the /api proxy below means reaching it also reaches the backend.
    allowedHosts: [
      '.app.github.dev',
      // This project's reserved ngrok domain. It is permanent and specific to
      // this account, so listing it here removes the one step people forget:
      // without it the tunnel serves a bare "Blocked request" page and the
      // cause is not obvious from anything the browser shows.
      'richness-feminine-auction.ngrok-free.dev',
      ...(process.env.VITE_ALLOWED_HOSTS ?? '')
        .split(',')
        .map((host) => host.trim())
        .filter(Boolean),
    ],
    // Proxy /api to the backend so the browser sees one origin in dev. This
    // keeps CORS out of the picture entirely for the common case; the backend
    // still allows the Vite origin explicitly for direct calls.
    proxy: {
      '/api': {
        target: process.env.VITE_PROXY_TARGET ?? 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  preview: { port: 4173, strictPort: true },
  build: {
    outDir: 'dist',
    sourcemap: true,
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      output: {
        manualChunks: {
          react: ['react', 'react-dom', 'react-router-dom'],
          charts: ['recharts'],
          query: ['@tanstack/react-query'],
        },
      },
    },
  },
})
