<!--
  伏羲 v2.1 — 文档管理页 DocumentsView
  表格/卡片双视图、拖拽上传、预览/下载/删除
  搜索筛选 + 分页
  小米简约风适配
-->
<template>
  <div class="documents-view">
    <!-- 页面标题 -->
    <div class="documents-header">
      <div class="header-left">
        <h2>文档中心</h2>
        <p class="header-desc">上传、管理、预览企业文档知识</p>
      </div>
      <el-button type="primary" :icon="Plus" @click="showUpload = true"> 上传文件 </el-button>
    </div>

    <!-- 上传对话框 -->
    <el-dialog v-model="showUpload" title="上传文件" width="640px" destroy-on-close>
      <UploadZone @success="handleUploadSuccess" />
    </el-dialog>

    <!-- 搜索和筛选栏 -->
    <div class="documents-toolbar">
      <div class="toolbar-search">
        <el-input
          v-model="searchInput"
          placeholder="搜索文件名或内容摘要..."
          :prefix-icon="Search"
          clearable
          @input="handleSearchInput"
          @clear="handleClearSearch"
        />
      </div>
      <div class="toolbar-filters">
        <el-select
          v-model="fileStore.typeFilter"
          placeholder="文件类型"
          clearable
          style="width: 140px"
          @change="handleFilterChange"
        >
          <el-option label="全部" value="" />
          <el-option label="PDF" value="pdf" />
          <el-option label="Word" value="docx" />
          <el-option label="Excel" value="xlsx" />
          <el-option label="图片" value="png" />
          <el-option label="Markdown" value="md" />
        </el-select>

        <div class="toolbar-view-toggle">
          <el-tooltip content="表格视图" placement="top">
            <button
              class="view-btn"
              :class="{ active: viewMode === 'table' }"
              @click="viewMode = 'table'"
            >
              <el-icon :size="16"><List /></el-icon>
            </button>
          </el-tooltip>
          <el-tooltip content="卡片视图" placement="top">
            <button
              class="view-btn"
              :class="{ active: viewMode === 'card' }"
              @click="viewMode = 'card'"
            >
              <el-icon :size="16"><Grid /></el-icon>
            </button>
          </el-tooltip>
        </div>
      </div>
    </div>

    <!-- 全文搜索结果提示 -->
    <div v-if="searchInput && filteredFiles.length > 0" class="search-hint">
      找到 {{ filteredFiles.length }} 个匹配结果
    </div>

    <!-- 加载骨架屏 -->
    <div v-if="loading && files.length === 0" class="documents-skeleton">
      <el-skeleton v-for="n in 6" :key="n" :rows="2" animated style="margin-bottom: 12px" />
    </div>

    <!-- 错误状态 -->
    <div v-else-if="loadError" class="documents-error">
      <el-icon :size="32"><WarningFilled /></el-icon>
      <p>{{ loadError }}</p>
      <el-button type="primary" @click="loadFiles">重试</el-button>
    </div>

    <!-- 空状态 -->
    <div v-else-if="files.length === 0" class="documents-empty">
      <el-empty description="暂无文件">
        <template #image>
          <el-icon :size="64" color="var(--fuxi-text-tertiary)"><FolderOpened /></el-icon>
        </template>
        <el-button type="primary" @click="showUpload = true">上传文件</el-button>
      </el-empty>
    </div>

    <!-- 表格视图 -->
    <div v-else-if="viewMode === 'table'" class="documents-table-wrap">
      <el-table :data="filteredFiles" stripe style="width: 100%" @row-click="handleRowClick">
        <el-table-column prop="filename" label="文件名" min-width="250">
          <template #default="{ row }">
            <div class="table-filename">
              <el-icon :size="16" :color="getFileColor(row)">
                <component :is="getFileIcon(row)" />
              </el-icon>
              <span>{{ row.filename }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="size" label="大小" width="120">
          <template #default="{ row }">{{ formatSize(row.size) }}</template>
        </el-table-column>
        <el-table-column label="上传时间" width="180">
          <template #default="{ row }">{{ formatDate(row.uploadedAt) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text @click.stop="handlePreview(row)">预览</el-button>
            <el-button size="small" text @click.stop="handleDownload(row)">下载</el-button>
            <el-button size="small" text type="primary" @click.stop="handleEdit(row)">
              在线编辑
            </el-button>
            <el-popconfirm
              title="确定删除此文件？"
              confirm-button-text="确定"
              cancel-button-text="取消"
              @confirm="handleDelete(row)"
            >
              <template #reference>
                <el-button size="small" text type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 卡片视图 -->
    <div v-else class="documents-cards">
      <FileCard
        v-for="file in files"
        :key="file.id"
        :file="file"
        @click="handlePreview"
        @preview="handlePreview"
        @download="handleDownload"
        @delete="handleDelete"
      />
    </div>

    <!-- 分页 -->
    <div v-if="total > pageSize" class="documents-pagination">
      <el-pagination
        v-model:current-page="fileStore.currentPage"
        :page-size="fileStore.pageSize"
        :total="total"
        layout="prev, pager, next"
        background
        @current-change="handlePageChange"
      />
    </div>

    <!-- 预览对话框 -->
    <FilePreview v-model="previewVisible" :file="previewFile" @download="handleDownload" />

    <!-- 在线编辑对话框（支持实时协作） -->
    <el-dialog
      v-model="editDialogVisible"
      :title="`在线编辑 - ${editingFile?.filename || ''}`"
      width="1100px"
      destroy-on-close
      :close-on-click-modal="false"
      @close="handleEditClose"
    >
      <div class="edit-layout">
        <!-- 左侧：编辑区 -->
        <div class="edit-main">
          <div class="edit-toolbar">
            <div class="edit-toolbar-left">
              <el-radio-group v-model="editMode" size="small">
                <el-radio-button value="text">纯文本</el-radio-button>
                <el-radio-button value="markdown">Markdown</el-radio-button>
              </el-radio-group>
              <el-divider direction="vertical" />
              <el-switch
                v-model="collabEnabled"
                size="small"
                active-text="协作"
                @change="handleCollabToggle"
              />
            </div>
            <div class="edit-actions">
              <el-button size="small" @click="handleRevertEdit" :disabled="!editContentModified">
                还原
              </el-button>
            </div>
          </div>
          <div class="edit-content-area">
            <el-input
              v-model="editContent"
              type="textarea"
              :rows="20"
              :placeholder="editMode === 'markdown' ? '输入 Markdown 内容...' : '输入文本内容...'"
              class="edit-textarea"
              @keydown="handleEditKeydown"
              @mouseup="handleEditMouseUp"
              ref="editTextareaRef"
            />
            <div v-if="editMode === 'markdown'" class="edit-preview">
              <div class="preview-header">预览</div>
              <div class="preview-body markdown-body" v-html="renderedMarkdown" />
            </div>
          </div>
        </div>
        <!-- 右侧：协作面板 -->
        <div v-if="collabEnabled && editingFile" class="edit-collab-panel">
          <CollaborationPanel
            :document-id="editingFile.id"
            :user-id="currentUserId"
            :user-name="currentUserName"
            @leave="collabEnabled = false"
            @connection-change="handleCollabConnectionChange"
          />
        </div>
      </div>
      <template #footer>
        <template v-if="collabEnabled && collabConnected">
          <el-tag type="success" size="small" effect="plain" style="margin-right: auto">
            协作中 · {{ collabUserCount }} 人在线
          </el-tag>
        </template>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSaveEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue';
import { ElMessage } from 'element-plus';
import {
  Plus,
  Search,
  List,
  Grid,
  WarningFilled,
  Document,
  FolderOpened,
  DocumentChecked,
  DataAnalysis,
  PictureFilled,
  Files,
} from '@element-plus/icons-vue';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import { formatSize, formatDate } from '@/utils/helpers';
import { useFileStore } from '@/stores/files';
import { useAuthStore } from '@/stores/auth';
import apiClient from '@/api';
import UploadZone from '@/components/files/UploadZone.vue';
import FileCard from '@/components/files/FileCard.vue';
import FilePreview from '@/components/files/FilePreview.vue';
import { useCollaborationStore } from '@/services/collaboration/store';
import CollaborationPanel from '@/services/collaboration/CollaborationPanel.vue';
import type { FileInfo } from '@/types';
import type { ConnectionStatus } from '@/services/collaboration';

const fileStore = useFileStore();
const authStore = useAuthStore();

// ============================
// 视图状态
// ============================

const viewMode = ref<'table' | 'card'>('table');
const showUpload = ref(false);
const searchInput = ref('');
const loadError = ref<string | null>(null);

// 预览
const previewVisible = ref(false);
const previewFile = ref<FileInfo | null>(null);

// 在线编辑
const editDialogVisible = ref(false);
const editingFile = ref<FileInfo | null>(null);
const editContent = ref('');
const editOriginalContent = ref('');
const editMode = ref<'text' | 'markdown'>('text');
const saving = ref(false);
const editContentModified = ref(false);
const editTextareaRef = ref<InstanceType<typeof import('element-plus')['ElInput']> | null>(null);

// 实时协作
const collabEnabled = ref(false);
const collabConnected = ref(false);
const collabUserCount = ref(0);
const collabStore = useCollaborationStore();
const currentUserId = computed(() => String(authStore.user?.id ?? 'anonymous'));
const currentUserName = computed(() => authStore.user?.username ?? authStore.user?.display_name ?? '匿名用户');

// ============================
// 计算属性
// ============================

const files = computed(() => fileStore.files);
const loading = computed(() => fileStore.loading);
const total = computed(() => fileStore.total);
const pageSize = computed(() => fileStore.pageSize);

// 全文搜索过滤（前端实时过滤文件名和内容摘要）
const filteredFiles = computed(() => {
  const allFiles = files.value;
  if (!searchInput.value.trim()) return allFiles;
  const q = searchInput.value.toLowerCase().trim();
  return allFiles.filter((f) => {
    if ((f.filename || '').toLowerCase().includes(q)) return true;
    // 内容摘要匹配（如果 file 有 summary/excerpt/text_content 字段）
    const summary = (f as Record<string, unknown>).summary || (f as Record<string, unknown>).excerpt || (f as Record<string, unknown>).text_content || '';
    if (typeof summary === 'string' && summary.toLowerCase().includes(q)) return true;
    return false;
  });
});

// Markdown 渲染
const renderedMarkdown = computed(() => {
  if (!editContent.value) return '';
  try {
    const html = marked.parse(editContent.value) as string;
    return DOMPurify.sanitize(html);
  } catch {
    return '';
  }
});

// ============================
// 数据加载
// ============================

async function loadFiles(): Promise<void> {
  loadError.value = null;
  try {
    await fileStore.fetchFiles();
  } catch {
    // 降级为 Mock 数据
    fileStore.loadMockData();
  }
}

// ============================
// 搜索和筛选
// ============================

let searchTimer: ReturnType<typeof setTimeout> | null = null;

function handleSearchInput(value: string): void {
  if (searchTimer) clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    fileStore.setSearch(value);
    loadFiles();
  }, 300);
}

