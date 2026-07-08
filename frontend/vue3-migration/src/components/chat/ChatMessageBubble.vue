<!--
  伏羲 v2.2 — 消息气泡组件（SAG Event 粒度改造）
  支持用户/AI 消息区分、Markdown 渲染、Event 粒度引用溯源
-->
<template>
  <div class="message-bubble" :class="[message.role]">
    <!-- 头像 -->
    <div class="bubble-avatar">
      <div v-if="message.role === 'user'" class="avatar user-avatar">
        <el-icon :size="18"><User /></el-icon>
      </div>
      <div v-else class="avatar ai-avatar">
        <span class="bagua-symbol">☰</span>
      </div>
    </div>

    <!-- 内容区 -->
    <div class="bubble-content">
      <div class="bubble-name">
        {{ message.role === 'user' ? '你' : '伏羲' }}
      </div>

      <!-- Markdown 渲染 -->
      <div class="bubble-text" v-html="safeContent" />

      <!-- SAG Event 粒度引用溯源卡片 -->
      <div v-if="hasEvents" class="bubble-references bubble-references--events">
        <div class="references-header">
          <el-icon :size="14"><Link /></el-icon>
          <span>引用来源（Event 粒度）</span>
        </div>

        <!-- 按文档分组展示 Events -->
        <div
          v-for="(docGroup, docIdx) in eventDocs"
          :key="docIdx"
          class="event-doc-group"
        >
          <div class="event-doc-header">
            <el-icon><Document /></el-icon>
            <span>{{ docGroup.title }}</span>
            <el-tag size="small" type="info" effect="plain">
              {{ docGroup.events.length }} Event
            </el-tag>
          </div>

          <div
            v-for="event in docGroup.events"
            :key="event.event_id"
            class="event-card"
            :class="{ 'event-card--expanded': expandedEventId === event.event_id }"
            @click="toggleEventExpand(event)"
          >
            <!-- Event 卡片头 -->
            <div class="event-card-header">
              <div class="event-title">
                <el-icon :size="12"><Collection /></el-icon>
                <span>{{ truncateText(event.content, 50) }}</span>
              </div>
              <div class="event-score">
                <span class="score-value">{{ (event.score * 100).toFixed(0) }}</span>
                <span class="score-unit">%</span>
              </div>
            </div>

            <!-- 实体标签 -->
            <div v-if="event.entities?.length" class="event-entities">
              <span
                v-for="entity in event.entities"
                :key="entity.name"
                class="entity-tag"
                :style="{ background: entityColorBg(entity.color), color: entity.color }"
              >
                {{ entity.name }}
              </span>
            </div>

            <!-- 检索路径标识 -->
            <div class="event-path">
              <el-tag
                :type="getPathType(event.retrieval_path)"
                size="small"
                effect="dark"
                class="path-tag"
              >
                {{ getPathLabel(event.retrieval_path) }}
              </el-tag>
              <span v-if="event.retrieval_path?.hop_count != null" class="path-hop">
                {{ event.retrieval_path.hop_count }} hop
              </span>
            </div>

            <!-- 悬停展开的完整内容 -->
            <div v-if="expandedEventId === event.event_id" class="event-detail">
              <div class="event-full-content">
                <div class="event-full-content__label">完整内容：</div>
                <p>{{ event.content }}</p>
              </div>

              <!-- text_span 原文跳转 -->
              <div v-if="event.text_span" class="event-span-action">
                <el-button
                  size="small"
                  type="primary"
                  text
                  @click.stop="showSpanPreview(event)"
                >
                  <el-icon :size="12"><View /></el-icon>
                  查看原文
                </el-button>
                <span class="span-location">
                  {{ event.text_span.doc_name }}
                  · offset {{ event.text_span.start_offset }}-{{ event.text_span.end_offset }}
                </span>
              </div>

              <div class="event-meta-detail">
                <span>chunk: {{ event.chunk_id }}</span>
                <span v-if="event.retrieval_path?.trigger_entity">
                  触发实体: {{ event.retrieval_path.trigger_entity }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 传统 Chunk 粒度引用（向后兼容：无 events 时回退） -->
      <div v-else-if="message.references?.length" class="bubble-references">
        <div class="references-header">
          <el-icon :size="14"><Link /></el-icon>
          <span>引用来源</span>
        </div>
        <a
          v-for="ref in message.references"
          :key="ref.id"
          class="reference-card"
          :href="ref.url || '#'"
          :target="ref.url ? '_blank' : undefined"
        >
          <div class="reference-type">
            <el-icon v-if="ref.type === 'document'" :size="14"><Document /></el-icon>
            <el-icon v-else-if="ref.type === 'knowledge'" :size="14"><Collection /></el-icon>
            <el-icon v-else :size="14"><Link /></el-icon>
          </div>
          <div class="reference-info">
            <div class="reference-title">{{ ref.title }}</div>
            <div v-if="ref.snippet" class="reference-snippet">{{ ref.snippet }}</div>
          </div>
        </a>
      </div>

      <!-- Span 原文弹窗 -->
      <el-dialog
        v-model="spanDialogVisible"
        title="原文定位"
        width="640px"
        :close-on-click-modal="true"
        destroy-on-close
      >
        <div v-if="spanDialogEvent?.text_span" class="span-preview-dialog">
          <div class="span-preview-meta">
            <el-tag size="small">{{ spanDialogEvent.text_span.doc_name }}</el-tag>
            <span>offset {{ spanDialogEvent.text_span.start_offset }} → {{ spanDialogEvent.text_span.end_offset }}</span>
          </div>
          <div class="span-preview-content" v-html="highlightedSpanSnippet" />
        </div>
      </el-dialog>

      <!-- 元信息 -->
      <div class="bubble-meta">
        <span class="meta-time">{{ formatTime(message.timestamp) }}</span>
        <span v-if="message.confidence != null" class="meta-confidence">
          置信度 {{ (message.confidence * 100).toFixed(0) }}%
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onUnmounted } from 'vue';
import { User, Link, Document, Collection, View } from '@element-plus/icons-vue';
import { renderMarkdown } from '@/utils/markdown';
import { formatTime } from '@/utils/helpers';
import DOMPurify from 'dompurify';
import type { ChatMessage, EventReference, RetrievalPath } from '@/types';

