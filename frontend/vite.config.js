import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { generateThemeTokens, themeSource } from './scripts/generate_theme_tokens.mjs'

import { generateSlideTokens, slideThemeSource, slideGeometrySource } from './scripts/generate_slide_tokens.mjs'

export default defineConfig({
  plugins: [
    {
      name: 'shared-theme-tokens',
      configureServer(server) { server.watcher.add([slideThemeSource, slideGeometrySource]); },
      async buildStart() { await generateThemeTokens(); await generateSlideTokens(); },
      async handleHotUpdate({ file }) {
        if (file === slideThemeSource || file === slideGeometrySource) await generateSlideTokens();
        if (file === themeSource) await generateThemeTokens();
      }
    },
    react()
  ],
  server: {
    host: true,
    port: 5175,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8020',
        changeOrigin: true
      }
    }
  }
})