function handleClearSearch(): void {
  fileStore.setSearch('');
  loadFiles();
}

function handleFilterChange(): void {
  loadFiles();
}

// ============================
// 文件操作
// ============================

function handlePreview(file: FileInfo): void {
  previewFile.value = file;
  previewVisible.value = true;
}

function handleDownload(file: FileInfo): void {
  const url = fileStore.getDownloadUrl(file);
  window.open(url, '_blank');
}

async function handleDelete(file: FileInfo): Promise<void> {
  try {
    await fileStore.deleteFile(file.id);
    ElMessage.success('删除成功');
  } catch {
    ElMessage.error('删除失败');
  }
}

function handleRowClick(row: FileInfo): void {
  handlePreview(row);
}

function handleUploadSuccess(): void {
  showUpload.value = false;
  loadFiles();
}

function handlePageChange(): void {
  loadFiles();
  // 滚动到顶部
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ============================
// 在线编辑
// ============================

async function handleEdit(file: FileInfo): Promise<void> {
  editingFile.value = file;
  editDialogVisible.value = true;
  saving.value = false;

  // 根据扩展名自动选择编辑模式
  const ext = file.filename?.split('.').pop()?.toLowerCase() || '';
  editMode.value = ['md', 'markdown'].includes(ext) ? 'markdown' : 'text';

  try {
    // 尝试从 API 获取文件内容
    const data = (await apiClient.get(`/api/documents/${(file as Record<string, unknown>).hash || file.id}/content`)) as
      | { content: string }
      | string;
    const content = typeof data === 'string' ? data : data?.content || '';
    editContent.value = content;
    editOriginalContent.value = content;
    editContentModified.value = false;
  } catch {
    // 降级：使用空内容或模拟内容
    const mockContent =
      editMode.value === 'markdown'
        ? `# ${file.filename}\n\n在此编辑 Markdown 内容...\n\n## 概述\n\n这是一个示例文档。`
        : `这是文件「${file.filename}」的内容预览。\n\n在线编辑功能允许您直接修改文档内容并保存。`;
    editContent.value = mockContent;
    editOriginalContent.value = mockContent;
    editContentModified.value = false;
  }
}

function handleRevertEdit(): void {
  editContent.value = editOriginalContent.value;
  editContentModified.value = false;
}

async function handleSaveEdit(): Promise<void> {
  if (!editingFile.value) return;
  saving.value = true;
  try {
    const hash = (editingFile.value as Record<string, unknown>).hash || editingFile.value.id;
    await apiClient.put(`/api/documents/${hash}`, {
      content: editContent.value,
      format: editMode.value,
      filename: editingFile.value.filename,
    });
    ElMessage.success('保存成功');
    editOriginalContent.value = editContent.value;
    editContentModified.value = false;
    // 同步协作内容
    if (collabEnabled.value) {
      collabStore.replaceText(0, collabStore.documentContent.length, editContent.value);
    }
    editDialogVisible.value = false;
  } catch {
    ElMessage.error('保存失败，请重试');
  } finally {
    saving.value = false;
  }
}

// ============================
// 实时协作
// ============================

function handleCollabToggle(enabled: boolean): void {
  if (enabled && editingFile.value) {
    // 加入协作房间
    collabStore.joinRoom(
      editingFile.value.id,
      currentUserId.value,
      currentUserName.value,
    );
  } else {
    collabStore.leaveRoom();
    collabConnected.value = false;
    collabUserCount.value = 0;
  }
}

function handleCollabConnectionChange(status: ConnectionStatus): void {
  collabConnected.value = status === 'connected';
  if (collabConnected.value) {
    collabUserCount.value = collabStore.onlineCount;
  }
}

function handleEditClose(): void {
  if (collabEnabled.value) {
    collabStore.leaveRoom();
    collabEnabled.value = false;
    collabConnected.value = false;
  }
}

function handleEditKeydown(): void {
  // 标记内容已修改
  editContentModified.value = true;

  if (!collabEnabled.value || !collabConnected.value) return;

  // 将本地编辑同步到协作文档
  nextTick(() => {
    const textarea = getTextareaElement();
    if (textarea) {
      const cursorPos = textarea.selectionStart;
      // 简单同步：全文替换（生产环境建议使用差分同步或 Y.Text binding）
      collabStore.replaceText(0, collabStore.documentContent.length, editContent.value);
    }
  });
}

function handleEditMouseUp(): void {
  if (!collabEnabled.value || !collabConnected.value) return;

  const textarea = getTextareaElement();
  if (textarea) {
    const text = textarea.value || '';
    const beforeCursor = text.slice(0, textarea.selectionStart);
    const lines = beforeCursor.split('\n');
    const line = lines.length;
    const column = lines[lines.length - 1].length + 1;

    collabStore.sendCursorPosition({
      line,
      column,
    });
  }
}

function getTextareaElement(): HTMLTextAreaElement | null {
  const dialog = document.querySelector('.edit-textarea');
  return dialog?.querySelector('textarea') ?? null;
}

// ============================
// 工具函数
// ============================

// 文件图标按扩展名分类
function getFileIcon(file: FileInfo): unknown {
  const ext = file.filename?.split('.').pop()?.toLowerCase() || '';
  if (ext === 'pdf') return DocumentChecked;
  if (['doc', 'docx'].includes(ext)) return Files;
  if (['xls', 'xlsx', 'csv'].includes(ext)) return DataAnalysis;
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(ext)) return PictureFilled;
  return Document;
}

