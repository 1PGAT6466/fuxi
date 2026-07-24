<template>
  <!--
    MobileNav — 移动端底部导航栏
    支持底部 Tab 切换、抽屉菜单、手势返回
    响应式显示：仅在移动端（<768px）可见
  -->
  <nav
    class="mobile-nav"
    :class="{ 'mobile-nav--dark': isDark }"
    role="navigation"
    aria-label="移动端主导航"
  >
    <!-- 主菜单按钮（抽屉触发） -->
    <button
      class="mobile-nav__item"
      :class="{ 'mobile-nav__item--active': drawerOpen }"
      aria-label="打开菜单"
      @click="toggleDrawer"
    >
      <svg
        class="mobile-nav__icon"
        width="24"
        height="24"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <line x1="3" y1="6" x2="21" y2="6" />
        <line x1="3" y1="12" x2="21" y2="12" />
        <line x1="3" y1="18" x2="21" y2="18" />
      </svg>
      <span class="mobile-nav__label">菜单</span>
    </button>

    <!-- 导航项 -->
    <button
      v-for="item in navItems"
      :key="item.id"
      class="mobile-nav__item"
      :class="{ 'mobile-nav__item--active': item.id === activeId }"
      :aria-label="item.label"
      :aria-current="item.id === activeId ? 'page' : undefined"
      @click="handleNavClick(item)"
    >
      <component
        :is="item.icon"
        v-if="item.iconComponent"
        class="mobile-nav__icon"
        :size="24"
      />
      <svg
        v-else
        class="mobile-nav__icon"
        width="24"
        height="24"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path :d="item.svgPath" />
      </svg>
      <span class="mobile-nav__label">{{ item.label }}</span>
      <!-- 徽标 -->
      <span v-if="item.badge" class="mobile-nav__badge">{{ item.badge }}</span>
    </button>

    <!-- 更多按钮 -->
    <button
      v-if="moreItems.length > 0"
      class="mobile-nav__item"
      aria-label="更多选项"
      @click="showMoreDrawer = true"
    >
      <svg
        class="mobile-nav__icon"
        width="24"
        height="24"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <circle cx="12" cy="5" r="1" />
        <circle cx="12" cy="12" r="1" />
        <circle cx="12" cy="19" r="1" />
      </svg>
      <span class="mobile-nav__label">更多</span>
    </button>
  </nav>

  <!-- 抽屉式侧边菜单 -->
  <MobileDrawer
    v-model="drawerOpen"
    title="伏羲导航"
    placement="left"
    :width="drawerWidth"
    aria-label="主导航菜单"
  >
    <div class="drawer-menu">
      <!-- 用户信息 -->
      <div v-if="userInfo" class="drawer-menu__user">
        <el-avatar :size="48" :src="userInfo.avatar">
          {{ userInfo.display_name?.[0] || userInfo.username?.[0] || 'U' }}
        </el-avatar>
        <div class="drawer-menu__user-info">
          <span class="drawer-menu__user-name">
            {{ userInfo.display_name || userInfo.username || '用户' }}
          </span>
          <span class="drawer-menu__user-role">
            {{ userInfo.role === 'admin' ? '管理员' : '普通用户' }}
          </span>
        </div>
      </div>

      <!-- 导航分组 -->
      <div v-for="group in navGroups" :key="group.id" class="drawer-menu__group">
        <div class="drawer-menu__group-title">{{ group.label }}</div>
        <button
          v-for="subItem in group.items"
          :key="subItem.id"
          class="drawer-menu__item"
          :class="{ 'drawer-menu__item--active': subItem.id === activeId }"
          :aria-current="subItem.id === activeId ? 'page' : undefined"
          @click="handleDrawerItemClick(subItem)"
        >
          <component
            :is="subItem.icon"
            v-if="subItem.iconComponent"
            class="drawer-menu__item-icon"
            :size="20"
          />
          <span class="drawer-menu__item-label">{{ subItem.label }}</span>
          <span v-if="subItem.badge" class="drawer-menu__item-badge">{{ subItem.badge }}</span>
        </button>
      </div>
    </div>
  </MobileDrawer>

  <!-- 更多选项抽屉 -->
  <MobileDrawer
    v-if="moreItems.length > 0"
    v-model="showMoreDrawer"
    title="更多功能"
    placement="right"
    width="260px"
    aria-label="更多功能菜单"
  >
    <div class="drawer-menu">
      <div class="drawer-menu__group">
        <button
          v-for="item in moreItems"
          :key="item.id"
          class="drawer-menu__item"
          :class="{ 'drawer-menu__item--active': item.id === activeId }"
          @click="handleDrawerItemClick(item)"
        >
          <component
            :is="item.icon"
            v-if="item.iconComponent"
            class="drawer-menu__item-icon"
            :size="20"
          />
          <span class="drawer-menu__item-label">{{ item.label }}</span>
        </button>
      </div>
    </div>
  </MobileDrawer>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { useTheme } from '@/composables/useTheme';
import MobileDrawer from './MobileDrawer.vue';

// ============================
// 类型
// ============================

export interface MobileNavItem {
  id: string;
  label: string;
  route?: string;
  icon?: unknown;
  iconComponent?: unknown;
  svgPath?: string;
  badge?: string | number;
}

export interface NavGroup {
  id: string;
  label: string;
  items: MobileNavItem[];
}

// ============================
// Props & Emits
// ============================

const props = withDefaults(
  defineProps<{
    /** 底部导航栏项目（最多 4 个 + 菜单按钮） */
    navItems?: MobileNavItem[];
    /** 导航分组（抽屉菜单中显示） */
    navGroups?: NavGroup[];
    /** 更多菜单项 */
    moreItems?: MobileNavItem[];
    /** 当前激活项 */
    activeId?: string | null;
    /** 抽屉宽度 */
    drawerWidth?: string;
  }>(),
  {
    navItems: () => [],
    navGroups: () => [],
    moreItems: () => [],
    activeId: null,
    drawerWidth: '280px',
  },
);

