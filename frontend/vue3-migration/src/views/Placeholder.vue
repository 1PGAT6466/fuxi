<!--
  伏羲 v2.1 — 占位页面
  用于 /profile /settings /about 等功能规划中的路由
-->
<template>
  <div class="placeholder-page">
    <div class="placeholder-card">
      <div class="placeholder-icon">
        <div class="bagua-ring">
          <span class="bagua-core">☰</span>
        </div>
      </div>
      <h2 class="placeholder-title">{{ pageTitle }}</h2>
      <p class="placeholder-desc">{{ pageDesc }}</p>
      <div class="placeholder-status">
        <el-tag type="warning" size="large" effect="plain">
          <el-icon><Clock /></el-icon>
          功能开发中
        </el-tag>
      </div>
      <p class="placeholder-hint">
        此功能正在规划与开发中，敬请期待。
        <br />
        如需帮助，请通过 AI 对话或联系管理员。
      </p>
      <div class="placeholder-actions">
        <el-button type="primary" @click="$router.push('/')">
          <el-icon><HomeFilled /></el-icon>
          返回首页
        </el-button>
        <el-button @click="$router.back()">
          <el-icon><Back /></el-icon>
          返回上页
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import { Clock, HomeFilled, Back } from '@element-plus/icons-vue';

const route = useRoute();

const PAGE_CONFIG: Record<string, { title: string; desc: string }> = {
  Profile: { title: '个人中心', desc: '管理您的账户信息、偏好设置与操作历史' },
  Settings: { title: '系统设置', desc: '配置应用主题、通知偏好与集成选项' },
  About: { title: '关于伏羲', desc: '了解伏羲系统的版本信息、技术架构与团队' },
};

const pageTitle = computed(() => PAGE_CONFIG[route.name as string]?.title || '页面');
const pageDesc = computed(() => PAGE_CONFIG[route.name as string]?.desc || '此功能正在开发中');
</script>

<style scoped lang="scss">
.placeholder-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100%;
  padding: 40px 20px;
  background: var(--fuxi-bg);
}

.placeholder-card {
  text-align: center;
  max-width: 420px;
  width: 100%;
  padding: 48px 32px;
  background: var(--fuxi-bg-card);
  border-radius: var(--radius-lg);
  box-shadow: var(--fuxi-shadow);
  border: 1px solid var(--fuxi-border);
}

.placeholder-icon {
  margin-bottom: 20px;
}

.bagua-ring {
  width: 72px;
  height: 72px;
  margin: 0 auto;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--fuxi-primary-light), var(--qian-color-light));
  display: flex;
  align-items: center;
  justify-content: center;

  .bagua-core {
    font-size: 28px;
    color: var(--fuxi-primary);
  }
}

.placeholder-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--fuxi-text);
  margin: 0 0 8px;
}

.placeholder-desc {
  font-size: 14px;
  color: var(--fuxi-text-secondary);
  margin: 0 0 24px;
  line-height: 1.6;
}

.placeholder-status {
  margin-bottom: 20px;
}

.placeholder-hint {
  font-size: 13px;
  color: var(--fuxi-text-tertiary);
  line-height: 1.8;
  margin: 0 0 28px;
}

.placeholder-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  flex-wrap: wrap;
}

@media (max-width: 480px) {
  .placeholder-card {
    padding: 32px 20px;
  }

  .placeholder-actions {
    flex-direction: column;
  }
}
</style>
