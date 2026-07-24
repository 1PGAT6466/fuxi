<template>
  <!--
    伏羲 v1.44 — 工作空间侧边栏（重构版）
    小米简约风：5 组手风琴分组，按业务领域组织，emoji 图标
    支持折叠/展开、分组标题、活跃状态高亮、Feature Flags 控制
  -->
  <aside
    class="workspace-sidebar"
    :class="{ 'sidebar--collapsed': collapsed }"
    :style="{ width: collapsed ? '64px' : `${width}px` }"
  >
    <div class="sidebar-inner">
      <!-- 菜单区域 — 5 组手风琴 -->
      <nav class="sidebar-menu" role="navigation" aria-label="侧边栏导航">
        <el-collapse
          :model-value="expandedGroups"
          accordion
          @change="handleGroupChange"
        >
          <!-- Group 1: 🏠 工作区 -->
          <el-collapse-item
            v-if="!collapsed"
            key="workspace"
            title="🏠 工作区"
            name="workspace"
          >
            <div class="menu-sub-items">
              <div
                v-for="item in workspaceItems"
                :key="item.route"
                class="menu-item"
                :class="{
                  'menu-item--active': isActive(item.route),
                  'menu-item--disabled': item.disabled,
                }"
                :aria-current="isActive(item.route) ? 'page' : undefined"
                role="menuitem"
                @click="handleMenuClick(item)"
              >
                <div class="menu-item-icon" :style="{ color: item.iconColor }">
                  <el-icon :size="18">
                    <component :is="item.icon" />
                  </el-icon>
                </div>
                <span class="menu-item-label">{{ item.label }}</span>
                <span v-if="item.badge" class="menu-item-badge">{{ item.badge }}</span>
              </div>
            </div>
          </el-collapse-item>

          <!-- 折叠模式：工作区直接显示图标 -->
          <div v-if="collapsed" class="collapsed-group">
            <el-tooltip
              v-for="item in workspaceItems"
              :key="item.route"
              :content="item.label"
              placement="right"
              :show-after="400"
            >
              <div
                class="menu-item"
                :class="{
                  'menu-item--active': isActive(item.route),
                  'menu-item--disabled': item.disabled,
                }"
                role="menuitem"
                @click="handleMenuClick(item)"
              >
                <div class="menu-item-icon" :style="{ color: item.iconColor }">
                  <el-icon :size="20">
                    <component :is="item.icon" />
                  </el-icon>
                </div>
              </div>
            </el-tooltip>
          </div>

          <!-- Group 2: 📊 数据分析（Feature Flag 控制） -->
          <el-collapse-item
            v-if="!collapsed && featureFlags.enableDataAnalytics"
            key="analytics"
            title="📊 数据分析"
            name="analytics"
          >
            <div class="menu-sub-items">
              <div
                v-for="item in analyticsItems"
                :key="item.route"
                class="menu-item"
                :class="{
                  'menu-item--active': isActive(item.route),
                  'menu-item--disabled': item.disabled,
                }"
                role="menuitem"
                @click="handleMenuClick(item)"
              >
                <span class="menu-item-emoji">{{ item.emoji }}</span>
                <span class="menu-item-label">{{ item.label }}</span>
              </div>
            </div>
          </el-collapse-item>

          <!-- Group 3: 🛠️ 文档工程（Feature Flag 控制） -->
          <el-collapse-item
            v-if="!collapsed && featureFlags.enableDocTools"
            key="doc-tools"
            title="🛠️ 文档工程"
            name="doc-tools"
          >
            <div class="menu-sub-items">
              <div
                v-for="item in docToolsItems"
                :key="item.route"
                class="menu-item"
                :class="{
                  'menu-item--active': isActive(item.route),
                  'menu-item--disabled': item.disabled,
                }"
                role="menuitem"
                @click="handleMenuClick(item)"
              >
                <span class="menu-item-emoji">{{ item.emoji }}</span>
                <span class="menu-item-label">{{ item.label }}</span>
                <span v-if="item.disabled" class="menu-item-construction">建设中的</span>
              </div>
            </div>
          </el-collapse-item>

          <!-- Group 4: ⚙️ 管理中心（仅 admin 角色可见） -->
          <el-collapse-item
            v-if="!collapsed && isAdmin"
            key="admin"
            title="⚙️ 管理中心"
            name="admin"
          >
            <div class="menu-sub-items">
              <div
                v-for="item in adminItems"
                :key="item.route"
                class="menu-item"
                :class="{
                  'menu-item--active': isActive(item.route),
                  'menu-item--disabled': item.disabled,
                }"
                role="menuitem"
                @click="handleMenuClick(item)"
              >
                <div class="menu-item-icon" :style="{ color: item.iconColor }">
                  <el-icon :size="18">
                    <component :is="item.icon" />
                  </el-icon>
                </div>
                <span class="menu-item-label">{{ item.label }}</span>
              </div>
            </div>
          </el-collapse-item>

          <!-- Group 5: 👤 个人 -->
          <el-collapse-item
            v-if="!collapsed"
            key="personal"
            title="👤 个人"
            name="personal"
          >
            <div class="menu-sub-items">
              <div
                v-for="item in personalItems"
                :key="item.route"
                class="menu-item"
                :class="{
                  'menu-item--active': isActive(item.route),
                  'menu-item--disabled': item.disabled,
                }"
                role="menuitem"
                @click="handleMenuClick(item)"
              >
                <div class="menu-item-icon" :style="{ color: item.iconColor }">
                  <el-icon :size="18">
                    <component :is="item.icon" />
                  </el-icon>
                </div>
                <span class="menu-item-label">{{ item.label }}</span>
                <span
                  v-if="item.construction"
                  class="menu-item-construction"
                >建设中的</span>
              </div>
            </div>
          </el-collapse-item>
        </el-collapse>
      </nav>

      <!-- 底部区域：折叠按钮 -->
      <div class="sidebar-bottom">
        <button
          class="collapse-btn"
          :aria-label="collapsed ? '展开侧边栏' : '折叠侧边栏'"
          @click="$emit('toggle')"
        >
          <el-icon :size="18">
            <DArrowLeft v-if="!collapsed" />
            <DArrowRight v-else />
          </el-icon>
        </button>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { useFeatureFlags } from '@/stores/featureFlags';
