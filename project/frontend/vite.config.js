import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',     // ← чтобы слушал внешний интерфейс
    port: 5173,          // ← должен совпадать с containerPort
    strictPort: true
  },
  test: {
    globals: true,
    environment: 'happy-dom',
    setupFiles: './tests/setup.js',
  }
})
