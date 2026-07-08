<template>
  <!--
    伏羲 v2.1 — 关键词提取面板
  -->
  <div class="keywords-panel">
    <div class="panel-desc">从文本中自动提取核心关键词，按权重展示</div>

    <!-- 输入区 -->
    <div class="input-section">
      <el-input
        v-model="inputText"
        type="textarea"
        :rows="5"
        placeholder="请输入文本内容…"
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
        @click="handleExtract"
      >
        <el-icon><Aim /></el-icon>
        提取关键词
      </el-button>
    </div>

    <!-- 错误态 -->
    <div v-if="error" class="error-section">
      <el-result icon="error" title="提取失败" sub-title="请检查网络连接后重试">
        <template #extra>
          <el-button type="primary" size="small" @click="handleExtract">重试</el-button>
        </template>
      </el-result>
    </div>

    <!-- 空态 -->
    <div v-else-if="showEmpty" class="empty-section">
      <el-empty description="未提取到关键词，请尝试其他文本" :image-size="60" />
    </div>

    <!-- 结果区：标签云 -->
    <div v-if="keywords.length > 0" class="result-section">
      <div class="result-header">
        <span class="result-title">关键词 {{ keywords.length }} 个</span>
        <el-button size="small" text @click="copyResult">
          <el-icon><CopyDocument /></el-icon>
          复制
        </el-button>
      </div>
      <div class="tag-cloud">
        <el-tag
          v-for="(kw, idx) in keywords"
          :key="idx"
          :style="{ fontSize: getTagSize(kw.weight), opacity: getTagOpacity(kw.weight) }"
          effect="plain"
          :type="getTagType(idx)"
          class="cloud-tag"
        >
          {{ kw.keyword }}
          <span class="tag-weight">{{ (kw.weight * 100).toFixed(0) }}%</span>
        </el-tag>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { ElMessage } from 'element-plus';
import { Aim, CopyDocument } from '@element-plus/icons-vue';
import * as aiApi from './api';
import { useAiToolsStore } from './store';
import type { KeywordItem } from './types';

const aiStore = useAiToolsStore();

// 状态
const inputText = ref('');
const loading = ref(false);
const error = ref(false);
const showEmpty = ref(false);
const keywords = ref<KeywordItem[]>([]);

// 方法
async function handleExtract() {
  const text = inputText.value.trim();
  if (!text) return;

  loading.value = true;
  error.value = false;
  showEmpty.value = false;
  keywords.value = [];
  try {
    const res = await aiApi.keywords(text);
    if (!res.keywords || res.keywords.length === 0) {
      showEmpty.value = true;
    } else {
      keywords.value = res.keywords;
    }
    aiStore.addHistory({ tool: 'keywords', input: text, result: res });
  } catch {
    error.value = true;
    ElMessage.error('关键词提取失败');
  } finally {
    loading.value = false;
  }
}

// 标签云样式计算
function getTagSize(weight: number): string {
  // 权重映射到 12px - 22px
  const minSize = 12;
  const maxSize = 22;
  const size = minSize + weight * (maxSize - minSize);
  return `${size}px`;
}

function getTagOpacity(weight: number): number {
  // 权重映射到不透明度 0.6 - 1.0
  return 0.6 + weight * 0.4;
}

function getTagType(index: number): string {
  const types = ['', 'success', 'warning', 'info', 'danger'];
  return types[index % types.length];
}

async function copyResult() {
  const text = keywords.value.map((k) => k.keyword).join('、');
  try {
    await navigator.clipboard.writeText(text);
    ElMessage.success('已复制关键词');
  } catch {
    ElMessage.error('复制失败');
  }
}
</script>

<style scoped lang="scss">
.keywords-panel {
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
  justify-content: space-between;
  margin-bottom: var(--space-md);

  .result-title {
    font-weight: 600;
    font-size: var(--font-size-caption);
    color: var(--fuxi-text);
  }
}

.tag-cloud {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.cloud-tag {
  cursor: pointer;
  transition: transform var(--duration-fast) var(--ease-out);

  &:hover {
    transform: scale(1.1);
  }

  .tag-weight {
    font-size: 10px;
    margin-left: 2px;
    opacity: 0.6;
  }
}
</style>
