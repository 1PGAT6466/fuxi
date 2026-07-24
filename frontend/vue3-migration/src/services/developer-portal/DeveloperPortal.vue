<template>
  <div class="developer-portal">
    <!-- 顶部统计卡片 -->
    <div class="portal-summary">
      <div class="portal-summary__card" v-for="stat in summaryStats" :key="stat.key">
        <div class="portal-summary__icon" :class="`portal-summary__icon--${stat.key}`">
          <el-icon :size="22"><component :is="stat.icon" /></el-icon>
        </div>
        <div class="portal-summary__body">
          <span class="portal-summary__value">{{ stat.value }}</span>
          <span class="portal-summary__label">{{ stat.label }}</span>
        </div>
      </div>
    </div>

    <!-- 主导航 Tabs -->
    <el-tabs v-model="store.activeTab" class="portal-tabs">
      <!-- ────── API 文档 Tab ────── -->
      <el-tab-pane label="API 文档" name="api-docs">
        <ApiDocBrowser
          :versions="store.apiVersions"
          :current-version="store.currentApiVersion"
          :doc="store.apiDoc"
          :groups="store.apiGroups"
          :loading="store.apiDocLoading"
          :error="store.apiDocError"
          @select-version="handleSelectVersion"
          @refresh="loadApiDoc"
        />
      </el-tab-pane>

      <!-- ────── SDK 下载 Tab ────── -->
      <el-tab-pane label="SDK 下载" name="sdk-download">
        <SdkDownloadPage
          :sdks="store.sdks"
          :loading="store.sdkLoading"
          :error="store.sdkError"
          :selected-language="store.selectedSdkLanguage"
          @select-language="(lang: SdkLanguage | null) => store.selectSdkLanguage(lang)"
          @refresh="loadSdks"
        />
      </el-tab-pane>

      <!-- ────── OAuth 2.0 认证 Tab ────── -->
      <el-tab-pane label="OAuth 2.0 认证" name="oauth">
        <OAuthConfig
          :apps="store.oauthApps"
          :loading="store.oauthLoading"
          :error="store.oauthError"
          :show-create-dialog="store.showCreateAppDialog"
          :last-created-app="store.lastCreatedApp"
          :show-new-app-modal="store.showNewAppModal"
          @open-create="store.openCreateAppDialog()"
          @close-create="store.closeCreateAppDialog()"
          @create-app="handleCreateOAuthApp"
          @close-new-modal="store.closeNewAppModal()"
          @refresh="loadOAuthApps"
        />
      </el-tab-pane>

      <!-- ────── 开发者社区 Tab ────── -->
      <el-tab-pane label="开发者社区" name="community">
        <DeveloperCommunity
          :posts="store.filteredPosts"
          :total="store.communityTotal"
          :loading="store.communityLoading"
          :error="store.communityError"
          :current-page="store.communityPage"
          :page-size="store.communityPageSize"
          :selected-category="store.selectedCommunityCategory"
          @select-category="(cat: CommunityCategory | null) => store.selectCommunityCategory(cat)"
          @page-change="handleCommunityPageChange"
          @refresh="loadCommunityPosts"
        />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
/**
 * 开发者门户 — 主容器组件
 *
 * 提供四个 Tab 页：
 * 1. API 文档浏览器 — OpenAPI/Swagger 文档查看
 * 2. SDK 下载 — Python / JavaScript / Java 等 SDK
 * 3. OAuth 2.0 认证 — 应用注册与配置
 * 4. 开发者社区 — 公告、教程、讨论
 */
import { ref, onMounted, watch } from 'vue';
import { ElMessage } from 'element-plus';
import {
  Document,
  Download,
  Lock,
  ChatDotRound,
} from '@element-plus/icons-vue';
import { useDeveloperPortalStore } from './store';
import type {
  SdkLanguage,
  CommunityCategory,
  CreateOAuthAppRequest,
} from './types';
import {
  getApiDocVersions,
  getApiDoc,
  getSdkList,
  getOAuthApps,
  registerOAuthApp,
  getCommunityPosts,
} from './api';
import ApiDocBrowser from './components/ApiDocBrowser.vue';
import SdkDownloadPage from './components/SdkDownloadPage.vue';
import OAuthConfig from './components/OAuthConfig.vue';
import DeveloperCommunity from './components/DeveloperCommunity.vue';

