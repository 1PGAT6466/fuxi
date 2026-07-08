import { defineConfig, loadEnv } from 'vite';
import vue from '@vitejs/plugin-vue';
import { resolve } from 'path';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd());

  return {
    plugins: [vue()],
    root: '.',
    base: './',
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
            'element-plus': ['element-plus', '@element-plus/icons-vue'],
            'utils': ['axios', 'lodash-es', 'marked', 'dompurify'],
          },
        },
      },
      // esbuild 压缩
      minify: 'esbuild',
      // chunk 大小警告阈值
      chunkSizeWarningLimit: 500,
    },
    server: {
      port: 3000,
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
