<template>
  <!--
    伏羲 v2.1 — 离线状态指示器组件
    显示离线状态提示、同步进度、待处理操作数和冲突数
  -->
  <Teleport to="body">
    <Transition name="offline-indicator-fade">
      <div
        v-if="visible"
        class="offline-indicator"
        :class="[`offline-indicator--${statusClass}`]"
        role="status"
        aria-live="polite"
        :aria-label="ariaLabel"
      >
        <!-- 连接状态图标 -->
        <div class="offline-indicator__icon">
          <el-icon v-if="isReconnecting" class="icon-spin" :size="16"><Loading /></el-icon>
          <el-icon v-else-if="isOnline" :size="16"><CircleCheckFilled /></el-icon>
          <el-icon v-else :size="16"><WarningFilled /></el-icon>
        </div>

        <!-- 状态文本 -->
        <span class="offline-indicator__text">{{ statusText }}</span>

        <!-- 操作详情 -->
        <div v-if="showDetails" class="offline-indicator__details">
          <!-- 待处理操作 -->
          <el-tooltip
            v-if="hasPendingOps"
            content="点击查看待同步的操作"
            placement="top"
          >
            <span class="offline-indicator__badge offline-indicator__badge--pending" @click="toggleQueuePanel">
              <el-icon :size="12"><Clock /></el-icon>
              {{ pendingCount }} 项待同步
            </span>
          </el-tooltip>

          <!-- 冲突 -->
          <el-tooltip
            v-if="hasConflicts"
            content="点击查看同步冲突"
            placement="top"
          >
            <span class="offline-indicator__badge offline-indicator__badge--conflict" @click="toggleConflictPanel">
              <el-icon :size="12"><Warning /></el-icon>
              {{ conflictCount }} 个冲突
            </span>
          </el-tooltip>

          <!-- 同步进度 -->
          <el-progress
            v-if="isSyncing"
            :percentage="syncProgress"
            :stroke-width="3"
            :show-text="false"
            class="offline-indicator__progress"
            status="warning"
          />

          <!-- 上次同步时间 -->
          <span v-if="lastSyncTimeFormatted && !isSyncing" class="offline-indicator__time">
            {{ lastSyncTimeFormatted }}
          </span>
        </div>

        <!-- 关闭按钮 -->
        <button
          v-if="dismissible && !isOffline"
          class="offline-indicator__close"
          @click="dismiss"
          :aria-label="'关闭离线提示'"
        >
          <el-icon :size="14"><Close /></el-icon>
        </button>
      </div>
    </Transition>
  </Teleport>

  <!-- 操作队列面板 -->
  <Teleport to="body">
    <Transition name="offline-panel-slide">
      <div v-if="showQueuePanel" class="offline-panel offline-panel--queue" role="dialog" aria-modal="true" aria-label="待同步操作列表">
        <div class="offline-panel__header">
          <h3>待同步操作 ({{ queue.length }})</h3>
          <div class="offline-panel__actions">
            <el-button size="small" text @click="handleSyncNow" :loading="isSyncing">
              立即同步
            </el-button>
            <el-button size="small" text @click="handleClearQueue">
              清空
            </el-button>
            <el-button size="small" text @click="toggleQueuePanel">
              <el-icon :size="16"><Close /></el-icon>
            </el-button>
          </div>
        </div>
        <div class="offline-panel__body">
          <div v-if="queue.length === 0" class="offline-panel__empty">
            暂无待处理操作
          </div>
          <div
            v-for="op in queue"
            :key="op.id"
            class="offline-panel__item"
          >
            <div class="offline-panel__item-type">
              <el-tag :type="tagTypeForOp(op.type)" size="small" disable-transitions>
                {{ opLabelForOp(op.type) }}
              </el-tag>
            </div>
            <div class="offline-panel__item-desc">
              <span class="offline-panel__item-endpoint">{{ op.description || op.endpoint }}</span>
              <span class="offline-panel__item-time">{{ formatTime(op.createdAt) }}</span>
            </div>
            <div class="offline-panel__item-retry">
              重试 {{ op.retryCount }}/{{ op.maxRetries }}
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>

  <!-- 冲突面板 -->
  <Teleport to="body">
    <Transition name="offline-panel-slide">
      <div v-if="showConflictPanel" class="offline-panel offline-panel--conflict" role="dialog" aria-modal="true" aria-label="同步冲突列表">
        <div class="offline-panel__header">
          <h3>同步冲突 ({{ conflicts.length }})</h3>
          <el-button size="small" text @click="toggleConflictPanel">
            <el-icon :size="16"><Close /></el-icon>
          </el-button>
        </div>
        <div class="offline-panel__body">
          <div v-if="conflicts.length === 0" class="offline-panel__empty">
            暂无冲突
          </div>
          <div
            v-for="conflict in conflicts"
            :key="conflict.id"
            class="offline-panel__item offline-panel__item--conflict"
          >
            <p class="offline-panel__conflict-desc">{{ conflict.description }}</p>
            <div v-if="!conflict.resolution" class="offline-panel__conflict-actions">
              <el-button size="small" type="primary" @click="handleResolve(conflict.id, 'local')">
                使用本地
              </el-button>
              <el-button size="small" @click="handleResolve(conflict.id, 'server')">
                使用服务端
              </el-button>
              <el-button size="small" @click="handleResolve(conflict.id, 'merge')">
                合并
              </el-button>
            </div>
            <el-tag v-else type="info" size="small">
              已解决：{{ resolutionLabel(conflict.resolution) }}
            </el-tag>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
