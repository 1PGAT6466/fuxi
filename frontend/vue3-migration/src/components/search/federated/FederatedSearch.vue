<template>
  <!--
    伏羲 v2.1 — 联邦搜索组件
    统一搜索入口：多数据源并发搜索、结果聚合去重、分类筛选、权限过滤
  -->
  <div class="federated-search" role="search" aria-label="联邦搜索">
    <!-- 搜索入口 -->
    <div class="fs-search-bar">
      <div class="fs-input-wrapper">
        <span class="fs-search-icon">🔍</span>
        <input
          ref="inputRef"
          v-model="query"
          class="fs-input"
          type="text"
          :placeholder="placeholderText"
          autocomplete="off"
          spellcheck="false"
          aria-label="联邦搜索查询"
          @input="handleInput"
          @keydown="handleKeydown"
          @focus="handleFocus"
        />
        <span v-if="searching" class="fs-spinner" aria-label="搜索中" />
        <button
          v-if="query.length > 0"
          class="fs-clear-btn"
          aria-label="清除查询"
          @click="clearQuery"
        >
          ✕
        </button>
        <button
          class="fs-advanced-btn"
          aria-label="高级搜索选项"
          :class="{ 'fs-advanced-btn--active': showAdvanced }"
          @click="showAdvanced = !showAdvanced"
        >
          ⚙
        </button>
      </div>
      <button
        class="fs-search-btn"
        :disabled="!query.trim() || searching"
        @click="handleSearch"
      >
        {{ searching ? '搜索中...' : '搜索' }}
      </button>
    </div>

    <!-- 高级选项 -->
    <Transition name="fs-collapse">
      <div v-if="showAdvanced" class="fs-advanced-panel">
        <div class="fs-advanced-row">
          <label class="fs-advanced-label">搜索源</label>
          <div class="fs-source-chips">
            <button
              v-for="src in sortedSources"
              :key="src.id"
              class="fs-source-chip"
              :class="{
                'fs-source-chip--active': selectedSources.includes(src.id),
                'fs-source-chip--offline': src.status !== 'online',
              }"
              :title="src.status !== 'online' ? `${src.name} (${statusLabel(src.status)})` : src.name"
              :disabled="src.status !== 'online'"
              @click="toggleSource(src.id)"
            >
              <span class="fs-source-chip-icon">{{ src.icon }}</span>
              <span>{{ src.name }}</span>
              <span class="fs-source-chip-status" :class="`fs-source-status--${src.status}`" />
            </button>
          </div>
        </div>
        <div class="fs-advanced-row">
          <label class="fs-advanced-label">排序方式</label>
          <select v-model="sortBy" class="fs-select" aria-label="排序方式">
            <option value="relevance">相关性</option>
            <option value="date">日期</option>
            <option value="source">来源</option>
          </select>
        </div>
        <div class="fs-advanced-row">
          <label class="fs-advanced-label">最少相关度</label>
          <input
            v-model.number="minScore"
            type="range"
            min="0"
            max="1"
            step="0.05"
            class="fs-range"
          />
          <span class="fs-range-value">{{ (minScore * 100).toFixed(0) }}%</span>
        </div>
      </div>
    </Transition>

    <!-- 来源统计 -->
    <div v-if="hasResults && currentQuery" class="fs-meta-bar">
      <div class="fs-meta-stats">
        <span class="fs-meta-total">
          共 <strong>{{ total }}</strong> 条结果
          <template v-if="rawTotal > total">（去重前 {{ rawTotal }}）</template>
        </span>
        <span class="fs-meta-time">⏱ {{ tookMs }}ms</span>
      </div>
      <div class="fs-sources-indicator">
        <span
          v-for="stat in sourceStats"
          :key="stat.sourceId"
          class="fs-source-badge"
          :class="`fs-source-badge--${stat.status}`"
          :title="`${stat.sourceName}: ${stat.resultCount} 条 · ${stat.responseTimeMs}ms`"
        >
          {{ stat.sourceIcon }} {{ stat.resultCount }}
        </span>
      </div>
    </div>

    <!-- 快速筛选 -->
    <div v-if="hasResults && currentQuery" class="fs-filter-bar">
      <div class="fs-filter-group">
        <span class="fs-filter-label">来源:</span>
        <button
          v-for="f in sourceFilters"
          :key="f.value"
          class="fs-filter-chip"
          :class="{ 'fs-filter-chip--active': f.active }"
          @click="setFilter('source', f.value as string)"
        >
          {{ f.label }}
        </button>
      </div>
      <div class="fs-filter-group">
        <span class="fs-filter-label">分类:</span>
        <button
          v-for="f in categoryFilters"
          :key="f.value"
          class="fs-filter-chip"
          :class="{ 'fs-filter-chip--active': f.active }"
          @click="setFilter('category', f.value as string)"
        >
          {{ f.label }}
        </button>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="searching && !hasResults" class="fs-loading">
      <span class="fs-spinner-lg" />
      <span>正在搜索多个数据源...</span>
    </div>

    <!-- 结果列表 -->
    <div v-if="hasResults && currentQuery" class="fs-results-container">
      <div
        v-for="(group, category) in groupedFilteredResults"
        :key="category"
        class="fs-result-group"
      >
        <h3 class="fs-group-title" @click="toggleGroup(String(category))">
          <span class="fs-group-icon">{{ categoryIcon(category as ResultCategory) }}</span>
          <span>{{ categoryLabel(category as ResultCategory) }}</span>
          <span class="fs-group-count">{{ (group as FederatedSearchResult[]).length }}</span>
          <span class="fs-group-toggle">{{ collapsedGroups.has(String(category)) ? '▸' : '▾' }}</span>
        </h3>

        <Transition name="fs-collapse">
          <div v-if="!collapsedGroups.has(String(category))" class="fs-group-items">
            <div
              v-for="result in (group as FederatedSearchResult[])"
              :key="result.id"
              class="fs-result-item"
              :class="{ 'fs-result-item--selected': selectedResultId === result.id }"
              tabindex="0"
              role="link"
              @click="navigateToResult(result)"
              @keydown.enter="navigateToResult(result)"
            >
              <span class="fs-result-source-icon" :title="result.sourceName">
                {{ result.sourceIcon }}
              </span>
              <div class="fs-result-body">
                <div class="fs-result-header">
                  <h4 class="fs-result-title">
                    <span
                      v-for="(part, idx) in highlightParts(result.title)"
                      :key="idx"
                      :class="{ 'fs-highlight': part.highlight }"
                    >{{ part.text }}</span>
                  </h4>
                  <div class="fs-result-badges">
                    <span
                      v-if="result.accessLevel && result.accessLevel !== 'public'"
                      class="fs-badge fs-badge--access"
                      :class="`fs-badge--${result.accessLevel}`"
                    >
                      {{ accessLabel(result.accessLevel) }}
                    </span>
                    <span v-if="result.fileType" class="fs-badge fs-badge--file">
                      {{ result.fileType.toUpperCase() }}
                    </span>
                  </div>
                </div>
                <p class="fs-result-snippet">
                  <span
                    v-for="(part, idx) in highlightParts(result.snippet)"
                    :key="idx"
                    :class="{ 'fs-highlight': part.highlight }"
                  >{{ part.text }}</span>
                </p>
                <div class="fs-result-meta">
                  <span class="fs-result-source-label">{{ result.sourceName }}</span>
                  <span class="fs-result-score">相关度 {{ (result.score * 100).toFixed(0) }}%</span>
                  <span v-if="result.timestamp" class="fs-result-time">
                    {{ formatTime(result.timestamp) }}
                  </span>
                </div>
              </div>
              <span v-if="result.url" class="fs-result-arrow">→</span>
            </div>
          </div>
        </Transition>
      </div>
    </div>

    <!-- 空结果 -->
    <div v-else-if="currentQuery && !searching" class="fs-empty">
      <span class="fs-empty-icon">📭</span>
      <p>没有找到「{{ currentQuery }}」相关的结果</p>
      <div v-if="suggestions.length" class="fs-suggestions">
        <p class="fs-suggestions-title">搜索建议：</p>
        <button
          v-for="s in suggestions"
          :key="s.text"
          class="fs-suggestion-chip"
          @click="handleSuggestionClick(s)"
        >
          {{ s.text }}
        </button>
      </div>
    </div>

    <!-- 搜索源状态底栏 -->
    <div v-if="sources.length > 0" class="fs-sources-footer">
      <div class="fs-sources-list">
        <span class="fs-sources-label">搜索源状态：</span>
        <span
          v-for="src in sources"
          :key="src.id"
          class="fs-source-status-item"
          :class="`fs-source-status-item--${src.status}`"
          :title="`${src.name}: ${statusLabel(src.status)}`"
        >
          {{ src.icon }} {{ src.name }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted } from 'vue';
