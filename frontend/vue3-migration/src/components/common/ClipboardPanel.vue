<!--
  伏羲 v2.1 — 剪贴板面板 (ClipboardPanel)
  
  功能：
  - 剪贴板历史列表
  - 快速粘贴（双击或点击粘贴按钮）
  - 收藏常用内容（⭐）
  - 搜索过滤
  - 格式筛选（文本/HTML/JSON）
  - 跨窗口同步状态指示
  - 批量删除 & 清空
  
  触发方式：Cmd/Ctrl + Shift + V（全局快捷键）
-->
<template>
  <Teleport to="body">
    <Transition name="clipboard-panel">
      <div
        v-if="visible"
        class="clipboard-panel-overlay"
        @click.self="closePanel"
      >
        <div
          class="clipboard-panel"
          role="dialog"
          aria-label="剪贴板面板"
          aria-modal="true"
        >
          <!-- ── 头部 ── -->
          <div class="clipboard-panel-header">
            <div class="clipboard-panel-title">
              <span class="clipboard-panel-icon">📋</span>
              <span>剪贴板</span>
              <span
                v-if="store.isInitialized && store.totalCount > 0"
                class="clipboard-panel-count"
              >
                {{ store.totalCount }}
              </span>
            </div>
            <div class="clipboard-panel-actions">
              <!-- 跨窗口同步状态 -->
              <el-tooltip
                :content="syncStatusTooltip"
                placement="bottom"
              >
                <span
                  class="clipboard-sync-indicator"
                  :class="{ 'is-synced': syncEnabled }"
                >
                  {{ syncEnabled ? '🔄' : '⚡' }}
                </span>
              </el-tooltip>

              <button
                class="clipboard-panel-close"
                aria-label="关闭"
                @click="closePanel"
              >
                ✕
              </button>
            </div>
          </div>

          <!-- ── 搜索 & 过滤栏 ── -->
          <div class="clipboard-panel-toolbar">
            <div class="clipboard-search-wrapper">
              <el-icon :size="14" class="clipboard-search-icon">
                <Search />
              </el-icon>
              <input
                v-model="localSearchQuery"
                type="text"
                class="clipboard-search-input"
                placeholder="搜索剪贴板..."
                @input="handleSearch"
              />
              <button
                v-if="localSearchQuery"
                class="clipboard-search-clear"
                @click="clearSearch"
              >
                ✕
              </button>
            </div>

            <div class="clipboard-toolbar-actions">
              <!-- 格式过滤 -->
              <el-dropdown trigger="click" @command="handleFormatFilter">
                <el-button size="small" :text="true">
                  {{ filterLabel }}
                  <el-icon><ArrowDown /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="">全部格式</el-dropdown-item>
                    <el-dropdown-item command="text">📝 纯文本</el-dropdown-item>
                    <el-dropdown-item command="html">🌐 HTML</el-dropdown-item>
                    <el-dropdown-item command="json">📦 JSON</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>

              <!-- 仅收藏 -->
              <el-button
                size="small"
                :text="true"
                :type="store.favoritesOnly ? 'warning' : 'default'"
                @click="store.toggleFavoritesOnly"
              >
                ⭐ 收藏
              </el-button>

              <!-- 清空 -->
              <el-popconfirm
                title="确认清空所有剪贴板历史？"
                confirm-button-text="清空"
                cancel-button-text="取消"
                @confirm="handleClearHistory"
              >
                <template #reference>
                  <el-button size="small" text type="danger" :disabled="store.totalCount === 0">
                    🗑 清空
                  </el-button>
                </template>
              </el-popconfirm>
            </div>
          </div>

          <!-- ── 内容区 ── -->
          <div class="clipboard-panel-body">
            <!-- 空状态 -->
            <div v-if="store.filteredHistory.length === 0" class="clipboard-empty">
              <span class="clipboard-empty-icon">📋</span>
              <span class="clipboard-empty-text">
                {{ store.totalCount === 0 ? '剪贴板为空' : '没有匹配的内容' }}
              </span>
              <span class="clipboard-empty-hint">
                {{ store.totalCount === 0 ? '使用 Ctrl+C / ⌘+C 复制内容开始使用' : '尝试调整过滤条件' }}
              </span>
            </div>

            <!-- 历史列表 -->
            <div
              v-else
              ref="listRef"
              class="clipboard-history-list"
            >
              <div
                v-for="entry in store.filteredHistory"
                :key="entry.id"
                class="clipboard-entry-item"
                :class="{
                  'is-favorite': entry.isFavorite,
                  'is-selected': selectedEntryId === entry.id,
                }"
                @click="selectEntry(entry.id)"
                @dblclick="handleQuickPaste(entry)"
              >
                <!-- 格式图标 -->
                <span class="clipboard-entry-format" :title="formatLabel(entry.format)">
                  {{ formatIcon(entry.format) }}
                </span>

                <!-- 内容预览 -->
                <div class="clipboard-entry-content">
                  <div class="clipboard-entry-text">
                    {{ truncateText(entry.plainText, 120) }}
                  </div>
                  <div class="clipboard-entry-meta">
                    <span class="clipboard-entry-size">
                      {{ formatSize(entry.size) }}
                    </span>
                    <span class="clipboard-entry-time">
                      {{ formatTime(entry.createdAt) }}
                    </span>
                    <span
                      v-if="entry.sourceService"
                      class="clipboard-entry-source"
                    >
                      {{ entry.sourceService }}
                    </span>
                  </div>
                </div>

                <!-- 操作按钮 -->
                <div class="clipboard-entry-actions">
                  <!-- 粘贴 -->
                  <el-tooltip content="粘贴" placement="top">
                    <button
                      class="clipboard-entry-btn paste-btn"
                      @click.stop="handleQuickPaste(entry)"
                    >
                      📋
                    </button>
                  </el-tooltip>

                  <!-- 收藏 -->
                  <el-tooltip
                    :content="entry.isFavorite ? '取消收藏' : '收藏'"
                    placement="top"
                  >
                    <button
                      class="clipboard-entry-btn favorite-btn"
                      :class="{ 'is-active': entry.isFavorite }"
                      @click.stop="store.toggleFavorite(entry.id)"
                    >
                      {{ entry.isFavorite ? '⭐' : '☆' }}
                    </button>
                  </el-tooltip>

                  <!-- 复制 -->
                  <el-tooltip content="重新复制" placement="top">
                    <button
                      class="clipboard-entry-btn copy-btn"
                      @click.stop="handleReCopy(entry)"
                    >
                      📝
                    </button>
                  </el-tooltip>

                  <!-- 删除 -->
                  <el-tooltip content="删除" placement="top">
                    <button
                      class="clipboard-entry-btn delete-btn"
                      @click.stop="store.deleteEntry(entry.id)"
                    >
                      🗑
                    </button>
                  </el-tooltip>
                </div>
              </div>
            </div>
          </div>

          <!-- ── 底部状态栏 ── -->
          <div class="clipboard-panel-footer">
            <span class="clipboard-footer-stats">
              共 {{ store.totalCount }} 条 · 收藏 {{ store.favoritesCount }} 条
            </span>
            <span class="clipboard-footer-hint">
              双击快速粘贴 · {{ shortcutDisplay }} 打开面板
            </span>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue';
