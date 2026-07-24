<template>
  <!--
    伏羲 v2.1 — 联邦搜索页面
    完整的联邦搜索视图，集成到路由系统中
  -->
  <div class="federated-search-page">
    <div class="fs-page-header">
      <h1 class="fs-page-title">🔍 联邦搜索</h1>
      <p class="fs-page-desc">跨数据源智能搜索：本地知识库 · Wiki · 对话历史 · 文件索引</p>
    </div>

    <FederatedSearch
      :auto-focus="true"
      placeholder="输入关键词搜索所有数据源..."
      @search="onSearch"
      @result-click="onResultClick"
    />

    <!-- 搜索提示 / 最近历史 -->
    <div v-if="!currentQuery && queryHistory.length > 0" class="fs-history-section">
      <h3 class="fs-section-title">📋 最近搜索</h3>
      <div class="fs-history-chips">
        <button
          v-for="(h, idx) in queryHistory.slice(0, 8)"
          :key="idx"
          class="fs-history-chip"
          @click="onHistoryClick(h)"
        >
          🕐 {{ h }}
        </button>
      </div>
      <button
        v-if="queryHistory.length > 0"
        class="fs-clear-history-btn"
        @click="clearHistory"
      >
        清除历史
      </button>
    </div>

    <!-- 搜索源介绍 -->
    <div v-if="!currentQuery" class="fs-sources-intro">
      <h3 class="fs-section-title">📡 可用搜索源</h3>
      <div class="fs-sources-grid">
        <div
          v-for="src in sources"
          :key="src.id"
          class="fs-source-card"
          :class="`fs-source-card--${src.status}`"
        >
          <span class="fs-source-card-icon">{{ src.icon }}</span>
          <div class="fs-source-card-body">
            <h4 class="fs-source-card-name">{{ src.name }}</h4>
            <p class="fs-source-card-desc">{{ src.description }}</p>
          </div>
          <span class="fs-source-card-status" :class="`fs-source-status--${src.status}`">
            {{ statusLabel(src.status) }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import { useFederatedSearch } from '@/composables/useFederatedSearch';
import FederatedSearch from '@/components/search/federated/FederatedSearch.vue';
import type { FederatedSearchResult } from '@/types/federated-search';

const router = useRouter();

const {
  query, currentQuery, queryHistory, sources,
  searchNow, clearHistory,
} = useFederatedSearch({ debounceMs: 300, autoLoadSources: true });

function onSearch(q: string): void {
  // 搜索已由 composable 处理，此处处理额外逻辑（如分析追踪）
  console.log(`[联邦搜索] 用户搜索: "${q}"`);
}

function onResultClick(result: FederatedSearchResult): void {
  console.log(`[联邦搜索] 用户点击: ${result.title} → ${result.url}`);
}

function onHistoryClick(historyQuery: string): void {
  query.value = historyQuery;
  searchNow(historyQuery);
}

function statusLabel(status: string): string {
  const m: Record<string, string> = {
    online: '在线', offline: '离线', degraded: '降级', maintenance: '维护中',
  };
  return m[status] || status;
}
</script>

<style scoped>
.federated-search-page {
  max-width: 960px;
  margin: 0 auto;
  padding: 40px 20px;
}

.fs-page-header {
  text-align: center;
  margin-bottom: 32px;
}

.fs-page-title {
  font-size: 28px;
  font-weight: 700;
  color: var(--fuxi-text, #333333);
  margin: 0 0 8px 0;
}

.fs-page-desc {
  font-size: 14px;
  color: var(--fuxi-text-secondary, #999999);
  margin: 0;
}

/* 搜索历史 */
.fs-history-section {
  margin-top: 24px;
}

.fs-section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--fuxi-text, #333333);
  margin: 0 0 12px 0;
}

.fs-history-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.fs-history-chip {
  background: var(--fuxi-bg-subtle, #f0ede5);
  border: 1px solid var(--fuxi-border, #e0e0e0);
  border-radius: 20px;
  padding: 6px 14px;
  font-size: 13px;
  cursor: pointer;
  color: var(--fuxi-text-secondary, #999999);
  transition: border-color 0.15s, color 0.15s;
}

.fs-history-chip:hover {
  border-color: var(--fuxi-primary, #ff6700);
  color: var(--fuxi-primary, #ff6700);
}

.fs-clear-history-btn {
  margin-top: 8px;
  background: none;
  border: none;
  font-size: 12px;
  color: var(--fuxi-text-tertiary, #cccccc);
  cursor: pointer;
}

.fs-clear-history-btn:hover {
  color: var(--fuxi-primary, #ff6700);
}

/* 搜索源介绍 */
.fs-sources-intro {
  margin-top: 40px;
}

.fs-sources-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
}

.fs-source-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px;
  background: var(--fuxi-bg-card, #ffffff);
  border: 1px solid var(--fuxi-border, #e0e0e0);
  border-radius: var(--radius-sm, 8px);
  transition: box-shadow 0.15s;
}

.fs-source-card:hover {
  box-shadow: var(--fuxi-shadow-sm, 0 2px 8px rgba(0,0,0,0.06));
}

.fs-source-card--offline {
  opacity: 0.5;
}

.fs-source-card-icon {
  font-size: 24px;
  flex-shrink: 0;
}

.fs-source-card-body {
  flex: 1;
  min-width: 0;
}

.fs-source-card-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--fuxi-text, #333333);
  margin: 0 0 2px 0;
}

.fs-source-card-desc {
  font-size: 12px;
  color: var(--fuxi-text-tertiary, #cccccc);
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.fs-source-card-status {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  flex-shrink: 0;
}
</style>
