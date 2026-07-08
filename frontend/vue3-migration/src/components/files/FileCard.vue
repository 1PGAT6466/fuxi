<!--
  伏羲 v2.1 — 文件卡片组件
  用于卡片视图展示文件信息
-->
<template>
  <div class="file-card" @click="$emit('click', file)">
    <!-- 文件图标 -->
    <div class="file-card-icon" :class="fileTypeClass">
      <el-icon :size="28">
        <Document v-if="isDocument" />
        <PictureFilled v-else-if="isImage" />
        <VideoPlay v-else-if="isVideo" />
        <Files v-else />
      </el-icon>
    </div>

    <!-- 文件信息 -->
    <div class="file-card-info">
      <div class="file-card-name" :title="file.filename">{{ file.filename }}</div>
      <div class="file-card-meta">
        <span>{{ formatSize(file.size) }}</span>
        <span>·</span>
        <span>{{ formatDateOnly(file.uploadedAt) }}</span>
      </div>
      <div v-if="file.status" class="file-card-status">
        <el-tag :type="statusTagType" size="small">{{ statusLabel }}</el-tag>
      </div>
    </div>

    <!-- 操作按钮 -->
    <div class="file-card-actions" @click.stop>
      <el-tooltip content="预览" placement="top">
        <button class="action-btn" @click="$emit('preview', file)">
          <el-icon :size="16"><View /></el-icon>
        </button>
      </el-tooltip>
      <el-tooltip content="下载" placement="top">
        <button class="action-btn" @click="$emit('download', file)">
          <el-icon :size="16"><Download /></el-icon>
        </button>
      </el-tooltip>
      <el-popconfirm
        title="确定删除此文件？"
        confirm-button-text="确定"
        cancel-button-text="取消"
        @confirm="$emit('delete', file)"
      >
        <template #reference>
          <button class="action-btn danger">
            <el-icon :size="16"><Delete /></el-icon>
          </button>
        </template>
      </el-popconfirm>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import {
  Document,
  PictureFilled,
  VideoPlay,
  Files,
  View,
  Download,
  Delete,
} from '@element-plus/icons-vue';
import { formatSize, formatDateOnly } from '@/utils/helpers';
import type { FileInfo } from '@/types';

const props = defineProps<{
  file: FileInfo;
}>();

defineEmits<{
  click: [file: FileInfo];
  preview: [file: FileInfo];
  download: [file: FileInfo];
  delete: [file: FileInfo];
}>();

const ext = computed(() => {
  const name = props.file.filename || '';
  const idx = name.lastIndexOf('.');
  return idx >= 0 ? name.slice(idx + 1).toLowerCase() : '';
});

const isDocument = computed(() =>
  ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'md', 'csv'].includes(ext.value),
);
const isImage = computed(() => ['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp'].includes(ext.value));
const isVideo = computed(() => ['mp4', 'avi', 'mov', 'mkv'].includes(ext.value));

const fileTypeClass = computed(() => {
  if (isDocument.value) return 'type-doc';
  if (isImage.value) return 'type-img';
  if (isVideo.value) return 'type-video';
  return 'type-other';
});

const statusLabel = computed(() => {
  const status = props.file.status;
  if (!status) return '';
  const map: Record<string, string> = {
    uploaded: '已上传',
    processing: '处理中',
    ready: '就绪',
    error: '失败',
  };
  return map[status] || status;
});

const statusTagType = computed<'success' | 'warning' | 'danger' | 'info'>(() => {
  const status = props.file.status;
  if (!status) return 'info';
  const map: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
    uploaded: 'info',
    processing: 'warning',
    ready: 'success',
    error: 'danger',
  };
  return map[status] || 'info';
});
</script>

<style scoped lang="scss">
.file-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px;
  background: var(--fuxi-bg-card);
  border: 1px solid var(--fuxi-border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.2s var(--ease-out);

  &:hover {
    border-color: var(--fuxi-primary);
    box-shadow: var(--fuxi-shadow);
    transform: translateY(-1px);
  }
}

.file-card-icon {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;

  &.type-doc {
    background: var(--kan-color-light);
    color: var(--kan-color);
  }

  &.type-img {
    background: var(--li-color-light);
    color: var(--li-color);
  }

  &.type-video {
    background: var(--zhen-color-light);
    color: var(--zhen-color);
  }

  &.type-other {
    background: var(--fuxi-bg-subtle);
    color: var(--fuxi-text-secondary);
  }
}

.file-card-info {
  flex: 1;
  min-width: 0;
}

.file-card-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--fuxi-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-bottom: 4px;
}

.file-card-meta {
  font-size: 12px;
  color: var(--fuxi-text-secondary);
  display: flex;
  gap: 6px;
}

.file-card-status {
  margin-top: 4px;
}

.file-card-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;

  .file-card:hover & {
    opacity: 1;
  }
}

.action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 1px solid var(--fuxi-border);
  border-radius: var(--radius-sm);
  background: var(--fuxi-bg-card);
  color: var(--fuxi-text-secondary);
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    border-color: var(--fuxi-primary);
    color: var(--fuxi-primary);
    background: var(--fuxi-primary-light);
  }

  &.danger:hover {
    border-color: var(--fuxi-error);
    color: var(--fuxi-error);
    background: var(--fuxi-error-bg);
  }
}
</style>
