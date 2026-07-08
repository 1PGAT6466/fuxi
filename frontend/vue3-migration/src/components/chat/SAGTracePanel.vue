<!--
  伏羲 v2.2 — SAG 检索追踪可视化组件
  可视化三阶段流水线：种子检索 → 查询时扩展 → LLM Rerank
-->
<template>
  <div class="sag-trace-panel" v-if="trace">
    <div class="sag-trace-header">
      <div class="sag-trace-title">
        <el-icon :size="16"><DataAnalysis /></el-icon>
        <span>SAG 检索追踪</span>
      </div>
      <div class="sag-trace-stats">
        <el-tag size="small" type="info" effect="plain">
          {{ trace.total_candidates ?? totalCandidates }} 候选
        </el-tag>
        <el-tag size="small" :type="latencyType" effect="plain">
          {{ trace.latency_ms ?? '—' }}ms
        </el-tag>
      </div>
    </div>

    <div class="sag-trace-body">
      <!-- Step 1: 种子检索 -->
      <div class="trace-stage" :class="{ 'trace-stage--active': activeStage === 1 }">
        <div class="stage-header" @click="activeStage = activeStage === 1 ? 0 : 1">
          <div class="stage-indicator">
            <span class="stage-number">1</span>
            <span class="stage-label">种子检索</span>
          </div>
          <el-icon :class="{ 'rotate-icon': activeStage === 1 }">
            <ArrowDown />
          </el-icon>
        </div>

        <div v-if="activeStage === 1" class="stage-body">
          <!-- 提取的实体 -->
          <div v-if="trace.seed_entities.length" class="trace-section">
            <div class="section-label">
              <el-icon :size="12"><Collection /></el-icon>
              <span>提取实体</span>
              <span class="section-count">{{ trace.seed_entities.length }}</span>
            </div>
            <div class="entity-list">
              <span
                v-for="entity in trace.seed_entities"
                :key="entity.name"
                class="entity-chip"
                :class="getEntityClass(entity.type)"
              >
                {{ entity.name }}
                <span v-if="entity.score != null" class="entity-chip-score">
                  ({{ (entity.score * 100).toFixed(0) }}%)
                </span>
              </span>
            </div>
          </div>

          <!-- 种子事件 -->
          <div v-if="trace.seed_events.length" class="trace-section">
            <div class="section-label">
              <el-icon :size="12"><Grid /></el-icon>
              <span>初始事件</span>
              <span class="section-count">{{ trace.seed_events.length }}</span>
            </div>
            <div class="event-mini-list">
              <div
                v-for="evt in trace.seed_events.slice(0, 5)"
                :key="evt.event_id"
                class="event-mini-item"
                :title="evt.content"
              >
                <span class="event-mini-id">{{ evt.event_id }}</span>
                <span class="event-mini-content">{{ truncateText(evt.content, 40) }}</span>
                <span class="event-mini-score">{{ (evt.score * 100).toFixed(0) }}%</span>
              </div>
              <div v-if="trace.seed_events.length > 5" class="event-mini-more">
                还有 {{ trace.seed_events.length - 5 }} 个事件…
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 2: 查询时扩展 -->
      <div class="trace-stage" :class="{ 'trace-stage--active': activeStage === 2 }">
        <!-- 【修复 HIGH-4】Stage 2 折叠切换应跳转到 Stage 2 而非 Stage 1 -->
        <div class="stage-header" @click="activeStage = activeStage === 2 ? 0 : 2">
          <div class="stage-indicator">
            <span class="stage-number">2</span>
            <span class="stage-label">查询时扩展（Entity Frontier）</span>
          </div>
          <el-icon :class="{ 'rotate-icon': activeStage === 2 }">
            <ArrowDown />
          </el-icon>
        </div>

        <div v-if="activeStage === 2" class="stage-body">
          <!-- 扩展实体 -->
          <div v-if="trace.expanded_entities.length" class="trace-section">
            <div class="section-label">
              <el-icon :size="12"><Connection /></el-icon>
              <span>扩展实体（多跳）</span>
              <span class="section-count">{{ trace.expanded_entities.length }}</span>
            </div>

            <!-- 按 hop 分组 -->
            <div
              v-for="hop in hopGroups"
              :key="hop.hop"
              class="hop-group"
            >
              <div class="hop-label">H={{ hop.hop }}</div>
              <div class="entity-frontier">
                <template v-for="(item, i) in hop.entities" :key="item.name">
                  <span
                    v-if="i > 0"
                    class="edge-arrow"
                  >→</span>
                  <span class="entity-chip entity-chip--expanded">
                    {{ item.name }}
                    <span class="entity-chip-sim">{{ (item.similarity * 100).toFixed(0) }}%</span>
                  </span>
                </template>
              </div>
            </div>
          </div>

          <!-- 扩展事件 -->
          <div v-if="trace.expanded_events.length" class="trace-section">
            <div class="section-label">
              <el-icon :size="12"><Grid /></el-icon>
              <span>扩展事件</span>
              <span class="section-count">{{ trace.expanded_events.length }}</span>
            </div>
            <div class="event-mini-list">
              <div
                v-for="evt in trace.expanded_events.slice(0, 5)"
                :key="'exp-' + evt.event_id"
                class="event-mini-item event-mini-item--expanded"
                :title="evt.content"
              >
                <span class="event-mini-id">{{ evt.event_id }}</span>
                <span class="event-mini-content">{{ truncateText(evt.content, 40) }}</span>
                <span class="event-mini-score">{{ (evt.score * 100).toFixed(0) }}%</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 3: LLM Rerank -->
      <div class="trace-stage" :class="{ 'trace-stage--active': activeStage === 3 }">
        <!-- 【修复 HIGH-4】Stage 3 折叠切换应跳转到 Stage 3 而非 Stage 1 -->
        <div class="stage-header" @click="activeStage = activeStage === 3 ? 0 : 3">
          <div class="stage-indicator">
            <span class="stage-number">3</span>
            <span class="stage-label">LLM Rerank</span>
          </div>
          <el-icon :class="{ 'rotate-icon': activeStage === 3 }">
            <ArrowDown />
          </el-icon>
        </div>

        <div v-if="activeStage === 3" class="stage-body">
          <!-- 最终排序结果 -->
          <div v-if="trace.reranked_events.length" class="trace-section">
            <div class="section-label">
              <el-icon :size="12"><Trophy /></el-icon>
              <span>最终排序结果</span>
              <span class="section-count">{{ trace.reranked_events.length }}</span>
            </div>

            <div class="rerank-list">
              <div
                v-for="(evt, idx) in trace.reranked_events"
                :key="'rank-' + evt.event_id"
                class="rerank-item"
                :style="{ '--rank-opacity': 1 - idx * 0.08 }"
              >
                <span class="rerank-rank" :class="getRankClass(idx)">
                  #{{ idx + 1 }}
                </span>
                <span class="rerank-content">{{ truncateText(evt.content, 60) }}</span>
                <span class="rerank-score">{{ (evt.score * 100).toFixed(0) }}%</span>
                <el-tag
                  size="small"
                  :type="getPathTagType(evt.retrieval_path?.source)"
                  effect="dark"
                >
                  {{ getPathShortLabel(evt.retrieval_path?.source) }}
                </el-tag>
              </div>
            </div>
          </div>

          <!-- 统计摘要 -->
          <div class="trace-summary">
            <div class="summary-row">
              <span class="summary-label">Path A 结构化路径</span>
              <span class="summary-value">{{ pathACount }}</span>
            </div>
            <div class="summary-row">
              <span class="summary-label">Path B 传统路径</span>
              <span class="summary-value">{{ pathBCount }}</span>
            </div>
            <div class="summary-row summary-row--total">
              <span class="summary-label">去重合并 → 最终输出</span>
              <span class="summary-value summary-value--highlight">{{ trace.reranked_events.length }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 超图概览（极简版） -->
    <div v-if="trace.entity_hypergraph?.nodes?.length" class="sag-trace-footer">
      <div class="hypergraph-mini">
        <span class="hypergraph-label">
          <el-icon :size="12"><Share /></el-icon>
          实体超图: {{ trace.entity_hypergraph.nodes.length }} 节点,
          {{ trace.entity_hypergraph.edges.length }} 边
        </span>
      </div>
    </div>
  </div>

  <!-- Loading 状态 -->
  <div v-else-if="loading" class="sag-trace-panel sag-trace-panel--loading">
    <div class="sag-trace-loading">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>等待 SAG 检索追踪数据…</span>
    </div>
  </div>

  <!-- Empty 状态 -->
  <div v-else-if="showEmpty" class="sag-trace-panel sag-trace-panel--empty">
    <div class="sag-trace-empty">
      <span class="empty-icon">🔍</span>
      <span>暂无 SAG 追踪数据</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import {
  DataAnalysis,
  ArrowDown,
  Collection,
  Grid,
  Connection,
  Trophy,
  Share,
  Loading,
} from '@element-plus/icons-vue';
import type { SAGRetrievalTrace } from '@/types';

const props = withDefaults(defineProps<{
  trace: SAGRetrievalTrace | null;
  loading?: boolean;
  showEmpty?: boolean;
}>(), {
  loading: false,
  showEmpty: false,
});

const activeStage = ref<number>(0);

// ───── 计算属性 ─────

const totalCandidates = computed(() => {
  const t = props.trace;
  if (!t) return 0;
  return (t.seed_events?.length ?? 0) + (t.expanded_events?.length ?? 0);
});

const latencyType = computed(() => {
  const ms = props.trace?.latency_ms ?? 0;
  if (ms < 500) return 'success';
  if (ms < 2000) return 'warning';
  return 'danger';
});

/** 按 hop 分组扩展实体 */
const hopGroups = computed(() => {
  const entities = props.trace?.expanded_entities ?? [];
  const map: Record<number, typeof entities> = {};
  for (const entity of entities) {
    const hop = entity.hop ?? 0;
    if (!map[hop]) map[hop] = [];
    map[hop].push(entity);
  }
  return Object.entries(map)
    .map(([hop, items]) => ({ hop: Number(hop), entities: items }))
    .sort((a, b) => a.hop - b.hop);
});

const pathACount = computed(() => {
  return (props.trace?.reranked_events ?? []).filter(
    (e) => e.retrieval_path?.source === 'entity_guided' || e.retrieval_path?.source === 'query_time_expansion',
  ).length;
});

const pathBCount = computed(() => {
  return (props.trace?.reranked_events ?? []).filter(
    (e) => e.retrieval_path?.source === 'vector_direct',
  ).length;
});

// ───── 工具函数 ─────

function truncateText(text: string, maxLen: number): string {
  if (!text || text.length <= maxLen) return text || '';
  return text.slice(0, maxLen) + '…';
}

function getEntityClass(type: string): string {
  const typeMap: Record<string, string> = {
    材料: 'entity-material',
    指标: 'entity-metric',
    设备: 'entity-device',
    工艺: 'entity-process',
    产品: 'entity-product',
    标准: 'entity-standard',
  };
  return typeMap[type] || 'entity-default';
}

function getRankClass(idx: number): string {
  if (idx === 0) return 'rank-top1';
  if (idx === 1) return 'rank-top2';
  if (idx === 2) return 'rank-top3';
  return '';
}

function getPathTagType(source?: string): 'success' | 'warning' | 'info' {
  if (!source) return 'info';
  return source === 'vector_direct' ? 'warning' : 'success';
}

function getPathShortLabel(source?: string): string {
  if (!source) return 'B';
  return source === 'vector_direct' ? 'Path B' : 'Path A';
}
</script>

<style scoped lang="scss">
.sag-trace-panel {
  background: var(--fuxi-bg-card);
  border: 1px solid var(--fuxi-border);
  border-radius: var(--radius-md);
  margin-top: 12px;
  overflow: hidden;
}

.sag-trace-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--fuxi-bg-subtle);
  border-bottom: 1px solid var(--fuxi-border);
}

