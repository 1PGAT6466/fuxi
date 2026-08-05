import { defineConfig, loadEnv } from 'vite';
import vue from '@vitejs/plugin-vue';
import ElementPlus from 'unplugin-element-plus/vite';
import Components from 'unplugin-vue-components/vite';
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers';
import { resolve } from 'path';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd());

  return {
    plugins: [
      vue(),
      ElementPlus({ useSource: true }),
      Components({ resolvers: [ElementPlusResolver()] }),
    ],
    root: '.',
    base: '/',
    build: {
      outDir: 'dist',
      // 目标浏览器优化
      target: 'es2015',
      // 代码分割
      rollupOptions: {
        input: {
          main: resolve(__dirname, 'index.html'),
        },
        output: {
          // 手动分包，将大型依赖拆分为独立 chunk
          manualChunks: {
            'vue-vendor': ['vue', 'vue-router', 'pinia'],
            'utils': ['axios', 'lodash-es', 'marked', 'dompurify'],
          },
          // 小模块内联到父 chunk，减少 HTTP 请求
          inlineSizeLimit: 4096,
        },
      },
      // esbuild 压缩
      minify: 'esbuild',
      // chunk 大小警告阈值
      chunkSizeWarningLimit: 500,
    },
    server: {
      host: '0.0.0.0',
      port: 3000,
      headers: {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Referrer-Policy': 'strict-origin-when-cross-origin',
      },
      proxy: {
        '/api': {
          target: env.VITE_API_TARGET || 'http://localhost:8080',
          changeOrigin: true,
        },
      },
    },
    css: {
      preprocessorOptions: {
        scss: {
          api: 'modern-compiler',
          // additionalData 注入 variables 供所有 scss 文件使用
          additionalData: `@use "@/assets/styles/variables.scss" as *;\n`,
        },
      },
    },
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src'),
      },
    },
  };
});
