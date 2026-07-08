<!--
  伏羲 v2.1 — 文件预览模态框
  支持图片/PDF/文本在线预览
-->
<template>
  <el-dialog
    v-model="visible"
    :title="file?.filename || '文件预览'"
    width="800px"
    top="5vh"
    destroy-on-close
    @close="$emit('close')"
  >
    <div v-loading="loading" class="file-preview">
      <!-- 图片预览 -->
      <div v-if="isImage" class="preview-image">
        <img :src="previewUrl" :alt="file?.filename" />
      </div>

      <!-- PDF 预览 -->
      <div v-else-if="isPdf" class="preview-pdf">
        <iframe :src="previewUrl" class="pdf-iframe" />
      </div>

      <!-- 文本预览 -->
      <div v-else-if="isText" class="preview-text">
        <pre>{{ textContent }}</pre>
      </div>

      <!-- 不支持预览 -->
      <div v-else class="preview-unsupported">
        <el-icon :size="48"><WarningFilled /></el-icon>
        <p>该文件类型不支持在线预览</p>
        <el-button type="primary" @click="$emit('download', file!)"> 下载文件 </el-button>
      </div>
    </div>

    <template #footer>
      <div class="preview-footer">
        <span v-if="file" class="preview-meta">
          {{ formatSize(file.size) }} · {{ formatDateOnly(file.uploadedAt) }}
        </span>
        <div class="preview-actions">
          <el-button @click="visible = false">关闭</el-button>
          <el-button v-if="file" type="primary" @click="$emit('download', file!)"> 下载 </el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { WarningFilled } from '@element-plus/icons-vue';
import { formatSize, formatDateOnly } from '@/utils/helpers';
import type { FileInfo } from '@/types';
import apiClient from '@/api';

const props = defineProps<{
  modelValue: boolean;
  file: FileInfo | null;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: boolean];
  close: [];
  download: [file: FileInfo];
}>();

const visible = ref(props.modelValue);
const loading = ref(false);
const previewUrl = ref('');
const textContent = ref('');

watch(
  () => props.modelValue,
  (val) => {
    visible.value = val;
    if (val && props.file) {
      loadPreview();
    }
  },
);

watch(visible, (val) => {
  emit('update:modelValue', val);
});

const ext = computed(() => {
  if (!props.file?.filename) return '';
  const idx = props.file.filename.lastIndexOf('.');
  return idx >= 0 ? props.file.filename.slice(idx + 1).toLowerCase() : '';
});

const isImage = computed(() =>
  ['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'bmp'].includes(ext.value),
);

const isPdf = computed(() => ext.value === 'pdf');

const isText = computed(() =>
  ['txt', 'md', 'csv', 'json', 'xml', 'html', 'css', 'js', 'ts'].includes(ext.value),
);

async function loadPreview(): Promise<void> {
  if (!props.file?.hash) return;
  loading.value = true;

  try {
    const hash = props.file.hash || props.file.id;
    previewUrl.value = `/api/view/${hash}`;

    // 文本文件额外拉取内容
    if (isText.value) {
      const data = (await apiClient.get(`/api/view/${hash}`)) as string;
      textContent.value = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
    }
  } catch {
    // 预览失败，显示未支持
    previewUrl.value = '';
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped lang="scss">
.file-preview {
  min-height: 300px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-image {
  text-align: center;

  img {
    max-width: 100%;
    max-height: 70vh;
    border-radius: var(--radius-sm);
  }
}

.preview-pdf {
  width: 100%;
  height: 70vh;

  .pdf-iframe {
    width: 100%;
    height: 100%;
    border: none;
    border-radius: var(--radius-sm);
  }
}

.preview-text {
  width: 100%;
  max-height: 70vh;
  overflow: auto;

  pre {
    background: var(--fuxi-bg, #FAFAF5);
    border: 1px solid var(--fuxi-border, #E8E4D9);
    color: var(--fuxi-text-primary, #333333);
    [data-theme='dark'] & {
      background: #1A1A2E;
      border-color: #333355;
      color: #E0E0E0;
    }
    padding: 20px;
    border-radius: var(--radius-sm);
    font-size: 13px;
    line-height: 1.6;
    white-space: pre-wrap;
    word-break: break-word;
    margin: 0;
  }
}

.preview-unsupported {
  text-align: center;
  color: var(--fuxi-text-secondary);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;

  p {
    margin: 0;
    font-size: 14px;
  }
}

.preview-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.preview-meta {
  font-size: 12px;
  color: var(--fuxi-text-tertiary);
}

.preview-actions {
  display: flex;
  gap: 8px;
}
</style>
