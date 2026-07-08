# 伏羲体系 v1.50 前端 Vue 3 迁移

## 项目概述

这是伏羲体系企业知识认知平台的前端 Vue 3 迁移版本。从传统的 HTML/CSS/JavaScript 架构迁移到现代化的 Vue 3 + Vite + Element Plus 架构。

## 技术栈

- **前端框架**: Vue 3.4+
- **构建工具**: Vite 5.4+
- **UI 组件库**: Element Plus 2.7+
- **状态管理**: Pinia 2.1+
- **路由**: Vue Router 4.3+
- **HTTP 客户端**: Axios 1.7+
- **样式**: SCSS
- **图标**: @element-plus/icons-vue

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
│   │   │   ├── SystemStatus.vue
│   │   │   ├── EvaluationPanel.vue
│   │   │   ├── KnowledgePanel.vue
│   │   │   └── UserPanel.vue
│   │   ├── chat/               # 对话组件
│   │   │   ├── ChatMessage.vue
│   │   │   └── ChatInput.vue
│   │   ├── files/              # 文件组件
│   │   │   └── FileUpload.vue
│   │   └── search/             # 搜索组件
│   │       └── SearchResult.vue
│   ├── layouts/                # 布局组件
│   │   └── MainLayout.vue
│   ├── router/                 # 路由配置
│   │   └── index.js
│   ├── stores/                 # 状态管理
│   │   ├── auth.js             # 认证状态
│   │   ├── chat.js             # 对话状态
│   │   └── files.js            # 文件状态
│   ├── views/                  # 页面视图
│   │   ├── Login.vue           # 登录页
│   │   ├── Chat.vue            # 对话页
│   │   ├── Search.vue          # 搜索页
│   │   ├── Files.vue           # 文件管理页
│   │   └── Admin.vue           # 管理面板页
│   ├── App.vue                 # 根组件
│   └── main.js                 # 入口文件
├── index.html                  # 主入口 HTML
├── login.html                  # 登录页 HTML
├── admin.html                  # 管理页 HTML
├── package.json                # 项目配置
├── vite.config.js              # Vite 配置
└── README.md                   # 项目说明
```

## 功能特性

### 1. 用户认证
- 登录/登出功能
- JWT Token 管理
- 路由守卫保护
- 角色权限控制

### 2. 智能对话
- 实时对话界面
- Markdown 渲染
- 消息来源显示
- 置信度显示
- 自动滚动到底部

### 3. 知识搜索
- 全文搜索
- 搜索结果展示
- 匹配度显示
- 来源信息

### 4. 文件管理
- 文件上传（支持拖拽）
- 文件列表展示
- 文件下载
- 文件删除

### 5. 管理面板
- 系统状态监控
- 评测报告管理
- 知识库管理
- 用户管理

## 安装与运行

### 安装依赖

```bash
cd vue3-migration
npm install
```

### 开发环境

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

## 配置说明

### Vite 配置

- **端口**: 3000
- **代理**: `/api` -> `http://localhost:8080`
- **构建输出**: `dist` 目录
- **多页面入口**: 支持 index.html、login.html、admin.html

### API 接口

- **认证**: `/api/auth/login`, `/api/auth/me`
- **对话**: `/api/chat`
- **搜索**: `/api/search`
- **文件**: `/api/files`, `/api/upload`
- **管理**: `/api/admin/*`

## 迁移说明

### 从旧版本迁移

1. **备份原项目**
2. **安装依赖**: `npm install`
3. **配置 API 地址**: 修改 `vite.config.js` 中的代理配置
4. **启动开发服务器**: `npm run dev`
5. **测试功能**: 验证所有功能正常工作
6. **构建生产版本**: `npm run build`
7. **部署**: 将 `dist` 目录部署到服务器

### 主要改进

1. **现代化架构**: 使用 Vue 3 Composition API
2. **组件化开发**: 可复用的组件设计
3. **状态管理**: 使用 Pinia 进行状态管理
4. **路由管理**: 使用 Vue Router 进行路由管理
5. **UI 组件库**: 使用 Element Plus 提供丰富的 UI 组件
6. **构建工具**: 使用 Vite 提供快速的开发体验
7. **样式管理**: 使用 SCSS 进行样式管理
8. **类型安全**: 更好的代码提示和错误检查

## 开发指南

### 组件开发

- 使用 `<script setup>` 语法
- 遵循 Vue 3 Composition API 最佳实践
- 使用 TypeScript 风格的 props 定义

### 状态管理

- 使用 Pinia stores 管理全局状态
- 按功能模块划分 stores
- 使用 computed 属性处理派生状态

### 样式管理

- 使用 SCSS 变量管理主题
- 使用 scoped 样式避免样式冲突
- 遵循 BEM 命名规范

### API 调用

- 使用统一的 API 客户端
- 处理请求/响应拦截
- 统一的错误处理

## 部署说明

### 生产环境部署

1. 构建项目: `npm run build`
2. 将 `dist` 目录上传到服务器
3. 配置 Nginx 或其他 Web 服务器
4. 配置 API 代理

### Nginx 配置示例

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

# 重新安装
npm install
```

### 2. 开发服务器启动失败

- 检查端口 3000 是否被占用
- 检查 Node.js 版本（推荐 16+）

### 3. API 请求失败

- 检查后端服务是否启动
- 检查代理配置是否正确
- 检查网络连接

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