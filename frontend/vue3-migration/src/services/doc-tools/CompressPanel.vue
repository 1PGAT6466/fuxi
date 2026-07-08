<template>
  <!--
    伏羲 v2.1 — 文件压缩面板
    文件上传 → 压缩选项（质量/分辨率）→ 压缩前后对比 → 下载
  -->
  <div class="compress-panel">
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
      <p class="upload-text">拖放文件到此处或点击上传</p>
      <p class="upload-hint">支持 PDF、图片（PNG/JPG/WebP）</p>
      <input ref="fileInputRef" type="file" class="file-input-hidden" @change="handleFileChange" />
    </div>

    <div v-else class="compress-config">
      <div class="file-info-bar">
        <el-icon :size="20"><Document /></el-icon>
        <span class="file-name">{{ uploadedFile.name }}</span>
        <span class="file-size">{{ formatSize(uploadedFile.size) }}</span>
        <el-button text size="small" @click="resetFile">重新选择</el-button>
      </div>

      <div class="compress-options">
        <div class="option-group">
          <label class="option-label">压缩质量</label>
          <el-radio-group v-model="quality" size="small">
            <el-radio-button value="high">高质量</el-radio-button>
            <el-radio-button value="medium">中等</el-radio-button>
            <el-radio-button value="low">高压缩</el-radio-button>
          </el-radio-group>
        </div>
        <div class="option-group">
          <label class="option-label">分辨率</label>
          <el-radio-group v-model="resolution" size="small">
            <el-radio-button value="original">原始</el-radio-button>
            <el-radio-button value="1080p">1080p</el-radio-button>
            <el-radio-button value="720p">720p</el-radio-button>
          </el-radio-group>
        </div>
      </div>

      <el-button type="primary" :loading="compressing" @click="handleCompress">
        <el-icon><Minus /></el-icon> 开始压缩
      </el-button>
    </div>

    <div v-if="compressing" class="compress-progress">
      <el-progress :percentage="compressProgress" :stroke-width="8" striped striped-flow />
      <p class="progress-text">正在压缩文件...</p>
    </div>

    <div v-if="compressResult" class="compress-result">
      <h4 class="result-title">压缩完成</h4>
      <div class="compare-grid">
        <div class="compare-card">
          <span class="compare-label">压缩前</span>
          <span class="compare-value">{{ formatSize(compressResult.original_size) }}</span>
        </div>
        <div class="compare-arrow">→</div>
        <div class="compare-card compare-card--compressed">
          <span class="compare-label">压缩后</span>
          <span class="compare-value">{{ formatSize(compressResult.compressed_size) }}</span>
        </div>
      </div>
      <div class="stats-row">
        <el-tag type="success" size="small">压缩率 {{ compressResult.ratio }}%</el-tag>
        <el-tag size="small" type="info">
          节省 {{ formatSize(compressResult.original_size - compressResult.compressed_size) }}
        </el-tag>
      </div>
      <el-button type="primary" class="download-btn" @click="downloadFile">
        <el-icon><Download /></el-icon> 下载压缩文件
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { ElMessage } from 'element-plus';
import { UploadFilled, Document, Minus, Download } from '@element-plus/icons-vue';
import * as docToolsApi from './api';
import { useDocToolsStore } from './store';
import type { CompressResult, CompressOptions } from './types';

const store = useDocToolsStore();
const fileInputRef = ref<HTMLInputElement | null>(null);
const isDragover = ref(false);
const uploadedFile = ref<File | null>(null);
const quality = ref<CompressOptions['quality']>('medium');
const resolution = ref<CompressOptions['resolution']>('original');
const compressing = ref(false);
const compressProgress = ref(0);
const compressResult = ref<CompressResult | null>(null);
let progressTimer: ReturnType<typeof setInterval> | null = null;

function formatSize(b: number): string {
  if (b >= 1024 * 1024) return (b / (1024 * 1024)).toFixed(2) + ' MB';
  return (b / 1024).toFixed(1) + ' KB';
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
  compressResult.value = null;
}
function resetFile() {
  uploadedFile.value = null;
  compressResult.value = null;
  if (fileInputRef.value) fileInputRef.value.value = '';
}

async function handleCompress() {
  if (!uploadedFile.value) return;
  compressing.value = true;
  compressProgress.value = 0;
  compressResult.value = null;
  progressTimer = setInterval(() => {
    if (compressProgress.value < 90) compressProgress.value += Math.floor(Math.random() * 10) + 3;
  }, 250);
  try {
    const res = await docToolsApi.compressFile(uploadedFile.value, {
      quality: quality.value,
      resolution: resolution.value,
    });
    compressProgress.value = 100;
    compressResult.value = res;
    store.addRecord({
      tool: 'compress',
      filename: uploadedFile.value.name,
      status: 'completed',
      details: `压缩率 ${res.ratio}%`,
    });
    ElMessage.success('压缩完成');
  } catch {
    ElMessage.error('压缩失败');
  } finally {
    if (progressTimer) clearInterval(progressTimer);
    compressing.value = false;
  }
}

function downloadFile() {
  if (compressResult.value) ElMessage.info('文件下载中...（Mock 模式）');
}
</script>

<style scoped lang="scss">
.compress-panel {
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
.compress-config {
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
.compress-options {
  display: flex;
  gap: var(--space-lg);
  flex-wrap: wrap;
}
.option-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.option-label {
  font-weight: 600;
  font-size: var(--font-size-caption);
  color: var(--fuxi-text);
}
.compress-progress {
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
.compress-result {
  padding: var(--space-md);
  background: var(--fuxi-bg-subtle);
  border-radius: var(--radius-md);
  border-left: 3px solid var(--fuxi-success);
}
.result-title {
  margin: 0 0 var(--space-sm) 0;
  font-size: var(--font-size-caption);
  font-weight: 600;
  color: var(--fuxi-text);
}
.compare-grid {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  margin-bottom: var(--space-sm);
}
.compare-card {
  flex: 1;
  padding: var(--space-md);
  background: var(--fuxi-bg-card);
  border-radius: var(--radius-sm);
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.compare-card--compressed {
  border: 1px solid var(--fuxi-success);
}
.compare-label {
  font-size: var(--font-size-small);
  color: var(--fuxi-text-tertiary);
}
.compare-value {
  font-size: var(--font-size-body);
  font-weight: 700;
  color: var(--fuxi-text);
}
.compare-arrow {
  font-size: 20px;
  color: var(--fuxi-text-tertiary);
}
.stats-row {
  display: flex;
  gap: var(--space-sm);
  margin-bottom: var(--space-md);
}
.download-btn {
  width: 100%;
}
</style>