const store = useDeveloperPortalStore();

// ───── 统计卡片 ─────
interface SummaryStat {
  key: string;
  icon: typeof Document;
  value: string;
  label: string;
}

const summaryStats = ref<SummaryStat[]>([
  { key: 'docs', icon: Document, value: 'OpenAPI 3.0', label: 'API 规范' },
  { key: 'sdk', icon: Download, value: '3 种语言', label: 'SDK 支持' },
  { key: 'oauth', icon: Lock, value: 'OAuth 2.0', label: '认证标准' },
  { key: 'community', icon: ChatDotRound, value: '社区', label: '开发者生态' },
]);

// ───── 数据加载 ─────

async function loadApiDoc(version?: string): Promise<void> {
  store.apiDocLoading = true;
  store.apiDocError = null;
  try {
    // 先加载版本列表
    const versionRes = await getApiDocVersions();
    store.setApiVersions(versionRes.versions, versionRes.currentVersion);

    // 再加载具体文档
    const targetVersion = version || versionRes.currentVersion;
    const doc = await getApiDoc(targetVersion);

    // 将 OpenAPI paths 解析为分组
    const groups = parseOpenApiDoc(doc);
    store.setApiDoc(doc, groups);
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : '加载 API 文档失败';
    store.apiDocError = msg;
    ElMessage.error(msg);
  } finally {
    store.apiDocLoading = false;
  }
}

async function loadSdks(): Promise<void> {
  store.sdkLoading = true;
  store.sdkError = null;
  try {
    const res = await getSdkList();
    store.setSdks(res.sdks);
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : '加载 SDK 列表失败';
    store.sdkError = msg;
    ElMessage.error(msg);
  } finally {
    store.sdkLoading = false;
  }
}

async function loadOAuthApps(): Promise<void> {
  store.oauthLoading = true;
  store.oauthError = null;
  try {
    const res = await getOAuthApps();
    store.setOAuthApps(res.apps);
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : '加载 OAuth 应用列表失败';
    store.oauthError = msg;
    ElMessage.error(msg);
  } finally {
    store.oauthLoading = false;
  }
}

async function loadCommunityPosts(): Promise<void> {
  store.communityLoading = true;
  store.communityError = null;
  try {
    const res = await getCommunityPosts(
      store.communityPage,
      store.communityPageSize,
      store.selectedCommunityCategory || undefined,
    );
    store.setCommunityPosts(res.posts, res.total, res.page);
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : '加载社区帖子失败';
    store.communityError = msg;
    ElMessage.error(msg);
  } finally {
    store.communityLoading = false;
  }
}

// ───── 事件处理 ─────

function handleSelectVersion(version: string): void {
  loadApiDoc(version);
}

async function handleCreateOAuthApp(data: CreateOAuthAppRequest): Promise<void> {
  try {
    const app = await registerOAuthApp(data);
    store.addOAuthApp(app);
    store.setLastCreatedApp(app);
    store.closeCreateAppDialog();
    ElMessage.success(`OAuth 应用「${app.name}」注册成功`);
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : '注册 OAuth 应用失败';
    ElMessage.error(msg);
  }
}

function handleCommunityPageChange(page: number): void {
  store.communityPage = page;
  loadCommunityPosts();
}

// ───── 生命周期 ─────

onMounted(() => {
  // 只加载首个 Tab 的数据，其他 Tab 按需加载
  loadApiDoc();
});