.sag-trace-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: var(--fuxi-text);
}

.sag-trace-stats {
  display: flex;
  gap: 8px;
}

/* ───── 阶段卡片 ───── */

.sag-trace-body {
  padding: 0;
}

.trace-stage {
  border-bottom: 1px solid var(--fuxi-border);

  &:last-child {
    border-bottom: none;
  }

  &--active {
    .stage-header {
      background: var(--brand-soft);
    }
  }
}

.stage-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  cursor: pointer;
  transition: background 0.15s var(--ease-out);
  user-select: none;

  &:hover {
    background: var(--fuxi-bg-subtle);
  }
}

.stage-indicator {
  display: flex;
  align-items: center;
  gap: 10px;
}

.stage-number {
width: 24px;
height: 24px;
border-radius: 50%;
background: var(--fuxi-primary, #FF6700);
color: #FFFFFF;
display: flex;
align-items: center;
justify-content: center;
font-size: 12px;
font-weight: 700;
flex-shrink: 0;
}

.stage-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--fuxi-text);
}

.rotate-icon {
  transform: rotate(180deg);
  transition: transform 0.2s var(--ease-out);
}

/* ───── 阶段展开内容 ───── */

.stage-body {
  padding: 12px 16px 16px;
}

.trace-section {
  margin-bottom: 14px;

  &:last-child {
    margin-bottom: 0;
  }
}

