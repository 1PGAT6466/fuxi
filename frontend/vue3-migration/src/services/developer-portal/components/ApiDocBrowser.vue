<template>
  <div class="api-doc-browser">
    <!-- 版本选择 & 刷新 -->
    <div class="api-doc-browser__toolbar">
      <div class="api-doc-browser__version-selector">
        <span class="api-doc-browser__label">API 版本：</span>
        <el-select
          :model-value="currentVersion"
          size="default"
          placeholder="选择版本"
          @update:model-value="$emit('select-version', $event)"
        >
          <el-option
            v-for="v in versions"
            :key="v.version"
            :label="`v${v.version} — ${v.title}`"
            :value="v.version"
          >
            <span>{{ `v${v.version} — ${v.title}` }}</span>
            <el-tag v-if="v.deprecated" size="small" type="warning" class="api-doc-browser__deprecated-tag">
              已弃用
            </el-tag>
          </el-option>
        </el-select>
      </div>
      <el-button text @click="$emit('refresh')">
        <el-icon><Refresh /></el-icon>
        刷新
      </el-button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="api-doc-browser__loading">
      <el-skeleton :rows="8" animated />
    </div>

    <!-- Error -->
    <el-alert
      v-else-if="error"
      :title="error"
      type="error"
      show-icon
      :closable="false"
      class="api-doc-browser__error"
    >
      <template #default>
        <el-button size="small" type="primary" link @click="$emit('refresh')">重试</el-button>
      </template>
    </el-alert>

    <!-- 内容：左右布局 -->
    <div v-else-if="doc" class="api-doc-browser__content">
      <!-- 左侧：分组导航 -->
      <aside class="api-doc-browser__sidebar">
        <div
          v-for="group in groups"
          :key="group.tag"
          class="api-doc-browser__group-nav"
          :class="{ 'is-active': activeGroup === group.tag }"
          @click="activeGroup = group.tag; scrollToGroup(group.tag)"
        >
          <span class="api-doc-browser__group-nav-name">{{ group.name || group.tag }}</span>
          <span class="api-doc-browser__group-nav-count">{{ group.endpoints.length }}</span>
        </div>
      </aside>

      <!-- 右侧：端点详情 -->
      <main class="api-doc-browser__main">
        <div class="api-doc-browser__info">
          <h2 class="api-doc-browser__title">{{ doc.info.title }}</h2>
          <p class="api-doc-browser__desc">{{ doc.info.description }}</p>
          <div class="api-doc-browser__meta">
            <el-tag size="small" type="info">{{ doc.openapi }}</el-tag>
            <span class="api-doc-browser__meta-item">版本：v{{ doc.info.version }}</span>
            <span
              v-if="doc.info.contact?.email"
              class="api-doc-browser__meta-item"
            >
              联系：{{ doc.info.contact.email }}
            </span>
          </div>

          <div v-if="doc.servers?.length" class="api-doc-browser__servers">
            <span class="api-doc-browser__servers-label">服务器：</span>
            <el-tag
              v-for="(server, idx) in doc.servers"
              :key="idx"
              size="small"
              effect="plain"
              class="api-doc-browser__server-tag"
            >
              {{ server.url }}
            </el-tag>
          </div>
        </div>

        <!-- 端点分组 -->
        <div
          v-for="group in groups"
          :key="group.tag"
          :id="`api-group-${group.tag}`"
          class="api-doc-browser__endpoint-group"
        >
          <h3 class="api-doc-browser__endpoint-group-title">
            {{ group.name || group.tag }}
            <el-tag size="small" round>{{ group.endpoints.length }} 个端点</el-tag>
          </h3>
          <p v-if="group.description" class="api-doc-browser__endpoint-group-desc">
            {{ group.description }}
          </p>

          <div
            v-for="ep in group.endpoints"
            :key="`${ep.method}-${ep.path}`"
            class="api-doc-browser__endpoint"
          >
            <div class="api-doc-browser__endpoint-header">
              <span class="api-doc-browser__method" :class="`api-doc-browser__method--${ep.method.toLowerCase()}`">
                {{ ep.method }}
              </span>
              <code class="api-doc-browser__path">{{ ep.path }}</code>
              <el-tag v-if="ep.deprecated" size="small" type="warning">已弃用</el-tag>
            </div>
            <p class="api-doc-browser__endpoint-summary">{{ ep.summary || ep.description }}</p>

            <!-- 参数 -->
            <div v-if="ep.parameters.length" class="api-doc-browser__section">
              <span class="api-doc-browser__section-title">参数</span>
              <el-table :data="ep.parameters" size="small" border stripe style="width: 100%">
                <el-table-column prop="name" label="名称" width="140" />
                <el-table-column prop="in" label="位置" width="80">
                  <template #default="{ row }">
                    <el-tag size="small" type="info">{{ row.in }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="required" label="必填" width="70">
                  <template #default="{ row }">
                    <span :style="{ color: row.required ? '#F56C6C' : '#909399' }">
                      {{ row.required ? '是' : '否' }}
                    </span>
                  </template>
                </el-table-column>
                <el-table-column prop="description" label="说明" min-width="180" />
              </el-table>
            </div>

            <!-- 响应 -->
            <div v-if="Object.keys(ep.responses).length" class="api-doc-browser__section">
              <span class="api-doc-browser__section-title">响应</span>
              <div
                v-for="(resp, code) in ep.responses"
                :key="code"
                class="api-doc-browser__response"
              >
                <el-tag
                  size="small"
                  :type="code.startsWith('2') ? 'success' : code.startsWith('4') ? 'warning' : 'danger'"
                >
                  {{ code }}
                </el-tag>
                <span class="api-doc-browser__response-desc">{{ resp.description }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 空状态 -->
        <el-empty v-if="!groups.length" description="暂无 API 端点" />
      </main>
    </div>

    <!-- 无文档状态 -->
    <el-empty v-else-if="!loading && !error" description="暂无 API 文档数据" />
  </div>
</template>

<script setup lang="ts">
/**
 * API 文档浏览器 — 展示 OpenAPI/Swagger 文档
 */
import { ref } from 'vue';
import { Refresh } from '@element-plus/icons-vue';
import type { ApiDocVersion, ApiEndpointGroup, OpenApiDoc } from '../types';

defineProps<{
  versions: ApiDocVersion[];
  currentVersion: string;
  doc: OpenApiDoc | null;
  groups: ApiEndpointGroup[];
  loading: boolean;
  error: string | null;
}>();

defineEmits<{
  'select-version': [version: string];
  refresh: [];
}>();

const activeGroup = ref<string>('');

function scrollToGroup(tag: string): void {
  const el = document.getElementById(`api-group-${tag}`);
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}
</script>

<style scoped lang="scss">
.api-doc-browser {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 400px;
}

.api-doc-browser__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--bg-subtle);
  border-radius: var(--radius-sm);
}

