# 伏羲 v2.1 前端 — 贡献指南

欢迎为伏羲前端项目做贡献！本文档将帮助你快速了解项目结构、开发流程和构建命令。

---

## 📂 项目结构

```
vue3-migration/
├── .vscode/                  # VS Code 推荐配置（ESLint + Prettier + Vitest）
├── public/                   # 静态资源（favicon 等）
├── src/
│   ├── api/                  # API 请求封装（auth, chat, files, kb, rag…）
│   ├── assets/styles/        # 全局样式变量（SCSS）
│   ├── components/           # 公共组件
│   │   ├── admin/            # 管理后台组件
│   │   ├── chat/             # 聊天相关组件
│   │   ├── common/           # 通用 UI 组件
│   │   ├── files/            # 文件管理组件
│   │   └── search/           # 搜索相关组件
│   ├── composables/          # 组合式函数（useTheme, useNetwork…）
│   ├── constants/            # 常量定义（storage-keys, bagua…）
│   ├── layouts/              # 布局组件（MainLayout, TabBar, Sidebar）
│   ├── locales/              # 国际化（zh-CN, en-US）
│   ├── router/               # Vue Router 配置
│   ├── services/             # 微服务模块（ai-tools, dxf-viewer…）
│   ├── stores/               # Pinia 状态管理
│   │   └── __tests__/        # Store 单元测试
│   ├── styles/               # 全局样式
│   ├── types/                # TypeScript 类型定义
│   ├── utils/                # 工具函数（TokenManager, markdown…）
│   └── views/                # 页面视图
├── tests/                    # 测试配置文件
│   ├── setup.ts              # 全局测试 Setup（mock localStorage, i18n, Element Plus）
│   └── unit/                 # 单元测试
├── env.d.ts                  # 全局类型声明
├── vitest.d.ts               # Vitest 全局类型引用
├── vitest.config.ts          # Vitest 配置
├── vite.config.ts            # Vite 构建配置
├── tsconfig.json             # TypeScript 配置（strict 模式）
├── package.json              # 项目依赖与脚本
└── CONTRIBUTING.md           # 本文件
```

---

## 🚀 开发流程

### 环境要求

- **Node.js** >= 18
- **pnpm** / **npm**（推荐 pnpm）

### 安装依赖

```bash
npm install
```

### 启动开发服务器

```bash
npm run dev
```

默认在 `http://localhost:3000` 启动，API 请求代理到 `http://localhost:8080`。

### 代码质量

| 命令 | 说明 |
|------|------|
| `npm run dev` | 启动 Vite 开发服务器 |
| `npm run build` | 生产构建（输出到 `dist/`） |
| `npm run preview` | 预览生产构建 |
| `npm run lint` | ESLint 检查并自动修复 |
| `npm run lint:check` | ESLint 检查（不修复） |
| `npm run format` | Prettier 格式化 |
| `npm run format:check` | Prettier 格式检查 |
| `npm run check` | ESLint + Prettier 联合检查 |
| `npm run test` | 运行所有 Vitest 测试 |
| `npm run test:watch` | 监视模式运行测试 |
| `npm run test:ui` | Vitest UI 界面 |
| `npm run test:coverage` | 运行测试并生成覆盖率报告 |

### Git 提交

项目配置了 `husky` + `lint-staged`，提交前自动执行：

- `eslint --fix` 对 `.vue/.js/.ts` 文件
- `prettier --write` 对全部文件

---

## 🧪 测试规范

- **测试框架**：Vitest + @vue/test-utils
- **测试环境**：jsdom
- **测试文件位置**：
  - Store 测试：`src/stores/__tests__/*.test.ts`
  - 其他测试：`tests/unit/**/*.test.ts`
- **全局 Setup**：`tests/setup.ts`（mock i18n、localStorage、Element Plus 组件）

### 编写测试

```ts
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

describe('my store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('should work', () => {
    // ...
  })
})
```

---

## 🏗️ 技术栈

| 类别 | 技术 |
|------|------|
| 框架 | Vue 3 (Composition API) |
| 构建工具 | Vite 5 |
| 状态管理 | Pinia 3 |
| 路由 | Vue Router 5 |
| UI 组件库 | Element Plus 2 |
| 图表 | ECharts 6 |
| Markdown | marked + DOMPurify |
| 国际化 | vue-i18n 11 |
| 类型检查 | TypeScript 6 (strict) |
| 代码检查 | ESLint + Prettier |
| 测试 | Vitest 4 + @vue/test-utils |
| Git Hooks | Husky + lint-staged |

---

## 📐 TypeScript 严格模式

项目开启 `strict: true`（含 `strictNullChecks`、`strictFunctionTypes` 等），提交前请确保类型检查通过。

---

## 🔧 VS Code 推荐配置

`.vscode/settings.json` 已配置：

- 保存时 ESLint 自动修复
- 保存时自动格式化（Prettier）
- Vue / JS / TS / SCSS / CSS 专用格式化器
- TypeScript 使用工作区版本

推荐安装扩展（`.vscode/extensions.json` 已配置）：

- [Vue - Official](https://marketplace.visualstudio.com/items?itemName=Vue.volar)
- [ESLint](https://marketplace.visualstudio.com/items?itemName=dbaeumer.vscode-eslint)
- [Prettier](https://marketplace.visualstudio.com/items?itemName=esbenp.prettier-vscode)
- [EditorConfig](https://marketplace.visualstudio.com/items?itemName=EditorConfig.EditorConfig)

---

## 📦 依赖分包策略

生产构建时 Vite 自动将依赖拆分为独立 chunk：

- **vue-vendor**：vue, vue-router, pinia
- **element-plus**：element-plus, @element-plus/icons-vue
- **utils**：axios, lodash-es, marked, dompurify

---

> 如有任何问题，请通过 Issue 或 PR 与我们沟通。🎉