import {
  DArrowLeft,
  DArrowRight,
  ChatDotRound,
  Search,
  FolderOpened,
  Document,
  Cpu,
  Grid,
  Setting,
  UserFilled,
  Monitor,
  DataAnalysis,
  TrendCharts,
  Switch,
  Guide,
  Timer,
} from '@element-plus/icons-vue';
import { h } from 'vue';

// ============================
// Props & Emits
// ============================

defineProps<{
  collapsed: boolean;
  width?: number;
}>();

defineEmits<{
  (e: 'toggle'): void;
}>();

// ============================
// 路由 & Store
// ============================

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();
const featureFlags = useFeatureFlags();

const isAdmin = computed(() => authStore.isAdmin);

// ============================
// 手风琴展开状态
// ============================

const expandedGroups = ref<string[]>(['workspace']);

function handleGroupChange(val: string | string[]): void {
  if (Array.isArray(val)) {
    expandedGroups.value = val;
  } else {
    expandedGroups.value = val ? [val] : [];
  }
}

// ============================
// 路由工具
// ============================

function isActive(targetRoute: string): boolean {
  if (targetRoute === '/') return route.path === '/';
  return route.path.startsWith(targetRoute);
}

// ============================
// 菜单数据结构
// ============================

interface MenuItem {
  label: string;
  route: string;
  icon?: unknown;
  emoji?: string;
  iconColor?: string;
  disabled?: boolean;
  construction?: boolean;
  badge?: string | number;
}

// 🏠 工作区
const workspaceItems = computed<MenuItem[]>(() => [
  {
    label: '对话',
    route: '/chat',
    icon: ChatDotRound,
    iconColor: '#FF6700',
  },
  {
    label: '搜索',
    route: '/search',
    icon: Search,
    iconColor: '#3a6b8c',
  },
  {
    label: '文档',
    route: '/workspace/documents',
    icon: Document,
    iconColor: '#4a7c59',
  },
  {
    label: 'Wiki',
    route: '/workspace/wiki',
    icon: Document,
    iconColor: '#c9a84c',
  },
  {
    label: '图谱',
    route: '/workspace/graph',
    icon: Grid,
    iconColor: '#c44b3c',
  },
  {
    label: '世界树',
    route: '/workspace/worldtree',
    icon: Guide,
    iconColor: '#5b8c5a',
  },
]);

