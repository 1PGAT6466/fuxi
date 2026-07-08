<template>
  <!--
    伏羲 v2.1 — 数据分析窗口
    布局：顶部统计卡片行 + 下方图表区（可切换 Tab）
  -->
  <div class="data-analytics-page">
    <!-- 页面头 -->
    <div class="page-header">
      <div class="header-top">
        <el-icon :size="24" class="header-icon"><DataAnalysis /></el-icon>
        <h2 class="header-title">数据分析</h2>
      </div>
      <p class="header-desc">实时数据看板 · 趋势分析 · 报表生成 · 数据导出</p>
    </div>

    <!-- 加载态 -->
    <div v-if="loading" class="page-loading">
      <el-skeleton :rows="6" animated />
    </div>

    <!-- 错误态 -->
    <div v-else-if="error" class="page-error">
      <el-result icon="error" title="加载失败">
        <template #extra>
          <el-button type="primary" size="small" @click="loadPageData">重试</el-button>
        </template>
      </el-result>
    </div>

    <!-- 空态 -->
    <div v-else-if="isEmpty" class="page-empty">
      <el-empty description="暂无分析数据" />
    </div>

    <!-- 正常内容 -->
    <template v-else>
      <!-- 统计卡片行 -->
      <div v-if="statsLoading" class="stats-loading">
        <el-skeleton :rows="2" animated />
      </div>
      <div v-else-if="statsError" class="stats-error">
        <el-result icon="error" title="数据加载失败" sub-title="无法获取统计数据">
          <template #extra>
            <el-button type="primary" size="small" @click="loadStats">重试</el-button>
          </template>
        </el-result>
      </div>
      <div v-else-if="statsData.length === 0" class="stats-empty">
        <el-empty description="暂无统计数据" />
      </div>
      <StatsOverview v-else :stats="statsData" />

      <!-- 图表区 Tab 切换 -->
      <div class="tab-panel">
        <el-tabs v-model="activeTab" class="analytics-tabs">
          <el-tab-pane label="趋势分析" name="trends">
            <TrendChart />
          </el-tab-pane>
          <el-tab-pane label="存储分布" name="storage">
            <StorageDistribution />
          </el-tab-pane>
          <el-tab-pane label="报表生成" name="report">
            <ReportPanel @export="handleReportExport" />
          </el-tab-pane>
        </el-tabs>
      </div>

      <!-- 导出弹窗 -->
      <ExportDialog
        v-model="showExportDialog"
        :default-format="exportFormat"
        @exported="handleExported"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import { DataAnalysis } from '@element-plus/icons-vue';
import StatsOverview from './StatsOverview.vue';
import TrendChart from './TrendChart.vue';
import StorageDistribution from './StorageDistribution.vue';
import ReportPanel from './ReportPanel.vue';
import ExportDialog from './ExportDialog.vue';
import * as analyticsApi from './api';
import { useDataAnalyticsStore } from './store';
import type { StatItem, ExportFormat } from './types';

const store = useDataAnalyticsStore();

// ───── 页面级状态 ─────
const loading = ref(false);
const error = ref(false);
const isEmpty = ref(false);

// 统计区块状态
const statsData = ref<StatItem[]>([]);
const statsLoading = ref(false);
const statsError = ref(false);
const activeTab = ref('trends');
const showExportDialog = ref(false);
const exportFormat = ref<ExportFormat>('csv');

// ───── 页面级数据加载 ─────
async function loadPageData() {
  loading.value = true;
  error.value = false;
  isEmpty.value = false;
  try {
    const res = await analyticsApi.getStats();
    store.setStatsCache(res);
    if (!res.stats || res.stats.length === 0) {
      isEmpty.value = true;
    } else {
      statsData.value = res.stats;
    }
  } catch {
    error.value = true;
    console.warn('[DataAnalyticsPage] 页面数据加载失败');
  } finally {
    loading.value = false;
  }
}

// 加载统计数据（已有缓存可用时直接使用）
async function loadStats() {
  // 优先使用缓存
  if (store.isStatsCacheValid && store.statsCache) {
    statsData.value = store.statsCache.stats;
    return;
  }

  statsLoading.value = true;
  statsError.value = false;
  try {
    const res = await analyticsApi.getStats();
    store.setStatsCache(res);
    statsData.value = res.stats;
  } catch {
    statsError.value = true;
    console.warn('[DataAnalyticsPage] 加载统计数据失败');
  } finally {
    statsLoading.value = false;
  }
}

// 报表导出按钮回调
function handleReportExport(format: 'pdf' | 'excel') {
  if (format === 'pdf') {
    ElMessage.info('PDF 导出功能开发中，请使用 Excel 导出');
    return;
  }
  exportFormat.value = 'excel';
  showExportDialog.value = true;
}

// 导出完成回调
function handleExported() {
  // 导出已由 ExportDialog 处理
}

onMounted(() => {
  loadPageData();
});
</script>

<style scoped lang="scss">
.data-analytics-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 28px 24px;
  height: 100%;
  overflow-y: auto;

  @media (max-width: 767px) {
    padding: 16px;
  }

  &::-webkit-scrollbar {
    width: 6px;
  }

  &::-webkit-scrollbar-thumb {
    background: var(--fuxi-border);
    border-radius: 3px;
  }
}

.page-header {
  margin-bottom: var(--space-lg);

  .header-top {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    margin-bottom: 6px;

    .header-icon {
      color: var(--li-color);
    }

    .header-title {
      margin: 0;
      font-size: 24px;
      font-weight: 700;
      color: var(--fuxi-text);
    }
  }

  .header-desc {
    margin: 0;
    font-size: var(--font-size-caption);
    color: var(--fuxi-text-secondary);
    padding-left: 34px;
  }
}

.stats-loading {
  padding: var(--space-lg);
  margin-bottom: var(--space-lg);
}

.stats-error {
  padding: var(--space-lg);
  margin-bottom: var(--space-lg);
  background: var(--fuxi-bg-card);
  border-radius: var(--fuxi-radius);
}

.stats-empty {
  padding: var(--space-lg);
  margin-bottom: var(--space-lg);
}

/* ───────── 页面级状态容器 ───────── */
.page-loading {
  padding: var(--space-lg);
  margin-bottom: var(--space-lg);
  background: var(--fuxi-bg-card);
  border-radius: var(--fuxi-radius);
  min-height: 300px;
  display: flex;
  align-items: center;
}

.page-error {
  padding: var(--space-lg);
  margin-bottom: var(--space-lg);
  background: var(--fuxi-bg-card);
  border-radius: var(--fuxi-radius);
  min-height: 300px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.page-empty {
  padding: var(--space-lg);
  margin-bottom: var(--space-lg);
  background: var(--fuxi-bg-card);
  border-radius: var(--fuxi-radius);
  min-height: 300px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.tab-panel {
  :deep(.el-tabs__nav-wrap::after) {
    height: 1px;
    background-color: var(--fuxi-border);
  }

  :deep(.el-tabs__item) {
    font-size: var(--font-size-caption);
    font-weight: 500;
    color: var(--fuxi-text-secondary);

    &.is-active {
      color: var(--fuxi-primary);
      font-weight: 600;
    }
  }

  :deep(.el-tabs__active-bar) {
    background-color: var(--fuxi-primary);
  }

  :deep(.el-tab-pane) {
    padding-top: var(--space-md);
  }
}
</style>
