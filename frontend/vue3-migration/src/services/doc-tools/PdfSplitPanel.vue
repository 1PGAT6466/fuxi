<template>
  <div class="pdf-split-panel">
    <div
      v-if="!uploadedFile"
      class="upload-zone"
      :class="{ 'upload-zone--dragover': isDragover }"
      @dragover.prevent="isDragover = true"
      @dragleave.prevent="isDragover = false"
      @drop.prevent="handleDrop"
      @click="triggerUpload"
    >
      <el-icon :size="40" class="upload-icon"><UploadFilled /></el-icon>
      <p class="upload-text">拖放 PDF 文件到此处或点击上传</p>
      <p class="upload-hint">支持 .pdf 文件</p>
      <input
        ref="fileInputRef"
        type="file"
        accept=".pdf"
        class="file-input-hidden"
        @change="handleFileChange"
      />
    </div>

    <div v-else class="split-config">
      <div class="file-info-bar">
        <el-icon :size="20"><Document /></el-icon>
        <span class="file-name">{{ uploadedFile.name }}</span>
        <span class="file-size">{{ formatSize(uploadedFile.size) }}</span>
        <el-button text size="small" @click="resetFile">重新选择</el-button>
      </div>

      <div class="page-input-section">
        <label class="option-label">页码范围</label>
        <el-input v-model="pageRange" placeholder="例如：1-5,8,10-12" class="page-input">
          <template #prepend>页码</template>
        </el-input>
        <p class="range-hint">支持逗号分隔和连字符范围，如 "1-5,8,10-12"</p>
      </div>

      <div v-if="parsedRanges.length" class="range-preview">
        <div class="preview-header">
          <span>已解析 {{ parsedRanges.length }} 个范围</span>
        </div>
        <div class="range-chips">
          <el-tag
            v-for="(r, i) in parsedRanges"
            :key="i"
            size="small"
            type="info"
            class="range-chip"
          >
            {{ r.start === r.end ? `${r.start}` : `${r.start}-${r.end}` }}
          </el-tag>
        </div>
      </div>

      <el-button
        type="primary"
        :loading="splitting"
        :disabled="!parsedRanges.length"
        @click="handleSplit"
      >
        <el-icon><Scissor /></el-icon> 开始拆分
      </el-button>
    </div>

    <div v-if="splitting" class="split-progress">
      <el-progress :percentage="splitProgress" :stroke-width="8" striped striped-flow />
      <p class="progress-text">正在拆分 PDF...</p>
    </div>

    <!-- 错误态 -->
    <div v-if="splitError" class="split-error">
      <el-result icon="error" title="拆分失败" sub-title="PDF 拆分失败，请重试">
        <template #extra>
          <el-button type="primary" size="small" @click="handleSplit">重试</el-button>
        </template>
      </el-result>
    </div>

    <div v-else-if="splitResult && splitResult.parts.length" class="split-result">
      <h4 class="result-title">拆分结果（{{ splitResult.parts.length }} 个文件）</h4>
      <div class="part-list">
        <div v-for="(part, i) in splitResult.parts" :key="i" class="part-item">
          <span class="part-index">{{ i + 1 }}</span>
          <span class="part-range">{{ part.range }}</span>
          <span class="part-name">{{ part.filename }}</span>
          <span class="part-pages">{{ part.page_count }} 页</span>
          <el-button size="small" type="primary" @click="$emit('downloadPart', part)">
            <el-icon><Download /></el-icon>
          </el-button>
        </div>
      </div>
      <el-button type="primary" class="download-all-btn" @click="$emit('downloadAll')">
        <el-icon><Download /></el-icon> 批量下载全部
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { ElMessage } from 'element-plus';
import { UploadFilled, Document, Scissor, Download } from '@element-plus/icons-vue';
import * as docToolsApi from './api';
import { useDocToolsStore } from './store';
import type { SplitResponse, SplitPageInfo } from './types';

defineEmits<{
  (e: 'downloadPart', part: SplitPageInfo): void;
  (e: 'downloadAll'): void;
}>();

