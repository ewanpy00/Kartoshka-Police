import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// The product tour as plain files for the Gatekeeper APK (make tour): one classic script, one stylesheet and
// an index.html, so the WebView can open it from file:///android_asset/tour/ with no server.
const PAGE = `<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
    <link rel="stylesheet" href="tour.css" />
    <style>html, body { margin: 0; background: #0b1320; }</style>
    <title>Kartoshka tour</title>
  </head>
  <body>
    <div id="app"></div>
    <script src="tour.js"></script>
  </body>
</html>
`

export default defineConfig({
  plugins: [vue(), { name: 'tour-page', generateBundle() { this.emitFile({ type: 'asset', fileName: 'index.html', source: PAGE }) } }],
  define: { 'process.env.NODE_ENV': '"production"' },
  publicDir: false,
  build: {
    outDir: '../gatekeeper/app/src/main/assets/tour',
    emptyOutDir: true,
    lib: { entry: 'src/showcase/tour-main.ts', formats: ['iife'], name: 'KartoshkaTour', fileName: () => 'tour.js', cssFileName: 'tour' },
  },
})
