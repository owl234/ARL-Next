import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import fs from 'node:fs'

// https://vite.dev/config/
export default defineConfig(({ command }) => {
  let httpsConfig = false;

  // 1. 动态加载 HTTPS 证书
  if (process.env.VITE_HTTPS === 'true') {
    // 生产环境：读取 Docker 挂载的公网真实 SSL 证书
    const keyPath = '/certs/arl.key';
    const certPath = '/certs/arl.crt';
    if (fs.existsSync(keyPath) && fs.existsSync(certPath)) {
      httpsConfig = {
        key: fs.readFileSync(keyPath),
        cert: fs.readFileSync(certPath),
      };
      console.log("🔒 生产环境：已成功加载公网 SSL 证书，启用 HTTPS。");
    } else {
      console.error("❌ 错误：生产环境未在 /certs 目录下找到 arl.key 或 arl.crt 证书！");
    }
  } else if (command === 'serve') {
    // 开发环境：读取本地自签名证书
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

  // 2. 动态加载 API 反代目标 (生产环境转发给 Docker 内的后端服务名)
  const apiTarget = process.env.VITE_API_TARGET || 'http://127.0.0.1:5001';
  console.log(`📡 API 转发目标设置为: ${apiTarget}`);

  return {
    plugins: [vue()],

    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url))
      }
    },

    server: {
      host: '0.0.0.0', // 允许局域网访问

      https: httpsConfig,// 动态赋值：开发或生产环境的 HTTPS 配置

      proxy: {
        // 当您请求 /api/user/login 时，Vite 会自动帮您把请求转发给后端
        '/api' : {
          target: apiTarget,
          changeOrigin: true,
          secure: false, // 忽略自签名的 HTTPS 证书错误
        }
      }
    }
  }
})