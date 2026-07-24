<template>
  <!--
    伏羲 v2.1 — 主布局框架
    小米简约风：顶栏(56px) + 侧边栏(220px) + Tab栏(42px) + 主内容区
    Phase 1: 伏羲令(Cmd+K) + 快捷键系统 + 太极主题切换
  -->
  <div class="v2-main-layout" :data-theme="isDark ? 'yin' : 'yang'">
    <!-- ========== 离线横幅 ========== -->
    <Transition name="banner-slide">
      <div v-if="!isOnline" class="offline-banner">
        <el-icon :size="16"><WarningFilled /></el-icon>
        <span>网络连接已断开，部分功能不可用</span>
        <span v-if="offlineState.pendingCount > 0" class="offline-banner-pending">
          ({{ offlineState.pendingCount }} 项待同步)
        </span>
      </div>
    </Transition>

    <!-- 离线状态指示器（浮动底部） -->
    <OfflineIndicator :dismissible="true" position="bottom" :show-details="true" />

    <!-- ========== 顶栏 56px ========== -->
    <header class="v2-header">
      <div class="header-left">
        <!-- 迷你八卦罗盘 -->
        <MiniBaguaCompass :active-gua="'qian'" />

        <!-- 伏羲令触发按钮（Cmd+K 提示） -->
        <button class="header-fuxiling-btn" @click="showFuxiLing = true" title="伏羲令全局搜索 (⌘K)">
          <el-icon :size="14"><Search /></el-icon>
          <span class="fuxiling-btn-text">搜索服务、命令、文档...</span>
          <kbd class="fuxiling-btn-kbd">⌘K</kbd>
        </button>
      </div>

      <!-- 中间区域 -->
      <div class="header-center">
        <span class="header-title">伏羲 v2.1</span>
      </div>

      <!-- 右侧：太极主题切换 + 通知 + 头像 -->
      <div class="header-right">
        <!-- 太极主题切换按钮 -->
        <el-tooltip :content="isDark ? '切换至☀️阳模式' : '切换至🌙阴模式'" placement="bottom">
          <button
            class="header-taiji-btn"
            :class="{ 'header-taiji-btn--flip': isAnimating }"
            :aria-label="isDark ? '切换亮色' : '切换暗色'"
            @click="handleTaijiToggle"
          >
            <!-- 太极 SVG 图标 -->
            <svg
              class="taiji-svg"
              :class="{ 'taiji-svg--yin': isDark }"
              width="24"
              height="24"
              viewBox="0 0 64 64"
              aria-hidden="true"
            >
              <circle cx="32" cy="32" r="31" fill="none" :stroke="strokeColor" stroke-width="1.5" />
              <path d="M32,1 A31,31 0 0,1 32,63 A15.5,15.5 0 0,1 32,32 A15.5,15.5 0 0,0 32,1 Z" :fill="isDark ? '#555' : '#FF6700'" />
              <path d="M32,1 A31,31 0 0,0 32,63 A15.5,15.5 0 0,0 32,32 A15.5,15.5 0 0,1 32,1 Z" :fill="isDark ? '#FF6700' : '#FFF'" />
              <circle cx="32" cy="16.5" r="5.5" :fill="isDark ? '#555' : '#FF6700'" />
              <circle cx="32" cy="16.5" r="2.5" :fill="isDark ? '#FF6700' : '#FFF'" />
              <circle cx="32" cy="47.5" r="5.5" :fill="isDark ? '#FF6700' : '#FFF'" />
              <circle cx="32" cy="47.5" r="2.5" :fill="isDark ? '#555' : '#FF6700'" />
            </svg>
          </button>
        </el-tooltip>

        <el-tooltip content="窗口布局管理" placement="bottom">
          <button
            class="header-action-btn"
            aria-label="窗口布局管理"
            @click="showLayoutManager = true"
          >
            <el-icon :size="20"><Grid /></el-icon>
          </button>
        </el-tooltip>

        <el-tooltip content="通知中心" placement="bottom">
          <button
            class="header-action-btn"
            aria-label="通知中心"
            @click="handleOpenNotificationCenter"
          >
            <el-badge :value="notificationCount" :hidden="notificationCount === 0" :max="99">
              <el-icon :size="20"><Bell /></el-icon>
            </el-badge>
          </button>
        </el-tooltip>

        <!-- 用户头像 -->
        <el-dropdown trigger="click" @command="handleUserCommand">
          <div class="header-user">
            <el-avatar :size="32" :src="authStore.user?.avatar">
              {{ authStore.user?.display_name?.[0] || authStore.user?.username?.[0] || 'U' }}
            </el-avatar>
            <span class="header-user-name">
              {{ authStore.user?.display_name || authStore.user?.username || '用户' }}
            </span>
            <el-icon :size="14"><ArrowDown /></el-icon>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="profile">
                <el-icon><UserFilled /></el-icon>
                个人中心
              </el-dropdown-item>
              <el-dropdown-item command="settings">
                <el-icon><Setting /></el-icon>
                设置
              </el-dropdown-item>
              <el-dropdown-item divided command="logout">
                <el-icon><SwitchButton /></el-icon>
                退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>

    <!-- ========== 主区域 ========== -->
    <div class="v2-main-area">
      <WorkspaceSidebar
        :collapsed="sidebarCollapsed"
        :width="220"
        @toggle="sidebarCollapsed = !sidebarCollapsed"
      />

      <div class="v2-content-area">
        <TabBar
          :tabs="tabItems"
          :active-id="activeTabId"
          :closing-ids="windowManager.closingWindowIds"
          @activate="handleTabActivate"
          @close="handleTabClose"
          @close-others="handleTabCloseOthers"
          @close-right="handleTabCloseRight"
          @pin="handleTabPin"
          @reorder="handleTabReorder"
        />

        <main class="v2-content">
          <div class="v2-content-inner">
            <router-view v-slot="{ Component }">
              <keep-alive :include="keepAliveIncludes">
                <component :is="Component" />
              </keep-alive>
            </router-view>
          </div>
        </main>
      </div>
    </div>

    <!-- 浮动窗口层 -->
    <div class="v2-floating-windows">
      <ServiceWindowShell
        v-for="win in floatingWindows"
        :key="win.id"
        :window="win"
        :visible="!windowManager.closingWindowIds.has(win.id)"
        @focus="windowManager.focus(win.id)"
        @minimize="windowManager.minimize(win.id)"
        @maximize="windowManager.toggleMaximize(win.id)"
        @close="windowManager.close(win.id)"
        @move="(x, y) => windowManager.move(win.id, x, y)"
        @resize="(w, h) => windowManager.resize(win.id, w, h)"
        @closed="handleWindowClosed(win.id)"
      >
        <div class="floating-window-placeholder">
          <el-icon :size="32"><component :is="win.icon" /></el-icon>
          <p>服务窗口: {{ win.title }}</p>
        </div>
      </ServiceWindowShell>
    </div>

    <!-- ══════════════════════════════════════
         Phase 1: 伏羲令全局搜索面板 (Cmd+K)
         ══════════════════════════════════════ -->
    <FuxiLing :visible="showFuxiLing" @close="showFuxiLing = false" />

    <!-- ══════════════════════════════════════
         Phase 1: 快捷键帮助面板 (Cmd+/)
         ══════════════════════════════════════ -->
    <ShortcutHelp :visible="showShortcutHelp" @close="showShortcutHelp = false" />

    <!-- ══════════════════════════════════════
         P2: 通知中心抽屉
         ══════════════════════════════════════ -->
    <el-drawer
      v-model="showNotificationCenter"
      title=""
      direction="rtl"
      size="420px"
      :close-on-click-modal="true"
      :with-header="false"
      destroy-on-close
      @closed="showNotificationCenter = false"
    >
      <NotificationCenter />
    </el-drawer>

    <!-- ══════════════════════════════════════
         P3: 布局管理器抽屉
         ══════════════════════════════════════ -->
    <el-drawer
      v-model="showLayoutManager"
      title="窗口布局"
      direction="rtl"
      size="440px"
      :close-on-click-modal="true"
      destroy-on-close
      @closed="handleLayoutManagerClosed"
    >
      <template #header>
        <div class="layout-drawer-header">
          <el-icon :size="20" color="#ff6700"><Grid /></el-icon>
          <span>窗口布局管理</span>
        </div>
      </template>
      <LayoutManager
        @apply-snapshots="handleApplySnapshots"
        @close="showLayoutManager = false"
      />
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import { logger } from '@/utils/logger';
import {
  Search,
  Bell,
  ArrowDown,
  UserFilled,
  Setting,
  SwitchButton,
  ChatDotRound,
  House,
  Document,
  WarningFilled,
  Grid,
} from '@element-plus/icons-vue';

