<!--
  伏羲 v2.1 — 拖拽上传区
  支持拖拽/点击上传，进度显示，多文件支持
-->
<template>
  <div class="upload-zone">
    <el-upload
      ref="uploadRef"
      class="upload-area"
      drag
      multiple
      :auto-upload="false"
      :file-list="fileList"
      :limit="20"
      :on-change="handleChange"
      :on-exceed="handleExceed"
      action="#"
    >
      <div class="upload-placeholder">
        <el-icon class="upload-icon" :size="40"><UploadFilled /></el-icon>
        <div class="upload-text">将文件拖拽到此处，或 <em>点击上传</em></div>
        <div class="upload-hint">支持 PDF、DOCX、XLSX、TXT、Markdown、CSV 等格式</div>
      </div>
    </el-upload>

    <!-- 上传进度 -->
    <div v-if="fileList.length > 0" class="upload-progress">
      <div class="upload-progress-header">
        <span>已选择 {{ fileList.length }} 个文件</span>
        <div class="upload-progress-actions">
          <el-button size="small" @click="clearFiles">清空</el-button>
          <el-button size="small" type="primary" :loading="uploading" @click="startUpload">
            {{ uploading ? '上传中...' : '开始上传' }}
          </el-button>
        </div>
      </div>

      <div class="upload-file-list">
        <div v-for="(file, idx) in fileList" :key="idx" class="upload-file-item">
          <el-icon :size="16"><Document /></el-icon>
          <span class="upload-file-name">{{ file.name }}</span>
          <span class="upload-file-size">{{ formatSize(file.size!) }}</span>
          <el-progress
            v-if="uploadProgress[idx] !== undefined"
            :percentage="uploadProgress[idx]"
            :status="uploadErrors[idx] ? 'exception' : undefined"
            :stroke-width="6"
            style="flex: 1; max-width: 150px"
          />
          <button v-if="!uploading" class="upload-file-remove" @click="removeFile(idx)">
            <el-icon :size="14"><Close /></el-icon>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { ElMessage } from 'element-plus';
import { UploadFilled, Document, Close } from '@element-plus/icons-vue';
import { formatSize } from '@/utils/helpers';
import { useFileStore } from '@/stores/files';
import type { UploadFile, UploadInstance } from 'element-plus';

const emit = defineEmits<{
  success: [];
}>();

const fileStore = useFileStore();
const uploadRef = ref<UploadInstance>();
const fileList = ref<UploadFile[]>([]);
const uploading = ref(false);
const uploadProgress = ref<number[]>([]);
const uploadErrors = ref<boolean[]>([]);

function handleChange(_file: UploadFile, files: UploadFile[]): void {
  fileList.value = files;
  uploadProgress.value = [];
  uploadErrors.value = [];
}

function handleExceed(): void {
  ElMessage.warning('最多上传 20 个文件');
}

function removeFile(idx: number): void {
  fileList.value.splice(idx, 1);
  uploadProgress.value.splice(idx, 1);
  uploadErrors.value.splice(idx, 1);
}

function clearFiles(): void {
  fileList.value = [];
  uploadProgress.value = [];
  uploadErrors.value = [];
  uploadRef.value?.clearFiles();
}

async function startUpload(): Promise<void> {
  if (fileList.value.length === 0) {
    ElMessage.warning('请先选择文件');
    return;
  }

  uploading.value = true;
  let successCount = 0;
  let failCount = 0;

  for (let i = 0; i < fileList.value.length; i++) {
    try {
      uploadProgress.value[i] = 0;
      await fileStore.uploadFile(fileList.value[i].raw as File);
      uploadProgress.value[i] = 100;
      successCount++;
    } catch {
      uploadErrors.value[i] = true;
      uploadProgress.value[i] = 50;
      failCount++;
    }
  }

  uploading.value = false;

  if (successCount > 0) {
    ElMessage.success(
      `成功上传 ${successCount} 个文件${failCount > 0 ? `，${failCount} 个失败` : ''}`,
    );
    emit('success');
  }
  if (failCount > 0 && successCount === 0) {
    ElMessage.error('所有文件上传失败');
  }

  // 清空成功的文件，保留失败的
  fileList.value = fileList.value.filter((_, i) => uploadErrors.value[i]);
  uploadProgress.value = [];
  uploadErrors.value = [];
}
</script>

<style scoped lang="scss">
.upload-zone {
  background: var(--fuxi-bg-card);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.upload-area {
  width: 100%;

  :deep(.el-upload) {
    width: 100%;
  }

  :deep(.el-upload-dragger) {
    width: 100%;
    border: 2px dashed var(--fuxi-border);
    border-radius: var(--radius-md);
    background: var(--fuxi-bg-card);
    padding: 32px 24px;
    transition: all 0.2s var(--ease-out);

    &:hover {
      border-color: var(--fuxi-primary);
      background: var(--fuxi-primary-light);
    }
  }
}

.upload-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.upload-icon {
  color: var(--fuxi-text-tertiary);
}

.upload-text {
  font-size: 15px;
  color: var(--fuxi-text);

  em {
    color: var(--fuxi-primary);
    font-style: normal;
    cursor: pointer;
  }
}

.upload-hint {
  font-size: 12px;
  color: var(--fuxi-text-tertiary);
}

/* ───── 进度区 ───── */

.upload-progress {
  padding: 0 16px 16px;
}

.upload-progress-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--fuxi-text-secondary);
}

.upload-progress-actions {
  display: flex;
  gap: 8px;
}

.upload-file-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.upload-file-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--fuxi-bg-subtle);
  border-radius: var(--radius-sm);
  font-size: 13px;
}

.upload-file-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--fuxi-text);
}

.upload-file-size {
  font-size: 12px;
  color: var(--fuxi-text-tertiary);
  flex-shrink: 0;
}

.upload-file-remove {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: var(--fuxi-text-tertiary);
  cursor: pointer;
  border-radius: 4px;

  &:hover {
    background: var(--fuxi-error-bg);
    color: var(--fuxi-error);
  }
}
</style>
