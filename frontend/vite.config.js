import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import fs from 'node:fs'

// https://vite.dev/config/
export default defineConfig(({ command }) => {
  let httpsConfig = false;

  // 核心逻辑：只有在本地开发环境 (执行 vite dev 时) 才尝试读取证书
  if (command === 'serve') {
    const keyPath = fileURLToPath(new URL('../certs/localhost-key.pem', import.meta.url));
    const certPath = fileURLToPath(new URL('../certs/localhost.pem', import.meta.url));

    // 加一个 existsSync 判断，防止本地还没生成证书时直接报错
    if (fs.existsSync(keyPath) && fs.existsSync(certPath)) {
      httpsConfig = {
        key: fs.readFileSync(keyPath),
        cert: fs.readFileSync(certPath),
      };
    } else {
      console.warn("⚠️ 警告：未找到本地自签名证书，开发服务器将回退到 HTTP 模式运行。");
    }
  }

  return {
    plugins: [vue()],

    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url))
      }
    },

    server: {
      // 动态赋值：开发时如果有证书就是 https 对象，否则/或打包时就是 false
      https: httpsConfig,

      proxy: {
        // 当你请求 /api/user/login 时，Vite会自动帮你把请求转发给后端
        '/api' : {
          target: 'http://127.0.0.1:5001', // 指向刚刚我们建好的 Docker 后端端口
          changeOrigin: true,
          secure: false, // 忽略本地自签名的HTTPS证书错误
        }
      }
    }
  }
})