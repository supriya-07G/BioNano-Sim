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
    // Opt in explicitly rather than disabling the check: this is a dev server,
    // and the /api proxy below means anything reaching it also reaches the
    // backend. Set VITE_ALLOWED_HOSTS to the tunnel hostname when sharing.
    allowedHosts: (process.env.VITE_ALLOWED_HOSTS ?? '')
      .split(',')
      .map((host) => host.trim())
      .filter(Boolean),
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
