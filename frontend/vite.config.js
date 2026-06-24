import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// 开发期把 /api 代理到 FastAPI(8848),避免跨域并统一同源
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5234,
    proxy: {
      '/api': 'http://127.0.0.1:8848',
    },
  },
})
