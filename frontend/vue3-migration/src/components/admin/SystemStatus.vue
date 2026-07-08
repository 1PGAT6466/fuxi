<template>
  <div class="system-status">
    <el-row :gutter="20">
      <el-col v-for="card in statusCards" :key="card.title" :xs="24" :sm="12" :md="12" :lg="6">
        <el-card class="status-card">
          <template #header>
            <div class="card-header">
              <span>{{ card.title }}</span>
              <el-tag :type="card.tagType" size="small">{{ card.tagText }}</el-tag>
            </div>
          </template>
          <div v-for="item in card.items" :key="item.label" class="status-item">
            <span class="label">{{ item.label }}</span>
            <span class="value">{{ item.value }}</span>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import apiClient from '@/api';

interface SystemStatusData {
  type: string;
  text: string;
  uptime: string;
  cpu: number;
  memory: number;
}

interface KnowledgeStatsData {
  documents: number;
  vectors: number;
  storage: string;
}

interface ApiStatsData {
  totalRequests: number;
  avgResponse: number;
  errorRate: number;
}

interface UserStatsData {
  total: number;
  online: number;
  todayQueries: number;
}

interface StatusCardItem {
  label: string;
  value: string | number;
}

interface StatusCard {
  title: string;
  tagType: string;
  tagText: string;
  items: StatusCardItem[];
}

const systemStatus = ref<SystemStatusData>({
  type: 'success',
  text: '正常',
  uptime: '0天 0小时',
  cpu: 0,
  memory: 0,
});

const knowledgeStats = ref<KnowledgeStatsData>({
  documents: 0,
  vectors: 0,
  storage: '0 MB',
});

const apiStats = ref<ApiStatsData>({
  totalRequests: 0,
  avgResponse: 0,
  errorRate: 0,
});

const userStats = ref<UserStatsData>({
  total: 0,
  online: 0,
  todayQueries: 0,
});

// 用 computed 生成响应式卡片数据
const statusCards = computed<StatusCard[]>(() => [
  {
    title: '系统状态',
    tagType: systemStatus.value.type === 'success' ? 'success' : 'danger',
    tagText: systemStatus.value.text || '正常',
    items: [
      { label: '运行时间', value: systemStatus.value.uptime },
      { label: 'CPU', value: `${systemStatus.value.cpu}%` },
      { label: '内存', value: `${systemStatus.value.memory}%` },
    ],
  },
  {
    title: '知识库',
    tagType: 'success',
    tagText: '正常',
    items: [
      { label: '文档数', value: knowledgeStats.value.documents },
      { label: '向量数', value: knowledgeStats.value.vectors },
      { label: '存储', value: knowledgeStats.value.storage },
    ],
  },
  {
    title: 'API 统计',
    tagType: apiStats.value.errorRate > 1 ? 'warning' : 'success',
    tagText: apiStats.value.errorRate > 1 ? '告警' : '正常',
    items: [
      { label: '总请求', value: apiStats.value.totalRequests },
      { label: '平均响应', value: `${apiStats.value.avgResponse}ms` },
      { label: '错误率', value: `${apiStats.value.errorRate}%` },
    ],
  },
  {
    title: '用户统计',
    tagType: 'info',
    tagText: '活跃',
    items: [
      { label: '总用户', value: userStats.value.total },
      { label: '在线', value: userStats.value.online },
      { label: '今日查询', value: userStats.value.todayQueries },
    ],
  },
]);

let refreshInterval: ReturnType<typeof setInterval> | null = null;

onMounted(async () => {
  await fetchStatus();
  // 每 30 秒自动刷新
  refreshInterval = setInterval(fetchStatus, 30_000);
});

onUnmounted(() => {
  if (refreshInterval) clearInterval(refreshInterval);
});

async function fetchStatus(): Promise<void> {
  try {
    const data = await apiClient.get('/api/admin/status');
    systemStatus.value = data.system || systemStatus.value;
    knowledgeStats.value = data.knowledge || knowledgeStats.value;
    apiStats.value = data.api || apiStats.value;
    userStats.value = data.users || userStats.value;
  } catch (error) {
    console.error('获取系统状态失败:', error);
  }
}
</script>

<style scoped lang="scss">
.system-status {
  padding: 20px;
}

.status-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.status-item {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid var(--border-color-light);
  transition: border-color 0.3s ease;

  &:last-child {
    border-bottom: none;
  }

  .label {
    color: var(--text-secondary);
    font-size: 14px;
  }

  .value {
    font-weight: 600;
    color: var(--text-primary);
  }
}
</style>