// 监听 Tab 切换实现懒加载
watch(
  () => store.activeTab,
  (tab) => {
    if (tab === 'sdk-download' && store.sdks.length === 0 && !store.sdkLoading) {
      loadSdks();
    }
    if (tab === 'oauth' && store.oauthApps.length === 0 && !store.oauthLoading) {
      loadOAuthApps();
    }
    if (tab === 'community' && store.communityPosts.length === 0 && !store.communityLoading) {
      loadCommunityPosts();
    }
  },
);

// ───── 工具函数 ─────

function parseOpenApiDoc(doc: import('./types').OpenApiDoc): import('./types').ApiEndpointGroup[] {
  const tagMap = new Map<string, import('./types').ApiEndpointDef[]>();

  // 从 tags 初始化分组
  if (doc.tags) {
    for (const tag of doc.tags) {
      tagMap.set(tag.name, []);
    }
  }

  // 遍历 paths 收集端点
  if (doc.paths) {
    for (const [path, methods] of Object.entries(doc.paths)) {
      if (!methods || typeof methods !== 'object') continue;
      for (const [method, detail] of Object.entries(methods as Record<string, unknown>)) {
        if (!['get', 'post', 'put', 'delete', 'patch'].includes(method)) continue;
        const d = detail as Record<string, unknown>;
        const tags: string[] = Array.isArray(d.tags) ? d.tags as string[] : ['default'];
        const endpointDef: import('./types').ApiEndpointDef = {
          method: method.toUpperCase() as 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH',
          path,
          summary: (d.summary as string) || (d.description as string) || '',
          description: (d.description as string) || '',
          parameters: Array.isArray(d.parameters)
            ? (d.parameters as Array<Record<string, unknown>>).map((p) => ({
                name: p.name as string,
                in: (p.in as string) || 'query',
                required: Boolean(p.required),
                description: (p.description as string) || '',
                schema: (p.schema || { type: 'string' }) as import('./types').ApiSchema,
              }))
            : [],
          requestBody: d.requestBody as import('./types').ApiRequestBody | undefined,
          responses: (d.responses || {}) as Record<string, import('./types').ApiResponseDef>,
          deprecated: Boolean(d.deprecated),
        };

        for (const tagName of tags) {
          if (!tagMap.has(tagName)) {
            tagMap.set(tagName, []);
          }
          tagMap.get(tagName)!.push(endpointDef);
        }
      }
    }
  }

  return Array.from(tagMap.entries())
    .filter(([, eps]) => eps.length > 0)
    .map(([tag, endpoints]) => ({
      tag,
      name: doc.tags?.find((t) => t.name === tag)?.description || tag,
      description: doc.tags?.find((t) => t.name === tag)?.description || '',
      endpoints,
    }));
}
</script>

<style scoped lang="scss">
.developer-portal {
  max-width: 1280px;
  margin: 0 auto;
  padding: 24px 24px;
  color: var(--text-primary);
}

/* ────── 统计卡片 ────── */
.portal-summary {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.portal-summary__card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 20px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  transition:
    transform var(--duration-normal) var(--ease-out),
    box-shadow var(--duration-normal) var(--ease-out);

  &:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
  }
}

.portal-summary__icon {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;

  &--docs {
    background: var(--brand-soft);
    color: var(--brand);
  }

  &--sdk {
    background: var(--xun-color-light);
    color: var(--xun-color);
  }

  &--oauth {
    background: var(--qian-color-light);
    color: var(--qian-color);
  }

  &--community {
    background: var(--li-color-light);
    color: var(--li-color);
  }
}

.portal-summary__body {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.portal-summary__value {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

.portal-summary__label {
  font-size: 12px;
  color: var(--text-tertiary);
}

/* ────── Tabs ────── */
.portal-tabs {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  padding: 4px 20px 20px;
}

/* ────── 响应式 ────── */
@media (max-width: 1023px) {
  .portal-summary {
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }
}

@media (max-width: 767px) {
  .developer-portal {
    padding: 16px 12px;
  }

  .portal-summary {
    grid-template-columns: 1fr;
    gap: 10px;
  }

  .portal-tabs {
    padding: 4px 12px 16px;
  }
}
</style>