import { useAuthStore } from '@/stores/auth';
import { useWindowManager } from '@/stores/windowManager';
import { useOfflineStore } from '@/services/offline/store';
import OfflineIndicator from '@/services/offline/OfflineIndicator.vue';
import { useTheme } from '@/composables/useTheme';
import { useNetwork } from '@/composables/useNetwork';
import { useShortcuts } from '@/composables/useShortcuts';
import WorkspaceSidebar from './WorkspaceSidebar.vue';
import TabBar from './TabBar.vue';
import type { TabItem } from './TabBar.vue';
import ServiceWindowShell from '@/services/_registry/ServiceWindowShell.vue';
import MiniBaguaCompass from '@/components/bagua/MiniBaguaCompass.vue';
import FuxiLing from '@/components/search/FuxiLing.vue';
import ShortcutHelp from '@/components/common/ShortcutHelp.vue';
import NotificationCenter from '@/services/notification-center/NotificationCenter.vue';
import LayoutManager from '@/services/layout-store/LayoutManager.vue';
import { useLayoutIntegration } from '@/composables/useLayoutIntegration';
import type { WindowSnapshot } from '@/types/layout';

// ============================
// Stores & Composables
// ============================

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();
const windowManager = useWindowManager();
const offlineStore = useOfflineStore();
const { isDark, toggleTheme } = useTheme();
const { isOnline } = useNetwork();

