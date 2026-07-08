<template>
  <aside class="app-sidebar" :class="{ collapsed }">
    <div class="sidebar-header">
      <div class="sidebar-brand">
        <div class="brand-logo">
          <svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2" />
            <path d="M12 6v6l4 2" />
          </svg>
        </div>
        <span v-show="!collapsed" class="brand-text">伏羲</span>
      </div>
      <el-button v-if="collapsible" class="collapse-btn" text @click="$emit('toggle')">
        <el-icon :size="16">
          <Fold v-if="!collapsed" />
          <Expand v-else />
        </el-icon>
      </el-button>
    </div>

    <nav class="sidebar-nav">
      <div
        v-for="group in menuGroups"
        v-show="group.items.length > 0"
        :key="group.title"
        class="nav-section"
      >
        <div v-show="!collapsed" class="nav-section-title">
          {{ group.title }}
        </div>
        <router-link
          v-for="item in group.items"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          :class="{ active: isActive(item.path) }"
          :title="collapsed ? item.label : ''"
        >
          <el-icon class="nav-icon"><component :is="item.icon" /></el-icon>
          <span v-show="!collapsed" class="nav-label">{{ item.label }}</span>
          <el-badge v-if="item.badge && !collapsed" :value="item.badge" class="nav-badge" />
        </router-link>
      </div>
    </nav>

    <div v-if="user" class="sidebar-footer" @click="$emit('logout')">
      <div class="footer-user">
        <div class="footer-avatar">
          {{ user.display_name?.charAt(0) || 'U' }}
        </div>
        <div v-show="!collapsed" class="footer-meta">
          <div class="footer-name">{{ user.display_name || user.username }}</div>
          <div class="footer-role">
            {{ user.role === 'admin' ? $t('sidebar.adminRole') : $t('sidebar.userRole') }}
          </div>
        </div>
        <el-icon v-show="!collapsed"><SwitchButton /></el-icon>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import { Fold, Expand, SwitchButton } from '@element-plus/icons-vue';
import type { UserInfo } from '@/types';

const props = defineProps<{
  collapsed?: boolean;
  collapsible?: boolean;
  user?: UserInfo | null;
  isAdmin?: boolean;
}>();

defineEmits<{
  toggle: [];
  logout: [];
}>();

const route = useRoute();

interface MenuItem {
  path: string;
  label: string;
  icon: string;
  badge?: number;
}

interface MenuGroup {
  title: string;
  items: MenuItem[];
}

const menuGroups = computed<MenuGroup[]>(() => {
  const groups: MenuGroup[] = [
    {
      title: '知识服务',
      items: [
        { path: '/', label: '智能对话', icon: 'ChatDotRound' },
        { path: '/chat', label: 'AI 对话', icon: 'ChatLineSquare' },
        { path: '/knowledge', label: '知识库', icon: 'Collection' },
        { path: '/search', label: '知识搜索', icon: 'Search' },
        { path: '/files', label: '文件管理', icon: 'Folder' },
        { path: '/wiki', label: '企业 Wiki', icon: 'Reading' },
      ],
    },
  ];

  if (props.isAdmin) {
    groups.push({
      title: '系统管理',
      items: [{ path: '/admin', label: '管理面板', icon: 'Setting' }],
    });
  }

  return groups;
});

function isActive(path: string): boolean {
  if (path === '/') {
    return route.path === '/';
  }
  return route.path.startsWith(path);
}
</script>

<style scoped lang="scss">
// 侧边栏使用固定的深色主题，不随亮/暗切换变化
// 但使用 CSS 变量中暗色主题的色调以获得统一感
.app-sidebar {
  width: 240px;
  background: linear-gradient(180deg, #1A1A2E 0%, #222236 100%); // 阴模式底板渐变 (was #1a1a2e→#16213e)
  color: white;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  transition: width 0.3s ease;
  overflow: hidden;

  &.collapsed {
    width: 64px;
  }
}

.sidebar-header {
  padding: 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand-logo {
  width: 28px;
  height: 28px;
  background: linear-gradient(135deg, #FF6700 0%, #E55A00 100%); // 暖橙渐变 (was #667eea→#764ba2)
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;

  svg {
    width: 16px;
    height: 16px;
  }
}

.brand-text {
  font-size: 18px;
  font-weight: 700;
  white-space: nowrap;
}

.collapse-btn {
  color: rgba(255, 255, 255, 0.5);

  &:hover {
    color: white;
  }
}

.sidebar-nav {
  flex: 1;
  padding: 12px 0;
  overflow-y: auto;
  overflow-x: hidden;
}

.nav-section {
  margin-bottom: 20px;
}

.nav-section-title {
  padding: 0 16px;
  margin-bottom: 6px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.4);
  text-transform: uppercase;
  letter-spacing: 1px;
  white-space: nowrap;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  color: rgba(255, 255, 255, 0.65);
  text-decoration: none;
  transition: all 0.2s ease;
  white-space: nowrap;
  position: relative;

  &:hover {
    background: rgba(255, 255, 255, 0.08);
    color: white;
  }

  &.active {
    background: rgba(255, 255, 255, 0.12);
    color: white;
    border-right: 3px solid var(--fuxi-primary, #FF6700); // 暖橙点缀 (was #667eea)
  }

  .nav-icon {
    font-size: 18px;
    flex-shrink: 0;
  }

  .nav-label {
    font-size: 14px;
  }
}

.nav-badge {
  margin-left: auto;
}

.sidebar-footer {
  padding: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  cursor: pointer;
  transition: background 0.2s;

  &:hover {
    background: rgba(255, 255, 255, 0.08);
  }
}

.footer-user {
  display: flex;
  align-items: center;
  gap: 10px;
}

.footer-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, #FF6700 0%, #E55A00 100%); // 暖橙渐变 (was #667eea→#764ba2)
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 12px;
  flex-shrink: 0;
}

.footer-meta {
  flex: 1;
  min-width: 0;

  .footer-name {
    font-size: 13px;
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .footer-role {
    font-size: 11px;
    color: rgba(255, 255, 255, 0.45);
  }
}

// 响应式
@media (max-width: 768px) {
  .app-sidebar {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    z-index: 200;
    transform: translateX(-100%);
    transition: transform 0.3s ease;

    &.collapsed {
      transform: translateX(0);
      width: 240px;
    }
  }
}
</style>
