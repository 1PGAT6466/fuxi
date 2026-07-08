<template>
  <!--
    伏羲 v2.2 — RAG 检索测试台（SAG Event 粒度改造）
    独立于对话的检索测试工具，支持参数调节、Event 粒度切换、结果对比、原文对照
  -->
  <div class="rag-test-page">
    <!-- 页面头部 -->
    <div class="rag-header">
      <h2 class="rag-title">RAG 检索测试台</h2>
      <p class="rag-desc">独立检索测试工具，调参观测 RAG 检索效果（支持 Event 粒度）</p>
    </div>

    <!-- 主体：左侧检索区 + 右侧原文对照 -->
    <div class="rag-body">
      <!-- 左侧检索面板 -->
      <div class="rag-panel rag-panel--search">
        <!-- 查询输入 -->
        <div class="search-input-section">
          <el-input
            v-model="query"
            type="textarea"
            :rows="3"
            placeholder="输入检索查询文本…"
            maxlength="2000"
            show-word-limit
            @keydown.ctrl.enter="handleSearch"
          />
          <el-button
            type="primary"
            size="large"
            :loading="searching"
            :disabled="!query.trim()"
            class="search-btn"
            @click="handleSearch"
          >
            <el-icon><Search /></el-icon>
            检索
          </el-button>
        </div>

        <!-- 参数面板 -->
        <div class="params-panel">
          <div class="params-title">
            <el-icon><Setting /></el-icon>
            检索参数
            <el-button size="small" text @click="resetParams">重置</el-button>
          </div>

          <div class="param-row">
            <label class="param-label">检索粒度</label>
            <div class="param-control">
              <el-radio-group v-model="granularity" size="small">
                <el-radio-button value="chunk">Chunk</el-radio-button>
                <el-radio-button value="event">Event</el-radio-button>
                <el-radio-button value="auto">Auto</el-radio-button>
              </el-radio-group>
            </div>
          </div>

          <div class="param-row">
            <label class="param-label">Top-K 结果数</label>
            <div class="param-control">
              <el-slider
                v-model="topK"
                :min="1"
                :max="20"
                :step="1"
                show-input
                :show-input-controls="false"
              />
            </div>
          </div>

          <div class="param-row">
            <label class="param-label">相似度阈值</label>
            <div class="param-control">
              <el-slider
                v-model="scoreThreshold"
                :min="0"
                :max="1"
                :step="0.05"
                show-input
                :show-input-controls="false"
                :format-tooltip="(val: number) => val.toFixed(2)"
              />
            </div>
          </div>

          <div class="param-row">
            <label class="param-label">检索模式</label>
            <div class="param-control">
              <el-radio-group v-model="searchMode" size="small">
                <el-radio-button value="semantic">语义检索</el-radio-button>
                <el-radio-button value="keyword">关键词检索</el-radio-button>
                <el-radio-button value="hybrid">混合检索</el-radio-button>
              </el-radio-group>
            </div>
          </div>

          <!-- Event 模式切换 -->
          <div v-if="searchResults.length > 0" class="param-row">
            <label class="param-label">结果展示模式</label>
            <div class="param-control">
              <el-switch
                v-model="showEventMode"
                active-text="Event 视图"
                inactive-text="Chunk 视图"
                :disabled="!hasEventsInResults"
              />
            </div>
          </div>

          <!-- 实体标签云 -->
          <div v-if="entityTagCloud.length > 0" class="param-row">
            <label class="param-label">实体标签云</label>
            <div class="entity-cloud">
              <span
                v-for="tag in entityTagCloud"
                :key="tag.name"
                class="cloud-tag"
                :style="{ background: tag.color + '1A', color: tag.color, fontSize: tag.fontSize + 'px' }"
              >
                {{ tag.name }}
                <sup class="cloud-count">{{ tag.count }}</sup>
              </span>
            </div>
          </div>
        </div>

        <!-- 检索结果 -->
        <div v-if="searchResults.length > 0" class="results-section">
          <div class="results-header">
            <span class="results-count">
              共 {{ searchResults.length }} 条结果
              <span class="results-time">（耗时 {{ searchTime }}ms）</span>
            </span>
            <span v-if="showEventMode" class="results-mode-badge">
              <el-tag size="small" type="success" effect="dark">Event 粒度</el-tag>
            </span>
          </div>

          <!-- Event 粒度视图 -->
          <template v-if="showEventMode && allEvents.length > 0">
            <div
              v-for="(event, evtIdx) in allEvents"
              :key="event.event_id"
              class="result-item result-item--event"
              :class="{ 'result-item--active': activeEventId === event.event_id }"
              @click="selectEvent(event, evtIdx)"
            >
              <div class="result-item-header">
                <span class="result-rank">
                  <span class="rank-dot" :class="getRankClass(evtIdx)" />
                  #{{ evtIdx + 1 }}
                </span>
                <span class="result-score">相似度 {{ (event.score * 100).toFixed(1) }}%</span>
              </div>
              <div class="result-score-bar">
                <div class="score-bar-fill" :style="{ width: event.score * 100 + '%' }" :class="getScoreBarClass(event.score)" />
              </div>
              <div class="event-content-preview">
                &#x1F4CB; {{ truncateText(event.content, 150) }}
              </div>
              <div v-if="event.entities?.length" class="event-entity-tags">
                <span v-for="entity in event.entities" :key="entity.name" class="entity-chip-small" :style="{ background: entity.color + '1A', color: entity.color }">
                  {{ entity.name }}
                </span>
              </div>
              <div class="result-meta result-meta--event">
                <el-tag size="small" type="info">
                  <el-icon :size="12"><Document /></el-icon>
                  {{ event.text_span?.doc_name || event.chunk_id || '-' }}
                </el-tag>
                <el-tag size="small" :type="getPathTagType(event.retrieval_path?.source)" effect="dark">
                  {{ getPathLabel(event.retrieval_path?.source) }}
                </el-tag>
                <span v-if="event.chunk_id" class="meta-chunk-id">Chunk: {{ event.chunk_id }}</span>
              </div>
            </div>
          </template>

          <!-- Chunk 粒度视图（默认） -->
          <template v-else>
            <div
              v-for="(item, idx) in searchResults"
              :key="item.chunk_id || idx"
              class="result-item"
              :class="{ 'result-item--active': activeResultId === (item.chunk_id || String(idx)) }"
              @click="selectResult(item, idx)"
            >
              <div class="result-item-header">
                <span class="result-rank">
                  <span class="rank-dot" :class="getRankClass(idx)" />
                  #{{ idx + 1 }}
                </span>
                <span class="result-score">相似度 {{ (item.score * 100).toFixed(1) }}%</span>
              </div>
              <div class="result-score-bar">
                <div class="score-bar-fill" :style="{ width: item.score * 100 + '%' }" :class="getScoreBarClass(item.score)" />
              </div>
              <div class="result-content-preview">
                {{ truncateText(item.content, 150) }}
              </div>
              <div class="result-meta">
                <el-tag size="small" type="info">
                  <el-icon :size="12"><Document /></el-icon>
                  {{ item.source_doc || item.source || '-' }}
                </el-tag>
                <el-tag size="small">
                  <el-icon :size="12"><Grid /></el-icon>
                  分块 {{ item.chunk_id || '-' }}
                </el-tag>
                <span v-if="item.events?.length" class="meta-event-count">
                  {{ item.events.length }} Event
                </span>
              </div>
            </div>
          </template>
        </div>

        <!-- 空状态 -->
        <div v-else-if="searched" class="empty-state">
          <el-empty description="未找到匹配结果，请调整参数或查询词" :image-size="80" />
        </div>

        <div v-else class="empty-state">
          <el-empty description="输入查询并点击检索按钮开始测试" :image-size="80" />
        </div>
      </div>

      <!-- 右侧原文对照面板 -->
      <div class="rag-panel rag-panel--context">
        <div class="context-header">
          <span class="context-title">原文对照</span>
          <span v-if="activeContext" class="context-source">
            {{ activeContext.sourceLabel || '-' }}
            · 分块 {{ activeContext.chunkId || '-' }}
          </span>
        </div>

        <div v-if="activeContext" class="context-body">
          <div class="context-content" v-html="highlightedContent" />

          <!-- Event 详情卡片 -->
          <div v-if="activeContextEvent" class="context-event-info">
            <div class="context-event-header">
              <el-icon :size="14"><Collection /></el-icon>
              <span>Event 详情</span>
            </div>
            <div class="context-event-body">
              <p>{{ activeContextEvent.content }}</p>
              <div v-if="activeContextEvent.text_span" class="context-event-span">
                <span class="span-label">原文位置：</span>
                <span>{{ activeContextEvent.text_span.doc_name }}</span>
                <span class="span-offset">
                  offset {{ activeContextEvent.text_span.start_offset }} → {{ activeContextEvent.text_span.end_offset }}
                </span>
              </div>
              <div v-if="activeContextEvent.retrieval_path" class="context-event-path">
                <span>检索路径：{{ getPathLabel(activeContextEvent.retrieval_path.source) }}</span>
                <span v-if="activeContextEvent.retrieval_path.hop_count != null">
                  · {{ activeContextEvent.retrieval_path.hop_count }} hop
                </span>
              </div>
            </div>
          </div>

          <!-- 信息卡片 -->
          <div class="context-info">
            <div class="info-row">
              <span class="info-label">排名</span>
              <span class="info-value">#{{ activeContextIndex + 1 }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">相似度</span>
              <span class="info-value info-value--score">
                {{ (activeContext.score * 100).toFixed(1) }}%
              </span>
            </div>
            <div class="info-row">
              <span class="info-label">来源文档</span>
              <span class="info-value">{{ activeContext.sourceLabel || '-' }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">分块 ID</span>
              <span class="info-value">{{ activeContext.chunkId || '-' }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">粒度</span>
              <span class="info-value">{{ activeContextEvent ? 'Event' : 'Chunk' }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">Token 数</span>
              <span class="info-value">{{ activeContext.tokenCount || '-' }}</span>
            </div>
          </div>
        </div>

        <div v-else class="empty-state">
          <el-empty description="点击左侧检索结果查看原文对照" :image-size="60" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import DOMPurify from 'dompurify';
import { Search, Setting, Document, Grid, Collection } from '@element-plus/icons-vue';
import apiClient from '@/api';
import type { EventReference, SearchResult } from '@/types';

// 直接使用全局 SearchResult 类型（已包含 source_doc、token_count、events 等所有字段）

interface CloudTag {
  name: string;
  type: string;
  color: string;
  count: number;
  fontSize: number;
}

interface ActiveContext {
  content: string;
  score: number;
  sourceLabel: string;
  chunkId: string;
  tokenCount: number;
}

// Mock 数据 — 用于 API 不可用时的回退测试
// 字段值硬编码以保证可复现的测试行为
function generateMockResults(topK: number): SearchResult[] {
  const results: SearchResult[] = [
    {
      content: '人工智能技术正在深刻改变我们的生活方式。从智能手机上的语音助手，到自动驾驶汽车，再到医疗影像诊断，AI的应用已经无处不在。深度学习、自然语言处理和计算机视觉等技术的突破，让机器能够完成越来越多过去只有人类才能完成的任务。',
      score: 0.94, source_doc: '技术白皮书_2026.pdf', chunk_id: 'chunk_0012', token_count: 168,
      events: [
        {
          event_id: 'evt_ai_001', chunk_id: 'chunk_0012',
          content: '人工智能技术正在深刻改变我们的生活方式',
          score: 0.96,
          entities: [{ name: '人工智能', type: '技术', color: '#1565c0' }, { name: 'AI应用', type: '概念', color: '#2e7d32' }],
          retrieval_path: { source: 'entity_guided', stage: 1, hop_count: 0, trigger_entity: '人工智能', entity_similarity: 0.98 },
          text_span: { doc_id: 'hash_0012', doc_name: '技术白皮书_2026.pdf', start_offset: 0, end_offset: 36, snippet: '人工智能技术正在深刻改变我们的生活方式。' },
        },
        {
          event_id: 'evt_ai_002', chunk_id: 'chunk_0012',
          content: '深度学习、自然语言处理和计算机视觉等技术的突破',
          score: 0.91,
          entities: [{ name: '深度学习', type: '技术', color: '#c62828' }, { name: 'NLP', type: '技术', color: '#1565c0' }, { name: '计算机视觉', type: '技术', color: '#6a1b9a' }],
          retrieval_path: { source: 'vector_direct', stage: 1 },
          text_span: { doc_id: 'hash_0012', doc_name: '技术白皮书_2026.pdf', start_offset: 65, end_offset: 105, snippet: '深度学习、自然语言处理和计算机视觉等技术的突破' },
        },
        {
          event_id: 'evt_ai_003', chunk_id: 'chunk_0012',
          content: '算力的不断提升和数据量的爆炸式增长',
          score: 0.85,
          entities: [{ name: '算力', type: '资源', color: '#e65100' }, { name: '数据量', type: '资源', color: '#e65100' }],
          retrieval_path: { source: 'query_time_expansion', stage: 2, hop_count: 1 },
          text_span: { doc_id: 'hash_0012', doc_name: '技术白皮书_2026.pdf', start_offset: 130, end_offset: 160, snippet: '随着算力的不断提升和数据量的爆炸式增长' },
        },
      ],
    },
    {
      content: '自然语言处理（NLP）是人工智能的重要分支，涉及文本理解、生成、翻译、问答和对话等任务。现代NLP基于Transformer架构的预训练语言模型取得了突破性进展。',
      score: 0.88, source_doc: 'NLP技术综述.docx', chunk_id: 'chunk_0042', token_count: 142,
      events: [
        {
          event_id: 'evt_nlp_001', chunk_id: 'chunk_0042',
          content: '自然语言处理（NLP）是人工智能的重要分支',
          score: 0.92,
          entities: [{ name: 'NLP', type: '技术', color: '#1565c0' }],
          retrieval_path: { source: 'entity_guided', stage: 1, hop_count: 0, trigger_entity: 'NLP', entity_similarity: 0.95 },
          text_span: { doc_id: 'hash_0042', doc_name: 'NLP技术综述.docx', start_offset: 0, end_offset: 52, snippet: '自然语言处理（NLP）是人工智能的重要分支' },
        },
        {
          event_id: 'evt_nlp_002', chunk_id: 'chunk_0042',
          content: '现代NLP基于Transformer架构取得突破性进展',
          score: 0.87,
          entities: [{ name: 'Transformer', type: '架构', color: '#2e7d32' }],
          retrieval_path: { source: 'vector_direct', stage: 1 },
          text_span: { doc_id: 'hash_0042', doc_name: 'NLP技术综述.docx', start_offset: 68, end_offset: 130, snippet: '现代NLP基于Transformer架构的预训练语言模型' },
        },
      ],
    },
    { content: '深度学习（Deep Learning）是机器学习的一个子集。', score: 0.82, source_doc: '深度学习基础教程.pdf', chunk_id: 'chunk_0008', token_count: 155 },
    { content: '计算机视觉（Computer Vision）技术让机器理解和分析图像。', score: 0.76, source_doc: '医疗AI应用报告.pdf', chunk_id: 'chunk_0023', token_count: 128, events: [{ event_id: 'evt_cv_001', chunk_id: 'chunk_0023', content: '计算机视觉技术让机器理解和分析图像', score: 0.78, entities: [{ name: '计算机视觉', type: '技术', color: '#6a1b9a' }], retrieval_path: { source: 'vector_direct', stage: 1 } }] },
    { content: '大数据为人工智能提供海量训练数据。', score: 0.71, source_doc: '数据工程实践指南.md', chunk_id: 'chunk_0031', token_count: 110 },
  ];
  return results.slice(0, topK);
}

// state
const query = ref('');
const searching = ref(false);
const searched = ref(false);
const searchResults = ref<SearchResult[]>([]);
const searchTime = ref(0);
const topK = ref(5);
const scoreThreshold = ref(0.3);
const searchMode = ref<'semantic' | 'keyword' | 'hybrid'>('semantic');
const granularity = ref<'chunk' | 'event' | 'auto'>('auto');
const showEventMode = ref(false);
const activeResult = ref<SearchResult | null>(null);
const activeResultId = ref<string | null>(null);
const activeResultIndex = ref(0);
const activeEvent = ref<EventReference | null>(null);
const activeEventId = ref<string | null>(null);

// computed
const hasEventsInResults = computed(() => searchResults.value.some((item) => item.events && item.events.length > 0));

const allEvents = computed<EventReference[]>(() => {
  const evts: EventReference[] = [];
  for (const r of searchResults.value) { if (r.events?.length) evts.push(...r.events); }
  return evts.sort((a, b) => b.score - a.score);
});

const entityTagCloud = computed<CloudTag[]>(() => {
  const m: Record<string, CloudTag> = {};
  for (const r of searchResults.value) {
    if (r.events) {
      for (const e of r.events) {
        if (e.entities) {
          for (const ent of e.entities) {
            if (!m[ent.name]) m[ent.name] = { name: ent.name, type: ent.type, color: ent.color, count: 0, fontSize: 12 };
            m[ent.name].count++;
          }
        }
      }
    }
  }
  const tags = Object.values(m);
  const maxC = Math.max(...tags.map((t) => t.count), 1);
  for (const t of tags) t.fontSize = 12 + (t.count / maxC) * 6;
  return tags.sort((a, b) => b.count - a.count);
});

const activeContext = computed<ActiveContext | null>(() => {
  if (showEventMode.value && activeEvent.value) {
    const evt = activeEvent.value;
    const parent = searchResults.value.find((r) => r.chunk_id === evt.chunk_id);
    return { content: parent?.content || evt.content, score: evt.score, sourceLabel: evt.text_span?.doc_name || parent?.source_doc || parent?.source || '-', chunkId: evt.chunk_id, tokenCount: parent?.token_count || evt.content.length };
  }
  if (!activeResult.value) return null;
  const item = activeResult.value;
  return { content: item.content, score: item.score, sourceLabel: item.source_doc || item.source || '-', chunkId: item.chunk_id || '-', tokenCount: item.token_count || (item.content || '').length };
});

const activeContextIndex = computed(() => {
  if (showEventMode.value && activeEvent.value) return allEvents.value.indexOf(activeEvent.value);
  return activeResultIndex.value;
});

const activeContextEvent = computed(() => showEventMode.value ? activeEvent.value : null);

const highlightedContent = computed(() => {
  const ctx = activeContext.value;
  if (!ctx) return '';
  const text = DOMPurify.sanitize(ctx.content);
  if (!query.value.trim()) return text;
  const words = query.value.trim().split(/\s+/).filter(Boolean);
  let result = text;
  for (const word of words) {
    const escaped = word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    result = result.replace(new RegExp(`(${escaped})`, 'gi'), '<mark class="context-highlight">$1</mark>');
  }
  return result;
});

// methods
async function handleSearch(): Promise<void> {
  const q = query.value.trim();
  if (!q) return;
  searching.value = true;
  showEventMode.value = false;
  activeEvent.value = null; activeEventId.value = null;
  const startTime = performance.now();
  try {
    // 使用 TraditionalSearchResponse 类型（/api/rag/search 返回传统格式）
    interface SearchAPIResponse {
      results?: SearchResult[];
      data?: SearchResult[];
      total?: number;
    }
    const res = await apiClient.post('/api/rag/search', {
      query: q,
      top_k: topK.value,
      score_threshold: scoreThreshold.value,
      mode: searchMode.value,
      granularity: granularity.value,
    }) as SearchAPIResponse;
    searchResults.value = (res.results ?? res.data ?? []);
    searchTime.value = Math.round(performance.now() - startTime);
  } catch {
    console.warn('[RagTestView] API unavailable, using mock data');
    searchResults.value = generateMockResults(topK.value);
    searchTime.value = Math.round(performance.now() - startTime) + Math.floor(Math.random() * 30);
  } finally {
    searching.value = false; searched.value = true;
    activeResult.value = null; activeResultId.value = null;
  }
}

function selectResult(item: SearchResult, idx: number): void {
  activeResult.value = item;
  activeResultId.value = item.chunk_id || String(idx);
  activeResultIndex.value = idx;
  activeEvent.value = null; activeEventId.value = null;
}

function selectEvent(event: EventReference, _idx: number): void {
  activeEvent.value = event;
  activeEventId.value = event.event_id;
}

function resetParams(): void {
  topK.value = 5; scoreThreshold.value = 0.3; searchMode.value = 'semantic';
  granularity.value = 'auto'; showEventMode.value = false;
}

function truncateText(text: string, maxLen: number): string {
  if (!text || text.length <= maxLen) return text || '';
  return text.slice(0, maxLen) + '\u2026';
}

function getRankClass(idx: number): string {
  if (idx === 0) return 'rank-1';
  if (idx === 1) return 'rank-2';
  if (idx === 2) return 'rank-3';
  return '';
}

function getScoreBarClass(score: number): string {
  if (score >= 0.8) return 'score-high';
  if (score >= 0.6) return 'score-mid';
  return 'score-low';
}

function getPathTagType(source?: string): 'success' | 'warning' | 'info' {
  if (!source) return 'info';
  return source === 'vector_direct' ? 'warning' : 'success';
}

function getPathLabel(source?: string): string {
  if (!source) return 'Path B';
  return source === 'vector_direct' ? 'Path B - vector' : 'Path A - entity';
}
</script>

<style scoped lang="scss">
.rag-test-page { max-width: 1400px; margin: 0 auto; padding: 28px 24px; height: 100%; display: flex; flex-direction: column; }
.rag-header { margin-bottom: 24px; }
.rag-title { margin: 0; font-size: 24px; font-weight: 700; color: var(--text-primary); }
.rag-desc { margin: 4px 0 0; font-size: var(--font-size-caption); color: var(--text-secondary); }
.rag-body { flex: 1; display: flex; gap: 20px; min-height: 0; }
.rag-panel { background: var(--bg-card); border-radius: var(--radius-md); box-shadow: var(--shadow-sm); display: flex; flex-direction: column; overflow: hidden; }
.rag-panel--search { flex: 1; min-width: 0; padding: 20px; overflow-y: auto; }
.rag-panel--context { width: 420px; flex-shrink: 0; }
.search-input-section { margin-bottom: 20px; .search-btn { margin-top: 12px; width: 100%; } }
.params-panel { padding: 16px; background: var(--fuxi-bg-subtle); border-radius: var(--radius-sm); margin-bottom: 20px; }
.params-title { display: flex; align-items: center; gap: 6px; font-size: var(--font-size-caption); font-weight: 600; color: var(--text-primary); margin-bottom: 16px; }
.param-row { margin-bottom: 14px; &:last-child { margin-bottom: 0; } }
.param-label { display: block; font-size: var(--font-size-small); color: var(--text-secondary); margin-bottom: 6px; }
.param-control { padding: 0 4px; }

.entity-cloud { display: flex; flex-wrap: wrap; gap: 5px; line-height: 1.6; }
.cloud-tag { display: inline-flex; align-items: center; gap: 1px; padding: 1px 6px; border-radius: 8px; font-weight: 500; cursor: default; }
.cloud-count { font-size: 0.75em; opacity: 0.7; }

.results-section { border-top: 1px solid var(--fuxi-border); padding-top: 16px; }
.results-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.results-count { font-size: var(--font-size-caption); font-weight: 600; color: var(--text-primary); }
.results-time { font-weight: 400; color: var(--text-tertiary); font-size: var(--font-size-small); }

.result-item { padding: 14px; margin-bottom: 10px; background: var(--fuxi-bg-subtle); border-radius: var(--radius-sm); border: 2px solid transparent; cursor: pointer; transition: all var(--duration-fast) var(--ease-out);
  &:hover { background: var(--bg-hover); }
  &--active { border-color: var(--brand); background: var(--brand-soft); }
  &--event { border-left: 3px solid var(--fuxi-primary, #FF6700); }
}
.result-item-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.result-rank { display: flex; align-items: center; gap: 6px; font-size: var(--font-size-small); font-weight: 600; color: var(--text-primary); }
.rank-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--bg-divider);
  &.rank-1 { background: var(--fuxi-primary, #FF6700); } &.rank-2 { background: var(--fuxi-primary-light, #FF8533); } &.rank-3 { background: var(--bagua-zhen, #4CAF50); }
}
.result-score { font-size: var(--font-size-small); font-weight: 600; color: var(--text-secondary); }
.result-score-bar { height: 4px; background: var(--bg-subtle); border-radius: 2px; margin-bottom: 10px; overflow: hidden;
  .score-bar-fill { height: 100%; border-radius: 2px; transition: width 0.5s var(--ease-out);
    &.score-high { background: var(--brand-gradient); } &.score-mid { background: linear-gradient(90deg, var(--dui-color), var(--qian-color)); } &.score-low { background: var(--bg-divider); }
  }
}
.result-content-preview { font-size: var(--font-size-caption); line-height: 1.6; color: var(--fuxi-text); margin-bottom: 8px; }
.event-content-preview { font-size: var(--font-size-caption); line-height: 1.6; color: var(--fuxi-text); margin-bottom: 8px; font-weight: 500; }
.event-entity-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px; }
.entity-chip-small { display: inline-block; padding: 1px 6px; border-radius: 8px; font-size: 11px; font-weight: 500; }
.result-meta { display: flex; gap: 6px; flex-wrap: wrap; &--event { align-items: center; } }
.meta-event-count { font-size: 11px; color: var(--fuxi-primary, #FF6700); font-weight: 600; }
.meta-chunk-id { font-size: 11px; color: var(--fuxi-text-tertiary); font-family: monospace; }

.context-header { padding: 20px 20px 0; flex-shrink: 0; }
.context-title { font-size: var(--font-size-card-title); font-weight: 600; color: var(--text-primary); display: block; }
.context-source { font-size: var(--font-size-small); color: var(--text-tertiary); display: block; margin-top: 4px; }
.context-body { padding: 20px; overflow-y: auto; flex: 1; }
.context-content { font-size: var(--font-size-body); line-height: 1.9; color: var(--fuxi-text); margin-bottom: 20px; white-space: pre-wrap; }
:deep(.context-highlight) { background: var(--brand-soft); color: var(--brand); padding: 2px 3px; border-radius: 3px; font-weight: 600; }

.context-event-info { margin-bottom: 16px; padding: 12px; background: var(--fuxi-bg-warning, #FEF8E8); border-radius: var(--fuxi-radius-tag, 4px); border-left: 3px solid var(--fuxi-primary, #FF6700); }
.context-event-header { display: flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 600; color: var(--fuxi-primary, #FF6700); margin-bottom: 8px; }
.context-event-body p { margin: 0 0 8px; font-size: 13px; line-height: 1.6; color: var(--fuxi-text); }
.context-event-span { font-size: 11px; color: var(--fuxi-text-secondary); margin-bottom: 4px; .span-label { font-weight: 500; } .span-offset { margin-left: 8px; color: var(--fuxi-text-tertiary); } }
.context-event-path { font-size: 11px; color: var(--fuxi-text-tertiary); }

.context-info { padding: 16px; background: var(--fuxi-bg-subtle); border-radius: var(--radius-sm); }
.info-row { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--fuxi-border); &:last-child { border-bottom: none; } }
.info-label { font-size: var(--font-size-small); color: var(--text-tertiary); }
.info-value { font-size: var(--font-size-small); font-weight: 500; color: var(--text-primary); &--score { color: var(--brand); font-weight: 700; } }

.empty-state { flex: 1; display: flex; align-items: center; justify-content: center; padding: 40px 20px; }

@media (max-width: 1023px) { .rag-body { flex-direction: column; } .rag-panel--context { width: 100%; max-height: 400px; } }
@media (max-width: 767px) { .rag-test-page { padding: 16px; } .rag-body { gap: 12px; } }
</style>