.section-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--fuxi-text-secondary);
  margin-bottom: 8px;
}

.section-count {
  color: var(--fuxi-text-tertiary);
  font-size: 11px;
}

/* ───── 实体标签 ───── */

.entity-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.entity-chip {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  background: var(--brand-soft);
  color: var(--brand);

  &--expanded {
    background: var(--fuxi-bg-warning, #FEF8E8);
    color: var(--fuxi-warning, #FAAD14);
  }

  &-score,
  &-sim {
    font-size: 10px;
    opacity: 0.7;
  }
}

// 实体类型色 — 与八宫色系协调
.entity-material  { background: rgba(76, 175, 80, 0.1); color: #2e7d32; }
.entity-metric   { background: rgba(58, 107, 140, 0.1); color: #1565c0; }
.entity-device   { background: rgba(229, 57, 53, 0.08); color: #c62828; }
.entity-process  { background: rgba(255, 103, 0, 0.08); color: #e65100; }
.entity-product  { background: rgba(106, 27, 154, 0.08); color: #6a1b9a; }
.entity-standard { background: rgba(0, 105, 92, 0.08); color: #00695c; }
.entity-default  { background: var(--fuxi-bg-tertiary, #F5F2ED); color: var(--fuxi-text-secondary, #666666); }

/* ───── 实体前沿 (多跳) ───── */

.hop-group {
  margin-bottom: 8px;

  &:last-child {
    margin-bottom: 0;
  }
}

.hop-label {
  font-size: 11px;
  font-weight: 700;
  color: var(--brand);
  margin-bottom: 4px;
}

.entity-frontier {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}

.edge-arrow {
  color: var(--fuxi-text-tertiary);
  font-size: 12px;
  margin: 0 2px;
}

/* ───── 事件迷你列表 ───── */

.event-mini-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.event-mini-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 8px;
  background: var(--fuxi-bg-subtle);
  border-radius: 4px;
  font-size: 12px;

  &--expanded {
    background: var(--fuxi-bg-warning, #FEF8E8);
  }
}

.event-mini-id {
  font-family: monospace;
  font-size: 11px;
  color: var(--fuxi-text-tertiary);
  flex-shrink: 0;
}

.event-mini-content {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--fuxi-text);
}

.event-mini-score {
  font-weight: 600;
  color: var(--brand);
  flex-shrink: 0;
}

.event-mini-more {
  font-size: 11px;
  color: var(--fuxi-text-tertiary);
  padding: 4px 0;
}

/* ───── Rerank 列表 ───── */

.rerank-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.rerank-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  background: var(--fuxi-bg-subtle);
  border-radius: 4px;
  opacity: var(--rank-opacity, 1);
}

.rerank-rank {
  font-size: 11px;
  font-weight: 700;
  width: 24px;
  flex-shrink: 0;

  &.rank-top1 { color: var(--fuxi-primary, #FF6700); }
  &.rank-top2 { color: var(--dui-color); }
  &.rank-top3 { color: var(--zhen-color); }
}

.rerank-content {
  flex: 1;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--fuxi-text);
}

.rerank-score {
  font-size: 12px;
  font-weight: 600;
  color: var(--brand);
  flex-shrink: 0;
}

/* ───── 统计摘要 ───── */

.trace-summary {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed var(--fuxi-border);
}

.summary-row {
  display: flex;
  justify-content: space-between;
  padding: 3px 0;
  font-size: 12px;

  &--total {
    margin-top: 4px;
    padding-top: 6px;
    border-top: 1px solid var(--fuxi-border);
  }
}

.summary-label {
  color: var(--fuxi-text-secondary);
}

.summary-value {
  font-weight: 600;
  color: var(--fuxi-text);

  &--highlight {
    color: var(--brand);
  }
}

/* ───── 超图概览 ───── */

.sag-trace-footer {
  padding: 8px 16px;
  border-top: 1px solid var(--fuxi-border);
}

.hypergraph-mini {
  font-size: 12px;
}

.hypergraph-label {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--fuxi-text-tertiary);
}

/* ───── Loading / Empty ───── */

.sag-trace-panel--loading,
.sag-trace-panel--empty {
  padding: 20px;
}

.sag-trace-loading,
.sag-trace-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 13px;
  color: var(--fuxi-text-tertiary);
}

.sag-trace-empty {
  .empty-icon {
    font-size: 18px;
  }
}
</style>
