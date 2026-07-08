# 伏羲体系 Vue 3 迁移文档

## 概述

本文档详细说明了伏羲体系企业知识认知平台前端从传统架构迁移到 Vue 3 架构的完整过程。

## 迁移目标

1. **现代化架构**: 从原生 JavaScript 迁移到 Vue 3 Composition API
2. **组件化开发**: 实现可复用的组件设计
3. **状态管理**: 使用 Pinia 进行全局状态管理
4. **路由管理**: 使用 Vue Router 进行声明式路由管理
5. **UI 组件库**: 集成 Element Plus 提供丰富的 UI 组件
6. **构建工具**: 使用 Vite 提供快速的开发体验
7. **样式管理**: 使用 SCSS 进行模块化样式管理

## 技术栈

### 核心框架
- **Vue 3.4+**: 渐进式 JavaScript 框架
- **Vite 5.4+**: 下一代前端构建工具
- **Element Plus 2.7+**: Vue 3 UI 组件库

### 状态管理
- **Pinia 2.1+**: Vue 状态管理库

### 路由管理
- **Vue Router 4.3+**: Vue 官方路由管理器

### HTTP 客户端
- **Axios 1.7+**: 基于 Promise 的 HTTP 客户端

### 工具库
- **DOMPurify 3.1+**: HTML 净化库
- **Lodash ES 4.17+**: 实用工具库
- **Marked 12.0+**: Markdown 解析器

### 开发工具
- **Sass 1.77+**: CSS 预处理器
- **@element-plus/icons-vue 2.3+**: Element Plus 图标库

## 项目结构

```
vue3-migration/
├── src/
│   ├── api/                    # API 客户端
│   │   └── index.js
│   ├── assets/                 # 静态资源
│   │   └── styles/             # 样式文件
│   │       ├── variables.scss  # SCSS 变量
│   │       └── main.scss       # 主样式
│   ├── components/             # 组件
│   │   ├── admin/              # 管理面板组件
│   │   ├── chat/               # 对话组件
│   │   ├── files/              # 文件组件
│   │   └── search/             # 搜索组件
│   ├── layouts/                # 布局组件
│   │   └── MainLayout.vue
│   ├── router/                 # 路由配置
│   │   └── index.js
│   ├── stores/                 # 状态管理
│   │   ├── auth.js
│   │   ├── chat.js
│   │   └── files.js
│   ├── views/                  # 页面视图
│   │   ├── Login.vue
│   │   ├── Chat.vue
│   │   ├── Search.vue
│   │   ├── Files.vue
│   │   └── Admin.vue
│   ├── App.vue                 # 根组件
│   └── main.js                 # 入口文件
├── index.html                  # 主入口 HTML
├── login.html                  # 登录页 HTML
├── admin.html                  # 管理页 HTML
├── package.json                # 项目配置
├── vite.config.js              # Vite 配置
└── README.md                   # 项目说明
```

## 核心模块说明

### 1. API 客户端 (`src/api/index.js`)

统一的 API 客户端，封装了 Axios 实例，包含：
- 请求拦截器：自动添加认证 Token
- 响应拦截器：统一处理错误和 401 认证失败
- 超时设置：30 秒超时
- 基础配置：JSON 格式请求/响应

### 2. 状态管理 (`src/stores/`)

#### auth.js - 认证状态
- Token 管理
- 用户信息管理
- 登录/登出功能
- 权限检查

#### chat.js - 对话状态
- 消息列表管理
- 发送消息功能
- 加载状态管理
- 错误处理

#### files.js - 文件状态
- 文件列表管理
- 文件上传功能
- 文件删除功能
- 加载状态管理

### 3. 路由配置 (`src/router/index.js`)

- 路由懒加载
- 路由守卫（认证检查）
- 权限控制（管理员权限）
- 路由元信息

### 4. 布局组件 (`src/layouts/MainLayout.vue`)

- 侧边栏导航
- 顶部栏
- 用户信息显示
- 响应式设计

### 5. 页面视图 (`src/views/`)

#### Login.vue - 登录页
- 登录表单
- 表单验证
- 错误提示
- 加载状态

#### Chat.vue - 对话页
- 消息列表
- 消息输入
- 自动滚动
- 加载指示器

#### Search.vue - 搜索页
- 搜索输入
- 搜索结果
- 结果展示
- 空状态处理

#### Files.vue - 文件管理页
- 文件列表
- 文件上传
- 文件下载
- 文件删除

#### Admin.vue - 管理面板页
- 系统状态
- 评测管理
- 知识库管理
- 用户管理

### 6. 组件 (`src/components/`)

#### 对话组件
- **ChatMessage.vue**: 消息展示组件
  - 用户/助手消息样式
  - Markdown 渲染
  - 来源显示
  - 置信度显示
  - 时间显示

- **ChatInput.vue**: 消息输入组件
  - 文本输入
  - 发送按钮
  - 快捷键支持
  - 禁用状态

#### 搜索组件
- **SearchResult.vue**: 搜索结果组件
  - 结果标题
  - 结果摘要
  - 匹配度显示
  - 来源信息

#### 文件组件
- **FileUpload.vue**: 文件上传组件
  - 拖拽上传
  - 文件选择
  - 上传进度
  - 文件限制

#### 管理组件
- **SystemStatus.vue**: 系统状态组件
  - 系统信息
  - 知识库统计
  - API 统计
  - 用户统计

- **EvaluationPanel.vue**: 评测面板组件
  - 评测列表
  - 运行评测
  - 查看报告
  - 状态显示

- **KnowledgePanel.vue**: 知识库组件
  - 文档列表
  - 重建索引
  - 删除文档
  - 上传文档

