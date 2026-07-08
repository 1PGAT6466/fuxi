<template>
  <!--
    伏羲 v2.1 — 文本分类面板
  -->
  <div class="classify-panel">
    <div class="panel-desc">自动对文本进行分类，返回各类别的置信度评分</div>

    <!-- 输入区 -->
    <div class="input-section">
      <el-input
        v-model="inputText"
        type="textarea"
        :rows="5"
        placeholder="请输入需要分类的文本…"
        maxlength="5000"
        show-word-limit
      />
    </div>

    <!-- 操作区 -->
    <div class="action-section">
      <el-button
        type="primary"
        :loading="loading"
        :disabled="!inputText.trim()"
        @click="handleClassify"
      >
        <el-icon><Collection /></el-icon>
        开始分类
      </el-button>
    </div>

    <!-- 错误态 -->
    <div v-if="error" class="error-section">
      <el-result icon="error" title="分类失败" sub-title="请检查网络连接后重试">
        <template #extra>
          <el-button type="primary" size="small" @click="handleClassify">重试</el-button>
        </template>
      </el-result>
    </div>

    <!-- 空态 -->
    <div v-else-if="showEmpty" class="empty-section">
      <el-empty description="未获取到分类结果，请尝试其他文本" :image-size="60" />
    </div>

    <!-- 结果区 -->
    <div v-if="results.length > 0" class="result-section">
      <div class="result-header">
        <span class="result-title">分类结果</span>
        <span class="result-subtitle">
          最佳匹配：<strong>{{ results[0]?.category }}</strong> （{{
            (results[0]?.confidence * 100).toFixed(0)
          }}%）
        </span>
        <el-button size="small" text @click="copyResult">
          <el-icon><CopyDocument /></el-icon>
          复制
        </el-button>
      </div>

      <!-- 分类条目 -->
      <div class="classify-list">
        <div
          v-for="(item, idx) in results"
          :key="item.category"
          class="classify-item"
          :class="{ 'classify-item--top': idx === 0 }"
        >
          <div class="classify-label">
            <span class="classify-rank">{{ idx + 1 }}</span>
            <span class="classify-category">{{ item.category }}</span>
          </div>
          <div class="classify-bar-wrap">
            <div class="classify-bar">
              <div
                class="classify-bar-fill"
                :style="{ width: `${item.confidence * 100}%` }"
                :class="getBarClass(idx)"
              />
            </div>
            <span class="classify-percent">{{ (item.confidence * 100).toFixed(1) }}%</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { ElMessage } from 'element-plus';
import { Collection, CopyDocument } from '@element-plus/icons-vue';
import * as aiApi from './api';
import { useAiToolsStore } from './store';
import type { ClassificationResult } from './types';

const aiStore = useAiToolsStore();

// 状态
const inputText = ref('');
const loading = ref(false);
const error = ref(false);
const showEmpty = ref(false);
const results = ref<ClassificationResult[]>([]);

// 方法
async function handleClassify() {
  const text = inputText.value.trim();
  if (!text) return;

  loading.value = true;
  error.value = false;
  showEmpty.value = false;
  results.value = [];
  try {
    const res = await aiApi.classify(text);
    if (!res.results || res.results.length === 0) {
      showEmpty.value = true;
    } else {
      results.value = res.results.sort((a, b) => b.confidence - a.confidence);
    }
    aiStore.addHistory({ tool: 'classify', input: text, result: res });
  } catch {
    error.value = true;
    ElMessage.error('文本分类失败');
  } finally {
    loading.value = false;
  }
}

function getBarClass(idx: number): string {
  if (idx === 0) return 'fill--primary';
  if (idx === 1) return 'fill--secondary';
  if (idx === 2) return 'fill--tertiary';
  return 'fill--others';
}

async function copyResult() {
  const text = results.value
    .map((r) => `${r.category}: ${(r.confidence * 100).toFixed(1)}%`)
    .join('\n');
  try {
    await navigator.clipboard.writeText(text);
    ElMessage.success('分类结果已复制');
  } catch {
    ElMessage.error('复制失败');
  }
}
</script>

<style scoped lang="scss">
.classify-panel {
  padding: 0 4px;
}

.panel-desc {
  font-size: var(--font-size-caption);
  color: var(--text-secondary);
  margin-bottom: var(--space-md);
}

.input-section {
  margin-bottom: var(--space-md);
}

.action-section {
  margin-bottom: var(--space-md);
}

.error-section {
  margin-top: var(--space-md);
  padding: var(--space-md);
  background: var(--fuxi-bg-subtle);
  border-radius: var(--fuxi-radius);
  border: 1px solid var(--fuxi-border);
}

.empty-section {
  margin-top: var(--space-md);
  padding: var(--space-md);
}

.result-section {
  margin-top: var(--space-md);
  padding: var(--space-md);
  background: var(--fuxi-bg-subtle);
  border-radius: var(--fuxi-radius);
  border: 1px solid var(--fuxi-border);
}

.result-header {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: var(--space-md);

  .result-title {
    font-weight: 600;
    font-size: var(--font-size-caption);
    color: var(--fuxi-text);
  }

  .result-subtitle {
    flex: 1;
    font-size: var(--font-size-small);
    color: var(--text-secondary);

    strong {
      color: var(--fuxi-primary);
    }
  }
}

.classify-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.classify-item {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-sm);
  border-radius: var(--radius-sm);
  transition: background var(--duration-fast);

  &--top {
    background: var(--fuxi-primary-light);
  }
}

.classify-label {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  min-width: 160px;
  flex-shrink: 0;
}

.classify-rank {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  font-size: 11px;
  font-weight: 700;
  border-radius: 50%;
  background: var(--bg-subtle);
  color: var(--text-tertiary);
}

.classify-category {
  font-size: var(--font-size-caption);
  font-weight: 500;
  color: var(--fuxi-text);
}

.classify-bar-wrap {
  flex: 1;
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.classify-bar {
  flex: 1;
  height: 8px;
  background: var(--bg-subtle);
  border-radius: 4px;
  overflow: hidden;
}

.classify-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.6s var(--ease-out);

  &.fill--primary {
    background: var(--fuxi-primary-gradient);
  }

  &.fill--secondary {
    background: linear-gradient(90deg, var(--qian-color), var(--dui-color));
  }

  &.fill--tertiary {
    background: linear-gradient(90deg, var(--zhen-color), var(--xun-color));
  }

  &.fill--others {
    background: var(--bg-divider);
  }
}

.classify-percent {
  font-size: var(--font-size-small);
  font-weight: 600;
  color: var(--text-secondary);
  min-width: 45px;
  text-align: right;
}
</style>