const emit = defineEmits<{
  (e: 'navigate', item: MobileNavItem): void;
  (e: 'drawer-toggle', open: boolean): void;
}>();

// ============================
// Stores & Composables
// ============================

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();
const { isDark } = useTheme();

// ============================
// 状态
// ============================

const drawerOpen = ref(false);
const showMoreDrawer = ref(false);

const userInfo = computed(() => authStore.user);

// ============================
// 方法
// ============================

function toggleDrawer(): void {
  drawerOpen.value = !drawerOpen.value;
  emit('drawer-toggle', drawerOpen.value);
}

function handleNavClick(item: MobileNavItem): void {
  if (item.route) {
    router.push(item.route);
  }
  emit('navigate', item);
}

function handleDrawerItemClick(item: MobileNavItem): void {
  drawerOpen.value = false;
  showMoreDrawer.value = false;
  if (item.route) {
    router.push(item.route);
  }
  emit('navigate', item);
}
</script>

<style scoped lang="scss">
/* ============================
   底部导航栏
   ============================ */

.mobile-nav {
  display: flex;
  align-items: stretch;
  justify-content: space-around;
  height: 56px;
  background: var(--fuxi-bg-card, #ffffff);
  border-top: 1px solid var(--fuxi-border, #eeeeee);
  box-shadow: 0 -2px 12px rgba(0, 0, 0, 0.04);
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 90;
  padding: 0;
  /* 安全区域适配 (iOS) */
  padding-bottom: env(safe-area-inset-bottom, 0);

  &--dark {
    background: var(--fuxi-bg-card, #252542);
    border-top-color: var(--fuxi-border, #333355);
    box-shadow: 0 -2px 12px rgba(0, 0, 0, 0.2);
  }
}

/* ============================
   导航项
   ============================ */

.mobile-nav__item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  min-width: 0;
  padding: 4px 4px 2px;
  border: none;
  background: transparent;
  cursor: pointer;
  color: var(--fuxi-text-tertiary, #cccccc);
  transition: color 0.2s ease;
  position: relative;
  -webkit-tap-highlight-color: transparent;
  touch-action: manipulation;

  &:hover {
    color: var(--fuxi-text-secondary, #999999);
  }

  &:active {
    color: var(--fuxi-primary, #ff6700);
  }

  &--active {
    color: var(--fuxi-primary, #ff6700);

    .mobile-nav__label {
      font-weight: 600;
    }

    // 顶部微妙指示线
    &::before {
      content: '';
      position: absolute;
      top: 0;
      left: 25%;
      right: 25%;
      height: 2px;
      background: var(--fuxi-primary, #ff6700);
      border-radius: 0 0 1px 1px;
    }
  }
}

.mobile-nav__icon {
  flex-shrink: 0;
  margin-bottom: 2px;
}

.mobile-nav__label {
  font-size: 10px;
  font-weight: 500;
  line-height: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.mobile-nav__badge {
  position: absolute;
  top: 4px;
  right: calc(50% - 18px);
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  font-size: 10px;
  font-weight: 700;
  line-height: 16px;
  color: #fff;
  background: var(--fuxi-primary, #ff6700);
  border-radius: 8px;
  text-align: center;
}

/* ============================
   抽屉菜单
   ============================ */

.drawer-menu {
  padding: 0;
}

.drawer-menu__user {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 16px 16px;
  border-bottom: 1px solid var(--fuxi-border, #eeeeee);
  background: var(--fuxi-bg-subtle, #f0ede5);
}

.drawer-menu__user-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.drawer-menu__user-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--fuxi-text, #333333);
}

.drawer-menu__user-role {
  font-size: 12px;
  color: var(--fuxi-text-secondary, #999999);
}

.drawer-menu__group {
  padding: 4px 0;

  & + & {
    border-top: 1px solid var(--fuxi-border, #eeeeee);
  }
}

.drawer-menu__group-title {
  padding: 12px 16px 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--fuxi-text-tertiary, #cccccc);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.drawer-menu__item {
  display: flex;
  align-items: center;
  width: 100%;
  padding: 12px 16px;
  border: none;
  background: transparent;
  cursor: pointer;
  color: var(--fuxi-text, #333333);
  font-size: 15px;
  transition: background 0.15s ease;
  text-align: left;
  -webkit-tap-highlight-color: transparent;

  &:hover {
    background: var(--fuxi-bg-hover, #fffcf9);
  }

  &:active {
    background: var(--fuxi-bg-subtle, #f0ede5);
  }

  &--active {
    color: var(--fuxi-primary, #ff6700);
    font-weight: 600;
    background: var(--fuxi-primary-light, rgba(255, 103, 0, 0.08));
  }
}

.drawer-menu__item-icon {
  margin-right: 12px;
  flex-shrink: 0;
  color: var(--fuxi-text-secondary, #999999);

  .drawer-menu__item--active & {
    color: var(--fuxi-primary, #ff6700);
  }
}

.drawer-menu__item-label {
  flex: 1;
}

.drawer-menu__item-badge {
  font-size: 12px;
  font-weight: 600;
  color: var(--fuxi-primary, #ff6700);
  padding: 2px 8px;
  background: var(--fuxi-primary-light, rgba(255, 103, 0, 0.08));
  border-radius: 10px;
}

/* ============================
   响应式：仅在移动端显示
   ============================ */

.mobile-nav {
  display: none;

  @media (max-width: 767px) {
    display: flex;
  }
}
</style>
