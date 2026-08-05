<template>
  <!--
    伏羲 v2.1 — 自进化管理
    进化规则列表 + 反馈数据面板 + 进化日志时间线
  -->
  <div class="evolution-view">
    <h2 class="page-title">自进化管理</h2>

    <el-tabs v-model="activeTab">
      <!-- ─── 进化规则 Tab ─── -->
      <el-tab-pane label="进化规则" name="rules">
        <div class="tab-header">
          <span class="tab-count">{{ rules.length }} 条规则</span>
          <el-button type="primary" size="small" @click="showCreateRule = true">
            <el-icon><Plus /></el-icon> 添加规则
          </el-button>
        </div>

        <el-table :data="Array.isArray(rules) ? rules : []" style="width: 100%" size="small">
          <el-table-column prop="name" label="规则名称" min-width="140" />
          <el-table-column prop="trigger" label="触发条件" min-width="180">
            <template #default="{ row }">
              <span class="trigger-text">{{ row.trigger }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="action" label="动作" min-width="160">
            <template #default="{ row }">
              <el-tag size="small" type="info">{{ row.action }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="priority" label="优先级" width="90" sortable>
            <template #default="{ row }">
              <span
                :class="`priority-level priority--${row.priority >= 8 ? 'high' : row.priority >= 5 ? 'mid' : 'low'}`"
              >
                {{ row.priority }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="enabled" label="启用" width="80">
            <template #default="{ row }">
              <el-switch v-model="row.enabled" size="small" @change="toggleRule(row)" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="80">
            <template #default="{ row }">
              <el-button type="danger" link size="small" @click="deleteRule(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- ─── 反馈数据 Tab ─── -->
      <el-tab-pane label="反馈数据" name="feedback">
        <div class="feedback-grid">
          <!-- 统计卡片 -->
          <div class="feedback-stats">
            <div class="stat-card">
              <div class="stat-value stat-value--positive">
                <el-icon :size="20"><CircleCheckFilled /></el-icon>
                {{ feedback.positive_count }}
              </div>
              <span class="stat-label">正面反馈</span>
            </div>
            <div class="stat-card">
              <div class="stat-value stat-value--negative">
                <el-icon :size="20"><CircleCloseFilled /></el-icon>
                {{ feedback.negative_count }}
              </div>
              <span class="stat-label">负面反馈</span>
            </div>
            <div class="stat-card">
              <div class="stat-value">
                {{
                  (
                    (feedback.positive_count /
                      Math.max(feedback.positive_count + feedback.negative_count, 1)) *
                    100
                  ).toFixed(1)
                }}%
              </div>
              <span class="stat-label">满意率</span>
            </div>
          </div>

          <!-- 趋势图 -->
          <div ref="feedbackChartRef" class="feedback-chart" />

          <!-- 反馈列表 -->
          <div class="feedback-list">
            <h4 class="section-title">最近反馈</h4>
            <div v-for="fb in feedback.recent" :key="fb.id" class="feedback-item">
              <div class="fb-header">
                <span class="fb-user">{{ fb.user }}</span>
                <el-tag :type="fb.type === 'positive' ? 'success' : 'danger'" size="small">
                  {{ fb.type === 'positive' ? '👍 正面' : '👎 负面' }}
                </el-tag>
                <span class="fb-time">{{ fb.time }}</span>
              </div>
              <div class="fb-body">
                <span class="fb-query">Q: {{ fb.query }}</span>
                <span class="fb-comment">{{ fb.comment }}</span>
              </div>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- ─── 进化日志 Tab ─── -->
      <el-tab-pane label="进化日志" name="logs">
        <el-timeline>
          <el-timeline-item
            v-for="log in evolutionLogs"
            :key="log.id"
            :timestamp="log.timestamp"
            :color="
              log.type === 'optimization'
                ? '#FF6700' // 暖橙点缀
                : log.type === 'auto_fix'
                  ? '#34C759' // 绿色成功色
                  : '#3A6B8C' // 蓝灰信息色
            "
            placement="top"
          >
            <div class="log-card">
              <div class="log-header">
                <span class="log-type">
                  <el-tag
                    :type="
                      log.type === 'optimization'
                        ? 'warning'
                        : log.type === 'auto_fix'
                          ? 'success'
                          : 'info'
                    "
                    size="small"
                  >
                    {{ logTypeLabel(log.type) }}
                  </el-tag>
                </span>
                <span class="log-title">{{ log.title }}</span>
              </div>
              <p class="log-desc">{{ log.description }}</p>
              <div class="log-meta">
                <span>触发规则：{{ log.rule_name }}</span>
                <span>影响范围：{{ log.affected }}</span>
              </div>
              <!-- Diff 对比（简化版） -->
              <div v-if="log.diff" class="log-diff">
                <div class="diff-header">配置变更</div>
                <div class="diff-content">
                  <div class="diff-line diff-line--old">
                    <span class="diff-prefix">-</span>{{ log.diff.old }}
                  </div>
                  <div class="diff-line diff-line--new">
                    <span class="diff-prefix">+</span>{{ log.diff.new }}
                  </div>
                </div>
              </div>
            </div>
          </el-timeline-item>
        </el-timeline>
      </el-tab-pane>
    </el-tabs>

    <!-- 创建规则对话框 -->
    <el-dialog v-model="showCreateRule" title="添加进化规则" width="500px">
      <el-form :model="newRule" label-width="80px">
        <el-form-item label="规则名称">
          <el-input v-model="newRule.name" placeholder="输入规则名称" />
        </el-form-item>
        <el-form-item label="触发条件">
          <el-input v-model="newRule.trigger" placeholder="如：错误率 > 5%" />
        </el-form-item>
        <el-form-item label="动作">
          <el-select v-model="newRule.action" style="width: 100%">
            <el-option label="自动回滚模型" value="auto_rollback" />
            <el-option label="调整检索参数" value="tune_params" />
            <el-option label="重建索引" value="rebuild_index" />
            <el-option label="发送告警" value="send_alert" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-slider v-model="newRule.priority" :min="1" :max="10" show-stops />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateRule = false">取消</el-button>
        <el-button type="primary" @click="createRule">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue';
import { Plus, CircleCheckFilled, CircleCloseFilled } from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { logger } from '@/utils/logger';
// P0-3: 按需导入 echarts
import * as echarts from 'echarts/core';
import { BarChart } from 'echarts/charts';
import { TooltipComponent, LegendComponent, GridComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

echarts.use([BarChart, TooltipComponent, LegendComponent, GridComponent, CanvasRenderer]);
import {
  getEvolutionRules,
  createEvolutionRule,
  updateEvolutionRule,
  deleteEvolutionRule,
  getEvolutionOverview,
  getEvolutionLogs,
} from '@/api/evolution';

// ─── 类型 ───
interface EvolutionRule {
  id: string;
  name: string;
  trigger: string;
  action: string;
  priority: number;
  enabled: boolean;
}

interface FeedbackItem {
  id: string;
  user: string;
  type: 'positive' | 'negative';
  query: string;
  comment: string;
  time: string;
}

interface FeedbackData {
  positive_count: number;
  negative_count: number;
  trend: number[];
  trend_dates: string[];
  recent: FeedbackItem[];
}

interface EvolutionLog {
  id: string;
  type: 'optimization' | 'auto_fix' | 'config_change';
  title: string;
  description: string;
  rule_name: string;
  affected: string;
  timestamp: string;
  diff?: { old: string; new: string };
}

// ─── State ───
const activeTab = ref('rules');
const showCreateRule = ref(false);
const newRule = ref({ name: '', trigger: '', action: 'tune_params', priority: 5 });

const rules = ref<EvolutionRule[]>([]);
const feedback = ref<FeedbackData>({
  positive_count: 0,
  negative_count: 0,
  trend: [],
  trend_dates: [],
  recent: [],
});
const evolutionLogs = ref<EvolutionLog[]>([]);

const feedbackChartRef = ref<HTMLDivElement | null>(null);
let fbChart: echarts.ECharts | null = null;

// ─── Helpers ───
function logTypeLabel(type: string): string {
  const map: Record<string, string> = {
    optimization: '优化',
    auto_fix: '自动修复',
    config_change: '配置变更',
  };
  return map[type] || type;
}

// ─── Fetch ───
function normalizeArray<T>(value: unknown, fallback: T[]): T[] {
  if (Array.isArray(value)) return value as T[];
  if (value && typeof value === 'object') {
    const record = value as Record<string, unknown>;
    const candidates = [record.items, record.rules, record.logs, record.list, record.data];
    for (const candidate of candidates) {
      if (Array.isArray(candidate)) return candidate as T[];
    }
  }
  return fallback;
}

function extractPayload<T>(value: unknown): T {
  if (value && typeof value === 'object') {
    const record = value as Record<string, unknown>;
    if ('data' in record && record.data !== undefined) {
      return record.data as T;
    }
  }
  return value as T;
}

async function fetchRules(): Promise<void> {
  try {
    const resp = await getEvolutionRules();
    const data = extractPayload<any>(resp);
    rules.value = normalizeArray<EvolutionRule>(data?.items || data, []);
  } catch (error) {
    console.error('获取进化规则失败:', error);
    rules.value = [];
  }
}

async function fetchFeedback(): Promise<void> {
  try {
    const resp = await getEvolutionOverview();
    const overview = extractPayload<any>(resp);
    
    // 从进化概览中提取反馈数据
    feedback.value = {
      positive_count: overview?.feedback?.positive_count ?? overview?.positive_count ?? 0,
      negative_count: overview?.feedback?.negative_count ?? overview?.negative_count ?? 0,
      trend: overview?.feedback?.trend ?? overview?.trend ?? [],
      trend_dates: overview?.feedback?.trend_dates ?? overview?.trend_dates ?? [],
      recent: overview?.feedback?.recent ?? overview?.recent ?? [],
    };
    nextTick(initFeedbackChart);
  } catch (error) {
    console.error('获取反馈数据失败:', error);
    feedback.value = { positive_count: 0, negative_count: 0, trend: [], trend_dates: [], recent: [] };
    nextTick(initFeedbackChart);
  }
}

async function fetchLogs(): Promise<void> {
  try {
    const resp = await getEvolutionLogs();
    const data = extractPayload<any>(resp);
    evolutionLogs.value = normalizeArray<EvolutionLog>(data?.items || data, []);
  } catch (error) {
    console.error('获取进化日志失败:', error);
    evolutionLogs.value = [];
  }
}

// ─── Actions ───
async function createRule(): Promise<void> {
  if (!newRule.value.name.trim()) {
    ElMessage.warning('请输入规则名称');
    return;
  }

  try {
    const resp = await createEvolutionRule({
      name: newRule.value.name,
      trigger: newRule.value.trigger,
      action: newRule.value.action,
      priority: newRule.value.priority,
      enabled: true,
    });

    const created = (extractPayload(resp) as EvolutionRule) ?? {
      id: String(Date.now()),
      name: newRule.value.name,
      trigger: newRule.value.trigger,
      action: newRule.value.action,
      priority: newRule.value.priority,
      enabled: true,
    };

    rules.value.unshift(created);
    showCreateRule.value = false;
    newRule.value = { name: '', trigger: '', action: 'tune_params', priority: 5 };
    ElMessage.success('规则添加成功');
  } catch (err) {
    logger.error('创建进化规则失败', err);
    ElMessage.error('创建规则失败，请稍后重试');
  }
}

async function toggleRule(rule: EvolutionRule): Promise<void> {
  const previous = rule.enabled;

  try {
    await updateEvolutionRule(rule.id, { enabled: rule.enabled });
    ElMessage.success(`规则「${rule.name}」${rule.enabled ? '已启用' : '已禁用'}`);
  } catch (err) {
    rule.enabled = previous;
    logger.error('切换规则状态失败', err);
    ElMessage.error('操作失败，请稍后重试');
  }
}

async function deleteRule(rule: EvolutionRule): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认删除规则「${rule.name}」？`, '删除确认', { type: 'warning' });
    await deleteEvolutionRule(rule.id);
    rules.value = rules.value.filter((r) => r.id !== rule.id);
    ElMessage.success('规则已删除');
  } catch (err) {
    if (err === 'cancel' || err === 'close') return;
    logger.error('删除进化规则失败', err);
    ElMessage.error('删除规则失败，请稍后重试');
  }
}

// ─── Chart ───
function initFeedbackChart(): void {
  if (!feedbackChartRef.value) return;
  if (fbChart) fbChart.dispose();

  fbChart = echarts.init(feedbackChartRef.value);
  fbChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['正面反馈', '负面反馈'], bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '12%', top: '10%', containLabel: true },
    xAxis: {
      type: 'category',
      data: feedback.value.trend_dates,
      axisLabel: { color: '#999999', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#999999', fontSize: 11 },
      splitLine: { lineStyle: { color: '#F0EDE5' } }, // 阳模式边框亮色
    },
    series: [
      {
        name: '正面反馈',
        type: 'bar',
        data: feedback.value.trend,
        itemStyle: { color: '#34C759', borderRadius: [4, 4, 0, 0] }, // 绿色成功色
        barWidth: '40%',
      },
    ],
  });
}

// ─── Lifecycle ───
let resizeHandler: (() => void) | null = null;

onMounted(async () => {
  await Promise.all([fetchRules(), fetchFeedback(), fetchLogs()]);
  nextTick(initFeedbackChart);
  resizeHandler = () => fbChart?.resize();
  window.addEventListener('resize', resizeHandler);
});

onUnmounted(() => {
  fbChart?.dispose();
  if (resizeHandler) window.removeEventListener('resize', resizeHandler);
});
</script>

<style scoped lang="scss">
.evolution-view {
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
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.tab-count {
  font-size: var(--font-size-caption);
  color: var(--text-tertiary);
}

.trigger-text {
  font-size: var(--font-size-small);
  color: var(--text-secondary);
  font-family: monospace;
}

/* ─── 优先级 ─── */
.priority-level {
  font-weight: 600;
}
.priority--high {
  color: var(--status-error);
}
.priority--mid {
  color: var(--status-warning);
}
.priority--low {
  color: var(--text-tertiary);
}

/* ─── 反馈 ─── */
.feedback-grid {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.feedback-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.stat-card {
  padding: 20px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: center;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 8px;

  &--positive {
    color: var(--status-healthy);
  }
  &--negative {
    color: var(--status-error);
  }
}

.stat-label {
  font-size: var(--font-size-caption);
  color: var(--text-tertiary);
}

.feedback-chart {
  width: 100%;
  height: 280px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  padding: 16px;
}

.section-title {
  font-size: var(--font-size-card-title);
  font-weight: 600;
  margin: 0 0 12px;
  color: var(--text-primary);
}

.feedback-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.feedback-item {
  padding: 12px 16px;
  background: var(--bg-card);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-sm);
}

.fb-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}

.fb-user {
  font-weight: 600;
  font-size: var(--font-size-caption);
  color: var(--text-primary);
}

.fb-time {
  margin-left: auto;
  font-size: var(--font-size-small);
  color: var(--text-tertiary);
}

.fb-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.fb-query {
  font-size: var(--font-size-caption);
  color: var(--text-secondary);
}

.fb-comment {
  font-size: var(--font-size-small);
  color: var(--text-tertiary);
  font-style: italic;
}

/* ─── 日志 ─── */
.log-card {
  padding: 12px;
  background: var(--bg-card);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-sm);
}

.log-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}

.log-title {
  font-weight: 600;
  font-size: var(--font-size-caption);
  color: var(--text-primary);
}

.log-desc {
  margin: 0 0 8px;
  font-size: var(--font-size-caption);
  color: var(--text-secondary);
  line-height: 1.5;
}

.log-meta {
  display: flex;
  gap: 20px;
  font-size: var(--font-size-small);
  color: var(--text-tertiary);
}

/* ─── Diff ─── */
.log-diff {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--bg-divider);
}

.diff-header {
  font-size: var(--font-size-small);
  font-weight: 600;
  color: var(--text-tertiary);
  margin-bottom: 6px;
}

.diff-content {
  font-family: monospace;
  font-size: var(--font-size-small);
  background: var(--bg-subtle);
  border-radius: 6px;
  padding: 8px 12px;
}

.diff-line {
  line-height: 1.6;
  white-space: pre-wrap;
}

.diff-line--old {
  color: var(--status-error);
  .diff-prefix {
    margin-right: 4px;
  }
}

.diff-line--new {
  color: var(--status-healthy);
  .diff-prefix {
    margin-right: 4px;
  }
}

/* ─── 响应式 ─── */
@media (max-width: 767px) {
  .evolution-view {
    padding: 16px 12px;
  }
  .feedback-stats {
    grid-template-columns: 1fr;
  }
}
</style>
