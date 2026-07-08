<template>
  <!--
    伏羲 v2.1 — 文本提取面板
    文件上传（PDF/图片/Office）→ 提取文本预览 → 复制/下载
  -->
  <div class="text-extract-panel">
    <div
      v-if="!uploadedFile"
      class="upload-zone"
      :class="{ 'upload-zone--dragover': isDragover }"
      @dragover.prevent="isDragover = true"
      @dragleave.prevent="isDragover = false"
      @drop.prevent="handleDrop"
      @click="triggerUpload"
    >
      <el-icon :size="40" class="upload-icon"><Tickets /></el-icon>
      <p class="upload-text">拖放文件到此处或点击上传</p>
      <p class="upload-hint">支持 PDF、图片（PNG/JPG）、Office 文档</p>
      <input ref="fileInputRef" type="file" class="file-input-hidden" @change="handleFileChange" />
    </div>

    <div v-else class="extract-content">
      <div class="file-info-bar">
        <el-icon :size="20"><Tickets /></el-icon>
        <span class="file-name">{{ uploadedFile.name }}</span>
        <span class="file-size">{{ formatSize(uploadedFile.size) }}</span>
        <el-button text size="small" @click="resetFile">重新选择</el-button>
      </div>

      <el-button type="primary" :loading="extracting" @click="handleExtract">
        <el-icon><MagicStick /></el-icon> 提取文本
      </el-button>

      <div v-if="extractResult" class="extract-result">
        <div class="result-header">
          <h4 class="result-title">提取结果</h4>
          <div class="result-meta">
            <el-tag size="small" type="info">{{ extractResult.page_count }} 页</el-tag>
            <el-tag size="small" type="info">{{ extractResult.char_count }} 字</el-tag>
            <el-tag size="small" type="info">{{ extractResult.language }}</el-tag>
          </div>
        </div>
        <div class="text-preview">
          <pre class="text-content">{{ extractResult.text }}</pre>
        </div>
        <div class="result-actions">
          <el-button size="small" @click="copyText">
            <el-icon><CopyDocument /></el-icon> 复制全部
          </el-button>
          <el-button size="small" type="primary" @click="downloadText">
            <el-icon><Download /></el-icon> 下载 TXT
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { ElMessage } from 'element-plus';
import { Tickets, MagicStick, CopyDocument, Download } from '@element-plus/icons-vue';
import * as docToolsApi from './api';
import { useDocToolsStore } from './store';
import type { TextExtractResult } from './types';

const store = useDocToolsStore();
const fileInputRef = ref<HTMLInputElement | null>(null);
const isDragover = ref(false);
const uploadedFile = ref<File | null>(null);
const extracting = ref(false);
const extractResult = ref<TextExtractResult | null>(null);

function formatSize(b: number): string {
  return b >= 1024 * 1024 ? (b / (1024 * 1024)).toFixed(1) + ' MB' : (b / 1024).toFixed(0) + ' KB';
}

function triggerUpload() {
  fileInputRef.value?.click();
}
function handleFileChange(e: Event) {
  const t = e.target as HTMLInputElement;
  if (t.files?.length) setFile(t.files[0]);
}
function handleDrop(e: DragEvent) {
  isDragover.value = false;
  if (e.dataTransfer?.files.length) setFile(e.dataTransfer.files[0]);
}
function setFile(f: File) {
  uploadedFile.value = f;
  extractResult.value = null;
}
function resetFile() {
  uploadedFile.value = null;
  extractResult.value = null;
  if (fileInputRef.value) fileInputRef.value.value = '';
}

async function handleExtract() {
  if (!uploadedFile.value) return;
  extracting.value = true;
  try {
    const res = await docToolsApi.extractText(uploadedFile.value);
    extractResult.value = res;
    store.addRecord({
      tool: 'extract',
      filename: uploadedFile.value.name,
      status: 'completed',
      details: `提取 ${res.char_count} 字`,
    });
    ElMessage.success('文本提取完成');
  } catch {
    ElMessage.error('文本提取失败');
  } finally {
    extracting.value = false;
  }
}

async function copyText() {
  if (!extractResult.value) return;
  try {
    await navigator.clipboard.writeText(extractResult.value.text);
    ElMessage.success('已复制到剪贴板');
  } catch {
    ElMessage.error('复制失败');
  }
}

function downloadText() {
  if (!extractResult.value) return;
  const blob = new Blob([extractResult.value.text], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = uploadedFile.value
    ? uploadedFile.value.name.replace(/\.[^.]+$/, '') + '_extracted.txt'
    : 'extracted.txt';
  a.click();
  URL.revokeObjectURL(url);
  ElMessage.success('下载已开始');
}
</script>

<style scoped lang="scss">
.text-extract-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}
.upload-zone {
  border: 2px dashed var(--fuxi-border);
  border-radius: var(--fuxi-radius);
  padding: 32px 20px;
  text-align: center;
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  background: var(--fuxi-bg-subtle);
  &:hover,
  &--dragover {
    border-color: var(--fuxi-primary);
    background: var(--fuxi-primary-light);
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
.extract-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}
.file-info-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  background: var(--fuxi-bg-subtle);
  border-radius: var(--radius-md);
}
.file-name {
  font-weight: 600;
  font-size: var(--font-size-caption);
  color: var(--fuxi-text);
}
.file-size {
  font-size: var(--font-size-small);
  color: var(--fuxi-text-secondary);
}
.extract-result {
  padding: var(--space-md);
  background: var(--fuxi-bg-subtle);
  border-radius: var(--radius-md);
}
.result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-sm);
  flex-wrap: wrap;
  gap: var(--space-sm);
}
.result-title {
  margin: 0;
  font-size: var(--font-size-caption);
  font-weight: 600;
  color: var(--fuxi-text);
}
.result-meta {
  display: flex;
  gap: 6px;
}
.text-preview {
  max-height: 320px;
  overflow-y: auto;
  padding: var(--space-md);
  background: var(--fuxi-bg-card);
  border-radius: var(--radius-sm);
  border: 1px solid var(--fuxi-border);
  margin-bottom: var(--space-md);
}
.text-content {
  margin: 0;
  font-size: var(--font-size-caption);
  line-height: 1.8;
  color: var(--fuxi-text);
  white-space: pre-wrap;
  word-break: break-word;
  font-family: var(--font-family-base);
}
.result-actions {
  display: flex;
  gap: var(--space-sm);
  justify-content: flex-end;
}
</style>
