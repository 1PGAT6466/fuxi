<template>
  <!--
    伏羲 v2.1 — 评测管理
    数据集列表 + 创建/上传 + 评测任务 + 结果对比（雷达图）
  -->
  <div class="evaluation-view">
    <h2 class="page-title">评测管理</h2>

    <el-tabs v-model="activeTab">
      <!-- ─── 数据集 Tab ─── -->
      <el-tab-pane label="数据集" name="datasets">
        <div class="tab-header">
          <span class="tab-count">{{ datasets.length }} 个数据集</span>
          <el-button type="primary" size="small" @click="showCreateDataset = true">
            <el-icon><Plus /></el-icon> 创建数据集
          </el-button>
        </div>

        <div class="dataset-list">
          <div v-for="ds in datasets" :key="ds.id" class="dataset-card">
            <div class="dataset-info">
              <el-icon :size="20" class="dataset-icon"><Collection /></el-icon>
              <div class="dataset-body">
                <span class="dataset-name">{{ ds.name }}</span>
                <span class="dataset-desc">{{ ds.description }}</span>
                <div class="dataset-meta">
                  <span>{{ ds.sample_count }} 条样本</span>
                  <span>{{ ds.created_at }}</span>
                </div>
              </div>
            </div>
            <el-tag size="small">{{ ds.task_type }}</el-tag>
          </div>

          <div v-if="datasets.length === 0" class="empty-state">
            <el-icon :size="40"><Collection /></el-icon>
            <span>暂无数据集</span>
          </div>
        </div>
      </el-tab-pane>

      <!-- ─── 任务 Tab ─── -->
      <el-tab-pane label="评测任务" name="tasks">
        <div class="tab-header">
          <span class="tab-count">{{ tasks.length }} 个任务</span>
          <el-button type="primary" size="small" @click="showCreateTask = true">
            <el-icon><Plus /></el-icon> 创建任务
          </el-button>
        </div>

        <el-table :data="tasks" style="width: 100%" size="small">
          <el-table-column prop="name" label="任务名称" min-width="160" />
          <el-table-column prop="dataset_name" label="数据集" min-width="120" />
          <el-table-column prop="model" label="模型" width="120" />
          <el-table-column prop="metrics" label="指标" min-width="180">
            <template #default="{ row }">
              <el-tag v-for="m in row.metrics" :key="m" size="small" class="metric-tag">{{
                m
              }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="100">
            <template #default="{ row }">
              <el-tag
                :type="
                  row.status === 'completed'
                    ? 'success'
                    : row.status === 'running'
                      ? 'warning'
                      : 'info'
                "
                size="small"
              >
                {{ statusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="140">
            <template #default="{ row }">
              <el-button
                v-if="row.status === 'completed'"
                type="primary"
                link
                size="small"
                @click="viewResult(row)"
              >
                查看结果
              </el-button>
              <el-button
                v-else-if="row.status === 'running'"
                type="warning"
                link
                size="small"
                disabled
              >
                运行中...
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- ─── 结果对比 Tab ─── -->
      <el-tab-pane label="结果对比" name="results">
        <div v-if="selectedResult" class="result-detail">
          <div class="result-header">
            <h3>{{ selectedResult.task_name }}</h3>
            <el-button size="small" text @click="selectedResult = null">返回</el-button>
          </div>

          <!-- 雷达图 -->
          <div ref="radarRef" class="radar-chart" />

          <!-- 指标明细 -->
          <div class="result-metrics">
            <div
              v-for="metric in selectedResult.metrics_detail"
              :key="metric.name"
              class="result-metric-item"
            >
              <span class="rm-label">{{ metric.name }}</span>
              <el-progress
                :percentage="Math.round(metric.value * 100)"
                :color="metric.color || '#FF6700'"
                :stroke-width="8"
              />
              <span class="rm-value">{{ (metric.value * 100).toFixed(1) }}%</span>
            </div>
          </div>

          <!-- 单条 Case 分析 -->
          <h4 class="section-title">单条 Case 分析</h4>
          <div class="case-list">
            <div v-for="c in selectedResult.cases" :key="c.id" class="case-item">
              <div class="case-header">
                <span class="case-id">#{{ c.id }}</span>
                <el-tag :type="c.pass ? 'success' : 'danger'" size="small">
                  {{ c.pass ? '通过' : '未通过' }}
                </el-tag>
              </div>
              <div class="case-body">
                <div class="case-field">
                  <span class="case-label">Query</span>
                  <span class="case-value">{{ c.query }}</span>
                </div>
                <div class="case-field">
                  <span class="case-label">Expected</span>
                  <span class="case-value">{{ c.expected }}</span>
                </div>
                <div class="case-field">
                  <span class="case-label">Actual</span>
                  <span class="case-value">{{ c.actual }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 结果列表 -->
        <div v-else class="result-list">
          <div v-for="r in results" :key="r.id" class="result-card" @click="viewResult(r)">
            <div class="result-card-header">
              <span class="result-name">{{ r.task_name }}</span>
              <el-tag size="small">{{ r.model }}</el-tag>
            </div>
            <div class="result-card-body">
              <span v-for="(v, k) in r.scores" :key="k" class="score-chip">
                {{ k }}: {{ (v * 100).toFixed(1) }}%
              </span>
            </div>
          </div>

          <div v-if="results.length === 0" class="empty-state">
            <el-icon :size="40"><DataAnalysis /></el-icon>
            <span>暂无评测结果</span>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 创建数据集对话框 -->
    <el-dialog v-model="showCreateDataset" title="创建数据集" width="500px">
      <el-form :model="newDataset" label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="newDataset.name" placeholder="输入数据集名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="newDataset.desc" type="textarea" :rows="2" placeholder="输入描述" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="newDataset.type" style="width: 100%">
            <el-option label="问答评测" value="qa" />
            <el-option label="文本分类" value="classification" />
            <el-option label="实体识别" value="ner" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDataset = false">取消</el-button>
        <el-button type="primary" @click="createDataset">创建</el-button>
      </template>
    </el-dialog>

    <!-- 创建任务对话框 -->
    <el-dialog v-model="showCreateTask" title="创建评测任务" width="500px">
      <el-form :model="newTask" label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="newTask.name" placeholder="输入任务名称" />
        </el-form-item>
        <el-form-item label="数据集">
          <el-select v-model="newTask.dataset_id" style="width: 100%">
            <el-option v-for="ds in datasets" :key="ds.id" :label="ds.name" :value="ds.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="模型">
          <el-select v-model="newTask.model" style="width: 100%">
            <el-option label="DeepSeek V4" value="deepseek-v4" />
            <el-option label="GPT-4o" value="gpt-4o" />
            <el-option label="Qwen-Max" value="qwen-max" />
          </el-select>
        </el-form-item>
        <el-form-item label="指标">
          <el-checkbox-group v-model="newTask.metrics">
            <el-checkbox label="Recall" />
            <el-checkbox label="Precision" />
            <el-checkbox label="MRR" />
            <el-checkbox label="NDCG" />
          </el-checkbox-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateTask = false">取消</el-button>
        <el-button type="primary" @click="createTask">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue';
import { Plus, Collection, DataAnalysis } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
// P0-3: 按需导入 echarts
import * as echarts from 'echarts/core';
import { RadarChart } from 'echarts/charts';
import { TooltipComponent, LegendComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

echarts.use([RadarChart, TooltipComponent, LegendComponent, CanvasRenderer]);
import apiClient from '@/api';

// ─── 类型 ───
interface Dataset {
  id: string;
  name: string;
  description: string;
  sample_count: number;
  task_type: string;
  created_at: string;
}

interface EvalTask {
  id: string;
  name: string;
  dataset_name: string;
  dataset_id: string;
  model: string;
  metrics: string[];
  status: 'pending' | 'running' | 'completed' | 'failed';
}

interface CaseItem {
  id: number;
  query: string;
  expected: string;
  actual: string;
  pass: boolean;
}

interface EvalResult {
  id: string;
  task_name: string;
  model: string;
  scores: Record<string, number>;
  metrics_detail: { name: string; value: number; color: string }[];
  cases: CaseItem[];
}

// ─── State ───
const activeTab = ref('datasets');
const datasets = ref<Dataset[]>([]);
const tasks = ref<EvalTask[]>([]);
const results = ref<EvalResult[]>([]);
const selectedResult = ref<EvalResult | null>(null);

const showCreateDataset = ref(false);
const showCreateTask = ref(false);

const newDataset = ref({ name: '', desc: '', type: 'qa' });
const newTask = ref({
  name: '',
  dataset_id: '',
  model: 'deepseek-v4',
  metrics: ['Recall', 'Precision'],
});

const radarRef = ref<HTMLDivElement | null>(null);
let radarChart: echarts.ECharts | null = null;

// ─── Mock 数据 ───
const mockDatasets: Dataset[] = [
  {
    id: '1',
    name: '通用问答测试集 v2',
    description: '覆盖财经/科技/医疗 500 条 QA',
    sample_count: 500,
    task_type: 'qa',
    created_at: '2026-06-15',
  },
  {
    id: '2',
    name: '长文本理解基准',
    description: '多跳推理 + 摘要评测',
    sample_count: 200,
    task_type: 'qa',
    created_at: '2026-06-20',
  },
];

const mockTasks: EvalTask[] = [
  {
    id: '1',
    name: 'DeepSeek V4 基准测试',
    dataset_name: '通用问答测试集 v2',
    dataset_id: '1',
    model: 'deepseek-v4',
    metrics: ['Recall', 'Precision', 'MRR', 'NDCG'],
    status: 'completed',
  },
  {
    id: '2',
    name: 'GPT-4o 对比测试',
    dataset_name: '长文本理解基准',
    dataset_id: '2',
    model: 'gpt-4o',
    metrics: ['Recall', 'Precision', 'MRR'],
    status: 'completed',
  },
  {
    id: '3',
    name: 'Qwen-Max 最新评测',
    dataset_name: '通用问答测试集 v2',
    dataset_id: '1',
    model: 'qwen-max',
    metrics: ['Recall', 'Precision', 'NDCG'],
    status: 'running',
  },
];

const mockResults: EvalResult[] = [
  {
    id: '1',
    task_name: 'DeepSeek V4 基准测试',
    model: 'deepseek-v4',
    scores: { Recall: 0.892, Precision: 0.876, MRR: 0.851, NDCG: 0.903 },
    metrics_detail: [
      { name: 'Recall', value: 0.892, color: '#FF6700' }, // 暖橙
      { name: 'Precision', value: 0.876, color: '#3A6B8C' }, // 蓝灰
      { name: 'MRR', value: 0.851, color: '#5B8C5A' }, // 绿
      { name: 'NDCG', value: 0.903, color: '#C44B3C' }, // 红棕
    ],
    cases: [
      {
        id: 1,
        query: '什么是向量检索？',
        expected: '基于embedding的相似度搜索技术',
        actual: '基于embedding向量相似度的检索技术',
        pass: true,
      },
      {
        id: 2,
        query: '如何优化RAG系统？',
        expected: '文档分块/检索增强/重排序',
        actual: '优化文档切分和检索策略',
        pass: false,
      },
      {
        id: 3,
        query: 'Transformer的核心机制',
        expected: '自注意力机制',
        actual: 'Self-Attention自注意力机制',
        pass: true,
      },
    ],
  },
  {
    id: '2',
    task_name: 'GPT-4o 对比测试',
    model: 'gpt-4o',
    scores: { Recall: 0.915, Precision: 0.902, MRR: 0.878 },
    metrics_detail: [
      { name: 'Recall', value: 0.915, color: '#FF6700' }, // 暖橙
      { name: 'Precision', value: 0.902, color: '#3A6B8C' }, // 蓝灰
      { name: 'MRR', value: 0.878, color: '#5B8C5A' }, // 绿
    ],
    cases: [
      {
        id: 1,
        query: '什么是RAG？',
        expected: '检索增强生成技术',
        actual: 'Retrieval-Augmented Generation检索增强生成',
        pass: true,
      },
    ],
  },
];

// ─── Helpers ───
function statusLabel(s: string): string {
  const map: Record<string, string> = {
    pending: '等待中',
    running: '运行中',
    completed: '已完成',
    failed: '失败',
  };
  return map[s] || s;
}

// ─── Data Fetch ───
async function fetchDatasets(): Promise<void> {
  try {
    datasets.value = (await apiClient.get('/api/evaluation/datasets')) as Dataset[];
  } catch {
    datasets.value = mockDatasets;
  }
}

async function fetchTasks(): Promise<void> {
  try {
    tasks.value = (await apiClient.get('/api/evaluation/tasks')) as EvalTask[];
  } catch {
    tasks.value = mockTasks;
  }
}

async function fetchResults(): Promise<void> {
  try {
    results.value = (await apiClient.get('/api/evaluation/results')) as EvalResult[];
  } catch {
    results.value = mockResults;
  }
}

// ─── Actions ───
function createDataset(): void {
  if (!newDataset.value.name.trim()) {
    ElMessage.warning('请输入数据集名称');
    return;
  }
  const ds: Dataset = {
    id: String(Date.now()),
    name: newDataset.value.name,
    description: newDataset.value.desc,
    sample_count: 0,
    task_type: newDataset.value.type,
    created_at: new Date().toISOString().split('T')[0],
  };
  datasets.value.unshift(ds);
  showCreateDataset.value = false;
  newDataset.value = { name: '', desc: '', type: 'qa' };
  ElMessage.success('数据集创建成功');
}

function createTask(): void {
  if (!newTask.value.name.trim() || !newTask.value.dataset_id) {
    ElMessage.warning('请填写完整信息');
    return;
  }
  const ds = datasets.value.find((d) => d.id === newTask.value.dataset_id);
  const task: EvalTask = {
    id: String(Date.now()),
    name: newTask.value.name,
    dataset_name: ds?.name || '',
    dataset_id: newTask.value.dataset_id,
    model: newTask.value.model,
    metrics: newTask.value.metrics,
    status: 'pending',
  };
  tasks.value.unshift(task);
  showCreateTask.value = false;
  newTask.value = {
    name: '',
    dataset_id: '',
    model: 'deepseek-v4',
    metrics: ['Recall', 'Precision'],
  };
  ElMessage.success('评测任务创建成功');
}

function viewResult(result: EvalResult): void {
  selectedResult.value = result;
  nextTick(initRadar);
}

// ─── Radar Chart ───
function initRadar(): void {
  if (!radarRef.value || !selectedResult.value) return;
  if (radarChart) radarChart.dispose();

  radarChart = echarts.init(radarRef.value);
  const detail = selectedResult.value.metrics_detail;

  radarChart.setOption({
    tooltip: {},
    legend: { data: [selectedResult.value.model], bottom: 0 },
    radar: {
      indicator: detail.map((d) => ({ name: d.name, max: 1 })),
      shape: 'polygon',
      center: ['50%', '50%'],
      radius: '65%',
    },
    series: [
      {
        name: selectedResult.value.model,
        type: 'radar',
        data: [{ value: detail.map((d) => d.value), name: selectedResult.value.model }],
        areaStyle: { color: 'rgba(255,103,0,0.15)' },
        lineStyle: { color: '#FF6700', width: 2 }, // 暖橙点缀
        itemStyle: { color: '#FF6700' }, // 暖橙点缀
      },
    ],
  });
}

// ─── Lifecycle ───
let resizeHandler: (() => void) | null = null;

onMounted(async () => {
  await Promise.all([fetchDatasets(), fetchTasks(), fetchResults()]);
  resizeHandler = () => radarChart?.resize();
  window.addEventListener('resize', resizeHandler);
});

onUnmounted(() => {
  radarChart?.dispose();
  if (resizeHandler) window.removeEventListener('resize', resizeHandler);
});
</script>

<style scoped lang="scss">
.evaluation-view {
  max-width: 1200px;
  margin: 0 auto;
  padding: 28px 24px;
}

.page-title {
  margin: 0 0 24px;
  font-size: var(--font-size-page-title);
  font-weight: 700;
  color: var(--text-primary);
}

.tab-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.tab-count {
  font-size: var(--font-size-caption);
  color: var(--text-tertiary);
}

/* ─── 数据集 ─── */
.dataset-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.dataset-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  transition: box-shadow var(--duration-fast) var(--ease-out);

  &:hover {
    box-shadow: var(--shadow-md);
  }
}

.dataset-info {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.dataset-icon {
  color: var(--xun-color);
  margin-top: 2px;
}

.dataset-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.dataset-name {
  font-weight: 600;
  font-size: var(--font-size-caption);
  color: var(--text-primary);
}

.dataset-desc {
  font-size: var(--font-size-small);
  color: var(--text-secondary);
}

.dataset-meta {
  display: flex;
  gap: 16px;
  font-size: var(--font-size-small);
  color: var(--text-tertiary);
}

/* ─── 指标标签 ─── */
.metric-tag {
  margin-right: 4px;
  margin-bottom: 4px;
}

/* ─── 结果对比 ─── */
.result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;

  h3 {
    margin: 0;
    font-size: var(--font-size-card-title);
  }
}

.result-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

.result-card {
  padding: 16px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);

  &:hover {
    box-shadow: var(--shadow-md);
    transform: translateY(-2px);
  }
}

.result-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.result-name {
  font-weight: 600;
  color: var(--text-primary);
}

.result-card-body {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.score-chip {
  font-size: var(--font-size-small);
  padding: 2px 8px;
  background: var(--bg-subtle);
  border-radius: 4px;
  color: var(--text-secondary);
}

/* ─── 雷达图 ─── */
.radar-chart {
  width: 100%;
  height: 350px;
  margin-bottom: 20px;
}

/* ─── 指标明细 ─── */
.result-metrics {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 24px;
}

.result-metric-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.rm-label {
  min-width: 80px;
  font-size: var(--font-size-caption);
  font-weight: 500;
  color: var(--text-primary);
}

.rm-value {
  min-width: 50px;
  text-align: right;
  font-size: var(--font-size-caption);
  font-weight: 600;
  color: var(--text-primary);
}

/* ─── Section ─── */
.section-title {
  font-size: var(--font-size-card-title);
  font-weight: 600;
  margin: 0 0 12px;
  color: var(--text-primary);
}

/* ─── Case 列表 ─── */
.case-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.case-item {
  padding: 12px;
  background: var(--bg-card);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-sm);
}

.case-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.case-id {
  font-weight: 600;
  font-size: var(--font-size-small);
  color: var(--text-tertiary);
}

.case-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.case-field {
  display: flex;
  gap: 12px;
}

.case-label {
  min-width: 70px;
  font-size: var(--font-size-small);
  font-weight: 600;
  color: var(--text-tertiary);
}

.case-value {
  font-size: var(--font-size-caption);
  color: var(--text-primary);
}

/* ─── Empty ─── */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 60px 0;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}

/* ─── 响应式 ─── */
@media (max-width: 767px) {
  .evaluation-view {
    padding: 16px 12px;
  }
  .result-list {
    grid-template-columns: 1fr;
  }
}
</style>
