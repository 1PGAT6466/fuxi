<template>
  <!--
    伏羲 v2.1 — PDF 合并面板
    多文件上传列表（可拖拽排序）→ 预览合并顺序 → 合并按钮 → 下载
  -->
  <div class="pdf-merge-panel">
    <!-- 上传区域 -->
    <div
      class="upload-zone"
      :class="{ 'upload-zone--dragover': isDragover }"
      @dragover.prevent="isDragover = true"
      @dragleave.prevent="isDragover = false"
      @drop.prevent="handleDrop"
      @click="triggerUpload"
    >
      <el-icon :size="40" class="upload-icon"><UploadFilled /></el-icon>
      <p class="upload-text">拖放 PDF 文件到此处或点击上传</p>
      <p class="upload-hint">支持多文件同时上传，可拖拽排序</p>
      <input
        ref="fileInputRef"
        type="file"
        accept=".pdf"
        multiple
        class="file-input-hidden"
        @change="handleFileChange"
      />
    </div>

    <!-- 文件列表（可拖拽排序） -->
    <div v-if="fileList.length" class="file-list-section">
      <div class="file-list-header">
        <h4 class="section-title">文件列表（{{ fileList.length }} 个文件）</h4>
        <el-button text size="small" @click="clearAll">清空全部</el-button>
      </div>

      <div ref="sortListRef" class="file-list">
        <div
          v-for="(file, idx) in fileList"
          :key="file.id"
          class="file-item"
          draggable="true"
          @dragstart="handleDragStart(idx)"
          @dragover.prevent="handleDragOver(idx)"
          @drop.prevent="handleDropSort(idx)"
        >
          <span class="file-order">{{ idx + 1 }}</span>
          <el-icon :size="16" class="file-icon"><Document /></el-icon>
          <span class="file-name">{{ file.name }}</span>
          <span class="file-size">{{ formatSize(file.size) }}</span>
          <el-button text size="small" type="danger" @click="removeFile(idx)">
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>
      </div>
    </div>

    <!-- 合并操作 -->
    <div v-if="fileList.length >= 2" class="merge-action">
      <el-button type="primary" :loading="merging" @click="handleMerge">
        <el-icon><Connection /></el-icon>
        合并 PDF
      </el-button>
      <span class="merge-hint">将按列表顺序合并为单个 PDF 文件</span>
    </div>

    <!-- 进度 -->
    <div v-if="merging || mergeResult" class="merge-progress">
      <el-progress
        :percentage="merging ? mergeProgress : 100"
        :status="merging ? undefined : 'success'"
        :stroke-width="8"
        striped
        :striped-flow="merging"
      />
    </div>

    <!-- 错误态 -->
    <div v-if="mergeError" class="merge-error">
      <el-result icon="error" title="合并失败" sub-title="PDF 合并失败，请重试">
        <template #extra>
          <el-button type="primary" size="small" @click="handleMerge">重试</el-button>
        </template>
      </el-result>
    </div>

    <!-- 结果下载 -->
    <div v-else-if="mergeResult" class="merge-result">
      <div class="result-row">
        <span class="result-name">{{ mergeResult.filename }}</span>
        <span class="result-pages">共 {{ mergeResult.page_count }} 页</span>
        <el-button type="primary" size="small" @click="downloadResult">
          <el-icon><Download /></el-icon>
          下载
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { ElMessage } from 'element-plus';
import { UploadFilled, Document, Delete, Connection, Download } from '@element-plus/icons-vue';
import * as docToolsApi from './api';
import { useDocToolsStore } from './store';
import type { MergeResponse, ToolFile } from './types';

const store = useDocToolsStore();

const fileInputRef = ref<HTMLInputElement | null>(null);
const isDragover = ref(false);
const fileList = ref<ToolFile[]>([]);
const merging = ref(false);
const mergeError = ref(false);
const mergeProgress = ref(0);
const mergeResult = ref<MergeResponse | null>(null);
let mergeTimer: ReturnType<typeof setInterval> | null = null;

// 拖拽排序
let dragIdx = -1;

function formatSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  return (bytes / 1024).toFixed(0) + ' KB';
}

function triggerUpload() {
  fileInputRef.value?.click();
}

