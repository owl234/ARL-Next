import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import viteCompression from 'vite-plugin-compression'
import Components from 'unplugin-vue-components/vite'
import { AntDesignVueResolver } from 'unplugin-vue-components/resolvers'
import AutoImport from 'unplugin-auto-import/vite'

// https://vite.dev/config/
export default defineConfig(({ command }) => {
  const apiTarget = process.env.VITE_API_TARGET || 'http://127.0.0.1:5000';

  return {
    plugins: [
      vue(),
      AutoImport({
        imports: ['vue', 'vue-router'],
        resolvers: [AntDesignVueResolver()],
      }),
      Components({
        resolvers: [
          AntDesignVueResolver({
            importStyle: false, // css in js
          }),
        ],
      }),
      viteCompression({
        verbose: true,
        disable: false,
        threshold: 1024, // only compress files larger than 1k
        algorithm: 'gzip',
        ext: '.gz',
      })
    ],

    // 生产环境移除 console.log 和 debugger，提升运行性能
    esbuild: {
      drop: command === 'build' ? ['console', 'debugger'] : [],
    },

    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url))
      }
    },

    server: {
      host: '0.0.0.0',
      port: 5173,
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
          secure: false,
        },
        '/update_stream': {
          target: process.env.VITE_UPDATER_TARGET || 'http://127.0.0.1:8888',
          changeOrigin: true,
        }
      }
    },

    // 打包优化配置
    build: {
      chunkSizeWarningLimit: 2000,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (id.includes('node_modules')) {
              if (id.includes('echarts') || id.includes('zrender')) {
                return 'echarts';
              }
              if (id.includes('codemirror') || id.includes('@codemirror') || id.includes('vue-codemirror')) {
                return 'codemirror';
              }
              if (id.includes('@ant-design/icons-vue') || id.includes('@ant-design/icons')) {
                return 'ant-design-icons';
              }
              if (id.includes('ant-design-vue')) {
                return 'ant-design-vue';
              }
              if (id.includes('vue') || id.includes('vue-router') || id.includes('@vue')) {
                return 'vue-vendor';
              }
              return 'vendor';
            }
          }
        }
      }
    }
  }
})