- **UserPanel.vue**: 用户管理组件
  - 用户列表
  - 添加用户
  - 编辑用户
  - 重置密码
  - 删除用户

## 样式系统

### SCSS 变量 (`src/assets/styles/variables.scss`)

定义了全局样式变量：
- 颜色变量
- 文本颜色
- 背景颜色
- 边框颜色
- 阴影
- 圆角
- 间距
- 字体大小
- 侧边栏宽度

### 主样式 (`src/assets/styles/main.scss`)

全局样式重置和增强：
- 盒模型重置
- 字体设置
- 滚动条样式
- 链接样式
- Element Plus 组件样式增强

## 配置说明

### Vite 配置 (`vite.config.js`)

```javascript
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { resolve } from 'path';

export default defineConfig({
  plugins: [vue()],
  root: '.',
  base: './',
  build: {
    outDir: 'dist',
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
        login: resolve(__dirname, 'login.html'),
        admin: resolve(__dirname, 'admin.html'),
      },
    },
    minify: 'terser',
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
  css: {
    preprocessorOptions: {
      scss: {
        additionalData: `@import "@/assets/styles/variables.scss";`,
      },
    },
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
});
```

### package.json 配置

```json
{
  "name": "fuxi-frontend-vue3",
  "version": "1.50.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "vue": "^3.4.0",
    "vue-router": "^4.3.0",
    "pinia": "^2.1.0",
    "element-plus": "^2.7.0",
    "@element-plus/icons-vue": "^2.3.0",
    "axios": "^1.7.0",
    "dompurify": "^3.1.0",
    "lodash-es": "^4.17.0",
    "marked": "^12.0.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.0",
    "vite": "^5.4.0",
    "sass": "^1.77.0"
  }
}
```

## 开发指南

### 环境准备

1. 安装 Node.js 16+
2. 安装 npm 或 yarn
3. 克隆项目代码

### 安装依赖

```bash
cd vue3-migration
npm install
```

### 开发服务器

```bash
npm run dev
```

访问 http://localhost:3000

### 生产构建

```bash
npm run build
```

### 预览构建结果

```bash
npm run preview
```

## 组件开发规范

### 1. 使用 `<script setup>` 语法

```vue
<script setup>
import { ref, computed } from 'vue';

const count = ref(0);
const doubleCount = computed(() => count.value * 2);

function increment() {
  count.value++;
}
</script>
```

### 2. Props 定义

```vue
<script setup>
const props = defineProps({
  title: {
    type: String,
    required: true,
  },
  count: {
    type: Number,
    default: 0,
  },
});
</script>
```

### 3. Emits 定义

```vue
<script setup>
const emit = defineEmits(['update', 'delete']);

function handleUpdate() {
  emit('update', data);
}
</script>
```

### 4. 样式作用域

```vue
<style scoped lang="scss">
.component {
  // 组件样式
}
</style>
```

## 状态管理规范

### 1. Store 定义

```javascript
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';

export const useCounterStore = defineStore('counter', () => {
  const count = ref(0);
  const doubleCount = computed(() => count.value * 2);

  function increment() {
    count.value++;
  }

  return {
    count,
    doubleCount,
    increment,
  };
});
```

### 2. Store 使用

```vue
<script setup>
import { useCounterStore } from '@/stores/counter';

const counterStore = useCounterStore();
</script>

<template>
  <div>
    <p>Count: {{ counterStore.count }}</p>
    <p>Double: {{ counterStore.doubleCount }}</p>
    <button @click="counterStore.increment()">Increment</button>
  </div>
</template>
```

## 路由管理规范

### 1. 路由定义

```javascript
import { createRouter, createWebHistory } from 'vue-router';

const routes = [
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    children: [
      {
        path: '',
        name: 'Home',
        component: () => import('@/views/Home.vue'),
      },
    ],
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
```

### 2. 路由守卫

```javascript
router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore();

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next('/login');
  } else {
    next();
  }
});
```

## API 调用规范

### 1. API 客户端使用

```javascript
import apiClient from '@/api';

// GET 请求
const data = await apiClient.get('/api/users');

// POST 请求
const result = await apiClient.post('/api/users', { name: 'John' });

// PUT 请求
const updated = await apiClient.put('/api/users/1', { name: 'Jane' });

// DELETE 请求
await apiClient.delete('/api/users/1');
```

### 2. 错误处理

```javascript
try {
  const data = await apiClient.get('/api/data');
  // 处理成功响应
} catch (error) {
  // 处理错误
  console.error('请求失败:', error.message);
}
```

## 部署指南

### 开发环境部署

```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 访问 http://localhost:3000
```

### 生产环境部署

```bash
# 构建生产版本
npm run build

# 预览构建结果
npm run preview

# 部署 dist 目录到服务器
```

### Nginx 配置

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        root /path/to/dist;
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 常见问题

### 1. 依赖安装失败

```bash
# 清除缓存
npm cache clean --force

# 删除 node_modules
rm -rf node_modules

# 重新安装
npm install
```

### 2. 开发服务器启动失败

- 检查端口 3000 是否被占用
- 检查 Node.js 版本（推荐 16+）
- 检查防火墙设置

### 3. API 请求失败

- 检查后端服务是否启动
- 检查代理配置是否正确
- 检查网络连接

### 4. 样式不生效

- 检查 SCSS 变量是否正确导入
- 检查样式作用域
- 检查 CSS 优先级

### 5. 组件不渲染

- 检查组件导入路径
- 检查组件注册
- 检查模板语法

## 更新日志

### v1.50.0 (2026-07-03)
- 初始 Vue 3 迁移版本
- 实现核心功能模块
- 完成组件化架构
- 集成 Element Plus UI 组件库

## 贡献指南

1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

## 许可证

ISC License