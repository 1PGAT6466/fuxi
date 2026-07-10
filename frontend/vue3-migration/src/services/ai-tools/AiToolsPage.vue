<template>
  <!--
    伏羲 v2.1 — AI 工具集页面
    布局：左侧 Tab 导航（5 个工具）+ 右侧内容面板
  -->
  <div class="ai-tools-page">
    <div class="ai-tools-header">
      <div class="header-top">
        <el-icon :size="24" class="header-icon"><Cpu /></el-icon>
        <h2 class="header-title">AI 工具集</h2>
      </div>
      <p class="header-desc">智能工具集：文本摘要、翻译、关键词提取、实体识别、文本分类</p>
    </div>

    <!-- 加载态 -->
    <div v-if="loading" class="state-container">
      <el-skeleton :rows="5" animated />
    </div>

    <!-- 错误态 -->
    <div v-else-if="error" class="state-container">
      <el-result icon="error" title="加载失败" sub-title="请稍后重试">
        <template #extra>
          <el-button type="primary" size="small" @click="fetchTools">重试</el-button>
        </template>
      </el-result>
    </div>

    <!-- 空态 -->
    <div v-else-if="isEmpty" class="state-container">
      <el-empty description="暂无AI工具数据" />
    </div>

    <!-- 正常内容 -->
    <div v-else class="ai-tools-body">
      <!-- 左侧工具导航 -->
      <div class="tools-sidebar">
        <div
          v-for="tool in tools"
          :key="tool.id"
          class="tool-nav-item"
          :class="{ 'tool-nav-item--active': activeTool === tool.id }"
          @click="switchTool(tool.id)"
        >
          <el-icon :size="18"><component :is="tool.icon" /></el-icon>
          <span class="tool-nav-label">{{ tool.label }}</span>
          <span class="tool-nav-desc">{{ tool.desc }}</span>
        </div>
      </div>

      <!-- 右侧内容面板 -->
      <div class="tools-content">
        <keep-alive>
          <component :is="currentPanel" :key="activeTool" />
        </keep-alive>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { Cpu, MagicStick, Connection, Aim, Pointer, Collection } from '@element-plus/icons-vue';
import SummarizePanel from './SummarizePanel.vue';
import TranslatePanel from './TranslatePanel.vue';
import KeywordsPanel from './KeywordsPanel.vue';
import EntitiesPanel from './EntitiesPanel.vue';
import ClassifyPanel from './ClassifyPanel.vue';
import * as aiToolsApi from './api';

// ───── 页面状态 ─────
const loading = ref(false);
const error = ref(false);
const isEmpty = ref(false);

// 工具列表
const tools = [
  { id: 'summarize', label: '文本摘要', desc: '自动提取核心要点', icon: MagicStick },
  { id: 'translate', label: '智能翻译', desc: '多语言互译', icon: Connection },
  { id: 'keywords', label: '关键词提取', desc: '提取核心关键词', icon: Aim },
  { id: 'entities', label: '实体识别', desc: '识别人名/地名/组织', icon: Pointer },
  { id: 'classify', label: '文本分类', desc: '自动文本归类', icon: Collection },
];

// 当前激活的工具
const activeTool = ref<string>('summarize');

// 动态面板组件映射
const panelMap: Record<string, any> = {
  summarize: SummarizePanel,
  translate: TranslatePanel,
  keywords: KeywordsPanel,
  entities: EntitiesPanel,
  classify: ClassifyPanel,
};
const currentPanel = computed(() => panelMap[activeTool.value] || SummarizePanel);

function switchTool(toolId: string) {
  activeTool.value = toolId;
}

// ───── 加载工具数据 ─────
async function fetchTools() {
  loading.value = true;
  error.value = false;
  isEmpty.value = false;
  try {
    const res = await aiToolsApi.health();
    // health 响应中包含 models_available 数组，为空则标记空态
    if (!res.models_available || res.models_available.length === 0) {
      isEmpty.value = true;
    }
  } catch {
    error.value = true;
    console.warn('[AiToolsPage] 加载AI工具数据失败');
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  fetchTools();
});
</script>

<style scoped lang="scss">
.ai-tools-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 28px 24px;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.ai-tools-header {
  margin-bottom: 24px;

  .header-top {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    margin-bottom: 6px;

    .header-icon {
      color: var(--qian-color);
    }

    .header-title {
      margin: 0;
      font-size: 24px;
      font-weight: 700;
      color: var(--text-primary);
    }
  }

  .header-desc {
    margin: 0;
    font-size: var(--font-size-caption);
    color: var(--text-secondary);
    padding-left: 34px;
  }
}

.ai-tools-body {
  flex: 1;
  display: flex;
  gap: 20px;
  min-height: 0;
  overflow: hidden;
}

/* ───────── 左侧工具导航 ───────── */
.tools-sidebar {
  width: 200px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tool-nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  position: relative;
  color: var(--text-secondary);
  background: transparent;

  &:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
  }

  &--active {
    background: var(--brand-soft);
    color: var(--brand);

    &::before {
      content: '';
      position: absolute;
      left: 0;
      top: 50%;
      transform: translateY(-50%);
      width: 3px;
      height: 28px;
      background: var(--brand);
      border-radius: 0 4px 4px 0;
    }

    .tool-nav-desc {
      color: var(--brand);
      opacity: 0.6;
    }
  }
}

.tool-nav-label {
  font-weight: 600;
  font-size: var(--font-size-caption);
  white-space: nowrap;
}

.tool-nav-desc {
  font-size: var(--font-size-small);
  opacity: 0.5;
  white-space: nowrap;
}

/* ───────── 右侧内容面板 ───────── */
.tools-content {
  flex: 1;
  overflow-y: auto;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  padding: 24px;
  min-width: 0;

  &::-webkit-scrollbar {
    width: 6px;
  }

  &::-webkit-scrollbar-thumb {
    background: var(--bg-divider);
    border-radius: 3px;
  }
}

/* ───────── 状态容器 ───────── */
.state-container {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 60px 24px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  min-height: 300px;
}

/* ───────── 响应式 ───────── */
@media (max-width: 767px) {
  .ai-tools-page {
    padding: 16px;
  }

  .ai-tools-body {
    flex-direction: column;
  }

  .tools-sidebar {
    width: 100%;
    flex-direction: row;
    overflow-x: auto;
    gap: 6px;

    &::-webkit-scrollbar {
      height: 2px;
    }
  }

  .tool-nav-item {
    flex-shrink: 0;
    padding: 10px 14px;

    .tool-nav-desc {
      display: none;
    }
  }

  .tools-content {
    padding: 16px;
  }
}
</style>
