<template>
  <!--
    伏羲 v2.1 — 格式转换面板
    文件拖放上传 + 源格式自动检测 + 目标格式选择 → 转换 → 进度 → 下载
  -->
  <div class="convert-panel">
    <!-- 上传区域 -->
    <div
      class="upload-zone"
      :class="{ 'upload-zone--dragover': isDragover, 'upload-zone--has-file': uploadedFile }"
      @dragover.prevent="isDragover = true"
      @dragleave.prevent="isDragover = false"
      @drop.prevent="handleDrop"
      @click="triggerUpload"
    >
      <el-icon :size="48" class="upload-icon"><UploadFilled /></el-icon>
      <p class="upload-text">{{ uploadedFile ? uploadedFile.name : '拖放文件到此处或点击上传' }}</p>
      <p v-if="!uploadedFile" class="upload-hint">支持 PDF、Word、TXT、图片格式</p>
      <input ref="fileInputRef" type="file" class="file-input-hidden" @change="handleFileChange" />
    </div>

    <!-- 源格式显示 -->
    <div v-if="uploadedFile" class="file-info">
      <el-tag size="small" type="info">源格式：{{ detectedFormat }}</el-tag>
      <span class="file-size">{{ formatSize(uploadedFile.size) }}</span>
      <el-button text size="small" @click="clearFile">清除</el-button>
    </div>

    <!-- 目标格式选择 -->
    <div v-if="uploadedFile" class="convert-options">
      <label class="option-label">目标格式</label>
      <el-select v-model="targetFormat" placeholder="选择目标格式">
        <el-option
          v-for="fmt in targetOptions"
          :key="fmt.value"
          :label="fmt.label"
          :value="fmt.value"
          :disabled="fmt.value === detectedFormat"
        />
      </el-select>
      <el-button
        type="primary"
        :loading="converting"
        :disabled="!targetFormat || targetFormat === detectedFormat"
        @click="handleConvert"
      >
        <el-icon><Switch /></el-icon>
        开始转换
      </el-button>
    </div>

    <!-- 进度条 -->
    <div v-if="converting || result" class="convert-progress">
      <el-progress
        :percentage="converting ? progress : 100"
        :status="converting ? undefined : 'success'"
        :stroke-width="8"
        striped
        :striped-flow="converting"
      />
      <p class="progress-text">
        {{ converting ? `转换中... ${progress}%` : '转换完成' }}
      </p>
    </div>

    <!-- 错误态 -->
    <div v-if="convertError" class="convert-error">
      <el-result icon="error" title="转换失败" sub-title="文件转换失败，请重试">
        <template #extra>
          <el-button type="primary" size="small" @click="handleConvert">重试</el-button>
        </template>
      </el-result>
    </div>

    <!-- 结果下载 -->
    <div v-else-if="result && result.status === 'completed'" class="convert-result">
      <div class="result-info">
        <span class="result-name">{{ result.target_filename }}</span>
        <el-button type="primary" size="small" @click="downloadFile">
          <el-icon><Download /></el-icon>
          下载文件
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { ElMessage } from 'element-plus';
import { UploadFilled, Switch, Download } from '@element-plus/icons-vue';
import * as docToolsApi from './api';
import { useDocToolsStore } from './store';
import type { ConvertResponse } from './types';

const store = useDocToolsStore();

const fileInputRef = ref<HTMLInputElement | null>(null);
const isDragover = ref(false);
const uploadedFile = ref<File | null>(null);
const targetFormat = ref('');
const converting = ref(false);
const convertError = ref(false);
const progress = ref(0);
const result = ref<ConvertResponse | null>(null);
let progressTimer: ReturnType<typeof setInterval> | null = null;

// 检测的源格式
const detectedFormat = computed(() => {
  if (!uploadedFile.value) return '';
  const ext = uploadedFile.value.name.split('.').pop()?.toLowerCase() || '';
  const map: Record<string, string> = {
    pdf: 'PDF',
    docx: 'DOCX',
    doc: 'DOC',
    txt: 'TXT',
    png: 'PNG',
    jpg: 'JPG',
    jpeg: 'JPEG',
    webp: 'WEBP',
    xlsx: 'XLSX',
    pptx: 'PPTX',
  };
  return map[ext] || ext.toUpperCase();
});

