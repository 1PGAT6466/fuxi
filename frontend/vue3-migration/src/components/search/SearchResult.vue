<template>
  <div class="search-result">
    <div class="result-header">
      <h3 class="result-title" v-html="highlightQuery(result.title)" />
      <div class="result-score">
        <el-tag :type="getScoreType(result.score)" size="small">
          {{ (result.score * 100).toFixed(0) }}% 匹配
        </el-tag>
      </div>
    </div>

    <div class="result-content">
      <p class="result-excerpt" v-html="highlightQuery(result.excerpt)" />
    </div>

    <div class="result-meta">
      <span v-if="result.source" class="result-source">
        <el-icon><Document /></el-icon>
        {{ result.source }}
      </span>
      <span v-if="result.date" class="result-date">
        <el-icon><Calendar /></el-icon>
        {{ formatDateOnly(result.date) }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Document, Calendar } from '@element-plus/icons-vue';
import DOMPurify from 'dompurify';
import { getScoreType, formatDateOnly } from '@/utils/helpers';

defineProps<{
  result: {
    id: string;
    title: string;
    excerpt: string;
    score: number;
    source?: string;
    date?: string;
  };
}>();

// 高亮搜索关键词（简易实现，后续可升级为完整的高亮组件）
function highlightQuery(text: string | null | undefined): string {
  if (!text) return '';
  // 基础 HTML 转义
  const escaped = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  return DOMPurify.sanitize(escaped);
}
</script>

<style scoped lang="scss">
.search-result {
  background: var(--bg-secondary);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 12px;
  box-shadow: var(--shadow-sm);
  transition:
    box-shadow 0.2s ease,
    background-color 0.3s ease;

  &:hover {
    box-shadow: var(--shadow-md);
  }
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 8px;
}

.result-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.4;
}

.result-content {
  margin-bottom: 12px;
}

.result-excerpt {
  margin: 0;
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.result-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--text-tertiary);

  span {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .el-icon {
    font-size: 14px;
  }
}
</style>