const props = defineProps<{
  message: ChatMessage;
}>();

const safeContent = computed(() => renderMarkdown(props.message.content));

// ───── Event 粒度引用 ─────
const expandedEventId = ref<string | null>(null);
const spanDialogVisible = ref(false);
const spanDialogEvent = ref<EventReference | null>(null);

/** 当前消息是否包含 Event 粒度引用 */
const hasEvents = computed(() => {
  return props.message.references?.some((ref) => ref.events && ref.events.length > 0) ?? false;
});

/** 按文档分组 Events */
interface DocEventGroup {
  title: string;
  events: EventReference[];
}

const eventDocs = computed<DocEventGroup[]>(() => {
  const groups: Record<string, DocEventGroup> = {};

  for (const ref of props.message.references || []) {
    if (!ref.events?.length) continue;
    const key = ref.title || ref.id;
    if (!groups[key]) {
      groups[key] = { title: ref.title, events: [] };
    }
    groups[key].events.push(...ref.events);
  }

  return Object.values(groups);
});

function toggleEventExpand(event: EventReference): void {
  // 使用 event_id 字符串比较，避免对象引用失效
  const eventId = event?.event_id;
  if (!eventId) return;
  expandedEventId.value =
    expandedEventId.value === eventId ? null : eventId;
}

function showSpanPreview(event: EventReference): void {
  // 防御：确保 event 有有效的 text_span 才展示原文
  if (!event?.text_span) return;
  spanDialogEvent.value = event;
  spanDialogVisible.value = true;
}

// 组件卸载时清理弹窗状态
onUnmounted(() => {
  spanDialogVisible.value = false;
  spanDialogEvent.value = null;
  expandedEventId.value = null;
});