function addFiles(files: FileList) {
  for (let i = 0; i < files.length; i++) {
    const f = files[i];
    if (!f.name.toLowerCase().endsWith('.pdf')) {
      ElMessage.warning(`文件 "${f.name}" 不是 PDF 格式，已跳过`);
      continue;
    }
    fileList.value.push({
      id: `f_${Date.now()}_${i}`,
      name: f.name,
      size: f.size,
      type: 'pdf',
      file: f,
    });
  }
}

function handleFileChange(e: Event) {
  const input = e.target as HTMLInputElement;
  if (input.files?.length) addFiles(input.files);
  if (fileInputRef.value) fileInputRef.value.value = '';
}

function handleDrop(e: DragEvent) {
  isDragover.value = false;
  if (e.dataTransfer?.files.length) addFiles(e.dataTransfer.files);
}

function removeFile(idx: number) {
  fileList.value.splice(idx, 1);
  mergeResult.value = null;
}

function clearAll() {
  fileList.value = [];
  mergeResult.value = null;
}

// 拖拽排序
function handleDragStart(idx: number) {
  dragIdx = idx;
}

function handleDragOver(idx: number) {
  if (dragIdx === -1 || dragIdx === idx) return;
  const item = fileList.value.splice(dragIdx, 1)[0];
  fileList.value.splice(idx, 0, item);
  dragIdx = idx;
}

function handleDropSort() {
  dragIdx = -1;
}

async function handleMerge() {
  if (fileList.value.length < 2) {
    ElMessage.warning('至少需要 2 个 PDF 文件');
    return;
  }

  merging.value = true;
  mergeError.value = false;
  mergeProgress.value = 0;
  mergeResult.value = null;

  mergeTimer = setInterval(() => {
    if (mergeProgress.value < 90) mergeProgress.value += Math.floor(Math.random() * 10) + 5;
  }, 200);

  const files = fileList.value.map((f) => f.file!).filter(Boolean);
  try {
    const res = await docToolsApi.mergePdfs(files);
    mergeProgress.value = 100;
    mergeResult.value = res;
    store.addRecord({
      tool: 'merge',
      filename: res.filename,
      status: 'completed',
      details: `合并 ${files.length} 个文件，共 ${res.page_count} 页`,
    });
    ElMessage.success('PDF 合并完成');
  } catch {
    mergeError.value = true;
    ElMessage.error('合并失败，请重试');
  } finally {
    if (mergeTimer) clearInterval(mergeTimer);
    merging.value = false;
  }
}

function downloadResult() {
  if (mergeResult.value?.download_url) {
    ElMessage.info('文件下载中...');
  }
}
</script>

<style scoped lang="scss">
.pdf-merge-panel {
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

.file-list-section {
  background: var(--fuxi-bg-subtle);
  border-radius: var(--radius-md);
  padding: var(--space-md);
}

.file-list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-sm);
}

.section-title {
  margin: 0;
  font-size: var(--font-size-caption);
  font-weight: 600;
  color: var(--fuxi-text);
}

.file-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: var(--fuxi-bg-card);
  border-radius: var(--radius-sm);
  border: 1px solid var(--fuxi-border);
  cursor: grab;
  transition: all var(--duration-fast);

  &:hover {
    border-color: var(--fuxi-primary);
  }
}

.file-order {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--fuxi-primary);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
}

.file-icon {
  color: var(--fuxi-primary);
  flex-shrink: 0;
}

.file-name {
  flex: 1;
  font-size: var(--font-size-caption);
  color: var(--fuxi-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-size {
  font-size: var(--font-size-small);
  color: var(--fuxi-text-tertiary);
  flex-shrink: 0;
}

.merge-action {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  flex-wrap: wrap;
}

.merge-hint {
  font-size: var(--font-size-small);
  color: var(--fuxi-text-tertiary);
}

.merge-progress {
  padding: var(--space-md);
  background: var(--fuxi-bg-subtle);
  border-radius: var(--radius-md);
}

.merge-error {
  padding: var(--space-md);
  background: var(--fuxi-bg-subtle);
  border-radius: var(--radius-md);
}

.merge-result {
  padding: var(--space-md);
  background: var(--fuxi-bg-subtle);
  border-radius: var(--radius-md);
  border-left: 3px solid var(--fuxi-success);
}

.result-row {
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

.result-pages {
  font-size: var(--font-size-small);
  color: var(--fuxi-text-secondary);
}
</style>
