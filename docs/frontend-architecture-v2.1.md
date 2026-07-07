# 伏羲 v2.1 八卦体系 · 前端技术架构设计文档

> **版本**: v2.1-draft  
> **作者**: 前端开发专家  
> **日期**: 2026-07-06  
> **状态**: 设计评审阶段  

---

## 目录

1. [前言](#前言)
2. [现状分析](#现状分析)
3. [技术栈选择](#1-技术栈选择)
4. [页面路由设计](#2-页面路由设计)
5. [组件树设计](#3-组件树设计)
6. [API 对接方案](#4-api-对接方案)
7. [性能优化](#5-性能优化)
8. [八卦主题与视觉规范](#6-八卦主题与视觉规范)
9. [工程化与部署](#7-工程化与部署)
10. [实施路线图](#8-实施路线图)

---

## 前言

### v2.1 八卦体系简述

伏羲 v2.1 将后端八大功能模块映射为八卦，前端同样以八卦为导航隐喻：

| 卦象 | 卦名 | 后端功能 | 前端路由 | 含义 |
|------|------|---------|---------|------|
| ☰ | 乾 (qián) | 意图循环对话 | `/chat` | 天行健 — AI 对话引擎 |
| ☷ | 坤 (kūn) | 知识库管理 | `/knowledge` | 地势坤 — 厚德载物，知识沉淀 |
| ☲ | 离 (lí) | 知识检索 | `/search` | 明两作 — 知识之光，精准搜索 |
| ☳ | 震 (zhèn) | 文档上传 | `/upload` | 震惊百里 — 文档注入，惊雷行动 |
| ☶ | 艮 (gèn) | 系统监控 | `/monitor` | 兼山艮 — 不动如山，稳定守护 |
| ☴ | 巽 (xùn) | 知识图谱 | `/graph` | 随风巽 — 知识关联网络 |
| ☵ | 坎 (kǎn) | 基础设施 | `/infra` | 水洊至 — 底层流动 |
| 中宫 | (Center) | 自进化数据 | `/evolution` | 中宫调和，体系自省 |

---

## 现状分析

### 现有前端状态

通过分析仓库 `E:\easyclaw\伏羲-v1.44\repo\frontend\` 目录，现状如下：

#### 当前技术栈（已实现，无需推翻）

| 层级 | 技术选型 | 版本 |
|------|---------|------|
| 框架 | **Vue 3** (Composition API) + TypeScript | 3.5.39 |
| 构建工具 | **Vite** | 5.4.21 |
| UI 组件库 | **Element Plus** | 2.7.0 |
| 状态管理 | **Pinia** | 3.0.4 |
| 路由 | **Vue Router** | 5.1.0 |
| HTTP 客户端 | **Axios** | 1.7.0 |
| 样式 | **SCSS** + CSS Variables (亮/暗双主题) | — |
| 国际化 | **vue-i18n** | 11.4.6 |
| Markdown | **marked** (已有) | 12.0.0 |
| XSS 防御 | **DOMPurify** (已有) | 3.1.0 |
| 测试 | **Vitest** + @vue/test-utils | 4.1.9 |
| Linter | **ESLint** + Prettier + Husky | 10.6.0 |

#### 已有目录结构

```
vue3-migration/
├── src/
│   ├── api/index.ts              ← API 客户端（Axios 封装）
│   ├── assets/styles/            ← SCSS 变量、主题、响应式
│   ├── components/
│   │   ├── admin/                ← 管理面板子组件（4个）
│   │   ├── chat/                 ← ChatMessage、ChatInput
│   │   ├── common/               ← AppHeader、AppSidebar
│   │   ├── files/                ← FileUpload
│   │   └── search/               ← SearchResult
│   ├── composables/              ← useTheme 等
│   ├── layouts/MainLayout.vue    ← 主布局
│   ├── locales/                  ← zh-CN / en-US
│   ├── router/index.ts           ← 路由配置 + 守卫
│   ├── stores/                   ← auth、chat、files (Pinia)
│   ├── types/index.ts            ← TypeScript 类型定义
│   ├── utils/                    ← helpers、markdown
│   └── views/                    ← 7 个页面视图
├── dist/                         ← 构建产物（已有 admin/login 多入口）
├── tests/                        ← Vitest 单元测试
└── config files...
```

#### 已有功能（v1.50 已实现）

| 功能 | 状态 | 说明 |
|------|------|------|
| JWT 登录 | ✅ | 含路由守卫、token 拦截器 |
| AI 对话 | ✅ | ChatMessage 组件 + Markdown 渲染 |
| 知识搜索 | ✅ | SearchResult 卡片 |
| 文件管理 | ✅ | 上传/列表/删除 |
| Wiki | ✅ | 含详情页 |
| 管理面板 | ✅ | 含评测/用户管理 |
| 暗色模式 | ✅ | useTheme composable + system 跟随 |
| 国际化 | ✅ | zh-CN + en-US |

#### 现有问题（v2.1 需要解决）

1. **无八卦导航**：首页是简单的 4 卡片布局，缺少九宫格八卦导航
2. **无八卦健康可视化**：`AppHeader` 中只有红/绿圆点，无八卦级状态
3. **无 SSE/WebSocket 流式对话**：当前是 `POST /api/chat` 一次性返回
4. **无虚拟滚动**：消息列表和文档列表未做大数据量优化
5. **路由缺少 v2.1 新页面**：knowledge、upload、monitor、evolution、graph、infra
6. **home.html 与 index.html 分离**：v1.50 有三个入口 HTML，需要统一为 SPA

### 结论

**继承 Vue 3 + Element Plus + Pinia 技术栈，不引入新框架。在现有 vue3-migration 基础上增量扩展。**

这最大程度保护了 v1.50 迁移的成果，团队无需重新学习，前端代码已在生产验证。

---

## 1. 技术栈选择

### 1.1 核心框架层（保持不变）

```
Vue 3.5 (Composition API + <script setup>)  → 框架核心，已生产验证
TypeScript 6.0                               → 类型安全（已有 93%+ TS 覆盖）
Vite 5.4                                     → 极速 HMR + ESBuild 压缩
```

### 1.2 UI 与交互层

| 包名 | 用途 | 版本 | 决策理由 |
|------|------|------|---------|
| **element-plus** | 全局 UI 组件库 | 2.7 | 已有，无需替换 |
| **@element-plus/icons-vue** | 图标系统 | 2.3 | 已有 |
| **ECharts** | 图表可视化（新增） | 5.5+ | 八卦仪表盘、进化趋势图、健康雷达图 |
| **vue-echarts** | ECharts Vue3 封装 | 7.0+ | 与 Vue3 声明式集成 |
| **GSAP** | 动画引擎（新增） | 3.12+ | 八卦转场动画、爻变过渡效果 |
| **@vueuse/core** | Composables 工具（新增） | 11+ | useIntervalFn（轮询）、useWebSocket、useVirtualList |

### 1.3 数据与状态层

| 包名 | 用途 | 版本 |
|------|------|------|
| **pinia** | 全局状态管理 | 3.0（已有） |
| **axios** | HTTP 请求 | 1.7（已有） |
| **marked** + **DOMPurify** | Markdown 渲染 + XSS | 已有 |

### 1.4 无需新增的决策

- ❌ **不引入 React/Vue 混合架构** — 增加包体积和心智负担
- ❌ **不使用 VitePress/Astro** — 这是 App 不是文档站
- ❌ **不引入 Three.js** — 八卦导航用 CSS 3D Transforms 即可，无需 WebGL

---

## 2. 页面路由设计

### 2.1 完整路由表

```
/login          → 登录页（独立布局，无 sidebar）
/ (redirect: /home)  → 根路径重定向

MainLayout 子路由（需 JWT 认证）:
  /home         → 首页 · 九宫格八卦导航 + 系统仪表盘
  /chat         → 乾卦 ☰ · AI 意图循环对话（流式 SSE）
  /knowledge    → 坤卦 ☷ · 知识库文档管理（表格 + 操作）
  /search       → 离卦 ☲ · 知识检索（全文搜索 + 结果卡片）
  /upload       → 震卦 ☳ · 文档上传（拖拽上传 + 批量处理）
  /monitor      → 艮卦 ☶ · 系统监控（八维健康雷达图 + 指标）
  /graph        → 巽卦 ☴ · 知识图谱可视化
  /infra        → 坎卦 ☵ · 基础设施状态（断路器、依赖健康）
  /evolution    → 中宫 · 自进化数据（意图统计、反馈分析、演化趋势）
  /admin        → 管理面板（管理员）（保留，重构为八卦子页面）
```

> **数据获取指令**: `GET /api/documents → 知识库文档列表`、`GET /api/health/bagua → 八卦级健康`、`GET /api/search → 知识检索`、`POST /api/chat?engine=v2 → 乾卦对话`（已有后端实现，前端直接对接）

### 2.2 路由懒加载配置

所有子路由使用 dynamic `import()`，在 `vite.config.ts` 的 `manualChunks` 中配合：

```ts
// router/index.ts — v2.1 扩展
const Home = () => import('@/views/Home.vue');
const Chat = () => import('@/views/Chat.vue');
const Knowledge = () => import('@/views/Knowledge.vue');
const Search = () => import('@/views/Search.vue');
const Upload = () => import('@/views/Upload.vue');
const Monitor = () => import('@/views/Monitor.vue');
const Graph = () => import('@/views/Graph.vue');
const Infra = () => import('@/views/Infra.vue');
const Evolution = () => import('@/views/Evolution.vue');
const Admin = () => import('@/views/Admin.vue');
```

### 2.3 路由守卫增强

保留现有 JWT 守卫逻辑，新增：

- **八卦导航面包屑**：`router.afterEach` 中设置 `document.title` 为当前卦象名
- **页面离开确认**：对话页和上传页使用 `beforeRouteLeave` 防数据丢失

### 2.4 多入口合并

v1.50 有 `index.html` / `login.html` / `admin.html` 三个入口。v2.1 统一为单一 `index.html` SPA：

```ts
// vite.config.ts — 移除多入口
build: {
  rollupOptions: {
    input: {
      main: resolve(__dirname, 'index.html'),  // 唯一入口
    },
    // ...
  },
}
```

---

## 3. 组件树设计

### 3.1 全局组件树

```
App.vue
├── Login.vue                              (独立路由，无布局)
│   └── LoginForm (内联)
├── NotFound.vue                           (独立路由)
└── MainLayout.vue                         (核心布局)
    ├── AppHeader.vue
    │   ├── BaguaStatusIndicator.vue        ← 八卦健康指示器
    │   ├── BreadcrumbTrail.vue             ← 卦象面包屑
    │   └── ThemeToggle                     (内联)
    ├── AppSidebar.vue
    │   ├── NavSection (知识服务)
    │   │   ├── NavItem → /chat     (乾 ☰)
    │   │   ├── NavItem → /knowledge (坤 ☷)
    │   │   ├── NavItem → /search   (离 ☲)
    │   │   ├── NavItem → /upload   (震 ☳)
    │   │   └── NavItem → /graph    (巽 ☴)
    │   └── NavSection (系统运维)
    │       ├── NavItem → /monitor  (艮 ☶)
    │       ├── NavItem → /infra    (坎 ☵)
    │       └── NavItem → /evolution (中宫)
    ├── <router-view />                    ← 页面插槽
    │   ├── Home.vue
    │   │   ├── BaguaGrid.vue              ← 九宫格导航
    │   │   │   └── BaguaCell.vue × 9      ← 每个卦格
    │   │   └── DashboardPanel.vue          ← 系统概览卡片
    │   ├── Chat.vue
    │   │   ├── ChatMessage.vue × N
    │   │   └── ChatInput.vue
    │   ├── Knowledge.vue
    │   │   └── DocumentTable.vue           ← 含虚拟滚动
    │   ├── Search.vue
    │   │   └── SearchResultCard.vue × N
    │   ├── Upload.vue
    │   │   └── FileUploadPanel.vue
    │   │       └── DropZone.vue
    │   ├── Monitor.vue
    │   │   ├── BaguaRadarChart.vue         ← ECharts 雷达图
    │   │   └── MetricGauges.vue            ← 指标仪表盘
    │   ├── Graph.vue
    │   │   └── KnowledgeGraphCanvas.vue    ← ECharts 关系图
    │   ├── Infra.vue
    │   │   └── ServiceHealthList.vue       ← 断路器状态列表
    │   ├── Evolution.vue
    │   │   ├── IntentDistributionChart.vue
    │   │   └── FeedbackTimeline.vue
    │   └── Admin.vue                       (保留 v1.50)
    │       ├── SystemStatus.vue
    │       ├── EvaluationPanel.vue
    │       ├── KnowledgePanel.vue
    │       └── UserPanel.vue
    └── AppFooter.vue                       ← 可选页脚
```

### 3.2 核心新增组件详解

#### 3.2.1 BaguaGrid（九宫格导航）

```
BaguaGrid.vue
  Props: { guaStatuses: BaguaStatus[] }
  Slots: 无

布局: CSS Grid 3×3，纯 CSS 实现，零 JavaScript。
每个格 = BaguaCell.vue，接收 guaName、status、route 等 props。

CSS 示意:
  .bagua-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    grid-template-rows: repeat(3, 1fr);
    gap: 16px;
    aspect-ratio: 1/1;
    max-width: 600px;
    margin: 0 auto;
  }
```

#### 3.2.2 BaguaCell（卦象格子）

```
BaguaCell.vue
  Props: {
    name: string,          // "乾"
    trigram: string,       // "☰"
    symbol: string,        // Unicode 八卦符号
    route: string,         // "/chat"
    healthLevel: 'FULL' | 'DEGRADED' | 'MINIMAL' | 'OFF',
    description: string,
  }
  Emits: ['navigate']

视觉:
  - FULL     → 渐变紫色边框 + 呼吸光晕
  - DEGRADED → 黄色边框 + 轻微闪烁
  - MINIMAL  → 橙色边框 + "降级运行"标签
  - OFF      → 灰色背景 + "不可用"戳记
```

#### 3.2.3 BaguaStatusIndicator（八卦状态指示器）

```
BaguaStatusIndicator.vue
  Props: { compact?: boolean }   // 紧凑模式用于 Sidebar
  Data: 从 pollHealth() 获取 8 个卦状态

用法:
  <BaguaStatusIndicator />        ← Header 中使用，展开 8 个小图标
  <BaguaStatusIndicator compact /> ← Sidebar 中使用，仅显示异常数

视觉效果:
  8 个互锁的阴阳鱼小点，颜色映射健康状态
  - 全部健康: 整体绿色呼吸
  - 部分异常: 黄色脉冲
  - 多个异常: 红色报警（但非阻塞）
```

#### 3.2.4 ChatMessage 增强（流式渲染）

在现有 `ChatMessage.vue` 基础上：
- 新增 `isStreaming` prop 控制打字机效果
- 使用 CSS `@keyframes blink` 显示流式光标
- 支持针对 v2 引擎的 `sources` 和 `confidence` 展示

#### 3.2.5 BaguaRadarChart（八卦健康雷达图）

```
BaguaRadarChart.vue
  使用 ECharts 雷达图 (radar type)
  8 个轴对应八卦，显示各卦健康分（0-100）
  数据来源: GET /api/health/bagua
```

---

## 4. API 对接方案

### 4.1 api.ts 增强封装

在现有 `src/api/index.ts` 基础上新增：

```ts
// src/api/index.ts — v2.1 新增 API 方法

import apiClient from './index';
import type {
  BaguaHealthResponse,
  InfrastructureHealth,
  EvolutionData,
  StreamChatRequest,
} from '@/types';

// ============ 八卦健康相关 ============

/** 八卦级健康状态 */
export async function getBaguaHealth(): Promise<BaguaHealthResponse> {
  return apiClient.get('/api/health/bagua');
}

/** 基础设施健康（坎卦） */
export async function getInfraHealth(): Promise<InfrastructureHealth> {
  return apiClient.get('/api/health/infra');
}

/** 系统整体健康 */
export async function getSystemHealth(): Promise<{ status: string; timestamp: number }> {
  return apiClient.get('/api/health');
}

// ============ 文档管理（坤卦）============

export async function getDocuments(params?: {
  page?: number;
  pageSize?: number;
}): Promise<{ documents: DocumentInfo[]; total: number }> {
  return apiClient.get('/api/documents', { params });
}

export async function deleteDocument(id: string): Promise<void> {
  return apiClient.delete(`/api/documents/${id}`);
}

// ============ 知识检索（离卦）============

export async function searchKnowledge(query: string, options?: {
  topK?: number;
  threshold?: number;
}): Promise<{ results: SearchResult[]; total: number }> {
  return apiClient.get('/api/search', { params: { q: query, ...options } });
}

// ============ 文件上传（震卦）============

export async function uploadDocument(
  file: File,
  onProgress?: (pct: number) => void,
): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append('file', file);

  return apiClient.post('/api/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (event) => {
      if (event.total && onProgress) {
        onProgress(Math.round((event.loaded * 100) / event.total));
      }
    },
  });
}

// ============ 自进化数据（中宫）============

export async function getEvolutionData(): Promise<EvolutionData> {
  return apiClient.get('/api/evolution');
}
```

### 4.2 SSE 流式对话（乾卦核心）

**当前**: `POST /api/chat` 一次性返回整个 `{ answer }`。

**v2.1**: 使用 Server-Sent Events (SSE) 逐步返回 token。

```ts
// src/api/stream.ts — SSE 流式对话客户端

import { fetchEventSource } from '@microsoft/fetch-event-source';

interface StreamCallbacks {
  onToken: (token: string) => void;
  onComplete: (fullAnswer: string) => void;
  onError: (error: Error) => void;
}

export async function streamChat(
  query: string,
  callbacks: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const token = localStorage.getItem('token');
  let fullAnswer = '';

  await fetchEventSource('/api/chat?engine=v2', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ query }),
    signal,
    onmessage(event) {
      if (event.data === '[DONE]') {
        callbacks.onComplete(fullAnswer);
        return;
      }
      try {
        const { token: t } = JSON.parse(event.data);
        fullAnswer += t;
        callbacks.onToken(fullAnswer);
      } catch {
        // 非 JSON 数据，可能是原始文本
        fullAnswer += event.data;
        callbacks.onToken(fullAnswer);
      }
    },
    onerror(err) {
      callbacks.onError(err);
      throw err; // 停止重连
    },
  });
}
```

**依赖**: `@microsoft/fetch-event-source` (约 2KB gzip)，需要 `npm install`。

**备选方案**: 如需更多控制（如双向通信），可使用 `@vueuse/core` 的 `useWebSocket`，但考虑到八卦对话是单向请求-流式响应，SSE 更轻量。

> **与后端的对接要求**: 后端 `POST /api/chat?engine=v2` 需将响应头设为 `Content-Type: text/event-stream`，并逐个发送 SSE 事件，格式：
> ```
> data: {"token":"你好"}
> data: {"token":"，我"}
> data: {"token":"是伏羲"}
> data: [DONE]
> ```

### 4.3 八卦健康状态轮询

#### 方案：增量轮询（非全量）

不采用固定间隔全量轮询，而是按用户可见性分层：

| 组件位置 | 轮询频率 | 数据来源 | 说明 |
|---------|---------|---------|------|
| `BaguaStatusIndicator` (Header 常驻) | 30s | `/api/health/bagua` | 全局状态，低频即可 |
| `Monitor.vue` (艮卦页面激活时) | 5s | `/api/health/bagua` | 用户正在观察，高频 |
| `Infra.vue` (坎卦页面激活时) | 10s | `/api/health/infra` | 基础设施详情 |

```ts
// src/composables/useBaguaHealth.ts

import { ref, onMounted, onUnmounted, computed } from 'vue';
import { useIntervalFn } from '@vueuse/core';
import { getBaguaHealth } from '@/api';
import type { BaguaHealthResponse } from '@/types';

export function useBaguaHealth(intervalMs: number = 30000) {
  const data = ref<BaguaHealthResponse | null>(null);
  const error = ref<string | null>(null);
  const loading = ref(false);

  const { pause, resume, isActive } = useIntervalFn(async () => {
    try {
      data.value = await getBaguaHealth();
      error.value = null;
    } catch (e) {
      error.value = e instanceof Error ? e.message : '健康检查失败';
    }
  }, intervalMs, { immediate: true });

  // 页面激活时提速，隐藏时降速 — 通过 composable 暴露 pause/resume 给页面级控制

  const overallHealth = computed(() => {
    if (!data.value) return 'unknown';
    const statuses = Object.values(data.value.gua_statuses);
    if (statuses.every(s => s.health_level === 'FULL')) return 'healthy';
    if (statuses.some(s => s.health_level === 'OFF')) return 'critical';
    return 'degraded';
  });

  return { data, error, loading, overallHealth, pause, resume, isActive };
}
```

### 4.4 错误处理统一层

扩展 `apiClient` 响应拦截器：

```ts
// 响应拦截器增强
apiClient.interceptors.response.use(
  (response) => response.data,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    if (error.response?.status === 503) {
      // 八卦断路 — 后端在降级模式，前端展示优雅降级提示
      console.warn('[Fuxi] 服务降级中，部分功能可能受限');
    }
    return Promise.reject(error);
  },
);
```

---

## 5. 性能优化

### 5.1 九宫格 — 纯 CSS Grid，零 JavaScript

```
设计原则: 不引入任何 JS 动画库来计算八卦位置。
使用 CSS Grid 3×3 + CSS Transforms 实现所有布局。

.bagua-grid {
  display: grid;
  grid-template-areas:
    "qian kun zhen"
    "xun  center gen"
    "li   kan   dui";
  gap: clamp(8px, 2vw, 24px);
}

.bagua-cell {
  aspect-ratio: 1;
  transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1),
              box-shadow 0.3s ease;
}

.bagua-cell:hover {
  transform: scale(1.05);
  box-shadow: 0 8px 32px rgba(102, 126, 234, 0.3);
}

/* 中宫特殊样式 — 更大、居中 */
.bagua-cell.center {
  grid-area: center;
  transform-origin: center;
  background: radial-gradient(circle, ...);
}
```

> 性能收益: 零布局计算、GPU 加速 transition、无重排（只改变 transform/opacity）

### 5.2 虚拟滚动 — 文档列表与对话记录

| 场景 | 方案 | 库 |
|------|------|-----|
| 文档列表（坤卦） | `el-table-v2` (Element Plus 内置虚拟表格) | 已有 |
| 对话消息列表（乾卦） | `useVirtualList` (@vueuse/core) | 新增 |
| 搜索结果列表 | 虚拟列表（超 100 条时启用） | @vueuse/core |

```vue
<!-- DocumentTable.vue — 使用 Element Plus 虚拟表格 -->
<template>
  <el-table-v2
    :columns="columns"
    :data="documents"
    :width="'100%'"
    :height="400"
    fixed
  />
</template>

<script setup lang="ts">
import { ElTableV2 } from 'element-plus';

const columns = [
  { key: 'filename', title: '文件名', dataKey: 'filename', width: 200 },
  { key: 'size', title: '大小', dataKey: 'size', width: 100 },
  { key: 'uploaded_at', title: '上传时间', dataKey: 'uploaded_at', width: 180 },
  { key: 'actions', title: '操作', width: 120, cellRenderer: ActionCell },
];
</script>
```

### 5.3 构建优化增强

在现有 `vite.config.ts` 的 `manualChunks` 基础上新增：

```ts
manualChunks: {
  'vue-vendor': ['vue', 'vue-router', 'pinia'],
  'element-plus': ['element-plus', '@element-plus/icons-vue'],
  'echarts': ['echarts', 'vue-echarts'],        // ← 新增
  'gsap': ['gsap'],                               // ← 新增
  'utils': ['axios', 'lodash-es', 'marked', 'dompurify'],
}
```

- ECharts 按需引入：只导入 `RadarChart`、`GaugeChart`、`GraphChart`，避免全量 1MB+
- GSAP 按需引入：只用 `gsap` 核心 + `ScrollTrigger` 插件

### 5.4 图片与资源优化

- 八卦符号使用 Unicode 字符（☰☷☲☳☶☴☵☱），零网络请求
- 太极图使用内联 SVG（~200 bytes），不加载外部资源
- favicon 保持不变

### 5.5 包体积目标

| 指标 | v1.50 当前 | v2.1 目标 | 增量 |
|------|-----------|-----------|------|
| 首屏 JS | ~400KB | ~450KB | +ECharts 八图模块 |
| 首屏 CSS | ~60KB | ~70KB | +八卦动画样式 |
| 懒加载页面均值 | ~5KB/页 | ~8KB/页 | 新增图表依赖 |
| Lighthouse Performance | ~90 | ≥90 | 保持 |
| Lighthouse Accessibility | ~95 | ≥95 | 追加 ARIA 标签 |

---

## 6. 八卦主题与视觉规范

### 6.1 八卦配色

| 卦象 | 主色 | 辅色 | CSS 变量 |
|------|------|------|---------|
| 乾 ☰ | `#9B59B6` (紫) | `#D2B4DE` | `--gua-qian` |
| 坤 ☷ | `#8B4513` (褐) | `#D2B48C` | `--gua-kun` |
| 离 ☲ | `#E74C3C` (赤) | `#F5B7B1` | `--gua-li` |
| 震 ☳ | `#27AE60` (绿) | `#A9DFBF` | `--gua-zhen` |
| 艮 ☶ | `#7F8C8D` (灰) | `#BDC3C7` | `--gua-gen` |
| 巽 ☴ | `#2980B9` (蓝) | `#AED6F1` | `--gua-xun` |
| 坎 ☵ | `#1ABC9C` (青) | `#A3E4D7` | `--gua-kan` |
| 兑 ☱ | `#F39C12` (金) | `#F9E79F` | `--gua-dui` |
| 中宫 | `#8E44AD` (深紫) | `#D7BDE2` | `--gua-center` |

### 6.2 关联 CSS 变量（扩展 variables.scss）

```scss
// src/assets/styles/variables.scss — 新增八卦色板
:root {
  // 八色 / 太极黑白
  --gua-bg: #ffffff;
  --gua-text: #1a1a2e;
  --gua-accent: var(--color-primary);

  // 健康状态色
  --health-full: #22c55e;      // 绿色 — FULL
  --health-degraded: #f59e0b;  // 黄色 — DEGRADED
  --health-minimal: #f97316;   // 橙色 — MINIMAL
  --health-off: #ef4444;       // 红色 — OFF
}

[data-theme="dark"] {
  --gua-bg: #0f0f23;
  --gua-text: #e0e0e0;
}
```

---

## 7. 工程化与部署

### 7.1 目录结构（v2.1 最终）

```
frontend/vue3-migration/          ← 保持项目根路径不变
├── index.html                    ← 唯一入口（合并 login/admin）
├── package.json                  ← 新增 deps: echarts, vue-echarts, gsap, @vueuse/core, @microsoft/fetch-event-source
├── vite.config.ts                ← 增强 manualChunks，移除多入口
├── tsconfig.json
├── src/
│   ├── main.ts                   ← 保持不变
│   ├── App.vue                   ← 新增 <BaguaStatusIndicator>
│   ├── api/
│   │   ├── index.ts              ← 增强：新增八卦 API 方法
│   │   └── stream.ts             ← 新增：SSE 流式对话
│   ├── assets/styles/
│   │   ├── variables.scss        ← 新增八卦色板 CSS 变量
│   │   ├── bagua-grid.scss       ← 新增：九宫格专用样式
│   │   ├── main.scss
│   │   └── ...
│   ├── components/
│   │   ├── bagua/                ← 新增目录
│   │   │   ├── BaguaGrid.vue
│   │   │   ├── BaguaCell.vue
│   │   │   └── BaguaStatusIndicator.vue
│   │   ├── chat/
│   │   │   ├── ChatMessage.vue   ← 增强：流式渲染
│   │   │   └── ChatInput.vue
│   │   ├── common/               ← 保持不变
│   │   │   ├── AppHeader.vue     ← 增加 BaguaStatusIndicator 引用
│   │   │   └── AppSidebar.vue    ← 八卦导航项
│   │   ├── monitor/              ← 新增目录
│   │   │   ├── BaguaRadarChart.vue
│   │   │   └── MetricGauges.vue
│   │   ├── knowledge/
│   │   │   └── DocumentTable.vue
│   │   ├── evolution/            ← 新增目录
│   │   │   ├── IntentDistributionChart.vue
│   │   │   └── FeedbackTimeline.vue
│   │   ├── infra/                ← 新增目录
│   │   │   └── ServiceHealthList.vue
│   │   ├── search/
│   │   │   └── SearchResultCard.vue
│   │   └── upload/
│   │       ├── DropZone.vue
│   │       └── FileUploadPanel.vue
│   ├── composables/
│   │   ├── useBaguaHealth.ts     ← 新增
│   │   ├── useTheme.ts           ← 保持
│   │   └── useStreamChat.ts      ← 新增
│   ├── layouts/
│   │   └── MainLayout.vue        ← 增强：八卦侧边栏
│   ├── router/
│   │   └── index.ts              ← 新增 6 条八卦路由
│   ├── stores/
│   │   ├── auth.ts
│   │   ├── chat.ts               ← 增强：流式状态管理
│   │   ├── files.ts
│   │   ├── knowledge.ts          ← 新增
│   │   └── monitor.ts
│   ├── stores/
│   │   ├── auth.ts
│   │   ├── chat.ts               ← 增强：流式状态管理
│   │   ├── files.ts
│   │   ├── knowledge.ts          ← 新增
│   │   └── monitor.ts            ← 新增
│   ├── types/
│   │   └── index.ts              ← 增强：新增 BaguaHealth、StreamChat 等类型
│   ├── utils/
│   │   ├── helpers.ts
│   │   └── markdown.ts
│   └── views/
│       ├── Home.vue              ← 重构：九宫格 + 仪表盘
│       ├── Chat.vue              ← 增强：流式对话
│       ├── Knowledge.vue         ← 新增（坤卦）
│       ├── Search.vue
│       ├── Upload.vue            ← 新增（震卦）
│       ├── Monitor.vue           ← 新增（艮卦）
│       ├── Graph.vue             ← 新增（巽卦）
│       ├── Infra.vue             ← 新增（坎卦）
│       ├── Evolution.vue         ← 新增（中宫）
│       ├── Admin.vue             ← 保留
│       └── NotFound.vue
├── tests/
│   └── unit/
│       ├── components/
│       │   ├── BaguaGrid.test.ts
│       │   ├── BaguaCell.test.ts
│       │   └── BaguaStatusIndicator.test.ts
│       ├── composables/
│       │   └── useBaguaHealth.test.ts
│       └── stores/
│           └── knowledgeStore.test.ts
└── ...

### 7.2 新增 npm 依赖清单

```bash
cd frontend/vue3-migration

# 图表可视化（八卦健康雷达图、进化趋势）
npm install echarts vue-echarts

# Composables 工具集（轮询、虚拟列表、WebSocket）
npm install @vueuse/core

# SSE 流式对话（乾卦核心）
npm install @microsoft/fetch-event-source

# 动画引擎（卦象转场、爻变效果）
npm install gsap
```

### 7.3 构建与部署

保持现有 Vite 构建流程，无需额外配置：

```bash
# 开发
npm run dev              # http://localhost:3000，代理 /api → localhost:8080

# 生产构建
npm run build            # → dist/

# 预览
npm run preview

# 测试
npm test                 # vitest run
npm run test:ui          # vitest --ui（可视化测试）
```

Nginx 部署配置保持不变（v1.50 已有完整配置）。

---

## 8. 实施路线图

### 阶段一：基础架构搭建（1-2 天）

| 任务 | 文件 | 说明 |
|------|------|------|
| 安装新依赖 | `package.json` | echarts, vue-echarts, @vueuse/core, @microsoft/fetch-event-source, gsap |
| 增强 TypeScript 类型 | `types/index.ts` | 新增 BaguaHealthResponse, StreamChatOptions, InfrastructureStatus 等 |
| 增强 API 模块 | `api/index.ts` | 新增 7 个八卦 API 方法 |
| 新增流式 API 模块 | `api/stream.ts` | SSE fetchEventSource 封装 |
| 新增八卦健康 composable | `composables/useBaguaHealth.ts` | 分层轮询逻辑 |
| 新增流式对话 composable | `composables/useStreamChat.ts` | 管理 streaming 状态 |
| 扩展 CSS 变量 | `assets/styles/variables.scss` | 八卦色板 + 健康状态色 |
| 新增九宫格样式 | `assets/styles/bagua-grid.scss` | 纯 CSS Grid 布局 |

### 阶段二：八卦导航系统（1 天）

| 任务 | 文件 | 说明 |
|------|------|------|
| BaguaCell 组件 | `components/bagua/BaguaCell.vue` | 八卦格子，含 healthy/degraded/minimal/off 四态 |
| BaguaGrid 组件 | `components/bagua/BaguaGrid.vue` | 九宫格容器，CSS Grid 3×3 |
| BaguaStatusIndicator | `components/bagua/BaguaStatusIndicator.vue` | 紧凑型 8 点状态指示器 |
| 重构 Home.vue | `views/Home.vue` | 九宫格 + 仪表盘替换旧的 4 卡片 |
| 更新 AppSidebar | `components/common/AppSidebar.vue` | 八卦导航项 + 紧凑状态指示器 |

### 阶段三：路由与页面骨架（1 天）

| 任务 | 文件 | 说明 |
|------|------|------|
| 扩展路由配置 | `router/index.ts` | 新增 6 条八卦路由 + 守卫增强 |
| Knowledge 页面 | `views/Knowledge.vue` | 坤卦 — 文档管理 |
| Upload 页面 | `views/Upload.vue` | 震卦 — 拖拽上传 |
| Monitor 页面 | `views/Monitor.vue` | 艮卦 — ECharts 雷达图 |
| Graph 页面 | `views/Graph.vue` | 巽卦 — 知识图谱 |
| Infra 页面 | `views/Infra.vue` | 坎卦 — 基础设施状态 |
| Evolution 页面 | `views/Evolution.vue` | 中宫 — 自进化数据 |
| 合并入口 HTML | `index.html` | 单一入口，移除 login.html/admin.html |

### 阶段四：功能实现（2-3 天）

| 任务 | 文件 | 说明 |
|------|------|------|
| SSE 流式对话 | `views/Chat.vue` + `api/stream.ts` | fetchEventSource + 打字机效果 |
| 文档表格虚拟滚动 | `components/knowledge/DocumentTable.vue` | el-table-v2 虚拟表格 |
| 健康雷达图 | `components/monitor/BaguaRadarChart.vue` | ECharts radar，8 轴八卦 |
| 上传拖拽区 | `components/upload/DropZone.vue` | HTML5 drag & drop |
| 知识图谱可视化 | `components/graph/KnowledgeGraphCanvas.vue` | ECharts graph |
| 进化趋势图 | `components/evolution/IntentDistributionChart.vue` | ECharts line/bar |
| 断路器状态面板 | `components/infra/ServiceHealthList.vue` | 表格 + 状态标签 |
| ChatMessage 增强 | `components/chat/ChatMessage.vue` | 流式渲染 + 置信度展示 |

### 阶段五：测试与优化（1-2 天）

| 任务 | 说明 |
|------|------|
| 组件单元测试 | BaguaGrid, BaguaCell, BaguaStatusIndicator 的 vitest |
| Composable 测试 | useBaguaHealth 的 mock API + 轮询行为测试 |
| 集成测试 | 整个八卦导航流程 + 路由守卫 |
| Lighthouse 审计 | 确保 Performance ≥ 90, Accessibility ≥ 95 |
| 包体积检查 | rollup-plugin-visualizer 生成分析报告 |
| 跨浏览器测试 | Chrome + Edge + Firefox（Windows/Linux） |
| 响应式测试 | 移动端 (<768px) + 平板 + 桌面 |

### 阶段六：部署上线（0.5 天）

| 任务 | 说明 |
|------|------|
| 生产构建 | `npm run build` → dist/ |
| Nginx 部署 | 更新配置（单一入口 SPA） |
| 冒烟测试 | 对话 / 搜索 / 上传 / 健康监控 全流程 |
| 回滚预案 | 保留 v1.50 dist 备份 |

---

## 附录 A：八卦路由配置代码

```ts
// router/index.ts — v2.1 完整路由配置（关键部分）

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { requiresAuth: false, title: '登录' },
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: '/home',
      },
      {
        path: 'home',
        name: 'Home',
        component: () => import('@/views/Home.vue'),
        meta: { title: '八卦中宫', icon: 'Compass' },
      },
      {
        path: 'chat',
        name: 'Chat',
        component: () => import('@/views/Chat.vue'),
        meta: { title: '乾卦 · 天行健', gua: 'qian', trigram: '☰' },
      },
      {
        path: 'knowledge',
        name: 'Knowledge',
        component: () => import('@/views/Knowledge.vue'),
        meta: { title: '坤卦 · 地势坤', gua: 'kun', trigram: '☷' },
      },
      {
        path: 'search',
        name: 'Search',
        component: () => import('@/views/Search.vue'),
        meta: { title: '离卦 · 明两作', gua: 'li', trigram: '☲' },
      },
      {
        path: 'upload',
        name: 'Upload',
        component: () => import('@/views/Upload.vue'),
        meta: { title: '震卦 · 震惊百里', gua: 'zhen', trigram: '☳' },
      },
      {
        path: 'monitor',
        name: 'Monitor',
        component: () => import('@/views/Monitor.vue'),
        meta: { title: '艮卦 · 兼山艮', gua: 'gen', trigram: '☶' },
      },
      {
        path: 'graph',
        name: 'Graph',
        component: () => import('@/views/Graph.vue'),
        meta: { title: '巽卦 · 随风巽', gua: 'xun', trigram: '☴' },
      },
      {
        path: 'infra',
        name: 'Infra',
        component: () => import('@/views/Infra.vue'),
        meta: { title: '坎卦 · 水洊至', gua: 'kan', trigram: '☵' },
      },
      {
        path: 'evolution',
        name: 'Evolution',
        component: () => import('@/views/Evolution.vue'),
        meta: { title: '中宫 · 自进化', gua: 'center' },
      },
      {
        path: 'admin',
        name: 'Admin',
        component: () => import('@/views/Admin.vue'),
        meta: { title: '管理面板', requiresAdmin: true },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFound.vue'),
    meta: { title: '404' },
  },
];
```

## 附录 B：核心类型扩展

```ts
// types/index.ts — v2.1 新增类型