// 📊 数据分析（链接到 data-analytics 服务）
const analyticsItems = computed<MenuItem[]>(() => [
  {
    label: '统计概览',
    route: '/workspace/analytics',
    emoji: '📈',
  },
  {
    label: '趋势分析',
    route: '/workspace/analytics/trends',
    emoji: '📉',
    disabled: true,
  },
  {
    label: '报表',
    route: '/workspace/analytics/report',
    emoji: '📋',
    disabled: true,
  },
  {
    label: '导出',
    route: '/workspace/analytics/export',
    emoji: '📤',
    disabled: true,
  },
]);

// 🛠️ 文档工程（链接到 doc-tools/dxf-viewer 服务）
const docToolsItems = computed<MenuItem[]>(() => {
  const items: MenuItem[] = [
    {
      label: '格式转换',
      route: '/workspace/doc-tools/convert',
      emoji: '🔄',
    },
    {
      label: '合并拆分',
      route: '/workspace/doc-tools/merge',
      emoji: '✂️',
    },
    {
      label: '图片处理',
      route: '/workspace/doc-tools/image',
      emoji: '🖼️',
    },
  ];
  // DXF查看 — feature flag 控制
  if (featureFlags.enableDxfViewer) {
    items.push({
      label: 'DXF查看',
      route: '/dxf-viewer',
      emoji: '📐',
    });
  }
  return items;
});

// ⚙️ 管理中心（仅 admin 角色可见）
const adminItems = computed<MenuItem[]>(() => [
  {
    label: '仪表板',
    route: '/admin/dashboard',
    icon: Monitor,
    iconColor: '#4a7c59',
  },
  {
    label: '评测',
    route: '/admin/evaluation',
    icon: DataAnalysis,
    iconColor: '#c44b3c',
  },
  {
    label: '进化',
    route: '/admin/evolution',
    icon: TrendCharts,
    iconColor: '#d4a574',
  },
  {
    label: '功能开关',
    route: '/admin/feature-flags',
    icon: Switch,
    iconColor: '#5b8c5a',
  },
  {
    label: '用户管理',
    route: '/admin/users',
    icon: UserFilled,
    iconColor: '#3a6b8c',
  },
  {
    label: '四象系统',
    route: '/admin/symbols',
    icon: Setting,
    iconColor: '#FF6700',
  },
  {
    label: '成长面板',
    route: '/admin/growth',
    icon: TrendCharts,
    iconColor: '#3a6b8c',
  },
  {
    label: '用户反馈',
    route: '/admin/feedback',
    icon: ChatDotRound,
    iconColor: '#4a7c59',
  },
]);

// 👤 个人
const personalItems = computed<MenuItem[]>(() => [
  {
    label: '用户中心',
    route: '/profile',
    icon: UserFilled,
    iconColor: '#d4a574',
  },
  {
    label: '收藏',
    route: '/personal/favorites',
    icon: FolderOpened,
    iconColor: '#c9a84c',
    construction: true,
  },
  {
    label: '历史',
    route: '/personal/history',
    icon: Timer,
    iconColor: '#5b8c5a',
  },
  {
    label: '设置',
    route: '/settings',
    icon: Setting,
    iconColor: '#a68a6b',
    construction: true,
  },
]);

// ============================
// 方法
// ============================

function handleMenuClick(item: MenuItem): void {
  if (item.disabled || item.construction) return;
  router.push(item.route);
}
</script>

<style scoped lang="scss">
.workspace-sidebar {
  height: 100%;
  background: var(--fuxi-bg-card, var(--bg-card));
  border-right: 1px solid var(--fuxi-border, var(--bg-divider));
  transition: width var(--duration-normal, 350ms) var(--ease-out, cubic-bezier(0.25, 0.46, 0.45, 0.94));
  overflow: hidden;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
}

.sidebar-inner {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: var(--space-sm, 8px) 0;
}

/* ============================
   菜单区域
   ============================ */

.sidebar-menu {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;

  // 自定义滚动条
  &::-webkit-scrollbar {
    width: 4px;
  }

  &::-webkit-scrollbar-thumb {
    background: var(--fuxi-border, var(--bg-divider));
    border-radius: 4px;
  }

  &::-webkit-scrollbar-track {
    background: transparent;
  }
}

/* ─── Element Plus Collapse 覆盖 ─── */
.sidebar-menu :deep(.el-collapse) {
  border: none;
}

