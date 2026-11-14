import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In dev, /api is proxied to the FastAPI server so the browser never needs the
// backend URL (and CORS is a non-issue). In production set VITE_API_URL.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true } },
  },
})
