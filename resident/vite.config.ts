import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Resident screens (docs/app-plan.md decision 8): published on BIND_ADDR so the demo phone can open them.
// They call only resident routes and never hold the write token.
export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 5174,
    strictPort: true,
    // shared tokens: ./design is mounted at /design (app at /app) in the container, ../design on the host
    fs: { allow: ['.', '..', '/design'] },
    proxy: {
      '/api': {
        target: process.env.CORE_PROXY_TARGET ?? 'http://127.0.0.1:8000',
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
