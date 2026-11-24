/// <reference types="vitest/config" />
import path from 'node:path'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  test: { environment: 'jsdom' },
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    // design/tokens.css is shared: the repo's design/ on the host, /design in the container. No parent directories.
    fs: { allow: [__dirname, path.resolve(__dirname, '../design'), '/design'] },
    proxy: {
      '/api': {
        target: process.env.CORE_PROXY_TARGET ?? 'http://127.0.0.1:8000',
        ws: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
