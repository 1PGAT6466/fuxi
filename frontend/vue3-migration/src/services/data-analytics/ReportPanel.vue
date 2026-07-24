<template>
  <!--
    伏羲 v2.1 — 报表生成面板
    选择报表类型 + 时间范围 + 选择维度 → 生成预览 → 导出按钮
  -->
  <div class="report-panel">
    <div class="report-header">
      <h3 class="report-title">报表生成</h3>
    </div>

    <!-- 表单区 -->
    <div class="report-form">
      <div class="form-row">
        <label class="form-label">报表类型</label>
        <el-radio-group v-model="reportType">
          <el-radio-button value="summary">摘要报表</el-radio-button>
          <el-radio-button value="detailed">详细报表</el-radio-button>
        </el-radio-group>
      </div>

      <div class="form-row">
        <label class="form-label">时间范围</label>
        <el-select v-model="reportPeriod" style="width: 160px">
          <el-option label="最近 7 天" value="7d" />
          <el-option label="最近 30 天" value="30d" />
          <el-option label="最近 90 天" value="90d" />
          <el-option label="最近 1 年" value="1y" />
        </el-select>
      </div>

      <div class="form-row">
        <label class="form-label">分析维度</label>
        <el-checkbox-group v-model="selectedDimensions">
          <el-checkbox value="queries" label="查询分析" />
          <el-checkbox value="documents" label="文档分析" />
          <el-checkbox value="users" label="用户分析" />
          <el-checkbox value="storage" label="存储分析" />
          <el-checkbox value="vectors" label="向量分析" />
        </el-checkbox-group>
      </div>

      <div class="form-row">
        <el-button
          type="primary"
          :loading="generating"
          :disabled="!selectedDimensions.length"
          @click="handleGenerate"
        >
          <el-icon><DataAnalysis /></el-icon>
          生成报表
        </el-button>
      </div>
    </div>

    <!-- 报表加载中 -->
    <div v-if="generating" class="report-generating">
      <el-skeleton :rows="4" animated />
      <p class="generating-text">正在生成报表...</p>
    </div>

    <!-- 报表错误 -->
    <div v-else-if="reportError" class="report-error">
      <el-result icon="error" title="生成失败" sub-title="报表生成失败，请重试">
        <template #extra>
          <el-button type="primary" size="small" @click="handleGenerate">重试</el-button>
        </template>
      </el-result>
    </div>

    <!-- 报表预览区 -->
    <div v-else-if="report" class="report-result">
      <div class="report-result__header">
        <div class="report-meta">
          <h4 class="report-result__title">{{ report.title }}</h4>
          <span class="report-result__time">
            生成时间：{{ new Date(report.generated_at).toLocaleString('zh-CN') }}
          </span>
        </div>
        <div class="report-actions">
          <el-button type="primary" size="small" @click="$emit('export', 'pdf')">
            <el-icon><Printer /></el-icon>
            导出 PDF
          </el-button>
          <el-button size="small" @click="$emit('export', 'excel')">
            <el-icon><Download /></el-icon>
            导出 Excel
          </el-button>
          <el-divider direction="vertical" />
          <el-button size="small" type="success" plain @click="handleShare">
            <el-icon><Share /></el-icon>
            分享
          </el-button>
        </div>
      </div>

      <div class="report-sections">
        <div v-for="(section, si) in report.sections" :key="si" class="report-section">
          <h5 class="report-section__title">{{ section.title }}</h5>
          <p class="report-section__content">{{ section.content }}</p>
          <div v-if="section.metrics" class="report-section__metrics">
            <div v-for="(val, key) in section.metrics" :key="key" class="metric-item">
              <span class="metric-label">{{ getMetricLabel(key as string) }}</span>
              <span class="metric-value">{{ typeof val === 'number' ? val.toFixed(1) : val }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { ElMessage } from 'element-plus';
import { DataAnalysis, Printer, Download, Share } from '@element-plus/icons-vue';
import * as analyticsApi from './api';
import { useDataAnalyticsStore } from './store';
import type { ReportResponse, ReportType, ReportDimension } from './types';

const emit = defineEmits<{
  (e: 'export', format: 'pdf' | 'excel'): void;
  (e: 'share', reportId: string): void;
}>();

const store = useDataAnalyticsStore();

const reportType = ref<ReportType>('summary');
const reportPeriod = ref('30d');
const selectedDimensions = ref<ReportDimension[]>(
  (store.lastReportDimensions as ReportDimension[]) || ['queries', 'documents', 'users'],
);
const generating = ref(false);
const reportError = ref(false);
const report = ref<ReportResponse | null>(null);

function getMetricLabel(key: string): string {
  const labels: Record<string, string> = {
    avg_value: '均值',
    peak_value: '峰值',
    growth_rate: '增长率(%)',
  };
  return labels[key] || key;
}

async function handleGenerate() {
  if (!selectedDimensions.value.length) {
    ElMessage.warning('请至少选择一个分析维度');
    return;
  }

  generating.value = true;
  reportError.value = false;
  report.value = null;
  store.setReportDimensions(selectedDimensions.value as string[]);

  try {
    const res = await analyticsApi.getReport({
      type: reportType.value,
      period: reportPeriod.value,
      dimensions: selectedDimensions.value,
    });
    report.value = res;
    ElMessage.success('报表生成成功');
  } catch {
    reportError.value = true;
    ElMessage.error('报表生成失败');
  } finally {
    generating.value = false;
  }
}

function handleShare() {
  if (report.value) {
    emit('share', report.value.id);
  } else {
    ElMessage.warning('请先生成报表');
  }
}
</script>

<style scoped lang="scss">
.report-panel {
  background: var(--fuxi-bg-card);
  border: 1px solid var(--fuxi-border);
  border-radius: var(--fuxi-radius);
  padding: 20px;
}

.report-header {
  margin-bottom: var(--space-md);
}

.report-title {
  margin: 0;
  font-size: var(--font-size-card-title);
  font-weight: 600;
  color: var(--fuxi-text);
}

.report-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
  margin-bottom: var(--space-lg);
  padding: var(--space-md);
  background: var(--fuxi-bg-subtle);
  border-radius: var(--radius-md);
}