.sidebar-menu :deep(.el-collapse-item__header) {
  height: 40px;
  padding: 0 12px;
  font-size: 13px;
  font-weight: 600;
  color: var(--fuxi-text-secondary, #999999);
  border: none;
  background: transparent;
  letter-spacing: 0.5px;
  transition: color 0.2s ease;
  user-select: none;
}

.sidebar-menu :deep(.el-collapse-item__header:hover) {
  color: var(--fuxi-primary, #FF6700);
}

.sidebar-menu :deep(.el-collapse-item__header.is-active) {
  color: var(--fuxi-primary, #FF6700);
  border-bottom: 1px solid var(--fuxi-border, #eee);
}

.sidebar-menu :deep(.el-collapse-item__wrap) {
  border: none;
  background: transparent;
}

.sidebar-menu :deep(.el-collapse-item__content) {
  padding: 4px 0;
}

.sidebar-menu :deep(.el-collapse-item__arrow) {
  margin-right: 4px;
}

/* ─── 子菜单项目 ─── */
.menu-sub-items {
  display: flex;
  flex-direction: column;
}

.menu-item {
  display: flex;
  align-items: center;
  padding: 9px 12px 9px 24px;
  border-radius: 8px;
  cursor: pointer;
  transition: all var(--duration-fast, 200ms) var(--ease-out);
  position: relative;
  user-select: none;
  margin: 1px 4px;

  &:hover {
    background: var(--fuxi-bg-hover, var(--bg-hover));
  }

  &--active {
    background: var(--fuxi-primary-light, rgba(255, 103, 0, 0.08));

    .menu-item-label {
      color: var(--fuxi-primary, #FF6700);
      font-weight: 600;
    }

    &::before {
      content: '';
      position: absolute;
      left: 8px;
      top: 50%;
      transform: translateY(-50%);
      width: 3px;
      height: 18px;
      background: var(--fuxi-primary, #FF6700);
      border-radius: 0 3px 3px 0;
    }
  }

  &--disabled {
    opacity: 0.4;
    cursor: not-allowed;

    &:hover {
      background: transparent;
    }
  }
}

.menu-item-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 4px;
  background: var(--fuxi-bg-subtle, var(--bg-subtle));
  flex-shrink: 0;
  transition: all 0.2s ease;

  .menu-item--active & {
    background: var(--fuxi-primary-light, rgba(255, 103, 0, 0.12));
  }
}

.menu-item-emoji {
  width: 30px;
  text-align: center;
  font-size: 14px;
  flex-shrink: 0;
}

.menu-item-label {
  margin-left: 8px;
  font-size: 13px;
  font-weight: 500;
  color: var(--fuxi-text, #333333);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}

.menu-item-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  background: var(--fuxi-primary, #FF6700);
  color: #fff;
  border-radius: 10px;
  margin-left: 4px;
  flex-shrink: 0;
}

.menu-item-construction {
  font-size: 10px;
  font-weight: 500;
  padding: 1px 6px;
  background: var(--fuxi-bg-subtle, #f0ede5);
  color: var(--fuxi-text-tertiary, #ccc);
  border-radius: 10px;
  margin-left: 4px;
  flex-shrink: 0;
}

/* ============================
   折叠状态 — 图标模式
   ============================ */

.collapsed-group {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 4px 0;
  gap: 2px;

  .menu-item {
    justify-content: center;
    padding: 8px 0;
    margin: 1px 8px;

    &::before {
      display: none;
    }
  }

  .menu-item-icon {
    width: 40px;
    height: 40px;
  }
}

/* ============================
   折叠按钮
   ============================ */

.sidebar-bottom {
  border-top: 1px solid var(--fuxi-border, var(--bg-divider));
  padding: var(--space-sm, 8px);
}

.collapse-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 36px;
  border: none;
  background: transparent;
  border-radius: 8px;
  cursor: pointer;
  color: var(--fuxi-text-tertiary, #999);
  transition: all var(--duration-fast, 200ms) var(--ease-out);

  &:hover {
    background: var(--fuxi-bg-hover, var(--bg-hover));
    color: var(--fuxi-text, #333);
  }
}

/* ============================
   折叠状态
   ============================ */

.sidebar--collapsed {
  .menu-item {
    justify-content: center;
    padding: 10px 0;
  }

  .menu-item-icon {
    width: 40px;
    height: 40px;
  }
}
</style>