const store = useDocToolsStore();
const fileInputRef = ref<HTMLInputElement | null>(null);
const isDragover = ref(false);
const uploadedFile = ref<File | null>(null);
const pageRange = ref('1-5,8,10-12');
const splitting = ref(false);
const splitError = ref(false);
const splitProgress = ref(0);
const splitResult = ref<SplitResponse | null>(null);
let progressTimer: ReturnType<typeof setInterval> | null = null;

interface ParsedRange {
  start: number;
  end: number;
}

function formatSize(b: number): string {
  return b >= 1024 * 1024 ? (b / (1024 * 1024)).toFixed(1) + ' MB' : (b / 1024).toFixed(0) + ' KB';
}

function parsePageRanges(inp: string): ParsedRange[] {
  const parts = inp.split(',').map((s) => s.trim());
  const ranges: ParsedRange[] = [];
  for (const p of parts) {
    if (!p) continue;
    if (p.includes('-')) {
      const [s, e] = p.split('-').map(Number);
      if (!isNaN(s) && !isNaN(e) && s > 0 && e >= s) ranges.push({ start: s, end: e });
    } else {
      const n = Number(p);
      if (!isNaN(n) && n > 0) ranges.push({ start: n, end: n });
    }
  }
  return ranges;
}

const parsedRanges = computed(() => parsePageRanges(pageRange.value));

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
  splitResult.value = null;
}
function resetFile() {
  uploadedFile.value = null;
  splitResult.value = null;
  if (fileInputRef.value) fileInputRef.value.value = '';
}

async function handleSplit() {
  if (!uploadedFile.value || !parsedRanges.value.length) return;
  splitting.value = true;
  splitProgress.value = 0;
  splitResult.value = null;
  progressTimer = setInterval(() => {
    if (splitProgress.value < 90) splitProgress.value += Math.floor(Math.random() * 12) + 3;
  }, 200);
  try {
    const allParts: SplitPageInfo[] = [];
    for (const r of parsedRanges.value) {
      const res = await docToolsApi.splitPdf(uploadedFile.value, r.start, r.end);
      allParts.push(...res.parts);
    }
    splitProgress.value = 100;
    splitResult.value = { id: `spl_${Date.now()}`, status: 'completed', parts: allParts };
    store.addRecord({
      tool: 'split',
      filename: uploadedFile.value.name,
      status: 'completed',
      details: `拆分为 ${allParts.length} 个文件`,
    });
    ElMessage.success('PDF 拆分完成');
  } catch {
    ElMessage.error('拆分失败，请重试');
  } finally {
    if (progressTimer) clearInterval(progressTimer);
    splitting.value = false;
  }
}
</script>

<style scoped lang="scss">
.pdf-split-panel {
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
.split-config {
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
.page-input-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.option-label {
  font-weight: 600;
  font-size: var(--font-size-caption);
  color: var(--fuxi-text);
}
.page-input {
  max-width: 360px;
}
.range-hint {
  margin: 0;
  font-size: var(--font-size-small);
  color: var(--fuxi-text-tertiary);
}
.range-preview {
  padding: var(--space-sm);
  background: var(--fuxi-bg-subtle);
  border-radius: var(--radius-sm);
}
.preview-header {
  margin-bottom: var(--space-xs);
  font-size: var(--font-size-small);
  color: var(--fuxi-text-secondary);
}
.range-chips {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.split-progress {
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
.split-result {
  padding: var(--space-md);
  background: var(--fuxi-bg-subtle);
  border-radius: var(--radius-md);
}
.result-title {
  margin: 0 0 var(--space-sm) 0;
  font-size: var(--font-size-caption);
  font-weight: 600;
  color: var(--fuxi-text);
}
.part-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: var(--space-md);
}
.part-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: var(--fuxi-bg-card);
  border-radius: var(--radius-sm);
  border: 1px solid var(--fuxi-border);
}
.part-index {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--fuxi-primary);
  color: #fff;
  font-size: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.part-range {
  font-size: var(--font-size-small);
  color: var(--fuxi-text-tertiary);
  flex-shrink: 0;
}
.part-name {
  flex: 1;
  font-size: var(--font-size-caption);
  color: var(--fuxi-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.part-pages {
  font-size: var(--font-size-small);
  color: var(--fuxi-text-secondary);
  flex-shrink: 0;
}
.download-all-btn {
  margin-top: var(--space-sm);
}
</style>
