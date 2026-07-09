<template>
  <!--
    伏羲令 v2.1 — 全局搜索面板 (Cmd+K)
    毛玻璃背景 + 居中搜索面板 + 动态联想
  -->
  <Teleport to="body">
    <Transition name="fuxiling">
      <div v-if="visible" class="fuxiling-overlay" @click.self="close" @keydown="handleKeydown">
        <!-- 搜索面板 -->
        <div class="fuxiling-panel" role="dialog" aria-label="伏羲令全局搜索" aria-modal="true">
          <!-- 输入区 -->
          <div class="fuxiling-input-row">
            <span class="fuxiling-icon">☯</span>
            <input
              ref="inputRef"
              v-model="query"
              class="fuxiling-input"
              type="text"
              placeholder="输入文档、工具、服务名称...（输入「乾宫」直接跳转）"
              autocomplete="off"
              spellcheck="false"
              aria-label="搜索"
              @input="handleInput"
            />
            <kbd class="fuxiling-kbd">Esc</kbd>
          </div>

          <!-- 加载状态 -->
          <div v-if="loading" class="fuxiling-loading">
            <span class="fuxiling-spinner" />
            <span>搜索中...</span>
          </div>

          <!-- 搜索结果列表 -->
          <div v-else-if="results.length > 0" class="fuxiling-results">
            <div
              v-for="(item, index) in results"
              :key="`${item.type}-${item.title}-${index}`"
              class="fuxiling-result-item"
              :class="{ 'fuxiling-result-item--active': index === activeIndex }"
              @click="selectItem(item)"
              @mouseenter="activeIndex = index"
            >
              <span class="fuxiling-result-icon">{{ item.icon || typeIcon(item.type) }}</span>
              <div class="fuxiling-result-body">
                <span class="fuxiling-result-title">{{ item.title }}</span>
                <span class="fuxiling-result-desc">{{ item.description }}</span>
              </div>
              <span class="fuxiling-result-type">{{ typeLabel(item.type) }}</span>
            </div>
          </div>

          <!-- 空结果 -->
          <div v-else-if="query.length > 0 && !loading" class="fuxiling-empty">
            <span>没有找到「{{ query }}」相关的结果</span>
          </div>

          <!-- 初始提示 -->
          <div v-else class="fuxiling-hint">
            <div class="fuxiling-hint-item">
              <span class="fuxiling-hint-key">⌘K</span>
              <span>搜索文档与工具</span>
            </div>
            <div class="fuxiling-hint-item">
              <span class="fuxiling-hint-key">⌘1-9</span>
              <span>切换九宫格宫位</span>
            </div>
            <div class="fuxiling-hint-item">
              <span class="fuxiling-hint-key">乾宫</span>
              <span>直接跳转八卦宫位</span>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue';
import { useRouter } from 'vue-router';
import { unifiedSearch } from '@/api/symbols';
import type { UnifiedSearchResult } from '@/api/symbols';
import { BAGUA_GRID } from '@/constants/bagua';

const props = defineProps<{
  visible: boolean;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
}>();

const router = useRouter();
const query = ref('');
const results = ref<UnifiedSearchResult[]>([]);
const activeIndex = ref(0);
const loading = ref(false);
const inputRef = ref<HTMLInputElement | null>(null);

let debounceTimer: ReturnType<typeof setTimeout> | null = null;

// ── 自动聚焦 ──
watch(
  () => props.visible,
  (val) => {
    if (val) {
      query.value = '';
      results.value = [];
      activeIndex.value = 0;
      nextTick(() => {
        inputRef.value?.focus();
      });
    }
  },
);

function close(): void {
  emit('close');
}

function typeIcon(type: string): string {
  const map: Record<string, string> = {
    document: '📄',
    wiki: '📝',
    tool: '🛠️',
    service: '⚙️',
    gua: '☯',
    search: '🔍',
  };
  return map[type] || '📌';
}

function typeLabel(type: string): string {
  const map: Record<string, string> = {
    document: '文档',
    wiki: 'Wiki',
    tool: '工具',
    service: '服务',
    gua: '卦象',
    search: '搜索',
  };
  return map[type] || type;
}

// ── 卦象命令检测 ──
function detectGuaCommand(input: string): { isGua: boolean; guaItem?: (typeof BAGUA_GRID)[number] } {
  const guaMap: Record<string, number> = {
    乾宫: 6,
    坤宫: 2,
    震宫: 3,
    巽宫: 4,
    坎宫: 1,
    离宫: 9,
    艮宫: 8,
    兑宫: 7,
    中宫: 5,
  };

  for (const [cmd, pos] of Object.entries(guaMap)) {
    if (input.includes(cmd)) {
      return { isGua: true, guaItem: BAGUA_GRID[pos] };
    }
  }
  return { isGua: false };
}

// ── 输入处理 ──
async function handleInput(): void {
  if (debounceTimer) clearTimeout(debounceTimer);

  const q = query.value.trim();

  // 卦象命令检测
  const { isGua, guaItem } = detectGuaCommand(q);
  if (isGua && guaItem) {
    results.value = [
      {
        type: 'gua',
        title: `${guaItem.symbol} ${guaItem.label}宫 → ${guaItem.functionDesc}`,
        url: guaItem.route,
        description: `${guaItem.organ} · ${guaItem.yijingQuote}`,
        icon: guaItem.symbol,
      },
    ];
    return;
  }

  if (!q) {
    results.value = [];
    return;
  }

  // 防抖搜索
  debounceTimer = setTimeout(async () => {
    loading.value = true;
    try {
      const res = await unifiedSearch(q);
      results.value = res.data.matches;
      activeIndex.value = 0;
    } catch {
      // 后端 API 不可用，显示空结果
      results.value = [];
    } finally {
      loading.value = false;
    }
  }, 200);
}

