import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In development, forward API and image requests to the Python backend (uv run atlas-serve).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/page-images': 'http://127.0.0.1:8000',
    },
  },
})