// 离线状态
const offlineState = computed(() => offlineStore.state);

// ============================
// Phase 1: 伏羲令 & 快捷键
// ============================

const showFuxiLing = ref(false);
const showNotificationCenter = ref(false);
const showLayoutManager = ref(false);

// ============================
// 布局集成
// ============================

const { applyLayoutSnapshots, autoSaveOnClose, autoRestoreLastSession, watchDisplayChanges } =
  useLayoutIntegration();

function handleApplySnapshots(snapshots: WindowSnapshot[]): void {
  applyLayoutSnapshots(snapshots);
}

function handleLayoutManagerClosed(): void {
  // 布局管理器关闭时不需额外处理
}

// ============================
// Phase 1: 快捷键
// ============================

const { showHelp: showShortcutHelp } = useShortcuts({
  onOpenFuxiLing: () => {
    showFuxiLing.value = !showFuxiLing.value;
  },
});

// ============================
// Phase 1: 太极旋转主题切换
// ============================

const isAnimating = ref(false);

const strokeColor = computed(() => (isDark.value ? 'rgba(255,255,255,0.3)' : 'rgba(0,0,0,0.1)'));

function handleTaijiToggle(): void {
  if (isAnimating.value) return;
  isAnimating.value = true;
  toggleTheme();
  setTimeout(() => {
    isAnimating.value = false;
  }, 600);
}

// ============================
// 侧边栏 & 通知
// ============================

const sidebarCollapsed = ref(false);
const notificationCount = ref(3);

function handleOpenNotificationCenter(): void {
  showNotificationCenter.value = true;
}

// ============================
// Tab 管理
// ============================

const tabList = ref<TabItem[]>([]);

const tabItems = computed<TabItem[]>(() => {
  const items: TabItem[] = [...tabList.value];
  for (const win of windowManager.visibleWindows) {
    if (!items.find((t) => t.id === win.id)) {
      items.push({
        id: win.id,
        title: win.title,
        icon: win.icon,
        serviceId: win.serviceId,
      });
    }
  }
  return items;
});

const activeTabId = computed<string | null>(() => {
  return windowManager.activeWindowId || route.path;
});

function handleTabActivate(id: string) {
  if (id.startsWith('window-')) {
    windowManager.focus(id);
  } else {
    router.push(id);
  }
}

function handleTabClose(id: string) {
  if (id.startsWith('window-')) {
    windowManager.close(id);
  } else {
    tabList.value = tabList.value.filter((t) => t.id !== id);
  }
}