const highlightedSpanSnippet = computed(() => {
  const span = spanDialogEvent.value?.text_span;
  if (!span) return '';
  const text = DOMPurify.sanitize(span.snippet);
  // 高亮 span 区域（简单高亮整个 snippet）
  return `<p class="span-snippet-text">${text}</p>`;
});

// ───── 工具函数 ─────
function truncateText(text: string, maxLen: number): string {
  if (!text || text.length <= maxLen) return text || '';
  return text.slice(0, maxLen) + '…';
}

function entityColorBg(color: string): string {
  // 使用 CSS color-mix 创建半透明背景（不支持时回退到 10% hex）
  // 优先使用 color-mix 以兼容 rgb/hsl/颜色名等格式
  if (!color) return 'transparent';
  return `color-mix(in srgb, ${color} 10%, transparent)`;
}

function getPathType(path?: RetrievalPath): 'success' | 'warning' | '' {
  if (!path) return '';
  switch (path.source) {
    case 'entity_guided':
      return 'success';
    case 'query_time_expansion':
      return 'warning';
    default:
      return '';
  }
}

function getPathLabel(path?: RetrievalPath): string {
  if (!path) return 'Path B';
  switch (path.source) {
    case 'entity_guided':
      return 'Path A · 实体引导';
    case 'query_time_expansion':
      return 'Path A · 查询扩展';
    case 'vector_direct':
      return 'Path B · 向量直接';
  }
}
</script>

<style scoped lang="scss">
.message-bubble {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
  max-width: 85%;

  &.user {
    margin-left: auto;
    flex-direction: row-reverse;

    .bubble-content {
      align-items: flex-end;
    }
  }

  &.assistant {
    margin-right: auto;
  }
}

/* ───── 头像 ───── */

.bubble-avatar {
  flex-shrink: 0;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
}

.user-avatar {
  background: var(--fuxi-primary-light);
  color: var(--fuxi-primary);
}

.ai-avatar {
  background: linear-gradient(135deg, var(--qian-color-light), var(--kun-color-light));
  color: var(--qian-color);

  .bagua-symbol {
    font-size: 16px;
    font-weight: bold;
  }
}

/* ───── 内容区 ───── */

