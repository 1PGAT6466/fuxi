<template>
  <!--
    伏羲 v2.1 — UploadZone：拖拽上传区
    格式校验（.dxf），拖拽 + 点击选择
  -->
  <div
    class="upload-zone"
    :class="{
      'upload-zone--dragover': isDragOver,
      'upload-zone--uploading': isUploading,
    }"
    @dragover.prevent="handleDragOver"
    @dragleave.prevent="handleDragLeave"
    @drop.prevent="handleDrop"
  >
    <div class="upload-content">
      <el-icon :size="36" class="upload-icon">
        <UploadFilled v-if="!isUploading" />
        <Loading v-else class="upload-icon--spinning" />
      </el-icon>

      <p class="upload-text">
        {{ isUploading ? '正在上传...' : '拖拽 DXF 文件到此处' }}
      </p>
      <p class="upload-hint">支持 .dxf 格式，最大 50MB</p>

      <label class="upload-btn">
        <el-button type="primary" :disabled="isUploading" size="small">
          <el-icon><FolderOpened /></el-icon>
          选择文件
        </el-button>
        <input type="file" accept=".dxf,application/dxf" hidden @change="handleFileChange" />
      </label>
    </div>

    <!-- 错误提示 -->
    <div v-if="errorMsg" class="upload-error">
      <el-icon :size="16"><WarningFilled /></el-icon>
      {{ errorMsg }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { UploadFilled, Loading, FolderOpened, WarningFilled } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { uploadDxf } from './api';
import { useDxfViewerStore } from './store';

const store = useDxfViewerStore();

// ─── 状态 ───
const isDragOver = ref(false);
const isUploading = ref(false);
const errorMsg = ref('');

const ALLOWED_EXTENSIONS = ['.dxf'];
const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB

// ─── 拖拽事件 ───
function handleDragOver(e: DragEvent): void {
  isDragOver.value = true;
  e.dataTransfer!.dropEffect = 'copy';
}

function handleDragLeave(): void {
  isDragOver.value = false;
}

async function handleDrop(e: DragEvent): Promise<void> {
  isDragOver.value = false;
  errorMsg.value = '';
  const files = e.dataTransfer?.files;
  if (files && files.length > 0) {
    await processFiles(Array.from(files));
  }
}

// ─── 文件选择 ───
async function handleFileChange(e: Event): Promise<void> {
  errorMsg.value = '';
  const target = e.target as HTMLInputElement;
  const files = target.files;
  if (files && files.length > 0) {
    await processFiles(Array.from(files));
    target.value = ''; // 重置以便重复选择同一文件
  }
}

// ─── 文件处理 ───
async function processFiles(files: File[]): Promise<void> {
  for (const file of files) {
    // 格式校验
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      errorMsg.value = `不支持的文件格式：${file.name}（仅支持 .dxf）`;
      ElMessage.error(errorMsg.value);
      continue;
    }

    // 大小校验
    if (file.size > MAX_FILE_SIZE) {
      errorMsg.value = `文件过大：${file.name}（最大 50MB）`;
      ElMessage.error(errorMsg.value);
      continue;
    }

    // 上传
    isUploading.value = true;
    try {
      const result = await uploadDxf(file);
      ElMessage.success(`文件 ${file.name} 上传成功`);
      // 刷新文件列表
      await store.loadFiles();
      // 自动加载到画布
      if (result.hash) {
        await store.loadFile(result.hash);
      }
    } catch {
      errorMsg.value = `上传失败：${file.name}`;
      ElMessage.error(errorMsg.value);
    } finally {
      isUploading.value = false;
    }
  }
}
</script>

<style scoped lang="scss">
.upload-zone {
  border: 2px dashed var(--bg-divider);
  border-radius: var(--radius-md);
  padding: 24px;
  text-align: center;
  transition: all var(--duration-fast) var(--ease-out);
  background: var(--bg-subtle);

  &--dragover {
    border-color: var(--brand);
    background: var(--brand-soft);
  }

  &--uploading {
    opacity: 0.7;
    pointer-events: none;
  }
}

.upload-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.upload-icon {
  color: var(--xun-color);
  transition: color var(--duration-fast) var(--ease-out);

  .upload-zone--dragover & {
    color: var(--brand);
  }

  &--spinning {
    animation: spin 1s linear infinite;
  }
}

.upload-text {
  margin: 0;
  font-size: var(--font-size-caption);
  font-weight: 500;
  color: var(--text-primary);
}

.upload-hint {
  margin: 0;
  font-size: var(--font-size-small);
  color: var(--text-tertiary);
}

.upload-btn {
  margin-top: 4px;
  cursor: pointer;
}

.upload-error {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin-top: 12px;
  padding: 8px 12px;
  background: var(--status-error-bg);
  color: var(--status-error);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-small);
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
