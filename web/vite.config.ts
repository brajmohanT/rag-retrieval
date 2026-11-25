import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// In development, forward API and image requests to the Python backend (uv run atlas-serve).
// The static export (VITE_STATIC=1) uses relative URLs so the site can live under any sub-path.
export default defineConfig(({ mode }) => ({
  plugins: [react()],
  base: loadEnv(mode, '.', 'VITE_').VITE_STATIC === '1' ? './' : '/',
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/page-images': 'http://127.0.0.1:8000',
    },
  },
}))
