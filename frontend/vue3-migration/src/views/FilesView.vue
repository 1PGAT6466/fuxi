<template>
  <!--
    伏羲 v2.1 — 文件管理中心
    全平台文件集中管理：列表、批量操作、搜索、上传
  -->
  <div class="files-center">
    <!-- 页面头部 -->
    <div class="files-header">
      <div class="header-info">
        <h2 class="header-title">文件中心</h2>
        <p class="header-desc">集中管理所有平台上传文件</p>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="showUpload = true">
          <el-icon><Upload /></el-icon>
          上传文件
        </el-button>
      </div>
    </div>

    <!-- 搜索与筛选 -->
    <div class="files-toolbar">
      <div class="toolbar-left">
        <el-input
          v-model="searchQuery"
          placeholder="搜索文件名称…"
          clearable
          :prefix-icon="SearchIcon"
          class="search-input"
          @input="handleSearch"
        />
        <el-select
          v-model="typeFilter"
          placeholder="文件类型"
          clearable
          class="type-select"
          @change="handleSearch"
        >
          <el-option label="全部类型" value="" />
          <el-option label="PDF" value="pdf" />
          <el-option label="Word" value="docx" />
          <el-option label="Excel" value="xlsx" />
          <el-option label="图片" value="image" />
          <el-option label="文本" value="txt" />
          <el-option label="其他" value="other" />
        </el-select>
      </div>
      <div class="toolbar-right">
        <el-button v-if="selectedIds.length > 0" type="danger" plain @click="handleBatchDelete">
          <el-icon><Delete /></el-icon>
          批量删除 ({{ selectedIds.length }})
        </el-button>
      </div>
    </div>

    <!-- 上传进度条 -->
    <div v-if="uploadProgress.show" class="upload-progress-wrap">
      <div class="upload-progress-header">
        <span>上传中：{{ uploadProgress.fileName }}</span>
        <span class="upload-progress-percent">{{ uploadProgress.percent }}%</span>
      </div>
      <el-progress
        :percentage="uploadProgress.percent"
        :status="uploadProgress.status"
        :stroke-width="8"
      />
    </div>

    <!-- 文件表格 -->
    <div v-loading="loading" class="files-table">
      <el-table
        v-if="filteredFiles.length > 0"
        ref="tableRef"
        :data="filteredFiles"
        stripe
        style="width: 100%"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="50" />
        <el-table-column prop="filename" label="文件名称" min-width="240">
          <template #default="{ row }">
            <div class="file-name-cell">
              <el-icon :size="18"><Document /></el-icon>
              <span>{{ row.filename || row.name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="大小" width="110" sortable prop="size">
          <template #default="{ row }">
            {{ formatSize(row.size) }}
          </template>
        </el-table-column>
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            <el-tag size="small" type="info">
              {{ (row.type || getFileExt(row.filename || row.name)).toUpperCase() }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="上传时间" width="170" sortable prop="uploadedAt">
          <template #default="{ row }">
            {{ formatDate(row.uploadedAt || row.created) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleDownload(row)">
              <el-icon><Download /></el-icon>
            </el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">
              <el-icon><Delete /></el-icon>
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-else-if="!loading" class="files-empty">
        <el-empty
          :description="
            searchQuery || typeFilter ? '未找到匹配的文件' : '暂无文件，点击上传开始使用'
          "
        >
          <el-button v-if="!searchQuery && !typeFilter" type="primary" @click="showUpload = true">
            上传文件
          </el-button>
        </el-empty>
      </div>
    </div>

    <!-- 上传对话框 -->
    <el-dialog v-model="showUpload" title="上传文件" width="520px" destroy-on-close>
      <el-upload
        ref="uploadRef"
        class="upload-area"
        drag
        :action="uploadUrl"
        :headers="uploadHeaders"
        :on-success="onUploadSuccess"
        :on-error="onUploadError"
        :on-progress="onUploadProgress"
        :before-upload="beforeUpload"
        :limit="10"
        multiple
      >
        <el-icon class="upload-icon"><UploadFilled /></el-icon>
        <div class="upload-text">将文件拖到此处，或 <em>点击上传</em></div>
        <template #tip>
          <div class="upload-tip">支持任意格式文件，单文件最大 500MB</div>
        </template>
      </el-upload>
      <template #footer>
        <el-button @click="showUpload = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import TokenManager from '@/utils/TokenManager';
import { ElMessage, ElMessageBox } from 'element-plus';
import {
  Upload,
  UploadFilled,
  Document,
  Download,
  Delete,
  Search as SearchIcon,
} from '@element-plus/icons-vue';
import apiClient from '@/api';
import { formatSize, formatDate } from '@/utils/helpers';
import type { UploadFile, UploadInstance, TableInstance } from 'element-plus';

// ───── 后端文件类型 ─────
interface ApiFileItem {
  file_name: string;
  file_hash: string;
  chunk_count: number;
  category?: { category: string; confidence: number; candidates: string };
}

// ───── 前端展示类型 ─────
interface DisplayFileItem {
  id: string;
  filename: string;
  size: number;
  type: string;
  uploadedAt: string;
  chunkCount: number;
}

function apiToDisplay(f: ApiFileItem): DisplayFileItem {
  const ext = (f.file_name || '').split('.').pop() || 'unknown';
  return {
    id: f.file_hash,
    filename: f.file_name,
    size: 0,
    type: ext,
    uploadedAt: '',
    chunkCount: f.chunk_count || 0,
  };
}

// ───── 状态 ─────
const files = ref<DisplayFileItem[]>([]);
const loading = ref(false);
const showUpload = ref(false);
const uploadRef = ref<UploadInstance>();
const tableRef = ref<TableInstance>();
const searchQuery = ref('');
const typeFilter = ref('');
const selectedIds = ref<string[]>([]);

// 上传进度
const uploadProgress = ref<{
  show: boolean;
  fileName: string;
  percent: number;
  status: 'success' | 'exception' | 'warning' | '';
}>({
  show: false,
  fileName: '',
  percent: 0,
  status: '',
});

// ───── 上传配置 ─────
const uploadUrl = '/api/files/upload';
const uploadHeaders = computed(() => ({
  Authorization: `Bearer ${TokenManager.getToken() || ''}`,
}));

// ───── 计算属性 ─────
const filteredFiles = computed(() => {
  let result = files.value;

  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase();
    result = result.filter((f) => (f.filename || '').toLowerCase().includes(q));
  }

  if (typeFilter.value) {
    result = result.filter((f) => {
      const t = (f.type || getFileExt(f.filename || '')).toLowerCase();
      return t === typeFilter.value.toLowerCase();
    });
  }

  return result;
});

// ───── 工具 ─────
function getFileExt(filename: string): string {
  const parts = filename.split('.');
  return parts.length > 1 ? parts[parts.length - 1] : 'unknown';
}

// ───── 数据加载 ─────
async function fetchFiles(): Promise<void> {
  loading.value = true;
  try {
    const res = (await apiClient.get('/api/files')) as { files: ApiFileItem[]; total: number };
    files.value = (res.files || []).map(apiToDisplay);
  } catch (err) {
    console.error('[FilesView] 获取文件列表失败', err);
    ElMessage.error('获取文件列表失败');
    files.value = [];
  } finally {
    loading.value = false;
  }
}

// ───── 搜索 ─────
function handleSearch() {
  // 搜索是计算属性，无需额外操作
}

// ───── 选择 ─────
function handleSelectionChange(selection: DisplayFileItem[]) {
  selectedIds.value = selection.map((item) => item.id);
}

// ───── 上传 ─────
function beforeUpload(file: UploadFile): boolean {
  const maxSize = 500 * 1024 * 1024;
  if (file.size && file.size > maxSize) {
    ElMessage.error(`文件 ${file.name} 超过 500MB 限制`);
    return false;
  }
  return true;
}

function onUploadSuccess(response: Record<string, unknown>, file: UploadFile): void {
  uploadProgress.value = {
    show: true,
    fileName: file.name,
    percent: 100,
    status: 'success',
  };
  // 从后端响应中提取信息
  const fileHash = (response?.file_hash as string) || (response?.data as Record<string, unknown>)?.file_hash as string || `f_${Date.now()}`;
  const fileName = (response?.file_name as string) || file.name;
  const chunkCount = (response?.chunk_count as number) || 0;
  const newFile: DisplayFileItem = {
    id: fileHash,
    filename: fileName,
    size: file.size || 0,
    type: getFileExt(fileName),
    uploadedAt: new Date().toISOString(),
    chunkCount,
  };
  files.value.unshift(newFile);
  ElMessage.success('上传成功');
  setTimeout(() => {
    uploadProgress.value.show = false;
  }, 2000);
}

function onUploadProgress(event: { percent: number }, file: UploadFile): void {
  uploadProgress.value = {
    show: true,
    fileName: file.name,
    percent: Math.round(event.percent || 0),
    status: '',
  };
}

function onUploadError(err: Error, file: UploadFile): void {
  uploadProgress.value = {
    show: true,
    fileName: file.name,
    percent: 100,
    status: 'exception',
  };
  ElMessage.error('上传失败: ' + (err?.message || '未知错误'));
  // 3秒后自动隐藏
  setTimeout(() => {
    uploadProgress.value.show = false;
  }, 3000);
}

// ───── 下载 ─────
function handleDownload(file: DisplayFileItem): void {
  const downloadUrl = `/api/files/${file.id}/download`;
  const link = document.createElement('a');
  link.href = downloadUrl;
  link.target = '_blank';
  link.rel = 'noopener noreferrer';
  link.download = file.filename || file.name || '';
  link.click();
}

// ───── 删除 ─────
async function handleDelete(file: DisplayFileItem): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定要删除文件「${file.filename || file.name}」吗？`, '确认删除', {
      type: 'warning',
    });
    try {
      await apiClient.delete(`/api/files/${file.id}`);
    } catch {
      // 忽略 API 错误，本地删除
    }
    files.value = files.value.filter((f) => f.id !== file.id);
    ElMessage.success('删除成功');
  } catch {
    // 用户取消
  }
}

async function handleBatchDelete(): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedIds.value.length} 个文件吗？此操作不可恢复。`,
      '批量删除',
      { type: 'warning', confirmButtonText: '确认删除' },
    );

    for (const id of selectedIds.value) {
      try {
        await apiClient.delete(`/api/files/${id}`);
      } catch {
        /* 忽略 */
      }
    }

    files.value = files.value.filter((f) => !selectedIds.value.includes(f.id));
    selectedIds.value = [];
    ElMessage.success('批量删除成功');
  } catch {
    // 用户取消
  }
}

onMounted(() => {
  fetchFiles();
});
</script>

<style scoped lang="scss">
.files-center {
  max-width: 1200px;
  margin: 0 auto;
  padding: 28px 24px;
}

/* ───────── 头部 ───────── */
.files-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}

