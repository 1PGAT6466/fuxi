<template>
  <!--
    伏羲 v2.1 — 智能翻译面板
  -->
  <div class="translate-panel">
    <div class="panel-desc">支持中/英/日/韩等多语言互译</div>

    <!-- 语言选择 -->
    <div class="lang-selects">
      <div class="lang-item">
        <label class="lang-label">源语言</label>
        <el-select
          v-model="sourceLang"
          placeholder="选择源语言"
          @change="aiStore.setPreference('translate', 'sourceLang', sourceLang)"
        >
          <el-option
            v-for="lang in languages"
            :key="lang.value"
            :label="lang.label"
            :value="lang.value"
          />
        </el-select>
      </div>
      <div class="lang-swap">
        <el-button circle size="small" :disabled="sourceLang === 'auto'" @click="swapLang">
          <el-icon><Sort /></el-icon>
        </el-button>
      </div>
      <div class="lang-item">
        <label class="lang-label">目标语言</label>
        <el-select
          v-model="targetLang"
          placeholder="选择目标语言"
          @change="aiStore.setPreference('translate', 'targetLang', targetLang)"
        >
          <el-option
            v-for="lang in languages"
            :key="lang.value"
            :label="lang.label"
            :value="lang.value"
          />
        </el-select>
      </div>
    </div>

    <!-- 输入区 -->
    <div class="input-section">
      <el-input
        v-model="inputText"
        type="textarea"
        :rows="5"
        placeholder="请输入要翻译的文本…"
        maxlength="3000"
        show-word-limit
      />
    </div>

    <!-- 操作区 -->
    <div class="action-section">
      <el-button
        type="primary"
        :loading="loading"
        :disabled="!inputText.trim() || sourceLang === targetLang"
        @click="handleTranslate"
      >
        <el-icon><Connection /></el-icon>
        翻译
      </el-button>
    </div>

    <!-- 错误态 -->
    <div v-if="error" class="error-section">
      <el-result icon="error" title="翻译失败" sub-title="请检查网络连接后重试">
        <template #extra>
          <el-button type="primary" size="small" @click="handleTranslate">重试</el-button>
        </template>
      </el-result>
    </div>

    <!-- 空态 -->
    <div v-else-if="showEmpty" class="empty-section">
      <el-empty description="翻译结果为空，请尝试其他文本" :image-size="60" />
    </div>

    <!-- 结果区 -->
    <div v-if="result" class="result-section">
      <div class="result-header">
        <span class="result-title">翻译结果</span>
        <el-tag size="small" type="success">
          置信度 {{ (result.confidence * 100).toFixed(0) }}%
        </el-tag>
        <el-button size="small" text @click="copyResult">
          <el-icon><CopyDocument /></el-icon>
          复制
        </el-button>
      </div>
      <div class="result-content">
        {{ result.translated_text }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import { Connection, Sort, CopyDocument } from '@element-plus/icons-vue';
import * as aiApi from './api';
import { useAiToolsStore } from './store';

const aiStore = useAiToolsStore();

// 语言列表
const languages = [
  { label: '自动检测', value: 'auto' },
  { label: '中文', value: 'zh' },
  { label: '英文', value: 'en' },
  { label: '日文', value: 'ja' },
  { label: '韩文', value: 'ko' },
  { label: '法文', value: 'fr' },
  { label: '德文', value: 'de' },
  { label: '西班牙文', value: 'es' },
  { label: '俄文', value: 'ru' },
];

// 状态
const inputText = ref('');
const sourceLang = ref('auto');
const targetLang = ref('en');
const loading = ref(false);
const error = ref(false);
const showEmpty = ref(false);
const result = ref<null | {
  translated_text: string;
  source_lang: string;
  target_lang: string;
  confidence: number;
}>(null);

onMounted(() => {
  const savedSource = aiStore.getPreference('translate', 'sourceLang');
  const savedTarget = aiStore.getPreference('translate', 'targetLang');
  if (typeof savedSource === 'string') sourceLang.value = savedSource;
  if (typeof savedTarget === 'string') targetLang.value = savedTarget;
});

// 方法
function swapLang() {
  if (sourceLang.value === 'auto') return;
  const temp = sourceLang.value;
  sourceLang.value = targetLang.value;
  targetLang.value = temp;
}

async function handleTranslate() {
  const text = inputText.value.trim();
  if (!text || !sourceLang.value || !targetLang.value) return;

  loading.value = true;
  error.value = false;
  showEmpty.value = false;
  result.value = null;
  try {
    const res = await aiApi.translate(text, sourceLang.value, targetLang.value);
    if (!res.translated_text) {
      showEmpty.value = true;
    } else {
      result.value = res;
    }
    aiStore.addHistory({ tool: 'translate', input: text, result: res });
  } catch {
    error.value = true;
    ElMessage.error('翻译失败');
  } finally {
    loading.value = false;
  }
}

async function copyResult() {
  if (!result.value) return;
  try {
    await navigator.clipboard.writeText(result.value.translated_text);
    ElMessage.success('已复制到剪贴板');
  } catch {
    ElMessage.error('复制失败');
  }
}
</script>

<style scoped lang="scss">
.translate-panel {
  padding: 0 4px;
}

.panel-desc {
  font-size: var(--font-size-caption);
  color: var(--text-secondary);
  margin-bottom: var(--space-md);
}

.lang-selects {
  display: flex;
  align-items: flex-end;
  gap: var(--space-sm);
  margin-bottom: var(--space-md);
}

.lang-item {
  flex: 1;
}

.lang-label {
  display: block;
  font-size: var(--font-size-small);
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.lang-swap {
  display: flex;
  align-items: flex-end;
  padding-bottom: 2px;
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
  margin-bottom: var(--space-sm);

  .result-title {
    font-weight: 600;
    font-size: var(--font-size-caption);
    color: var(--fuxi-text);
  }
}

.result-content {
  font-size: var(--font-size-body);
  line-height: 1.8;
  color: var(--fuxi-text);
  white-space: pre-wrap;
}
</style>