/** 单个八卦健康状态 */
export interface GuaHealth {
  gua_name: string;           // 'qian' | 'kun' | 'li' | 'zhen' | 'gen' | 'xun' | 'kan' | 'dui'
  health_level: 'FULL' | 'DEGRADED' | 'MINIMAL' | 'OFF';
  circuit_state: 'CLOSED' | 'HALF_OPEN' | 'OPEN';
  last_check: number;         // Unix timestamp in ms
  message?: string;
  dependencies?: {
    name: string;
    status: 'healthy' | 'degraded' | 'failed';
    latency_ms: number;
  }[];
}

/** 八卦健康 API 响应 */
export interface BaguaHealthResponse {
  timestamp: number;
  overall: 'healthy' | 'degraded' | 'critical';
  gua_statuses: Record<string, GuaHealth>;
}

/** 基础设施健康（坎卦） */
export interface InfrastructureHealth {
  services: {
    name: string;
    status: 'up' | 'down' | 'degraded';
    uptime_seconds: number;
    last_error?: string;
    circuit_breaker: 'CLOSED' | 'OPEN' | 'HALF_OPEN';
  }[];
  timestamp: number;
}

/** 自进化数据（中宫） */
export interface EvolutionData {
  intent_distribution: { intent: string; count: number }[];
  feedback_timeline: { timestamp: number; positive: number; negative: number }[];
  model_versions: { version: string; deployed_at: number; metrics: Record<string, number> }[];
}