function getFileColor(file: FileInfo): string {
  const ext = file.filename?.split('.').pop()?.toLowerCase() || '';
  if (ext === 'pdf') return '#e74c3c';       // PDF → 红色
  if (['doc', 'docx'].includes(ext)) return '#3a6b8c';  // DOCX → 蓝色
  if (['xls', 'xlsx', 'csv'].includes(ext)) return '#4a7c59'; // XLSX → 绿色
  if (['png', 'jpg', 'jpeg', 'gif'].includes(ext)) return 'var(--li-color)';
  if (ext === 'md') return '#c9a84c';        // MD → 金色
  return 'var(--fuxi-text-secondary)';
}

function getStatusType(status?: string): 'success' | 'warning' | 'danger' | 'info' {
  const map: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
    ready: 'success',
    uploaded: 'info',
    processing: 'warning',
    error: 'danger',
  };
  return map[status || ''] || 'info';
}

function getStatusLabel(status?: string): string {
  const map: Record<string, string> = {
    ready: '就绪',
    uploaded: '已上传',
    processing: '处理中',
    error: '失败',
  };
  return map[status || ''] || status || '未知';
}

// ============================
// 初始化
// ============================

onMounted(() => {
  loadFiles();
});
</script>

<style scoped lang="scss">
.documents-view {
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
}

