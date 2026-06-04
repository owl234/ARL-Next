import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import fs from 'node:fs' // 1. 新增：引入 Node 的文件读取模块

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],

  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },

  server: {
    // 2. 新增：开启 HTTPS 并读取刚才在根目录下生成的证书
    https: {
      key: fs.readFileSync(fileURLToPath(new URL('../certs/localhost-key.pem', import.meta.url))),
      cert: fs.readFileSync(fileURLToPath(new URL('../certs/localhost.pem', import.meta.url))),
    },

    proxy: {
      // 当你请求 /api/user/login 时，Vite会自动帮你把请求转发给后端
      '/api' : {
        target: 'http://127.0.0.1:5003', // 保持你原有的 5003 端口不变
        changeOrigin: true,
        secure: false, // 忽略ARL本地自签名的HTTPS证书错误
      }
    }
  }
})