import { useFederatedSearch } from '@/composables/useFederatedSearch';
import type {
  FederatedSearchResult,
  ResultCategory,
  SearchSuggestion,
} from '@/types/federated-search';

const props = withDefaults(
  defineProps<{
    initialQuery?: string;
    placeholder?: string;
    autoFocus?: boolean;
  }>(),
  {
    initialQuery: '',
    placeholder: '搜索文档、知识库、对话、工具...',
    autoFocus: false,
  },
);

const emit = defineEmits<{
  (e: 'search', query: string): void;
  (e: 'result-click', result: FederatedSearchResult): void;
  (e: 'close'): void;
}>();

const {
  query, searching, currentQuery, filteredResults, total, rawTotal,
  sourceStats, tookMs, suggestions, sources, sortedSources, hasResults,
  selectedResultId, sourceFilters, categoryFilters,
  searchDebounced, searchNow, setFilter, resetResults, navigateToResult,
} = useFederatedSearch({ debounceMs: 250 });

const inputRef = ref<HTMLInputElement | null>(null);
const showAdvanced = ref(false);
const selectedSources = ref<string[]>([]);
const sortBy = ref<'relevance' | 'date' | 'source'>('relevance');
const minScore = ref(0.1);
const collapsedGroups = ref<Set<string>>(new Set());