/* ───── 标题栏 ───── */

.documents-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 24px;

  .header-left h2 {
    font-size: 24px;
    font-weight: 700;
    color: var(--fuxi-text);
    margin: 0 0 4px;
  }

  .header-desc {
    font-size: 14px;
    color: var(--fuxi-text-secondary);
    margin: 0;
  }
}

/* ───── 工具栏 ───── */

.documents-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  padding: 12px 16px;
  background: var(--fuxi-bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--fuxi-shadow-sm);
}

.toolbar-search {
  flex: 1;
  max-width: 360px;
}

.toolbar-filters {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.toolbar-view-toggle {
  display: flex;
  border: 1px solid var(--fuxi-border);
  border-radius: var(--radius-sm);
  overflow: hidden;

  .view-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    border: none;
    background: var(--fuxi-bg-card);
    color: var(--fuxi-text-tertiary);
    cursor: pointer;
    transition: all 0.15s;

    &:hover {
      background: var(--fuxi-bg-hover);
    }

    &.active {
      background: var(--fuxi-primary-light);
      color: var(--fuxi-primary);
    }
  }
}

/* ───── 表格视图 ───── */

.documents-table-wrap {
  background: var(--fuxi-bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--fuxi-shadow-sm);
  overflow: hidden;
}

.table-filename {
display: flex;
align-items: center;
gap: 8px;
cursor: pointer;
color: var(--fuxi-text);

span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
}

