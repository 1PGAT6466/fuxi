<template>
  <!--
    伏羲 v2.1 — 导出配置弹窗
    CSV/Excel 导出配置（字段选择 + 格式 + 时间范围 + 导出）
  -->
  <el-dialog
    v-model="visible"
    title="数据导出"
    width="520px"
    :close-on-click-modal="false"
    destroy-on-close
  >
    <div class="export-dialog">
      <!-- 导出格式 -->
      <div class="export-section">
        <label class="export-label">导出格式</label>
        <el-radio-group v-model="config.format">
          <el-radio value="csv">CSV</el-radio>
          <el-radio value="excel">Excel (.xlsx)</el-radio>
        </el-radio-group>
      </div>

      <!-- 时间范围 -->
      <div class="export-section">
        <label class="export-label">时间范围</label>
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
          style="width: 100%"
        />
      </div>

      <!-- 字段选择 -->
      <div class="export-section">
        <label class="export-label">导出字段</label>
        <el-checkbox-group v-model="config.fields" class="export-fields">
          <el-checkbox value="date" label="日期" />
          <el-checkbox value="queries" label="查询量" />
          <el-checkbox value="documents" label="文档数" />
          <el-checkbox value="users" label="用户数" />
          <el-checkbox value="storage" label="存储用量" />
          <el-checkbox value="vectors" label="向量数" />
          <el-checkbox value="response_time" label="响应时间" />
          <el-checkbox value="success_rate" label="成功率" />
        </el-checkbox-group>
      </div>

      <!-- 选项全选 -->
      <div class="export-section">
        <el-button text size="small" @click="selectAll">
          {{ config.fields.length === allFields.length ? '取消全选' : '全选' }}
        </el-button>
      </div>
    </div>

    <template #footer>
      <div class="export-footer">
        <el-button @click="visible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="exporting"
          :disabled="!config.fields.length"
          @click="handleExport"
        >
          <el-icon><Download /></el-icon>
          导出
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue';
import { ElMessage } from 'element-plus';
import { Download } from '@element-plus/icons-vue';
import * as analyticsApi from './api';
import type { ExportConfig, ExportFormat } from './types';

const props = defineProps<{
  modelValue: boolean;
  defaultFormat?: ExportFormat;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void;
  (e: 'exported', res: { download_url: string; filename: string }): void;
}>();

const visible = ref(props.modelValue);
const exporting = ref(false);

const allFields = [
  'date',
  'queries',
  'documents',
  'users',
  'storage',
  'vectors',
  'response_time',
  'success_rate',
];

const config = reactive<ExportConfig>({
  format: props.defaultFormat || 'csv',
  fields: allFields.slice(0, 5),
  date_range: {},
});

const dateRange = ref<[string, string] | null>(null);

watch(
  () => props.modelValue,
  (val) => {
    visible.value = val;
  },
);

watch(visible, (val) => {
  emit('update:modelValue', val);
});

watch(dateRange, (val) => {
  if (val) {
    config.date_range = { start: val[0], end: val[1] };
  } else {
    config.date_range = {};
  }
});

function selectAll() {
  if (config.fields.length === allFields.length) {
    config.fields = [];
  } else {
    config.fields = [...allFields];
  }
}

async function handleExport() {
  if (!config.fields.length) {
    ElMessage.warning('请至少选择一个导出字段');
    return;
  }

  exporting.value = true;
  try {
    const res = await analyticsApi.exportData(config);
    emit('exported', { download_url: res.download_url, filename: res.filename });
    ElMessage.success(`导出成功：${res.filename}（${(res.size / 1024).toFixed(1)} KB）`);
    visible.value = false;
  } catch {
    ElMessage.error('导出失败，请重试');
  } finally {
    exporting.value = false;
  }
}
</script>

<style scoped lang="scss">
.export-dialog {
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
}

.export-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.export-label {
  font-weight: 600;
  font-size: var(--font-size-caption);
  color: var(--fuxi-text);
}

.export-fields {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-sm);

  @media (max-width: 400px) {
    grid-template-columns: repeat(2, 1fr);
  }
}

.export-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-sm);
}
</style>