/** 流式对话选项 */
export interface StreamChatOptions {
  onToken: (partialResponse: string) => void;
  onDone: (fullResponse: string) => void;
  onError: (error: Error) => void;
  abortSignal?: AbortSignal;
}

/** 增强 ChatMessage（已有，扩展） */
// ChatMessage 已有 role/content/timestamp/sources/confidence
// v2.1 新增 isStreaming 用于标识流式渲染中
```

## 附录 C：设计决策记录

| 决策编号 | 决策 | 理由 | 替代方案 |
|---------|------|------|---------|
| D-001 | 继承 Vue 3 而非 React | v1.50 生产验证、团队已熟悉、组件可复用 | React 生态更成熟但切换成本高 |
| D-002 | SSE 而非 WebSocket | 对话是单向流式，SSE 更轻量、可复用现有 HTTP 鉴权 | WebSocket 需额外握手，双向时再引入 |
| D-003 | @vueuse/core 的 useIntervalFn | 内置自动清理、暂停/恢复 API，避免手写 setInterval 清理逻辑 | 手写 setInterval（已有代码中已在使用）|
| D-004 | el-table-v2 虚拟表格 | Element Plus 内置，无需新增依赖，API 与 el-table 一致 | @tanstack/vue-virtual 更灵活但需额外包 |
| D-005 | 八卦符号用 Unicode | 零网络请求、零字体依赖、完全可控尺寸 | SVG 图标库更丰富但增加体积 |
| D-006 | 中宫放在九宫格中心 | 符合八卦布局文化语义、自进化是中控 | 独立页面更清晰但与"中宫"隐喻冲突 |
| D-007 | 不强行推倒重写 | 增量迭代保护 v1.50 生产验证代码，降低回归风险 | 全重写架构更干净但时间和风险太大 |

---

> **文档状态**: 初稿完成，待评审  
> **下次评审**: 需确认后端八卦 API 的具体响应字段格式，以及 `/api/evolution` 端点是否已实现  
> **相关文档**: `docs/architecture.md`, `docs/API.md`, `frontend/vue3-migration/MIGRATION_REPORT.md`