// ── 键盘导航 ──
function handleKeydown(e: KeyboardEvent): void {
  if (e.key === 'Escape') {
    e.preventDefault();
    close();
    return;
  }

  if (e.key === 'ArrowDown') {
    e.preventDefault();
    activeIndex.value = Math.min(activeIndex.value + 1, results.value.length - 1);
    return;
  }

  if (e.key === 'ArrowUp') {
    e.preventDefault();
    activeIndex.value = Math.max(activeIndex.value - 1, 0);
    return;
  }

  if (e.key === 'Enter') {
    e.preventDefault();
    const item = results.value[activeIndex.value];
    if (item) selectItem(item);
  }
}

function selectItem(item: UnifiedSearchResult): void {
  close();
  router.push(item.url);
}
</script>

<style scoped>
/* ═══════════════════════════════════════════
   毛玻璃遮罩
   ═══════════════════════════════════════════ */
.fuxiling-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 15vh;
  background: rgba(0, 0, 0, 0.35);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

/* ═══════════════════════════════════════════
   搜索面板
   ═══════════════════════════════════════════ */
.fuxiling-panel {
  width: 560px;
  max-width: calc(100vw - 32px);
  background: var(--fuxi-bg-card, #ffffff);
  border-radius: var(--radius-lg, 16px);
  box-shadow: var(--fuxi-shadow-lg, 0 8px 32px rgba(0, 0, 0, 0.06));
  overflow: hidden;
  border: 1px solid var(--fuxi-border, #eeeeee);
}

/* ── 输入行 ── */
.fuxiling-input-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--fuxi-border, #eeeeee);
}

.fuxiling-icon {
  font-size: 22px;
  flex-shrink: 0;
  color: var(--fuxi-primary, #ff6700);
}

.fuxiling-input {
  flex: 1;
  border: none;
  outline: none;
  font-size: 16px;
  color: var(--fuxi-text, #333333);
  background: transparent;
  font-family: var(--font-family-base);
}

.fuxiling-input::placeholder {
  color: var(--fuxi-text-tertiary, #cccccc);
  font-size: 14px;
}

.fuxiling-kbd {
  font-size: 11px;
  color: var(--fuxi-text-tertiary, #cccccc);
  background: var(--fuxi-bg-subtle, #f0ede5);
  padding: 3px 8px;
  border-radius: 4px;
  font-family: monospace;
  flex-shrink: 0;
}

/* ── 结果列表 ── */
.fuxiling-results {
  max-height: 360px;
  overflow-y: auto;
  padding: 8px;
}

.fuxiling-result-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: var(--radius-sm, 8px);
  cursor: pointer;
  transition: background 150ms ease;
}

.fuxiling-result-item:hover,
.fuxiling-result-item--active {
  background: var(--fuxi-bg-hover, #fffcf9);
}

.fuxiling-result-icon {
  font-size: 20px;
  flex-shrink: 0;
  width: 28px;
  text-align: center;
}

.fuxiling-result-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.fuxiling-result-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--fuxi-text, #333333);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.fuxiling-result-desc {
  font-size: 12px;
  color: var(--fuxi-text-secondary, #999999);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.fuxiling-result-type {
  font-size: 11px;
  color: var(--fuxi-text-tertiary, #cccccc);
  background: var(--fuxi-bg-subtle, #f0ede5);
  padding: 2px 8px;
  border-radius: 4px;
  flex-shrink: 0;
}

/* ── 空结果 ── */
.fuxiling-empty {
  padding: 32px 20px;
  text-align: center;
  color: var(--fuxi-text-tertiary, #cccccc);
  font-size: 14px;
}

/* ── 初始提示 ── */
.fuxiling-hint {
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.fuxiling-hint-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--fuxi-text-secondary, #999999);
}

.fuxiling-hint-key {
  background: var(--fuxi-bg-subtle, #f0ede5);
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-family: monospace;
  color: var(--fuxi-text, #333333);
  min-width: 50px;
  text-align: center;
}

/* ── 加载 ── */
.fuxiling-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 24px;
  color: var(--fuxi-text-secondary, #999999);
  font-size: 13px;
}

.fuxiling-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid var(--fuxi-border, #eeeeee);
  border-top-color: var(--fuxi-primary, #ff6700);
  border-radius: 50%;
  animation: fuxi-spin 0.6s linear infinite;
}

@keyframes fuxi-spin {
  to {
    transform: rotate(360deg);
  }
}

/* ── 过渡动画 ── */
.fuxiling-enter-active {
  transition: opacity 200ms ease;
}

.fuxiling-leave-active {
  transition: opacity 150ms ease;
}

.fuxiling-enter-from,
.fuxiling-leave-to {
  opacity: 0;
}

.fuxiling-enter-active .fuxiling-panel {
  animation: panel-slide-in 200ms ease;
}

.fuxiling-leave-active .fuxiling-panel {
  animation: panel-slide-in 150ms ease reverse;
}

@keyframes panel-slide-in {
  from {
    opacity: 0;
    transform: translateY(-12px) scale(0.97);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}
</style>