function handleTabCloseOthers(id: string) {
  if (id.startsWith('window-')) {
    for (const win of windowManager.visibleWindows) {
      if (win.id !== id) windowManager.close(win.id);
    }
  }
  tabList.value = tabList.value.filter((t) => t.id === id);
}

function handleTabCloseRight(tabId: string) {
  const idx = tabItems.value.findIndex((t) => t.id === tabId);
  if (idx === -1) return;
  const rightTabs = tabItems.value.slice(idx + 1);
  for (const tab of rightTabs) {
    if (tab.id.startsWith('window-')) windowManager.close(tab.id);
  }
  tabList.value = tabList.value.filter(
    (t) => tabItems.value.findIndex((ti) => ti.id === t.id) <= idx,
  );
}

function handleTabPin(tabId: string, pin: boolean) {
  if (tabId.startsWith('window-')) return;
  const tab = tabList.value.find((t) => t.id === tabId);
  if (tab) tab.pinned = pin;
}

function handleTabReorder(fromId: string, toId: string) {
  const fromIdx = tabItems.value.findIndex((t) => t.id === fromId);
  const toIdx = tabItems.value.findIndex((t) => t.id === toId);
  if (fromIdx === -1 || toIdx === -1) return;
  const newList = [...tabList.value];
  const realFrom = newList.findIndex((t) => t.id === fromId);
  const realTo = newList.findIndex((t) => t.id === toId);
  if (realFrom !== -1 && realTo !== -1) {
    const [moved] = newList.splice(realFrom, 1);
    newList.splice(realTo, 0, moved);
    tabList.value = newList;
  }
}

function handleWindowClosed(windowId: string): void {
  autoSaveOnClose(windowId);
}

// ============================
// KeepAlive
// ============================

const keepAliveIncludes = computed(() => {
  const names: string[] = [
    'HomeView',
    'ChatView',
    'Search',
    'FilesView',
    'Wiki',
    'KnowledgeView',
    'Admin',
  ];
  for (const win of windowManager.visibleWindows) {
    names.push(`ServiceWindow-${win.serviceId}`);
  }
  return names;
});

// ============================
// 浮动窗口
// ============================

const floatingWindows = computed(() => {
  return windowManager.visibleWindows.filter(
    (w) => w.state !== 'minimized' && w.state !== 'closed',
  );
});

// ============================
// 用户操作
// ============================

function handleUserCommand(command: string) {
  switch (command) {
    case 'profile':
      router.push('/profile');
      break;
    case 'settings':
      router.push('/settings');
      break;
    case 'logout':
      handleLogout();
      break;
  }
}

async function handleLogout() {
  try {
    await ElMessageBox.confirm('确定要退出登录吗？', '确认退出', {
      confirmButtonText: '退出',
      cancelButtonText: '取消',
      type: 'warning',
    });
    authStore.logout();
    router.push('/login');
  } catch (error) {
    logger.error('退出登录失败', error);
    ElMessage.error('退出登录失败，请稍后重试');
  }
}

// ============================
// 初始化
// ============================

onMounted(async () => {
  tabList.value = [
    { id: '/', title: '首页', icon: House, pinned: true, route: '/' },
    { id: '/workspace/chat', title: 'AI 对话', icon: ChatDotRound, pinned: true, route: '/workspace/chat' },
    { id: '/knowledge', title: '知识库', icon: Document, route: '/knowledge' },
  ];

  // P3: 自动恢复上次会话的窗口布局
  await autoRestoreLastSession();

  // P3: 监听显示器变化
  watchDisplayChanges();
});
</script>

<style scoped lang="scss">
/* ============================
   整体布局
   ============================ */