/**
 * 离线状态指示器组件
 *
 * 使用方式：
 *   <OfflineIndicator />
 *
 * Props:
 *   - dismissible: 是否允许关闭（离线时不可关闭）
 *   - position: 显示位置
 *   - showDetails: 是否显示详情
 */
import { ref, computed } from 'vue';
import {
  Loading,
  CircleCheckFilled,
  WarningFilled,
  Clock,
  Warning,
  Close,
} from '@element-plus/icons-vue';
import type { OfflineOperationType } from './types';
import { useOfflineStore } from './store';

// ============================
// Props
// ============================

interface Props {
  /** 是否允许关闭 */
  dismissible?: boolean;
  /** 显示位置 */
  position?: 'top' | 'bottom';
  /** 是否显示详情（操作数、冲突数、进度） */
  showDetails?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  dismissible: true,
  position: 'bottom',
  showDetails: true,
});

// ============================
// Store
// ============================

const store = useOfflineStore();

const {
  isOnline,
  isReconnecting,
  isOffline,
  isSyncing,
  hasPendingOps,
  hasConflicts,
  pendingCount,
  conflictCount,
  conflicts,
  queue,
  syncStatus,
} = store;

// ============================
// 本地状态
// ============================

const dismissed = ref(false);
const showQueuePanel = ref(false);
const showConflictPanel = ref(false);
const syncProgress = ref(0);

// ============================
// 计算属性
// ============================

/** 是否显示指示器 */
const visible = computed(() => {
  if (dismissed.value && !isOffline.value) return false;
  return true;
});

/** 状态样式类 */
const statusClass = computed(() => {
  if (isReconnecting.value) return 'reconnecting';
  if (isOnline.value && !hasPendingOps.value) return 'online';
  if (isOffline.value) return 'offline';
  return 'warning';
});

/** 状态文本 */
const statusText = computed(() => {
  if (isReconnecting.value) return '正在重新连接...';
  if (isSyncing.value) return `正在同步 (${pendingCount.value} 项)...`;
  if (isOffline.value) return '当前离线，部分功能不可用';
  if (store.state.value.syncStatus === 'conflict') return `同步完成，${conflictCount.value} 个冲突待解决`;
  if (store.state.value.syncStatus === 'error') return '部分操作同步失败';
  if (hasPendingOps.value) return `在线 — ${pendingCount.value} 项待同步`;
  return '已连接';
});

/** ARIA 标签 */
const ariaLabel = computed(() => {
  if (isOffline.value) return '当前离线状态';
  return `连接状态: ${statusText.value}`;
});

// ============================
// 方法
// ============================

function dismiss(): void {
  dismissed.value = true;
}

function toggleQueuePanel(): void {
  showQueuePanel.value = !showQueuePanel.value;
  if (showQueuePanel.value) {
    showConflictPanel.value = false; // 互斥
  }
}

function toggleConflictPanel(): void {
  showConflictPanel.value = !showConflictPanel.value;
  if (showConflictPanel.value) {
    showQueuePanel.value = false; // 互斥
  }
}

async function handleSyncNow(): Promise<void> {
  try {
    await store.syncPending();
  } catch {
    // handled by store
  }
}

async function handleClearQueue(): Promise<void> {
  await store.clearQueue();
}

async function handleResolve(
  conflictId: string,
  resolution: 'local' | 'server' | 'merge',
): Promise<void> {
  await store.resolveConflict(conflictId, resolution);
}

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  });
}

function tagTypeForOp(type: OfflineOperationType): 'success' | 'warning' | 'danger' | 'info' {
  switch (type) {
    case 'create': return 'success';
    case 'update': return 'warning';
    case 'delete': return 'danger';
    default: return 'info';
  }
}

function opLabelForOp(type: OfflineOperationType): string {
  switch (type) {
    case 'create': return '创建';
    case 'update': return '更新';
    case 'delete': return '删除';
    default: return type;
  }
}