.bubble-content {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.bubble-name {
  font-size: 12px;
  color: var(--fuxi-text-tertiary);
  margin-bottom: 4px;
  padding: 0 4px;
}

.bubble-text {
  padding: 12px 16px;
  background: var(--fuxi-bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--fuxi-shadow-sm);
  font-size: 14px;
  line-height: 1.7;
  color: var(--fuxi-text);
  word-break: break-word;

  .user & {
    background: var(--fuxi-bubble-user, #FFF3E8);
    color: var(--fuxi-primary-dark, #E55A00);
  }

  &:empty {
    min-height: 20px;
    padding: 10px 16px;
  }

  :deep(p) { margin: 0 0 8px; &:last-child { margin-bottom: 0; } }
  :deep(code) {
    background: rgba(128, 128, 128, 0.12);
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.92em;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    color: var(--fuxi-primary);
  }
  :deep(pre) {
    background: var(--fuxi-bg, #FAFAF5);
    border: 1px solid var(--fuxi-border, #E8E4D9);
    color: var(--fuxi-text-primary, #333333);
    padding: 16px; border-radius: var(--fuxi-radius-input, 8px);
    overflow-x: auto; margin: 8px 0;
    code { background: none; padding: 0; color: inherit; }
  }
  [data-theme='dark'] :deep(pre) {
    background: #1A1A2E;
    border-color: #333355;
    color: #E0E0E0;
  }
  :deep(a) { color: var(--fuxi-primary); text-decoration: none; &:hover { text-decoration: underline; } }
  :deep(ul), :deep(ol) { padding-left: 20px; margin: 8px 0; }
  :deep(blockquote) {
    border-left: 3px solid var(--fuxi-primary);
    padding-left: 12px; margin: 8px 0;
    color: var(--fuxi-text-secondary);
  }
  :deep(table) {
    border-collapse: collapse; width: 100%; margin: 8px 0;
    th, td { border: 1px solid var(--fuxi-border); padding: 8px 12px; text-align: left; }
    th { background: var(--fuxi-bg-subtle); }
  }
}

/* ───── Event 粒度引用 ───── */

.bubble-references {
  margin-top: 8px;
}

.references-header {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--fuxi-text-tertiary);
  margin-bottom: 8px;
  padding: 0 4px;
}

.event-doc-group {
  margin-bottom: 10px;
  border: 1px solid var(--fuxi-border);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.event-doc-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: var(--fuxi-bg-subtle);
  font-size: 13px;
  font-weight: 600;
  color: var(--fuxi-text);
  border-bottom: 1px solid var(--fuxi-border);
}

.event-card {
  padding: 10px 12px;
  border-bottom: 1px solid var(--fuxi-border);
  cursor: pointer;
  transition: background 0.2s var(--ease-out);

  &:last-child {
    border-bottom: none;
  }

  &:hover {
    background: var(--fuxi-bg-subtle);
  }

  &--expanded {
    background: var(--brand-soft);
  }
}

.event-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.event-title {
  display: flex;
  align-items: flex-start;
  gap: 4px;
  font-size: 13px;
  font-weight: 500;
  color: var(--fuxi-text);
  line-height: 1.4;
  flex: 1;
  min-width: 0;

  .el-icon {
    flex-shrink: 0;
    margin-top: 2px;
    color: var(--fuxi-primary);
  }
}

.event-score {
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 700;
  color: var(--brand);

  .score-unit {
    font-size: 10px;
    font-weight: 400;
  }
}

.event-entities {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
}

.entity-tag {
  display: inline-block;
  padding: 1px 7px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 500;
  line-height: 1.5;
}

.event-path {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
}

.path-tag {
  font-size: 11px;
}

.path-hop {
  font-size: 11px;
  color: var(--fuxi-text-tertiary);
}

/* ───── Event 展开详情 ───── */

.event-detail {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--fuxi-border);
}

.event-full-content {
  &__label {
    font-size: 11px;
    color: var(--fuxi-text-tertiary);
    margin-bottom: 4px;
  }

  p {
    margin: 0;
    font-size: 13px;
    line-height: 1.6;
    color: var(--fuxi-text);
  }
}

.event-span-action {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}

.span-location {
  font-size: 11px;
  color: var(--fuxi-text-tertiary);
}

.event-meta-detail {
  margin-top: 6px;
  font-size: 11px;
  color: var(--fuxi-text-tertiary);
  display: flex;
  gap: 12px;
}

/* ───── 原文 Span 弹窗 ───── */

.span-preview-dialog {
  .span-preview-meta {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
    font-size: 12px;
    color: var(--fuxi-text-secondary);
  }

  .span-preview-content {
    padding: 16px;
    background: var(--fuxi-bg-subtle);
    border-radius: var(--radius-sm);
    font-size: 14px;
    line-height: 1.8;
    color: var(--fuxi-text);

    :deep(.span-snippet-text) {
      margin: 0;
      white-space: pre-wrap;
    }
  }
}

/* ───── 传统 Chunk 引用（向后兼容） ───── */

.reference-card {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 12px;
  background: var(--fuxi-bg-card);
  border: 1px solid var(--fuxi-border);
  border-radius: var(--radius-sm);
  margin-bottom: 4px;
  text-decoration: none;
  transition: all 0.2s var(--ease-out);

  &:hover {
    border-color: var(--fuxi-primary);
    box-shadow: var(--fuxi-shadow-sm);
  }
}

.reference-type {
  flex-shrink: 0;
  color: var(--fuxi-primary);
  margin-top: 2px;
}

.reference-info {
  min-width: 0;
}

.reference-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--fuxi-text);
}

.reference-snippet {
  font-size: 12px;
  color: var(--fuxi-text-secondary);
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ───── 元信息 ───── */

.bubble-meta {
  display: flex;
  gap: 8px;
  margin-top: 4px;
  padding: 0 4px;
  font-size: 11px;
  color: var(--fuxi-text-tertiary);
}
</style>