const placeholderText = computed(() => props.placeholder.replace('...', ''));

const groupedFilteredResults = computed(() => {
  const grouped: Partial<Record<ResultCategory, FederatedSearchResult[]>> = {};
  for (const r of filteredResults.value) {
    if (!grouped[r.category]) grouped[r.category] = [];
    grouped[r.category]!.push(r);
  }
  return grouped;
});

function handleInput(): void {
  searchDebounced(query.value.trim(), {
    sourceIds: selectedSources.value.length > 0 ? selectedSources.value : undefined,
    sortBy: sortBy.value,
    minScore: minScore.value,
  });
}

function handleSearch(): void {
  emit('search', query.value.trim());
  searchNow(query.value.trim(), {
    sourceIds: selectedSources.value.length > 0 ? selectedSources.value : undefined,
    sortBy: sortBy.value,
    minScore: minScore.value,
  });
}

function handleFocus(): void { showAdvanced.value = true; }

function handleSuggestionClick(suggestion: SearchSuggestion): void {
  query.value = suggestion.text;
  handleSearch();
}

function clearQuery(): void {
  query.value = '';
  resetResults();
  nextTick(() => inputRef.value?.focus());
}

function handleKeydown(e: KeyboardEvent): void {
  if (e.key === 'Escape') {
    e.preventDefault();
    if (showAdvanced.value) { showAdvanced.value = false; }
    else { clearQuery(); emit('close'); }
    return;
  }
  if (e.key === 'Enter') { e.preventDefault(); handleSearch(); }
}

function toggleSource(sourceId: string): void {
  const idx = selectedSources.value.indexOf(sourceId);
  if (idx !== -1) selectedSources.value.splice(idx, 1);
  else selectedSources.value.push(sourceId);
  if (currentQuery.value) {
    searchNow(currentQuery.value, {
      sourceIds: selectedSources.value.length > 0 ? selectedSources.value : undefined,
      sortBy: sortBy.value,
      minScore: minScore.value,
    });
  }
}

function toggleGroup(category: string): void {
  if (collapsedGroups.value.has(category)) collapsedGroups.value.delete(category);
  else collapsedGroups.value.add(category);
}

// 高亮
interface HighlightPart { text: string; highlight: boolean }

function highlightParts(text: string): HighlightPart[] {
  if (!currentQuery.value || !text) return [{ text, highlight: false }];
  const keywords = currentQuery.value.split(/\s+/).filter(Boolean);
  if (keywords.length === 0) return [{ text, highlight: false }];
  const escaped = keywords.map((k) => k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  const regex = new RegExp(`(${escaped.join('|')})`, 'gi');
  const parts: HighlightPart[] = [];
  let lastIdx = 0; let match: RegExpExecArray | null;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIdx) parts.push({ text: text.slice(lastIdx, match.index), highlight: false });
    parts.push({ text: match[0], highlight: true });
    lastIdx = regex.lastIndex;
  }
  if (lastIdx < text.length) parts.push({ text: text.slice(lastIdx), highlight: false });
  return parts.length > 0 ? parts : [{ text, highlight: false }];
}

function categoryIcon(category: ResultCategory): string {
  const m: Record<ResultCategory, string> = { document:'📄', wiki:'📝', chat:'💬', tool:'🛠️', file:'📁', database:'🗄️', external:'🌐' };
  return m[category] || '📌';
}
function categoryLabel(category: ResultCategory): string {
  const m: Record<ResultCategory, string> = { document:'文档', wiki:'Wiki', chat:'对话', tool:'工具', file:'文件', database:'数据库', external:'外部源' };
  return m[category] || category;
}
function statusLabel(status: string): string {
  const m: Record<string, string> = { online:'在线', offline:'离线', degraded:'降级', maintenance:'维护中' };
  return m[status] || status;
}
function accessLabel(level: string): string {
  const m: Record<string, string> = { internal:'内部', restricted:'受限', admin:'管理' };
  return m[level] || level;
}
function formatTime(ts: number): string {
  const d = new Date(ts); const diff = Date.now() - d.getTime();
  if (diff < 60000) return '刚刚';
  if (diff < 3600000) return `${Math.floor(diff/60000)} 分钟前`;
  if (diff < 86400000) return `${Math.floor(diff/3600000)} 小时前`;
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}

onMounted(() => {
  if (props.initialQuery) { query.value = props.initialQuery; handleSearch(); }
  if (props.autoFocus) nextTick(() => inputRef.value?.focus());
});

watch(() => props.initialQuery, (val) => {
  if (val) { query.value = val; handleSearch(); }
});

defineExpose({ focus: () => inputRef.value?.focus(), clearQuery, handleSearch });
</script>

<style scoped>
@import './federated-search.css';
</style>
