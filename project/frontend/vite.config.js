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
    coverage: {
      reporter: ['lcov', 'text', 'html'],
      exclude: [
        '**/*.test.js',
        '**/*.test.jsx',
        'node_modules/',
        'dist/',
        '.eslintrc.cjs',
        'vite.config.js',
        'package.json',
        'package-lock.json',
        'nginx.conf',
        'Dockerfile',
        '.dockerignore',
        '.gitignore',
        'README.md',
        'setup.js',
        'public/',
        '.scannerwork/',
        'coverage/',
        'transferring',
      ],
    },
  }
})
