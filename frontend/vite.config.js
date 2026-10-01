import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { generateThemeTokens, themeSource } from './scripts/generate_theme_tokens.mjs'

export default defineConfig({
  plugins: [
    {
      name: 'scss-chart-tokens',
      buildStart: generateThemeTokens,
      async handleHotUpdate({ file }) {
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
