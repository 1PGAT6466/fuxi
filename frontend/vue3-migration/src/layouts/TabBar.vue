<template>
  <!--
    伏羲 v2.1 — TabBar 组件
    支持固定区（pinned）+ 临时区、激活态、关闭按钮、右键菜单、拖拽排序
  -->
  <div class="tab-bar" role="tablist" aria-label="标签栏">
    <!-- 固定区 Tabs -->
    <div class="tab-bar-section tab-bar-section--pinned">
      <div
        v-for="tab in pinnedTabs"
        :key="tab.id"
        :ref="
          (el) => {
            tabRefs[tab.id] = el as HTMLElement | null;
          }
        "
        class="tab-item"
        :class="{ 'tab-item--active': tab.id === activeId }"
        :draggable="true"
        role="tab"
        :aria-selected="tab.id === activeId"
        :aria-label="tab.title"
        @click="$emit('activate', tab.id)"
        @dragstart="handleDragStart($event, tab.id)"
        @dragover.prevent="handleDragOver($event, tab.id)"
        @drop="handleDrop($event, tab.id)"
        @dragend="handleDragEnd"
        @contextmenu.prevent="showContextMenu($event, tab.id)"
      >
        <el-icon class="tab-icon" :size="14">
          <component :is="tab.icon" v-if="tab.icon" />
        </el-icon>
        <span class="tab-label">{{ tab.title }}</span>
        <button
          class="tab-close"
          :aria-label="`关闭 ${tab.title}`"
          @click.stop="$emit('close', tab.id)"
        >
          <el-icon :size="12"><Close /></el-icon>
        </button>
      </div>
    </div>

    <!-- 分隔线 -->
    <div v-if="unpinnedTabs.length > 0 && pinnedTabs.length > 0" class="tab-divider" />

    <!-- 临时区 Tabs -->
    <div class="tab-bar-section tab-bar-section--unpinned">
      <div
        v-for="tab in unpinnedTabs"
        :key="tab.id"
        :ref="
          (el) => {
            tabRefs[tab.id] = el as HTMLElement | null;
          }
        "
        class="tab-item"
        :class="{
          'tab-item--active': tab.id === activeId,
          'tab-item--closing': closingIds.has(tab.id),
        }"
        :draggable="true"
        role="tab"
        :aria-selected="tab.id === activeId"
        :aria-label="tab.title"
        @click="$emit('activate', tab.id)"
        @dragstart="handleDragStart($event, tab.id)"
        @dragover.prevent="handleDragOver($event, tab.id)"
        @drop="handleDrop($event, tab.id)"
        @dragend="handleDragEnd"
        @contextmenu.prevent="showContextMenu($event, tab.id)"
      >
        <el-icon class="tab-icon" :size="14">
          <component :is="tab.icon" v-if="tab.icon" />
        </el-icon>
        <span class="tab-label">{{ tab.title }}</span>
        <button
          class="tab-close"
          :aria-label="`关闭 ${tab.title}`"
          @click.stop="$emit('close', tab.id)"
        >
          <el-icon :size="12"><Close /></el-icon>
        </button>
      </div>
    </div>

    <!-- 右键菜单 -->
    <Teleport to="body">
      <div
        v-if="contextMenu.visible"
        class="tab-context-menu"
        :style="{
          left: `${contextMenu.x}px`,
          top: `${contextMenu.y}px`,
        }"
        @click.stop
      >
        <div class="context-menu-item" @click="handleMenuAction('close')">
          <el-icon :size="14"><Close /></el-icon>
          <span>关闭标签</span>
        </div>
        <div class="context-menu-item" @click="handleMenuAction('close-others')">
          <el-icon :size="14"><Remove /></el-icon>
          <span>关闭其他标签</span>
        </div>
        <div class="context-menu-item" @click="handleMenuAction('close-right')">
          <el-icon :size="14"><DArrowRight /></el-icon>
          <span>关闭右侧标签</span>
        </div>
        <div class="context-menu-divider" />
        <div class="context-menu-item" @click="handleMenuAction('pin')">
          <el-icon :size="14"><Paperclip /></el-icon>
          <span>{{ isContextTabPinned ? '取消固定' : '固定标签' }}</span>
        </div>
      </div>
    </Teleport>

    <!-- 全局点击关闭右键菜单 -->
    <div v-if="contextMenu.visible" class="context-menu-mask" @click="closeContextMenu" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { Close, Remove, DArrowRight, Paperclip } from '@element-plus/icons-vue';

// ============================
// Tab 数据结构
// ============================

export interface TabItem {
  id: string;
  title: string;
  icon?: string;
  pinned?: boolean;
  route?: string;
  serviceId?: string;
}

// ============================
// Props & Emits
// ============================

const props = defineProps<{
  tabs: TabItem[];
  activeId: string | null;
  closingIds?: Set<string>;
}>();

const emit = defineEmits<{
  (e: 'activate', id: string): void;
  (e: 'close', id: string): void;
  (e: 'close-others', id: string): void;
  (e: 'close-right', id: string): void;
  (e: 'pin', id: string, pin: boolean): void;
  (e: 'reorder', fromId: string, toId: string): void;
}>();

// ============================
// 计算属性
// ============================

const pinnedTabs = computed(() => props.tabs.filter((t) => t.pinned));
const unpinnedTabs = computed(() => props.tabs.filter((t) => !t.pinned));