.form-row {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  flex-wrap: wrap;

  @media (max-width: 600px) {
    flex-direction: column;
    align-items: flex-start;
  }
}

.form-label {
  font-weight: 600;
  font-size: var(--font-size-caption);
  color: var(--fuxi-text-secondary);
  min-width: 70px;
}

.report-result {
  border-top: 1px solid var(--fuxi-border);
  padding-top: var(--space-md);
}

.report-result__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: var(--space-md);
  flex-wrap: wrap;
  gap: var(--space-sm);

  @media (max-width: 600px) {
    flex-direction: column;
  }
}

.report-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.report-result__title {
  margin: 0;
  font-size: var(--font-size-card-title);
  font-weight: 600;
  color: var(--fuxi-text);
}

.report-result__time {
  font-size: var(--font-size-small);
  color: var(--fuxi-text-tertiary);
}

.report-actions {
  display: flex;
  gap: var(--space-sm);
}

.report-sections {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.report-section {
  padding: var(--space-md);
  background: var(--fuxi-bg-subtle);
  border-radius: var(--radius-sm);
  border-left: 3px solid var(--fuxi-primary);

  &__title {
    margin: 0 0 var(--space-sm) 0;
    font-size: var(--font-size-caption);
    font-weight: 700;
    color: var(--fuxi-primary);
  }

  &__content {
    margin: 0 0 var(--space-sm) 0;
    font-size: var(--font-size-caption);
    line-height: 1.8;
    color: var(--fuxi-text);
  }

  &__metrics {
    display: flex;
    gap: var(--space-md);
    flex-wrap: wrap;
  }
}

.metric-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--space-xs) var(--space-sm);
  background: var(--fuxi-bg-card);
  border-radius: var(--radius-sm);
  min-width: 100px;
}

.metric-label {
  font-size: var(--font-size-small);
  color: var(--fuxi-text-tertiary);
}

.metric-value {
  font-size: var(--font-size-body);
  font-weight: 700;
  color: var(--fuxi-text);
  font-variant-numeric: tabular-nums;
}

.report-generating {
  padding: var(--space-md);
}

.generating-text {
  margin: var(--space-sm) 0 0;
  text-align: center;
  font-size: var(--font-size-small);
  color: var(--fuxi-text-secondary);
}

.report-error {
  padding: var(--space-md);
}
</style>
