<template>
  <!--
    伏羲 v2.1 — FileExplorer：已上传 DXF 文件列表
    点击加载到画布
  -->
  <div class="file-explorer">
    <div class="explorer-header">
      <el-icon :size="16"><FolderOpened /></el-icon>
      <span>DXF 文件</span>
      <el-button
        size="small"
        text
        :icon="Refresh"
        :loading="store.filesLoading"
        @click="store.loadFiles()"
      />
    </div>

    <!-- 文件列表 -->
    <div class="file-list">
      <div
        v-for="file in store.files"
        :key="file.id"
        class="file-item"
        :class="{
          'file-item--active': store.currentFileHash === file.hash,
          'file-item--loading': store.renderLoading && store.currentFileHash === file.hash,
        }"
        @click="handleFileClick(file.hash)"
      >
        <el-icon :size="20" class="file-icon"><Document /></el-icon>
        <div class="file-info">
          <span class="file-name">{{ file.name }}</span>
          <span class="file-meta">
            {{ formatSize(file.size) }} · {{ file.layers_count }} 层 ·
            {{ formatDate(file.uploaded_at) }}
          </span>
        </div>
        <el-icon
          v-if="store.renderLoading && store.currentFileHash === file.hash"
          class="file-loading-icon"
          :size="14"
        >
          <Loading />
        </el-icon>
      </div>

      <!-- 错误状态 -->
      <div v-if="filesError" class="file-error">
        <el-result icon="error" title="加载失败" sub-title="无法获取文件列表，请检查网络连接">
          <template #extra>
            <el-button type="primary" size="small" @click="retryLoadFiles">重试</el-button>
          </template>
        </el-result>
      </div>

      <!-- 空状态 -->
      <div v-else-if="!store.filesLoading && store.files.length === 0" class="file-empty">
        <el-empty description="暂无 DXF 文件">
          <template #extra>
            <span class="hint">请上传 DXF 文件开始浏览</span>
          </template>
        </el-empty>
      </div>

      <!-- 加载中 -->
      <div v-if="store.filesLoading" class="file-skeleton">
        <el-skeleton :rows="3" animated />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { FolderOpened, Document, Refresh } from '@element-plus/icons-vue';
import { useDxfViewerStore } from './store';

const store = useDxfViewerStore();
const filesError = ref(false);

async function loadFilesWithErrorHandling() {
  filesError.value = false;
  try {
    await store.loadFiles();
    if (store.files.length === 0) {
      // API succeeded but returned empty
    }
  } catch {
    filesError.value = true;
  }
}

function retryLoadFiles() {
  loadFilesWithErrorHandling();
}

onMounted(() => {
  loadFilesWithErrorHandling();
});

// ─── 文件操作方法 ───
function handleFileClick(hash: string): void {
  if (store.currentFileHash === hash) return;
  store.loadFile(hash);
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  const month = d.getMonth() + 1;
  const day = d.getDate();
  return `${month}/${day}`;
}
</script>

<style scoped lang="scss">
.file-explorer {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.explorer-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--bg-divider);
  font-size: var(--font-size-caption);
  font-weight: 600;
  color: var(--text-primary);
}

.file-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;

  &::-webkit-scrollbar {
    width: 4px;
  }
  &::-webkit-scrollbar-thumb {
    background: var(--bg-divider);
    border-radius: 4px;
  }
}

.file-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);

  &:hover {
    background: var(--bg-hover);
  }

  &--active {
    background: var(--brand-soft);

    .file-name {
      color: var(--brand);
      font-weight: 600;
    }
  }
}

.file-icon {
  color: var(--xun-color);
  flex-shrink: 0;
}

.file-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.file-name {
  font-size: var(--font-size-caption);
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-meta {
  font-size: var(--font-size-small);
  color: var(--text-tertiary);
}

.file-loading-icon {
  animation: spin 1s linear infinite;
  color: var(--brand);
}

.file-empty {
  text-align: center;
  padding: 20px 0;

  .hint {
    font-size: var(--font-size-small);
    color: var(--text-tertiary);
  }
}

.file-error {
  padding: 16px 0;
}

.file-skeleton {
  padding: 12px;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
