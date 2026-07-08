<template>
  <!--
    伏羲 v2.1 — 文档工具窗口
    布局：抽屉式侧边工具面板 + 主内容区
  -->
  <div class="doc-tools-page">
    <div class="page-header">
      <div class="header-top">
        <el-icon :size="24" class="header-icon"><Document /></el-icon>
        <h2 class="header-title">文档工具</h2>
      </div>
      <p class="header-desc">
        一站式文档处理：格式转换 · PDF 合并拆分 · 压缩 · 图片信息 · 文本提取
      </p>
    </div>

    <!-- 加载态 -->
    <div v-if="loading" class="doc-tools-body">
      <div class="tools-sidebar">
        <el-skeleton :rows="5" animated />
      </div>
      <div class="tools-content">
        <el-skeleton :rows="5" animated />
      </div>
    </div>

    <!-- 错误态 -->
    <div v-else-if="error" class="doc-tools-body doc-tools-body--center">
      <el-result icon="error" title="加载失败" sub-title="请稍后重试">
        <template #extra>
          <el-button type="primary" @click="loadData">重试</el-button>
        </template>
      </el-result>
    </div>

    <!-- 空态 -->
    <div v-else-if="isEmpty" class="doc-tools-body doc-tools-body--center">
      <el-empty description="暂无文档工具数据" />
    </div>

    <!-- 正常内容 -->
    <div v-else class="doc-tools-body">
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
        </div>

        <!-- 最近记录 -->
        <div v-if="recentRecords.length" class="recent-section">
          <div class="recent-header">最近记录</div>
          <div v-for="rec in recentRecords.slice(0, 5)" :key="rec.id" class="recent-item">
            <span
              class="recent-status"
              :class="rec.status === 'completed' ? 'status-ok' : 'status-fail'"
              >●</span
            >
            <span class="recent-name">{{ rec.filename }}</span>
            <span class="recent-time">{{ timeAgo(rec.timestamp) }}</span>
          </div>
        </div>
      </div>

      <!-- 右侧内容面板 -->
      <div class="tools-content">
        <keep-alive>
          <ConvertPanel v-if="activeTool === 'convert'" key="convert" />
          <PdfMergePanel v-if="activeTool === 'merge'" key="merge" />
          <PdfSplitPanel
            v-if="activeTool === 'split'"
            key="split"
            @download-part="handleDownloadPart"
            @download-all="handleDownloadAll"
          />
          <CompressPanel v-if="activeTool === 'compress'" key="compress" />
          <ImageInfoPanel v-if="activeTool === 'image-info'" key="image-info" />
          <TextExtractPanel v-if="activeTool === 'extract'" key="extract" />
        </keep-alive>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import {
  Document,
  Switch,
  Connection,
  Scissor,
  Minus,
  PictureFilled,
  Tickets,
} from '@element-plus/icons-vue';
import ConvertPanel from './ConvertPanel.vue';
import PdfMergePanel from './PdfMergePanel.vue';
import PdfSplitPanel from './PdfSplitPanel.vue';
import CompressPanel from './CompressPanel.vue';
import ImageInfoPanel from './ImageInfoPanel.vue';
import TextExtractPanel from './TextExtractPanel.vue';
import { useDocToolsStore } from './store';
import type { SplitPageInfo } from './types';

const store = useDocToolsStore();

// ─── 加载/空/错误状态 ───
const loading = ref(true);
const error = ref(false);
const isEmpty = ref(false);

async function loadData(): Promise<void> {
  loading.value = true;
  error.value = false;
  isEmpty.value = false;
  try {
    // 模拟数据加载 — 实际项目中替换为真实 API 调用
    await store.fetchRecords?.();
    // 加载完成后检查是否有数据
    if (!store.recentRecords || store.recentRecords.length === 0) {
      isEmpty.value = true;
    }
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
}

const tools = [
  { id: 'convert', label: '格式转换', icon: Switch },
  { id: 'merge', label: 'PDF 合并', icon: Connection },
  { id: 'split', label: 'PDF 拆分', icon: Scissor },
  { id: 'compress', label: '文件压缩', icon: Minus },
  { id: 'image-info', label: '图片信息', icon: PictureFilled },
  { id: 'extract', label: '文本提取', icon: Tickets },
];

const activeTool = ref(store.activeTool || 'convert');

const recentRecords = computed(() => store.recentRecords);

function switchTool(toolId: string) {
  activeTool.value = toolId;
  store.setActiveTool(toolId);
}

function timeAgo(ts: number): string {
  const diff = Date.now() - ts;
  if (diff < 60000) return '刚刚';
  if (diff < 3600000) return Math.floor(diff / 60000) + ' 分钟前';
  if (diff < 86400000) return Math.floor(diff / 3600000) + ' 小时前';
  return Math.floor(diff / 86400000) + ' 天前';
}

function handleDownloadPart(part: SplitPageInfo) {
  ElMessage.info(`下载 ${part.filename}`);
}

function handleDownloadAll() {
  ElMessage.info('批量下载已开始');
}

onMounted(() => {
  loadData();
});
</script>

<style scoped lang="scss">
.doc-tools-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 28px 24px;
  height: 100%;
  display: flex;
  flex-direction: column;

  @media (max-width: 767px) {
    padding: 16px;
  }
}