import { ElMessage } from 'element-plus';
import { Search, ArrowDown } from '@element-plus/icons-vue';
import { useClipboardStore } from '@/services/clipboard/store';
import type {
  ClipboardEntry,
  ClipboardContentFormat,
} from '@/services/clipboard/types';

// ═══════════════════════════════════════════
// Props & Emits
// ═══════════════════════════════════════════

defineProps<{
  /** 面板是否可见 */
  visible: boolean;
  /** 窗口 ID */
  windowId: string;
  /** 是否启用跨窗口同步 */
  syncEnabled?: boolean;
  /** 快捷键显示文本 */
  shortcutDisplay?: string;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  /** 粘贴内容时触发 */
  (e: 'paste', content: string): void;
}>();

// ═══════════════════════════════════════════
// Store
// ═══════════════════════════════════════════

const store = useClipboardStore();

// ═══════════════════════════════════════════
// 本地状态
// ═══════════════════════════════════════════

const listRef = ref<HTMLElement | null>(null);
const selectedEntryId = ref<string | null>(null);
const localSearchQuery = ref('');

// ═══════════════════════════════════════════
// 计算属性
// ═══════════════════════════════════════════

const syncStatusTooltip = computed(() => {
  return props.syncEnabled
    ? '跨窗口同步已启用'
    : '跨窗口同步已关闭（本地模式）';
});

const filterLabel = computed(() => {
  return `格式: ${filterLabelText()}`;
});

// ═══════════════════════════════════════════
// 工具函数
// ═══════════════════════════════════════════

