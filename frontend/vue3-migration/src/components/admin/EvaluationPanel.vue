<template>
  <div class="evaluation-panel">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>{{ $t('admin.evaluation.title') }}</span>
          <el-button type="primary" size="small" :loading="running" @click="runEvaluation">
            <el-icon><VideoPlay /></el-icon> {{ $t('admin.evaluation.runEval') }}
          </el-button>
        </div>
      </template>

      <el-table v-loading="loading" :data="evaluations">
        <el-table-column prop="name" :label="$t('admin.evaluation.evalName')" min-width="200" />
        <el-table-column :label="$t('admin.evaluation.runTime')" width="180">
          <template #default="{ row }">
            {{ formatDate(row.date) }}
          </template>
        </el-table-column>
        <el-table-column prop="score" :label="$t('admin.evaluation.score')" width="100">
          <template #default="{ row }">
            <el-tag :type="getPercentScoreType(row.score)"> {{ row.score }}% </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" :label="$t('admin.evaluation.evalStatus')" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'completed' ? 'success' : 'warning'">
              {{
                row.status === 'completed'
                  ? $t('admin.evaluation.completed')
                  : $t('admin.evaluation.running')
              }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="$t('admin.evaluation.evalActions')" width="120">
          <template #default="{ row }">
            <el-button size="small" :disabled="row.status !== 'completed'" @click="viewReport(row)">
              {{ $t('admin.evaluation.viewReport') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty
        v-if="!loading && evaluations.length === 0"
        :description="$t('admin.evaluation.noReports')"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import apiClient from '@/api';
import { ElMessage } from 'element-plus';
import { VideoPlay } from '@element-plus/icons-vue';
import { formatDate, getPercentScoreType } from '@/utils/helpers';

interface Evaluation {
  name: string;
  date: string;
  score: number;
  status: 'completed' | 'running';
  id?: string;
}

const evaluations = ref<Evaluation[]>([]);
const loading = ref<boolean>(false);
const running = ref<boolean>(false);

onMounted(async () => {
  await fetchEvaluations();
});

async function fetchEvaluations(): Promise<void> {
  loading.value = true;
  try {
    const data = (await apiClient.get('/api/admin/evaluations')) as { evaluations?: Evaluation[] };
    evaluations.value = data.evaluations || [];
  } catch (error) {
    console.error('获取评测列表失败:', error);
    ElMessage.error('获取评测列表失败');
  } finally {
    loading.value = false;
  }
}

async function runEvaluation(): Promise<void> {
  running.value = true;
  try {
    await apiClient.post('/api/admin/evaluations/run');
    ElMessage.success('评测任务已启动');
    await fetchEvaluations();
  } catch {
    ElMessage.error('评测启动失败');
  } finally {
    running.value = false;
  }
}

function viewReport(evaluation: Evaluation): void {
  // TODO: 实现查看报告详情 — 打开详情对话框或跳转到报告页面
  ElMessage.info(`查看报告：${evaluation.name}`);
}
</script>

<style scoped lang="scss">
.evaluation-panel {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