function resolutionLabel(resolution: string): string {
  switch (resolution) {
    case 'local': return '本地版本';
    case 'server': return '服务端版本';
    case 'merge': return '已合并';
    default: return resolution;
  }
}
</script>

<style scoped lang="scss">
// ============================
// 指示器
// ============================

.offline-indicator {
  position: fixed;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  border-radius: 12px;
  background: var(--fuxi-bg-card, #ffffff);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.12);
  z-index: 9999;
  font-size: 13px;
  font-family: var(--font-family-base);
  max-width: 600px;
  pointer-events: auto;

  // 底部显示
  bottom: 24px;

  &--offline {
    background: #fdf6ec;
    border: 1px solid #e6a23c;
    color: #b88230;
  }

  &--reconnecting {
    background: #ecf5ff;
    border: 1px solid #409eff;
    color: #337ecc;
  }

  &--online {
    background: #f0f9eb;
    border: 1px solid #67c23a;
    color: #529b2e;
  }

  &--warning {
    background: #fdf6ec;
    border: 1px solid #e6a23c;
    color: #b88230;
  }
}

.offline-indicator__icon {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.offline-indicator__text {
  font-weight: 500;
  white-space: nowrap;
}

.offline-indicator__details {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: 4px;
}

.offline-indicator__badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
  cursor: pointer;
  transition: opacity 0.2s ease;

  &:hover {
    opacity: 0.8;
  }

  &--pending {
    background: rgba(230, 162, 60, 0.15);
    color: #b88230;
  }

  &--conflict {
    background: rgba(245, 108, 108, 0.15);
    color: #c45656;
  }
}

.offline-indicator__progress {
  width: 60px;
  flex-shrink: 0;
}

.offline-indicator__time {
  font-size: 11px;
  color: var(--fuxi-text-tertiary, #cccccc);
}

.offline-indicator__close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border: none;
  background: transparent;
  border-radius: 50%;
  cursor: pointer;
  color: var(--fuxi-text-tertiary, #cccccc);
  flex-shrink: 0;
  margin-left: 4px;

  &:hover {
    background: rgba(0, 0, 0, 0.06);
    color: var(--fuxi-text, #333333);
  }
}

// ============================
// 旋转动画
// ============================

.icon-spin {
  animation: offline-icon-spin 1s linear infinite;
}

@keyframes offline-icon-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

// ============================
// 面板
// ============================

.offline-panel {
  position: fixed;
  bottom: 80px;
  right: 24px;
  width: 380px;
  max-height: 480px;
  background: var(--fuxi-bg-card, #ffffff);
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.16);
  z-index: 9998;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.offline-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--fuxi-border, #eeeeee);

  h3 {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    color: var(--fuxi-text, #333333);
  }
}

.offline-panel__actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.offline-panel__body {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;

  &::-webkit-scrollbar { width: 4px; }
  &::-webkit-scrollbar-thumb {
    background: var(--fuxi-border, #eeeeee);
    border-radius: 2px;
  }
}

.offline-panel__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px 16px;
  color: var(--fuxi-text-tertiary, #cccccc);
  font-size: 13px;
}

.offline-panel__item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--fuxi-border, #f5f5f5);
  transition: background 0.15s ease;

  &:hover {
    background: var(--fuxi-bg-hover, #fffcf9);
  }

  &:last-child {
    border-bottom: none;
  }

  &--conflict {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
}

.offline-panel__item-type {
  flex-shrink: 0;
}

.offline-panel__item-desc {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.offline-panel__item-endpoint {
  font-size: 13px;
  color: var(--fuxi-text, #333333);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.offline-panel__item-time {
  font-size: 11px;
  color: var(--fuxi-text-tertiary, #cccccc);
}

.offline-panel__item-retry {
  font-size: 11px;
  color: var(--fuxi-text-tertiary, #cccccc);
  flex-shrink: 0;
}

.offline-panel__conflict-desc {
  margin: 0;
  font-size: 13px;
  color: var(--fuxi-text, #333333);
  line-height: 1.5;
}

.offline-panel__conflict-actions {
  display: flex;
  gap: 8px;
}

// ============================
// 过渡动画
// ============================

.offline-indicator-fade-enter-active,
.offline-indicator-fade-leave-active {
  transition: all 0.3s ease;
}

.offline-indicator-fade-enter-from,
.offline-indicator-fade-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(8px);
}

.offline-panel-slide-enter-active,
.offline-panel-slide-leave-active {
  transition: all 0.25s ease;
}

.offline-panel-slide-enter-from,
.offline-panel-slide-leave-to {
  opacity: 0;
  transform: translateY(12px);
}
</style>