function formatIcon(format: ClipboardContentFormat): string {
  const icons: Record<ClipboardContentFormat, string> = {
    text: '📝',
    html: '🌐',
    json: '📦',
    'image-ref': '🖼',
    'file-ref': '📁',
  };
  return icons[format] || '📋';
}

function formatLabel(format: ClipboardContentFormat): string {
  const labels: Record<ClipboardContentFormat, string> = {
    text: '纯文本',
    html: 'HTML',
    json: 'JSON',
    'image-ref': '图片引用',
    'file-ref': '文件引用',
  };
  return labels[format] || format;
}

function filterLabelText(): string {
  if (!store.filterFormat) return '全部';
  return formatLabel(store.filterFormat);
}

function truncateText(text: string, maxLen: number): string {
  if (!text) return '(空)';
  const firstLine = text.split('\n')[0];
  if (firstLine.length <= maxLen) return firstLine;
  return firstLine.slice(0, maxLen) + '…';
}

function formatSize(bytes?: number): string {
  if (!bytes || bytes === 0) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatTime(isoString: string): string {
  try {
    const now = new Date();
    const date = new Date(isoString);
    const diffMs = now.getTime() - date.getTime();
    const diffSec = Math.floor(diffMs / 1000);

    if (diffSec < 60) return '刚刚';
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)} 分钟前`;
    if (diffSec < 86400) return `${Math.floor(diffSec / 3600)} 小时前`;

    return date.toLocaleDateString('zh-CN', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return '';
  }
}

// ═══════════════════════════════════════════
// 操作
// ═══════════════════════════════════════════

function closePanel(): void {
  emit('close');
  store.closePanel();
}

function selectEntry(entryId: string): void {
  selectedEntryId.value = entryId;
}

async function handleQuickPaste(entry: ClipboardEntry): Promise<void> {
  try {
    const content = await store.paste(entry.id);
    if (content) {
      emit('paste', content);
      ElMessage.success('已粘贴');
    }
  } catch {
    ElMessage.error('粘贴失败');
  }
}

async function handleReCopy(entry: ClipboardEntry): Promise<void> {
  try {
    await store.copy(entry.plainText, entry.format);
    ElMessage.success('已复制');
  } catch {
    ElMessage.error('复制失败');
  }
}

function handleSearch(): void {
  store.search(localSearchQuery.value);
}

function clearSearch(): void {
  localSearchQuery.value = '';
  store.search('');
}

function handleFormatFilter(command: string): void {
  if (command === '') {
    store.setFilter(null);
  } else {
    store.setFilter(command as ClipboardContentFormat);
  }
}

async function handleClearHistory(): Promise<void> {
  store.clearHistory();
  ElMessage.success('剪贴板历史已清空');
}

// ═══════════════════════════════════════════
// 键盘导航
// ═══════════════════════════════════════════

function handleKeyboard(e: KeyboardEvent): void {
  if (!props.visible) return;

  // Escape 关闭
  if (e.key === 'Escape') {
    e.preventDefault();
    closePanel();
    return;
  }

  // 上下箭头导航
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault();
    navigateList(e.key === 'ArrowDown' ? 1 : -1);
    return;
  }

  // Enter 快速粘贴
  if (e.key === 'Enter' && selectedEntryId.value) {
    e.preventDefault();
    const entry = store.filteredHistory.find(
      (e) => e.id === selectedEntryId.value,
    );
    if (entry) handleQuickPaste(entry);
  }
}

function navigateList(direction: number): void {
  if (store.filteredHistory.length === 0) return;

  const currentIdx = store.filteredHistory.findIndex(
    (e) => e.id === selectedEntryId.value,
  );

  let newIdx: number;
  if (currentIdx === -1) {
    newIdx = direction > 0 ? 0 : store.filteredHistory.length - 1;
  } else {
    newIdx = (currentIdx + direction + store.filteredHistory.length) % store.filteredHistory.length;
  }

  selectedEntryId.value = store.filteredHistory[newIdx].id;

  // 滚动到可见区域
  nextTick(() => {
    const selectedEl = listRef.value?.querySelector('.is-selected');
    selectedEl?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  });
}

// ═══════════════════════════════════════════
// 生命周期
// ═══════════════════════════════════════════

onMounted(() => {
  document.addEventListener('keydown', handleKeyboard);

  // 初始化 store
  if (!store.isInitialized) {
    store.init(props.windowId);
  }
});

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeyboard);
});

// 监听 visible 变化，打开时重置搜索
watch(
  () => props.visible,
  (val) => {
    if (val) {
      localSearchQuery.value = '';
      store.search('');
      selectedEntryId.value = null;
    }
  },
);
</script>

<style scoped lang="scss">
// ═══════════════════════════════════════════
// 变量
// ═══════════════════════════════════════════
$panel-width: 420px;
$panel-max-height: 600px;
$header-height: 52px;
$toolbar-height: 44px;
$footer-height: 36px;

// ═══════════════════════════════════════════
// 遮罩
// ═══════════════════════════════════════════
.clipboard-panel-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 80px;
  background: rgba(0, 0, 0, 0.2);
  backdrop-filter: blur(2px);
}

// ═══════════════════════════════════════════
// 面板
// ═══════════════════════════════════════════
.clipboard-panel {
  width: $panel-width;
  max-width: calc(100vw - 32px);
  max-height: $panel-max-height;
  display: flex;
  flex-direction: column;
  background: var(--fuxi-bg-card, #ffffff);
  border-radius: var(--radius-lg, 16px);
  box-shadow: var(--fuxi-shadow-xl, 0 12px 48px rgba(0, 0, 0, 0.12));
  border: 1px solid var(--fuxi-border, #eeeeee);
  overflow: hidden;

  // 暗色模式适配
  [data-theme='dark'] & {
    background: #1e1e2e;
    border-color: #3a3a4a;
    color: #e0e0e0;
  }
}

// ═══════════════════════════════════════════
// 头部
// ═══════════════════════════════════════════
.clipboard-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: $header-height;
  padding: 0 16px;
  border-bottom: 1px solid var(--fuxi-border, #eeeeee);
  flex-shrink: 0;
  background: var(--fuxi-bg-card, #ffffff);

  [data-theme='dark'] & {
    background: #1e1e2e;
    border-color: #3a3a4a;
  }
}

.clipboard-panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 700;
  color: var(--fuxi-text, #333333);

  [data-theme='dark'] & {
    color: #e0e0e0;
  }
}

.clipboard-panel-icon {
  font-size: 18px;
}

.clipboard-panel-count {
  font-size: 11px;
  font-weight: 600;
  color: var(--fuxi-text-secondary, #999999);
  background: var(--fuxi-bg-subtle, #f0ede5);
  padding: 2px 8px;
  border-radius: 10px;

  [data-theme='dark'] & {
    background: #2a2a3a;
    color: #aaa;
  }
}

.clipboard-panel-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.clipboard-sync-indicator {
  font-size: 14px;
  opacity: 0.4;
  transition: opacity 200ms ease;

  &.is-synced {
    opacity: 1;
  }
}

.clipboard-panel-close {
  width: 26px;
  height: 26px;
  border: none;
  border-radius: 50%;
  background: var(--fuxi-bg-subtle, #f0ede5);
  color: var(--fuxi-text-secondary, #999999);
  cursor: pointer;
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 150ms ease;

  &:hover {
    background: var(--fuxi-primary-light, #fff3e8);
    color: var(--fuxi-primary, #ff6700);
  }
}

// ═══════════════════════════════════════════
// 工具栏
// ═══════════════════════════════════════════
.clipboard-panel-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--fuxi-border, #eeeeee);
  flex-shrink: 0;
  background: var(--fuxi-bg-page, #fafafa);

  [data-theme='dark'] & {
    background: #181825;
    border-color: #3a3a4a;
  }
}

.clipboard-search-wrapper {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  background: var(--fuxi-bg-card, #ffffff);
  border: 1px solid var(--fuxi-border, #eeeeee);
  border-radius: var(--radius-sm, 8px);
  transition: border-color 150ms ease;

  &:focus-within {
    border-color: var(--fuxi-primary, #ff6700);
  }

  [data-theme='dark'] & {
    background: #2a2a3a;
    border-color: #3a3a4a;
  }
}

.clipboard-search-icon {
  flex-shrink: 0;
  color: var(--fuxi-text-tertiary, #cccccc);
}

.clipboard-search-input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 13px;
  color: var(--fuxi-text, #333333);
  padding: 2px 0;

  &::placeholder {
    color: var(--fuxi-text-tertiary, #cccccc);
  }

  [data-theme='dark'] & {
    color: #e0e0e0;
  }
}

.clipboard-search-clear {
  border: none;
  background: none;
  cursor: pointer;
  color: var(--fuxi-text-tertiary, #cccccc);
  font-size: 12px;
  padding: 2px;
  line-height: 1;

  &:hover {
    color: var(--fuxi-text, #333333);
  }
}

.clipboard-toolbar-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
}

// ═══════════════════════════════════════════
// 内容区
// ═══════════════════════════════════════════
.clipboard-panel-body {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

.clipboard-history-list {
  padding: 4px 0;
}

// ═══════════════════════════════════════════
// 空状态
// ═══════════════════════════════════════════
.clipboard-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 24px;
  gap: 8px;
}

.clipboard-empty-icon {
  font-size: 40px;
  opacity: 0.3;
}

.clipboard-empty-text {
  font-size: 14px;
  color: var(--fuxi-text-secondary, #999999);
}

.clipboard-empty-hint {
  font-size: 12px;
  color: var(--fuxi-text-tertiary, #cccccc);
  text-align: center;
}

// ═══════════════════════════════════════════
// 条目
// ═══════════════════════════════════════════
.clipboard-entry-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  cursor: pointer;
  transition: background 120ms ease;
  border-left: 3px solid transparent;

  &:hover {
    background: var(--fuxi-bg-hover, #f8f6f0);

    [data-theme='dark'] & {
      background: #252535;
    }

    .clipboard-entry-actions {
      opacity: 1;
    }
  }

  &.is-selected {
    background: var(--fuxi-primary-light, #fff3e8);
    border-left-color: var(--fuxi-primary, #ff6700);

    [data-theme='dark'] & {
      background: #332200;
    }
  }

  &.is-favorite {
    background: linear-gradient(90deg, #fffde7 0%, transparent 30%);

    [data-theme='dark'] & {
      background: linear-gradient(90deg, #2a2810 0%, transparent 30%);
    }
  }

  & + & {
    border-top: 1px solid var(--fuxi-border-light, #f5f5f5);

    [data-theme='dark'] & {
      border-color: #2a2a3a;
    }
  }
}

.clipboard-entry-format {
  flex-shrink: 0;
  font-size: 16px;
  width: 24px;
  text-align: center;
  line-height: 1.4;
}

.clipboard-entry-content {
  flex: 1;
  min-width: 0;
}

.clipboard-entry-text {
  font-size: 13px;
  line-height: 1.5;
  color: var(--fuxi-text, #333333);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;

  [data-theme='dark'] & {
    color: #e0e0e0;
  }
}

.clipboard-entry-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 2px;
  font-size: 11px;
  color: var(--fuxi-text-tertiary, #cccccc);
}

.clipboard-entry-source {
  padding: 0 4px;
  background: var(--fuxi-bg-subtle, #f0ede5);
  border-radius: 4px;

  [data-theme='dark'] & {
    background: #2a2a3a;
  }
}

// ═══════════════════════════════════════════
// 条目操作按钮
// ═══════════════════════════════════════════
.clipboard-entry-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 120ms ease;
}

.clipboard-entry-btn {
  width: 26px;
  height: 26px;
  border: none;
  border-radius: 6px;
  background: transparent;
  cursor: pointer;
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 120ms ease;

  &:hover {
    background: var(--fuxi-bg-subtle, #f0ede5);

    [data-theme='dark'] & {
      background: #353545;
    }
  }

  &.favorite-btn.is-active {
    background: rgba(255, 215, 0, 0.1);
  }

  &.delete-btn:hover {
    background: rgba(255, 0, 0, 0.1);
  }
}

// ═══════════════════════════════════════════
// 底部状态栏
// ═══════════════════════════════════════════
.clipboard-panel-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: $footer-height;
  padding: 0 16px;
  border-top: 1px solid var(--fuxi-border, #eeeeee);
  font-size: 11px;
  color: var(--fuxi-text-tertiary, #cccccc);
  flex-shrink: 0;
  background: var(--fuxi-bg-page, #fafafa);

  [data-theme='dark'] & {
    background: #181825;
    border-color: #3a3a4a;
  }
}

// ═══════════════════════════════════════════
// 过渡动画
// ═══════════════════════════════════════════
.clipboard-panel-enter-active {
  transition: opacity 200ms ease;
}
.clipboard-panel-leave-active {
  transition: opacity 150ms ease;
}
.clipboard-panel-enter-from,
.clipboard-panel-leave-to {
  opacity: 0;
}

.clipboard-panel-enter-active .clipboard-panel {
  animation: clipboard-slide-in 200ms cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes clipboard-slide-in {
  from {
    opacity: 0;
    transform: translateY(-12px) scale(0.96);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}
</style>
