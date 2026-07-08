<template>
  <div class="admin-container">
    <!-- 管理摘要卡片 -->
    <div class="admin-summary">
      <div class="admin-summary__card">
        <div class="admin-summary__icon admin-summary__icon--system">
          <el-icon :size="22"><Monitor /></el-icon>
        </div>
        <div class="admin-summary__body">
          <span class="admin-summary__value">系统运行中</span>
          <span class="admin-summary__label">系统状态</span>
        </div>
      </div>
      <div class="admin-summary__card">
        <div class="admin-summary__icon admin-summary__icon--users">
          <el-icon :size="22"><User /></el-icon>
        </div>
        <div class="admin-summary__body">
          <span class="admin-summary__value">用户管理</span>
          <span class="admin-summary__label">添加 · 编辑 · 权限</span>
        </div>
      </div>
      <div class="admin-summary__card">
        <div class="admin-summary__icon admin-summary__icon--eval">
          <el-icon :size="22"><DataAnalysis /></el-icon>
        </div>
        <div class="admin-summary__body">
          <span class="admin-summary__value">评测报告</span>
          <span class="admin-summary__label">RAG 质量追踪</span>
        </div>
      </div>
      <div class="admin-summary__card">
        <div class="admin-summary__icon admin-summary__icon--toggle">
          <el-icon :size="22"><Switch /></el-icon>
        </div>
        <div class="admin-summary__body">
          <span class="admin-summary__value">功能开关</span>
          <span class="admin-summary__label">模块启用/禁用</span>
        </div>
      </div>
    </div>

    <!-- 功能开关快速面板 -->
    <section class="admin-toggles">
      <h3 class="admin-toggles__title">
        <el-icon><Switch /></el-icon>
        功能开关
      </h3>
      <div class="admin-toggles__grid">
        <div v-for="feature in featureToggles" :key="feature.key" class="admin-toggles__item">
          <div class="admin-toggles__item-info">
            <span class="admin-toggles__item-name">{{ feature.name }}</span>
            <span class="admin-toggles__item-desc">{{ feature.desc }}</span>
          </div>
          <el-switch
            v-model="feature.enabled"
            :active-color="feature.activeColor || '#34C759'"
            @change="(val: boolean | string | number) => handleToggle(feature.key, val)"
          />
        </div>
      </div>
    </section>

    <!-- 详细管理 Tabs（复用现有组件） -->
    <el-tabs v-model="activeTab" class="admin-tabs">
      <el-tab-pane :label="$t('admin.tabs.status')" name="status">
        <SystemStatus />
      </el-tab-pane>
      <el-tab-pane :label="$t('admin.tabs.evaluation')" name="evaluation">
        <EvaluationPanel />
      </el-tab-pane>
      <el-tab-pane :label="$t('admin.tabs.knowledge')" name="knowledge">
        <KnowledgePanel />
      </el-tab-pane>
      <el-tab-pane :label="$t('admin.tabs.users')" name="users">
        <UserPanel />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue';
import { ElMessage } from 'element-plus';
import { Monitor, User, DataAnalysis, Switch } from '@element-plus/icons-vue';
import SystemStatus from '@/components/admin/SystemStatus.vue';
import EvaluationPanel from '@/components/admin/EvaluationPanel.vue';
import KnowledgePanel from '@/components/admin/KnowledgePanel.vue';
import UserPanel from '@/components/admin/UserPanel.vue';

const activeTab = ref<string>('status');

// ────── 功能开关 ──────
interface FeatureToggle {
  key: string;
  name: string;
  desc: string;
  enabled: boolean;
  activeColor?: string;
}

const featureToggles = reactive<FeatureToggle[]>([
  {
    key: 'chat_v2',
    name: 'AI 对话 v2',
    desc: '启用新版对话引擎，支持多轮上下文记忆',
    enabled: true,
    activeColor: '#FF6700', // 暖橙点缀主色 (was #667eea)
  },
  {
    key: 'search_semantic',
    name: '语义搜索',
    desc: '启用向量语义搜索，结果更精准',
    enabled: true,
    activeColor: '#34C759', // 绿色成功色
  },
  {
    key: 'auto_index',
    name: '自动索引',
    desc: '上传文档后自动触发向量化索引',
    enabled: true,
    activeColor: '#FF6700', // 暖橙点缀色 (was #FF9500)
  },
  {
    key: 'wiki_public',
    name: '公开 Wiki',
    desc: '允许所有用户创建和编辑 Wiki 页面',
    enabled: false,
  },
  {
    key: 'eval_auto',
    name: '自动评测',
    desc: '每日定时运行 RAG 质量评测并生成报告',
    enabled: false,
  },
  {
    key: 'rate_limit',
    name: '速率限制',
    desc: '启用 API 请求速率限制，防止滥用',
    enabled: true,
  },
]);

function handleToggle(key: string): void {
  const feature = featureToggles.find((f) => f.key === key);
  if (feature) {
    ElMessage.success(`「${feature.name}」已${feature.enabled ? '启用' : '禁用'}`);
  }
}

defineExpose({ activeTab, featureToggles });
</script>

<style scoped lang="scss">
.admin-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 28px 24px;
  color: var(--text-primary);
}

/* ────── 摘要卡片 ────── */
.admin-summary {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 28px;
}

.admin-summary__card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 20px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  transition:
    transform var(--duration-normal) var(--ease-out),
    box-shadow var(--duration-normal) var(--ease-out);
}

.admin-summary__card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.admin-summary__icon {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.admin-summary__icon--system {
  background: var(--brand-soft);
  color: var(--brand);
}

.admin-summary__icon--users {
  background: var(--qian-color-light);
  color: var(--qian-color);
}

.admin-summary__icon--eval {
  background: var(--xun-color-light);
  color: var(--xun-color);
}

.admin-summary__icon--toggle {
  background: var(--li-color-light);
  color: var(--li-color);
}

.admin-summary__body {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.admin-summary__value {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.3;
}

.admin-summary__label {
  font-size: 12px;
  color: var(--text-tertiary);
}

/* ────── 功能开关 ────── */
.admin-toggles {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  padding: 20px 24px;
  margin-bottom: 28px;
}

.admin-toggles__title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 16px;
}

.admin-toggles__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}

.admin-toggles__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--bg-subtle);
  border-radius: var(--radius-sm);
  transition: background var(--duration-fast) var(--ease-out);
}

.admin-toggles__item:hover {
  background: var(--bg-hover);
}

.admin-toggles__item-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
  margin-right: 12px;
}

.admin-toggles__item-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.admin-toggles__item-desc {
  font-size: 12px;
  color: var(--text-tertiary);
  line-height: 1.4;
}

/* ────── Tabs ────── */
.admin-tabs {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  padding: 4px 20px 20px;
}

/* ────── 响应式 ────── */
@media (max-width: 1023px) {
  .admin-summary {
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }
}

@media (max-width: 767px) {
  .admin-container {
    padding: 16px 12px;
  }

  .admin-summary {
    grid-template-columns: 1fr;
    gap: 10px;
  }

  .admin-toggles__grid {
    grid-template-columns: 1fr;
  }

  .admin-tabs {
    padding: 4px 12px 16px;
  }
}
</style>