/* ───── 全文搜索提示 ───── */
.search-hint {
padding: 6px 16px;
font-size: 12px;
color: var(--fuxi-primary, #FF6700);
margin-bottom: 8px;
font-weight: 500;
}

/* ───── 在线编辑 ───── */
.edit-toolbar {
display: flex;
align-items: center;
justify-content: space-between;
margin-bottom: 12px;
padding-bottom: 8px;
border-bottom: 1px solid var(--fuxi-border, #eee);
}

.edit-actions {
display: flex;
gap: 8px;
}

.edit-content-area {
display: flex;
gap: 12px;

.edit-textarea {
  flex: 1;

  :deep(.el-textarea__inner) {
    font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
    font-size: 13px;
    line-height: 1.6;
    resize: none;
  }
}
}

/* ───── 协作布局 ───── */
.edit-layout {
  display: flex;
  gap: 0;
  min-height: 480px;
}

.edit-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.edit-toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.edit-collab-panel {
  width: 280px;
  flex-shrink: 0;
  border-left: 1px solid var(--fuxi-border, #eee);
  background: var(--fuxi-bg-card, #ffffff);
  overflow: hidden;
}

.edit-preview {
flex: 1;
border: 1px solid var(--fuxi-border, #eee);
border-radius: var(--radius-sm, 4px);
overflow: hidden;
display: flex;
flex-direction: column;

.preview-header {
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 600;
  color: var(--fuxi-text-secondary);
  background: var(--fuxi-bg-subtle, #f5f5f5);
  border-bottom: 1px solid var(--fuxi-border, #eee);
}

.preview-body {
  flex: 1;
  padding: 12px;
  overflow-y: auto;
  max-height: 460px;

  :deep(h1) { font-size: 1.5em; margin: 0.5em 0; }
  :deep(h2) { font-size: 1.3em; margin: 0.5em 0; }
  :deep(h3) { font-size: 1.1em; margin: 0.4em 0; }
  :deep(p) { margin: 0.5em 0; line-height: 1.6; }
  :deep(code) {
    background: var(--fuxi-bg-subtle, #f5f5f5);
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 0.9em;
  }
  :deep(pre) {
    background: var(--fuxi-bg-subtle, #f5f5f5);
    padding: 12px;
    border-radius: 4px;
    overflow-x: auto;
    code { background: transparent; padding: 0; }
  }
  :deep(blockquote) {
    border-left: 3px solid var(--fuxi-primary, #FF6700);
    padding-left: 12px;
    margin: 0.5em 0;
    color: var(--fuxi-text-secondary);
  }
  :deep(ul), :deep(ol) { padding-left: 1.5em; }
}
}

@media (max-width: 767px) {
.edit-content-area {
  flex-direction: column;
}

.edit-layout {
  flex-direction: column;
}

.edit-collab-panel {
  width: 100%;
  max-height: 320px;
  border-left: none;
  border-top: 1px solid var(--fuxi-border, #eee);
}
}

/* ───── 卡片视图 ───── */

.documents-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  gap: 12px;
}

/* ───── 分页 ───── */

.documents-pagination {
  display: flex;
  justify-content: center;
  margin-top: 24px;
  padding: 16px;
}

/* ───── 加载态 ───── */

.documents-skeleton {
  background: var(--fuxi-bg-card);
  border-radius: var(--radius-md);
  padding: 20px;
  box-shadow: var(--fuxi-shadow-sm);
}

/* ───── 错误态 ───── */

.documents-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 64px 24px;
  background: var(--fuxi-bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--fuxi-shadow-sm);
  gap: 12px;
  color: var(--fuxi-error);

  p {
    margin: 0;
    font-size: 14px;
  }
}

/* ───── 空状态 ───── */

.documents-empty {
  background: var(--fuxi-bg-card);
  border-radius: var(--radius-md);
  padding: 40px;
  box-shadow: var(--fuxi-shadow-sm);
}

/* ───────── 响应式 ───────── */
@media (max-width: 767px) {
  .documents-view {
    padding: 16px;
  }

  .documents-header {
    flex-direction: column;
    gap: 12px;
  }

  .documents-toolbar {
    flex-direction: column;
    gap: 8px;
    padding: 10px;
  }

  .toolbar-search {
    max-width: 100%;
  }

  .documents-table-wrap {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;

    :deep(.el-table) {
      min-width: 600px;
    }
  }

  .documents-cards {
    grid-template-columns: 1fr;
  }
}
</style>