// ============================
// 拖拽
// ============================

const tabRefs = ref<Record<string, HTMLElement | null>>({});
const dragId = ref<string | null>(null);

function handleDragStart(e: DragEvent, id: string) {
  dragId.value = id;
  if (e.dataTransfer) {
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', id);
  }
}

function handleDragOver(e: DragEvent, id: string) {
  if (!dragId.value || dragId.value === id) return;
  if (e.dataTransfer) {
    e.dataTransfer.dropEffect = 'move';
  }
}

function handleDrop(e: DragEvent, targetId: string) {
  if (!dragId.value || dragId.value === targetId) return;
  emit('reorder', dragId.value, targetId);
  dragId.value = null;
}

function handleDragEnd() {
  dragId.value = null;
}

// ============================
// 右键菜单
// ============================

const contextMenu = ref({
  visible: false,
  x: 0,
  y: 0,
  tabId: '' as string,
});

function showContextMenu(e: MouseEvent, tabId: string) {
  contextMenu.value = {
    visible: true,
    x: e.clientX,
    y: e.clientY,
    tabId,
  };
}

function closeContextMenu() {
  contextMenu.value.visible = false;
}

const isContextTabPinned = computed(() => {
  const tab = props.tabs.find((t) => t.id === contextMenu.value.tabId);
  return tab?.pinned || false;
});

function handleMenuAction(action: string) {
  const tabId = contextMenu.value.tabId;
  closeContextMenu();

  switch (action) {
    case 'close':
      emit('close', tabId);
      break;
    case 'close-others':
      emit('close-others', tabId);
      break;
    case 'close-right':
      emit('close-right', tabId);
      break;
    case 'pin':
      emit('pin', tabId, !isContextTabPinned.value);
      break;
  }
}

// ============================
// 全局键盘快捷键
// ============================

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    closeContextMenu();
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown);
});

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown);
});
</script>

<style scoped lang="scss">
.tab-bar {
  display: flex;
  align-items: stretch;
  height: 42px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--bg-divider);
  overflow-x: auto;
  overflow-y: hidden;
  flex-shrink: 0;
  position: relative;

  &::-webkit-scrollbar {
    height: 2px;
  }

  &::-webkit-scrollbar-thumb {
    background: var(--bg-divider);
    border-radius: 2px;
  }
}

.tab-bar-section {
  display: flex;
  align-items: stretch;
  flex-shrink: 0;
}

.tab-bar-section--pinned {
  // 固定区左侧加上微妙的左边距
  padding-left: 4px;
}

.tab-divider {
  width: 1px;
  height: 20px;
  background: var(--bg-divider);
  align-self: center;
  margin: 0 4px;
  flex-shrink: 0;
}

/* ============================
   单个 Tab
   ============================ */

.tab-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 12px;
  height: 100%;
  cursor: pointer;
  color: var(--text-secondary);
  font-size: var(--font-size-caption);
  transition: all var(--duration-fast) var(--ease-out);
  position: relative;
  user-select: none;
  border-right: 1px solid transparent;
  white-space: nowrap;

  &:hover {
    color: var(--text-primary);
    background: var(--bg-hover);

    .tab-close {
      opacity: 1;
    }
  }

  &--active {
    color: var(--brand);
    background: var(--brand-soft);

    // 底部指示条
    &::after {
      content: '';
      position: absolute;
      bottom: 0;
      left: 12px;
      right: 12px;
      height: 2px;
      background: var(--brand);
      border-radius: 1px 1px 0 0;
    }

    .tab-close {
      opacity: 1;
    }
  }

  &--closing {
    opacity: 0.4;
    pointer-events: none;
  }
}

.tab-icon {
  flex-shrink: 0;
}

.tab-label {
  font-weight: 500;
}

.tab-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border: none;
  background: transparent;
  border-radius: 4px;
  cursor: pointer;
  color: var(--text-tertiary);
  opacity: 0;
  transition: all var(--duration-fast) var(--ease-out);
  flex-shrink: 0;

  &:hover {
    background: var(--bg-hover);
    color: var(--li-color);
  }

  .tab-item--active & {
    opacity: 0.7;
  }
}

/* ============================
   右键菜单
   ============================ */

.tab-context-menu {
  position: fixed;
  z-index: 9999;
  min-width: 160px;
  background: var(--bg-card);
  border: 1px solid var(--bg-divider);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-md);
  padding: 4px 0;
}

.context-menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  font-size: var(--font-size-caption);
  color: var(--text-primary);
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-out);

  &:hover {
    background: var(--bg-hover);
  }
}

.context-menu-divider {
  height: 1px;
  background: var(--bg-divider);
  margin: 4px 0;
}

.context-menu-mask {
  position: fixed;
  inset: 0;
  z-index: 9998;
}

/* ───────── 响应式 ───────── */
@media (max-width: 767px) {
  .tab-bar {
    overflow-x: auto;
    overflow-y: hidden;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;

    &::-webkit-scrollbar {
      height: 0;
    }
  }

  .tab-item {
    padding: 0 10px;
    font-size: 12px;
    flex-shrink: 0;
  }

  .tab-label {
    max-width: 80px;
    overflow: hidden;
    text-overflow: ellipsis;
  }
}
</style>