// 可选目标格式
const targetOptions = computed(() => {
  const allOptions = [
    { value: 'pdf', label: 'PDF' },
    { value: 'docx', label: 'Word (.docx)' },
    { value: 'txt', label: '纯文本 (.txt)' },
    { value: 'png', label: 'PNG 图片' },
    { value: 'jpg', label: 'JPG 图片' },
    { value: 'webp', label: 'WebP 图片' },
  ];
  return allOptions.filter(
    (o) => o.value !== uploadedFile.value?.name.split('.').pop()?.toLowerCase(),
  );
});

function formatSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  return (bytes / 1024).toFixed(1) + ' KB';
}

function triggerUpload() {
  fileInputRef.value?.click();
}

function handleFileChange(e: Event) {
  const input = e.target as HTMLInputElement;
  if (input.files?.length) {
    setFile(input.files[0]);
  }
}

function handleDrop(e: DragEvent) {
  isDragover.value = false;
  if (e.dataTransfer?.files.length) {
    setFile(e.dataTransfer.files[0]);
  }
}

function setFile(file: File) {
  uploadedFile.value = file;
  targetFormat.value = '';
  result.value = null;
}

function clearFile() {
  uploadedFile.value = null;
  targetFormat.value = '';
  result.value = null;
  if (fileInputRef.value) fileInputRef.value.value = '';
}

async function handleConvert() {
  if (!uploadedFile.value || !targetFormat.value) return;

  converting.value = true;
  convertError.value = false;
  progress.value = 0;
  result.value = null;

  // 模拟进度
  progressTimer = setInterval(() => {
    if (progress.value < 90) progress.value += Math.floor(Math.random() * 15) + 5;
  }, 300);

  try {
    const res = await docToolsApi.convertFile(uploadedFile.value, targetFormat.value);
    progress.value = 100;
    result.value = res;
    store.addRecord({
      tool: 'convert',
      filename: uploadedFile.value.name,
      status: 'completed',
      details: `${detectedFormat.value} → ${targetFormat.value.toUpperCase()}`,
    });
    ElMessage.success('转换完成');
  } catch {
    convertError.value = true;
    ElMessage.error('转换失败，请重试');
  } finally {
    if (progressTimer) clearInterval(progressTimer);
    converting.value = false;
  }
}

function downloadFile() {
  if (result.value?.download_url) {
    ElMessage.info('文件下载中...（Mock 模式下为模拟下载）');
    // 实际环境中触发下载
  }
}
</script>

<style scoped lang="scss">
.convert-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.upload-zone {
  border: 2px dashed var(--fuxi-border);
  border-radius: var(--fuxi-radius);
  padding: 40px 20px;
  text-align: center;
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  background: var(--fuxi-bg-subtle);

  &:hover,
  &--dragover {
    border-color: var(--fuxi-primary);
    background: var(--fuxi-primary-light);
  }

  &--has-file {
    border-style: solid;
    border-color: var(--fuxi-primary);
  }
}

.upload-icon {
  color: var(--fuxi-text-tertiary);
  margin-bottom: var(--space-sm);
}

.upload-text {
  margin: 0;
  font-size: var(--font-size-caption);
  color: var(--fuxi-text);
  font-weight: 500;
}

.upload-hint {
  margin: 6px 0 0;
  font-size: var(--font-size-small);
  color: var(--fuxi-text-tertiary);
}

.file-input-hidden {
  display: none;
}

.file-info {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.file-size {
  font-size: var(--font-size-small);
  color: var(--fuxi-text-secondary);
}

.convert-options {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  flex-wrap: wrap;

  @media (max-width: 500px) {
    flex-direction: column;
    align-items: flex-start;
  }
}

.option-label {
  font-weight: 600;
  font-size: var(--font-size-caption);
  color: var(--fuxi-text);
}

.convert-progress {
  padding: var(--space-md);
  background: var(--fuxi-bg-subtle);
  border-radius: var(--radius-md);
}

.convert-error {
  padding: var(--space-md);
  background: var(--fuxi-bg-subtle);
  border-radius: var(--radius-md);
}

.progress-text {
  margin: var(--space-sm) 0 0;
  font-size: var(--font-size-small);
  color: var(--fuxi-text-secondary);
  text-align: center;
}

.convert-result {
  padding: var(--space-md);
  background: var(--fuxi-bg-subtle);
  border-radius: var(--radius-md);
  border-left: 3px solid var(--fuxi-success);
}

.result-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--space-sm);
}

.result-name {
  font-weight: 600;
  font-size: var(--font-size-caption);
  color: var(--fuxi-text);
}
</style>