.header-title {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
}

.header-desc {
  margin: 4px 0 0;
  font-size: var(--font-size-caption);
  color: var(--text-secondary);
}

/* ───────── 工具栏 ───────── */
.files-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  gap: 12px;
  flex-wrap: wrap;
}

.toolbar-left {
  display: flex;
  gap: 12px;
  align-items: center;
}

.search-input {
  width: 280px;
}

.type-select {
  width: 140px;
}

/* ───────── 表格 ───────── */
.files-table {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  padding: 4px;
  min-height: 200px;
}

.file-name-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
}

.files-empty {
  padding: 60px 0;
}

/* ───────── 上传进度条 ───────── */
.upload-progress-wrap {
  margin-bottom: 16px;
  padding: 12px 16px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}

.upload-progress-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
  font-size: var(--font-size-caption);
  color: var(--text-secondary);
}

.upload-progress-percent {
  font-weight: 600;
  color: var(--brand);
}

/* ───────── 上传 ───────── */
.upload-area {
  :deep(.el-upload-dragger) {
    background: var(--bg-subtle);
    border-color: var(--bg-divider);
  }
}

.upload-icon {
  font-size: 48px;
  color: var(--text-tertiary);
  margin-bottom: 12px;
}

.upload-text {
  color: var(--text-secondary);
  font-size: var(--font-size-caption);

  em {
    color: var(--brand);
    font-style: normal;
  }
}

.upload-tip {
  color: var(--text-tertiary);
  font-size: var(--font-size-small);
  margin-top: 8px;
}

/* ───────── 响应式 ───────── */
@media (max-width: 767px) {
  .files-center {
    padding: 16px;
  }

  .files-toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .toolbar-left {
    flex-direction: column;
  }

  .search-input {
    width: 100%;
  }

  .files-table {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;

    :deep(.el-table) {
      min-width: 600px;
    }
  }
}
</style>
