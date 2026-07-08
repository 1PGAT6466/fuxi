<template>
  <header class="app-header">
    <div class="header-left">
      <!-- 移动端菜单切换按钮 -->
      <el-button v-if="showMenuToggle" class="menu-toggle" text @click="$emit('toggleSidebar')">
        <el-icon :size="20"><Expand v-if="sidebarCollapsed" /><Fold v-else /></el-icon>
      </el-button>

      <div v-if="showBrand" class="header-brand">
        <div class="brand-logo">
          <svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2" />
            <path d="M12 6v6l4 2" />
          </svg>
        </div>
        <span class="brand-text">伏羲</span>
      </div>

      <h1 class="header-title">{{ title }}</h1>
    </div>

    <div class="header-right">
      <!-- 系统状态指示器 -->
      <div v-if="showStatus" class="header-status">
        <span class="status-dot" :class="{ online: systemOnline }" />
        <span class="status-text">{{
          systemOnline ? $t('layout.systemNormal') : $t('layout.systemAbnormal')
        }}</span>
      </div>

      <!-- 操作区插槽（主题切换按钮等） -->
      <slot name="actions" />

      <!-- 用户信息 -->
      <el-dropdown v-if="user" trigger="click" @command="handleCommand">
        <div class="user-dropdown-trigger">
          <div class="user-avatar-sm">
            {{ user.display_name?.charAt(0) || 'U' }}
          </div>
          <span class="user-name">{{ user.display_name || user.username }}</span>
          <el-icon><ArrowDown /></el-icon>
        </div>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item disabled>
              <div class="dropdown-user-info">
                <div class="dropdown-avatar">
                  {{ user.display_name?.charAt(0) || 'U' }}
                </div>
                <div>
                  <div class="dropdown-name">{{ user.display_name || user.username }}</div>
                  <div class="dropdown-role">
                    {{ user.role === 'admin' ? $t('layout.adminRole') : $t('layout.normalRole') }}
                  </div>
                </div>
              </div>
            </el-dropdown-item>
            <el-dropdown-item divided command="profile">
              <el-icon><User /></el-icon> {{ $t('layout.profile') }}
            </el-dropdown-item>
            <el-dropdown-item command="settings">
              <el-icon><Setting /></el-icon> {{ $t('layout.settings') }}
            </el-dropdown-item>
            <el-dropdown-item divided command="logout">
              <el-icon><SwitchButton /></el-icon> {{ $t('layout.logout') }}
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </header>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import { Expand, Fold, ArrowDown, User, Setting, SwitchButton } from '@element-plus/icons-vue';
import apiClient from '@/api';
import type { UserInfo } from '@/types';

defineProps<{
  title?: string;
  user?: UserInfo | null;
  showBrand?: boolean;
  showStatus?: boolean;
  showMenuToggle?: boolean;
  sidebarCollapsed?: boolean;
}>();

const emit = defineEmits<{
  toggleSidebar: [];
  command: [command: string];
  logout: [];
}>();

const systemOnline = ref<boolean>(true);
let healthInterval: ReturnType<typeof setInterval> | null = null;

const HEALTH_CHECK_INTERVAL: number = Number(import.meta.env.VITE_ADMIN_REFRESH_INTERVAL) || 30000;

// 定期检查系统健康状态
onMounted(() => {
  checkHealth();

  healthInterval = setInterval(async () => {
    try {
      await apiClient.get('/api/health');
      systemOnline.value = true;
    } catch {
      systemOnline.value = false;
    }
  }, HEALTH_CHECK_INTERVAL);
});

onUnmounted(() => {
  if (healthInterval) {
    clearInterval(healthInterval);
    healthInterval = null;
  }
});

async function checkHealth(): Promise<void> {
  try {
    await apiClient.get('/api/health');
    systemOnline.value = true;
  } catch {
    systemOnline.value = false;
  }
}

function handleCommand(command: string): void {
  if (command === 'logout') {
    emit('logout');
  } else {
    emit('command', command);
  }
}
</script>

<style scoped lang="scss">
.app-header {
  height: 60px;
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  flex-shrink: 0;
  z-index: 100;
  transition:
    background-color 0.3s ease,
    border-color 0.3s ease;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.menu-toggle {
  display: none;
}

.header-brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand-logo {
  width: 32px;
  height: 32px;
  background: linear-gradient(135deg, #FF6700 0%, #E55A00 100%); // 暖橙渐变 (was #667eea→#764ba2)
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;

  svg {
    width: 20px;
    height: 20px;
  }
}

.brand-text {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

.header-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-status {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-secondary);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-danger);

  &.online {
    background: var(--color-success);
  }
}

// 用户下拉
.user-dropdown-trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 8px;
  transition: background 0.2s;

  &:hover {
    background: var(--component-hover);
  }
}

.user-avatar-sm {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, #FF6700 0%, #E55A00 100%); // 暖橙渐变 (was #667eea→#764ba2)
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 600;
  font-size: 13px;
}

.user-name {
  font-size: 14px;
  color: var(--text-primary);
}

.dropdown-user-info {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 4px 0;
}

.dropdown-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, #FF6700 0%, #E55A00 100%); // 暖橙渐变 (was #667eea→#764ba2)
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 600;
  font-size: 16px;
}

.dropdown-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.dropdown-role {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: 2px;
}

// 响应式
@media (max-width: 768px) {
  .app-header {
    padding: 0 16px;
  }

  .menu-toggle {
    display: inline-flex;
  }

  .status-text {
    display: none;
  }
}
</style>
