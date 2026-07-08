<template>
  <!--
    伏羲 v2.1 — 图片信息面板
    图片上传 → 元数据展示（尺寸/格式/DPI/EXIF/文件大小/宽高比/色彩空间）
  -->
  <div class="image-info-panel">
    <div
      v-if="!uploadedFile"
      class="upload-zone"
      :class="{ 'upload-zone--dragover': isDragover }"
      @dragover.prevent="isDragover = true"
      @dragleave.prevent="isDragover = false"
      @drop.prevent="handleDrop"
      @click="triggerUpload"
    >
      <el-icon :size="40" class="upload-icon"><PictureFilled /></el-icon>
      <p class="upload-text">拖放图片到此处或点击上传</p>
      <p class="upload-hint">支持 PNG、JPG、JPEG、WebP 格式</p>
      <input
        ref="fileInputRef"
        type="file"
        accept="image/*"
        class="file-input-hidden"
        @change="handleFileChange"
      />
    </div>

    <div v-else class="info-content">
      <div class="file-info-bar">
        <el-icon :size="20"><PictureFilled /></el-icon>
        <span class="file-name">{{ uploadedFile.name }}</span>
        <span class="file-size">{{ formatSize(uploadedFile.size) }}</span>
        <el-button text size="small" @click="resetFile">重新选择</el-button>
      </div>

      <el-button type="primary" :loading="loading" @click="fetchInfo">
        <el-icon><Search /></el-icon> 获取图片信息
      </el-button>

      <div v-if="info" class="meta-grid">
        <div class="meta-card">
          <span class="meta-label">尺寸</span>
          <span class="meta-value">{{ info.width }} × {{ info.height }} px</span>
        </div>
        <div class="meta-card">
          <span class="meta-label">格式</span>
          <span class="meta-value">{{ info.format }}</span>
        </div>
        <div class="meta-card">
          <span class="meta-label">DPI</span>
          <span class="meta-value">{{ info.dpi }}</span>
        </div>
        <div class="meta-card">
          <span class="meta-label">文件大小</span>
          <span class="meta-value">{{ formatSize(info.file_size) }}</span>
        </div>
        <div class="meta-card">
          <span class="meta-label">宽高比</span>
          <span class="meta-value">{{ info.aspect_ratio }}</span>
        </div>
        <div class="meta-card">
          <span class="meta-label">色彩空间</span>
          <span class="meta-value">{{ info.color_space }}</span>
        </div>
      </div>

      <div v-if="info && Object.keys(info.exif).length" class="exif-section">
        <h4 class="section-title">EXIF 信息</h4>
        <div class="exif-list">
          <div v-for="(val, key) in info.exif" :key="key" class="exif-item">
            <span class="exif-key">{{ key }}</span>
            <span class="exif-value">{{ val }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { ElMessage } from 'element-plus';
import { PictureFilled, Search } from '@element-plus/icons-vue';
import * as docToolsApi from './api';
import type { ImageMeta } from './types';

const fileInputRef = ref<HTMLInputElement | null>(null);
const isDragover = ref(false);
const uploadedFile = ref<File | null>(null);
const info = ref<ImageMeta | null>(null);
const loading = ref(false);

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
  info.value = null;
}
function resetFile() {
  uploadedFile.value = null;
  info.value = null;
  if (fileInputRef.value) fileInputRef.value.value = '';
}

async function fetchInfo() {
  if (!uploadedFile.value) return;
  loading.value = true;
  try {
    const res = await docToolsApi.getImageInfo(uploadedFile.value);
    info.value = res;
  } catch {
    ElMessage.error('获取图片信息失败');
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped lang="scss">
.image-info-panel {
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
.info-content {
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
.meta-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-sm);
  @media (max-width: 500px) {
    grid-template-columns: repeat(2, 1fr);
  }
}
.meta-card {
  padding: var(--space-md);
  background: var(--fuxi-bg-subtle);
  border-radius: var(--radius-sm);
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.meta-label {
  font-size: var(--font-size-small);
  color: var(--fuxi-text-tertiary);
}
.meta-value {
  font-size: var(--font-size-body);
  font-weight: 700;
  color: var(--fuxi-text);
  font-variant-numeric: tabular-nums;
}
.exif-section {
  padding: var(--space-md);
  background: var(--fuxi-bg-subtle);
  border-radius: var(--radius-md);
}
.section-title {
  margin: 0 0 var(--space-sm) 0;
  font-size: var(--font-size-caption);
  font-weight: 600;
  color: var(--fuxi-text);
}
.exif-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 240px;
  overflow-y: auto;
}
.exif-item {
  display: flex;
  justify-content: space-between;
  padding: 6px 8px;
  background: var(--fuxi-bg-card);
  border-radius: 4px;
  font-size: var(--font-size-small);
}
.exif-key {
  color: var(--fuxi-text-secondary);
  font-weight: 500;
}
.exif-value {
  color: var(--fuxi-text);
  font-variant-numeric: tabular-nums;
}
</style>
