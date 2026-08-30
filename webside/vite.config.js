import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// 前端 dev server 端口。后端在 9701（见 conf.ini），两者错开，
// 同机跑 FreeMarket_Manager（9600/9601）和图床（9990）时也不打架。
const DEV_PORT = 9700
const BACKEND = 'http://127.0.0.1:9701'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  build: {
    // 按 Safari 15 压 CSS：默认 target 会把 `@media (max-width: 768px)` 压成
    // 范围语法，iOS 16.4 以下整段忽略、手机样式全失效。
    cssTarget: 'safari15'
  },
  server: {
    host: '0.0.0.0',
    port: DEV_PORT,
    strictPort: true,
    // 放行全部 Host，内网直连 IP、换域名都不用改配置（仅自用/内网，勿暴露公网）
    allowedHosts: true,
    proxy: {
      // 后端全部端点都在 /api 下，一条代理规则就够
      '/api': { target: BACKEND, changeOrigin: true }
    }
  }
})