.api-doc-browser__version-selector {
  display: flex;
  align-items: center;
  gap: 8px;
}

.api-doc-browser__label {
  font-size: 14px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.api-doc-browser__deprecated-tag {
  margin-left: 8px;
}

.api-doc-browser__loading,
.api-doc-browser__error {
  padding: 16px 0;
}

.api-doc-browser__content {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 24px;
  align-items: start;
}

/* ── 侧边栏导航 ── */
.api-doc-browser__sidebar {
  position: sticky;
  top: 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px;
  background: var(--bg-subtle);
  border-radius: var(--radius-sm);
  max-height: calc(100vh - 160px);
  overflow-y: auto;
}

.api-doc-browser__group-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-radius: 4px;
  cursor: pointer;
  transition: background var(--duration-fast);
  font-size: 13px;
  color: var(--text-secondary);

  &:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
  }

  &.is-active {
    background: var(--brand-soft);
    color: var(--brand);
    font-weight: 600;
  }
}

.api-doc-browser__group-nav-count {
  font-size: 11px;
  background: var(--bg-card);
  padding: 1px 6px;
  border-radius: 10px;
  color: var(--text-tertiary);
}

/* ── 主内容 ── */
.api-doc-browser__main {
  min-width: 0;
}

.api-doc-browser__info {
  margin-bottom: 24px;
}

.api-doc-browser__title {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 8px;
}

.api-doc-browser__desc {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0 0 12px;
  line-height: 1.6;
}

.api-doc-browser__meta {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.api-doc-browser__meta-item {
  font-size: 13px;
  color: var(--text-tertiary);
}

.api-doc-browser__servers {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 4px;
}

.api-doc-browser__servers-label {
  font-size: 13px;
  color: var(--text-tertiary);
}

.api-doc-browser__server-tag {
  font-family: monospace;
  font-size: 12px;
}

/* ── 端点分组 ── */
.api-doc-browser__endpoint-group {
  margin-bottom: 28px;
  scroll-margin-top: 20px;
}

.api-doc-browser__endpoint-group-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 17px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 6px;
}

.api-doc-browser__endpoint-group-desc {
  font-size: 13px;
  color: var(--text-tertiary);
  margin: 0 0 12px;
}

/* ── 端点 ── */
.api-doc-browser__endpoint {
  padding: 14px 16px;
  background: var(--bg-subtle);
  border-radius: var(--radius-sm);
  margin-bottom: 12px;
  border-left: 3px solid transparent;
  transition: border-color var(--duration-fast);

  &:hover {
    border-left-color: var(--brand);
  }
}

.api-doc-browser__endpoint-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
  flex-wrap: wrap;
}

.api-doc-browser__method {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 700;
  font-family: monospace;
  color: #fff;
  text-transform: uppercase;

  &--get { background: #34C759; }
  &--post { background: #007AFF; }
  &--put { background: #FF9500; }
  &--delete { background: #FF3B30; }
  &--patch { background: #AF52DE; }
}

.api-doc-browser__path {
  font-family: monospace;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  background: var(--bg-card);
  padding: 2px 8px;
  border-radius: 4px;
}

.api-doc-browser__endpoint-summary {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 4px 0 10px;
}

/* ── 参数/响应 子段 ── */
.api-doc-browser__section {
  margin-top: 10px;
}

.api-doc-browser__section-title {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 6px;
}

.api-doc-browser__response {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
}

.api-doc-browser__response-desc {
  font-size: 13px;
  color: var(--text-secondary);
}

/* ── 响应式 ── */
@media (max-width: 767px) {
  .api-doc-browser__content {
    grid-template-columns: 1fr;
  }

  .api-doc-browser__sidebar {
    display: none;
  }
}
</style>