.page-header {
  margin-bottom: var(--space-lg);

  .header-top {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    margin-bottom: 6px;

    .header-icon {
      color: var(--xun-color);
    }

    .header-title {
      margin: 0;
      font-size: 24px;
      font-weight: 700;
      color: var(--fuxi-text);
    }
  }

  .header-desc {
    margin: 0;
    font-size: var(--font-size-caption);
    color: var(--fuxi-text-secondary);
    padding-left: 34px;
  }
}

.doc-tools-body {
  flex: 1;
  display: flex;
  gap: 20px;
  min-height: 0;
  overflow: hidden;

  @media (max-width: 767px) {
    flex-direction: column;
  }
}

/* ───────── 左侧工具导航 ───────── */
.tools-sidebar {
  width: 200px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow-y: auto;

  @media (max-width: 767px) {
    width: 100%;
    flex-direction: row;
    overflow-x: auto;
    gap: 6px;
    padding-bottom: var(--space-sm);

    &::-webkit-scrollbar {
      height: 2px;
    }
  }

  &::-webkit-scrollbar {
    width: 4px;
  }

  &::-webkit-scrollbar-thumb {
    background: var(--fuxi-border);
    border-radius: 4px;
  }
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
  color: var(--fuxi-text-secondary);
  background: transparent;

  &:hover {
    background: var(--bg-hover);
    color: var(--fuxi-text);
  }

  &--active {
    background: var(--fuxi-primary-light);
    color: var(--fuxi-primary);

    &::before {
      content: '';
      position: absolute;
      left: 0;
      top: 50%;
      transform: translateY(-50%);
      width: 3px;
      height: 28px;
      background: var(--fuxi-primary);
      border-radius: 0 4px 4px 0;
    }
  }

  @media (max-width: 767px) {
    flex-shrink: 0;
    padding: 10px 14px;
  }
}

.tool-nav-label {
  font-weight: 600;
  font-size: var(--font-size-caption);
  white-space: nowrap;
}

/* ───────── 最近记录 ───────── */
.recent-section {
  margin-top: var(--space-lg);
  padding-top: var(--space-md);
  border-top: 1px solid var(--fuxi-border);
}

.recent-header {
  font-size: var(--font-size-small);
  font-weight: 600;
  color: var(--fuxi-text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: var(--space-xs) var(--space-sm);
  margin-bottom: var(--space-xs);
}

.recent-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px var(--space-sm);
  font-size: var(--font-size-small);
  border-radius: 4px;
}

.recent-status {
  font-size: 8px;
  flex-shrink: 0;

  &.status-ok {
    color: var(--fuxi-success);
  }
  &.status-fail {
    color: var(--fuxi-error);
  }
}

.recent-name {
  flex: 1;
  color: var(--fuxi-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.recent-time {
  color: var(--fuxi-text-tertiary);
  flex-shrink: 0;
}

/* ───────── 居中状态容器 ───────── */
.doc-tools-body--center {
  display: flex;
  align-items: center;
  justify-content: center;
}

/* ───────── 右侧内容面板 ───────── */
.tools-content {
  flex: 1;
  overflow-y: auto;
  background: var(--fuxi-bg-card);
  border-radius: var(--fuxi-radius);
  border: 1px solid var(--fuxi-border);
  box-shadow: var(--fuxi-shadow-sm);
  padding: 24px;
  min-width: 0;

  @media (max-width: 767px) {
    padding: 16px;
  }

  &::-webkit-scrollbar {
    width: 6px;
  }

  &::-webkit-scrollbar-thumb {
    background: var(--fuxi-border);
    border-radius: 3px;
  }
}
</style>
