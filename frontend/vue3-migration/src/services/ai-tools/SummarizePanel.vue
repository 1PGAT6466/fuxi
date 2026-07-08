<template>
  <!--
    伏羲 v2.1 — 文本摘要面板
  -->
  <div class="summarize-panel">
    <div class="panel-desc">输入文本，AI 将自动提取核心要点并生成摘要</div>

    <!-- 输入区 -->
    <div class="input-section">
      <el-input
        v-model="inputText"
        type="textarea"
        :rows="6"
        placeholder="请输入需要摘要的文本内容…"
        maxlength="5000"
        show-word-limit
      />
    </div>

    <!-- 参数区 -->
    <div class="params-section">
      <label class="param-label">摘要长度</label>
      <div class="param-slider">
        <el-slider
          v-model="summaryLength"
          :min="0"
          :max="2"
          :step="1"
          :marks="lengthMarks"
          :show-tooltip="false"
          @change="aiStore.setPreference('summarize', 'length', summaryLength)"
        />
      </div>
    </div>

    <!-- 操作区 -->
    <div class="action-section">
      <el-button
        type="primary"
        :loading="loading"
        :disabled="!inputText.trim()"
        @click="handleSummarize"
      >
        <el-icon><MagicStick /></el-icon>
        生成摘要
      </el-button>
    </div>

    <!-- 错误态 -->
    <div v-if="error" class="error-section">
      <el-result icon="error" title="摘要生成失败" sub-title="请检查网络连接后重试">
        <template #extra>
          <el-button type="primary" size="small" @click="handleSummarize">重试</el-button>
        </template>
      </el-result>
    </div>

    <!-- 空态 -->
    <div v-else-if="showEmpty" class="empty-section">
      <el-empty description="未生成摘要，输入文本后点击生成" :image-size="60" />
    </div>

    <!-- 结果区 -->
    <div v-if="result" class="result-section">
      <div class="result-header">
        <span class="result-title">摘要结果</span>
        <div class="result-meta">
          <el-tag size="small" type="info"> 原文 {{ result.original_length }} 字 </el-tag>
          <el-tag size="small" type="success"> 压缩率 {{ result.compression_ratio }}% </el-tag>
        </div>
        <el-button size="small" text @click="copyResult">
          <el-icon><CopyDocument /></el-icon>
          复制
        </el-button>
      </div>
      <div class="result-content">
        {{ result.summary }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import { MagicStick, CopyDocument } from '@element-plus/icons-vue';
import * as aiApi from './api';
import { useAiToolsStore } from './store';

const aiStore = useAiToolsStore();

// 状态
const inputText = ref('');
const loading = ref(false);
const error = ref(false);
const showEmpty = ref(false);
const result = ref<null | {
  summary: string;
  original_length: number;
  summary_length: number;
  compression_ratio: number;
}>(null);

// 摘要长度：0=短, 1=中, 2=长
const summaryLength = ref(1);
const lengthMarks = { 0: '短', 1: '中', 2: '长' };

onMounted(() => {
  const saved = aiStore.getPreference('summarize', 'length');
  if (typeof saved === 'number') summaryLength.value = saved;
});

// 方法
async function handleSummarize() {
  const text = inputText.value.trim();
  if (!text) return;

  const lengthMap: Record<number, 'short' | 'medium' | 'long'> = {
    0: 'short',
    1: 'medium',
    2: 'long',
  };
  const length = lengthMap[summaryLength.value] || 'medium';

  loading.value = true;
  error.value = false;
  showEmpty.value = false;
  result.value = null;
  try {
    const res = await aiApi.summarize(text, length);
    if (!res.summary) {
      showEmpty.value = true;
    } else {
      result.value = res;
    }
    aiStore.addHistory({ tool: 'summarize', input: text, result: res });
  } catch {
    error.value = true;
    ElMessage.error('摘要生成失败');
  } finally {
    loading.value = false;
  }
}

async function copyResult() {
  if (!result.value) return;
  try {
    await navigator.clipboard.writeText(result.value.summary);
    ElMessage.success('已复制到剪贴板');
  } catch {
    ElMessage.error('复制失败');
  }
}
</script>

<style scoped lang="scss">
.summarize-panel {
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

.params-section {
  margin-bottom: var(--space-md);

  .param-label {
    font-size: var(--font-size-caption);
    color: var(--text-secondary);
    margin-bottom: var(--space-xs);
    display: block;
  }

  .param-slider {
    padding: 0 8px;
  }
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
  margin-bottom: var(--space-sm);

  .result-title {
    font-weight: 600;
    font-size: var(--font-size-caption);
    color: var(--fuxi-text);
  }

  .result-meta {
    display: flex;
    gap: 6px;
    flex: 1;
  }
}

.result-content {
  font-size: var(--font-size-body);
  line-height: 1.8;
  color: var(--fuxi-text);
  white-space: pre-wrap;
}
</style>