.v2-main-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--fuxi-bg, #fafaf5);
  color: var(--fuxi-text, #333333);
  font-family: var(--font-family-base);
  overflow: hidden;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

/* ============================
   顶栏 56px
   ============================ */
.v2-header {
  display: flex;
  align-items: center;
  height: 56px;
  padding: 0 var(--space-md);
  background: var(--fuxi-bg-card, #ffffff);
  border-bottom: 1px solid var(--fuxi-border, #eeeeee);
  box-shadow: var(--fuxi-shadow-sm, 0 1px 6px rgba(0, 0, 0, 0.04));
  z-index: 100;
  flex-shrink: 0;
  gap: var(--space-md);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

/* ── 伏羲令触发按钮 ── */
.header-fuxiling-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 36px;
  padding: 0 12px;
  border: 1px solid var(--fuxi-border, #eeeeee);
  border-radius: 8px;
  background: var(--fuxi-bg-subtle, #f0ede5);
  color: var(--fuxi-text-tertiary, #cccccc);
  cursor: pointer;
  transition: all 0.2s ease;
  font-size: 13px;
  font-family: var(--font-family-base);
  width: 280px;

  &:hover {
    border-color: var(--fuxi-primary, #ff6700);
    background: var(--fuxi-bg-card, #ffffff);
  }
}

.fuxiling-btn-text {
  flex: 1;
  text-align: left;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fuxiling-btn-kbd {
  font-size: 10px;
  font-family: 'SF Mono', monospace;
  color: var(--fuxi-text-tertiary, #cccccc);
  background: var(--fuxi-border, #eeeeee);
  padding: 2px 6px;
  border-radius: 4px;
  flex-shrink: 0;
}

/* ── 中间 ── */
.header-center {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.header-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--fuxi-text-tertiary, #cccccc);
  letter-spacing: 1px;
}

/* ── 右侧 ── */
.header-right {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

/* ── 太极主题切换按钮 ── */
.header-taiji-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: none;
  background: transparent;
  border-radius: 50%;
  cursor: pointer;
  padding: 0;
  transition: background 0.2s ease, transform 0.6s cubic-bezier(0.4, 0, 0.2, 1);

  &:hover {
    background: var(--fuxi-bg-hover, #fffcf9);
  }

  &.header-taiji-btn--flip {
    transform: rotate(180deg);
  }

  .taiji-svg {
    display: block;
    transition: transform 0.6s cubic-bezier(0.4, 0, 0.2, 1);
  }
}

.header-action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: none;
  background: transparent;
  border-radius: 8px;
  cursor: pointer;
  color: var(--fuxi-text-secondary, #999999);
  transition: all 0.2s ease;

  &:hover {
    background: var(--fuxi-bg-hover, #fffcf9);
    color: var(--fuxi-text, #333333);
  }
}

.header-user {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  border-radius: 12px;
  cursor: pointer;
  transition: background 0.2s ease;

  &:hover {
    background: var(--fuxi-bg-hover, #fffcf9);
  }

  .header-user-name {
    font-size: 14px;
    color: var(--fuxi-text, #333333);
    font-weight: 500;
    max-width: 100px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

/* ============================
   主区域
   ============================ */
.v2-main-area {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.v2-content-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

.v2-content {
  flex: 1;
  overflow: hidden;
  background: var(--fuxi-bg, #fafaf5);
}

.v2-content-inner {
  width: 100%;
  height: 100%;
  overflow: auto;

  &::-webkit-scrollbar { width: 6px; }
  &::-webkit-scrollbar-thumb {
    background: var(--fuxi-border, #eeeeee);
    border-radius: 3px;
  }
  &::-webkit-scrollbar-track { background: transparent; }
}

/* ============================
   浮动窗口层
   ============================ */
.v2-floating-windows {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 50;
  > * { pointer-events: auto; }
}

.floating-window-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 200px;
  color: var(--fuxi-text-tertiary, #cccccc);
  gap: 12px;
  p { font-size: 14px; }
}

/* ============================
   离线横幅
   ============================ */
.offline-banner {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 36px;
  background: #fdf6ec;
  color: #e6a23c;
  font-size: 14px;
  flex-shrink: 0;
  z-index: 110;
}

.offline-banner-pending {
  font-size: 12px;
  color: #b88230;
}

.banner-slide-enter-active,
.banner-slide-leave-active { transition: all 0.3s ease; }
.banner-slide-enter-from,
.banner-slide-leave-to { height: 0; opacity: 0; }

/* ============================
   响应式
   ============================ */
@media (max-width: 767px) {
  .v2-header { padding: 0 8px; }
  .header-fuxiling-btn { width: 140px; }
  .header-center { display: none; }
}
@media (max-width: 479px) {
  .header-user .header-user-name { display: none; }
  .header-fuxiling-btn { width: 100px; }
}

/* ============================
   布局管理器抽屉样式
   ============================ */
.layout-drawer-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: var(--fuxi-text, #333333);
}
</style>
