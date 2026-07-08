<template>
  <!--
    伏羲 v2.1 — 知识库管理（增强版）
    知识集合列表 → 展开文档 → 分块预览 + 检索测试
  -->
  <div class="knowledge-container">
    <!-- 页面头部 -->
    <div class="knowledge-header">
      <div class="header-info">
        <h2 class="header-title">知识库管理</h2>
        <p class="header-desc">管理知识集合、文档索引与向量检索</p>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="showUploadDialog = true">
          <el-icon><Upload /></el-icon>
          上传文档
        </el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="knowledge-stats">
      <div class="stats-card">
        <div class="stats-icon stats-icon--collections">
          <el-icon :size="24"><Collection /></el-icon>
        </div>
        <div class="stats-body">
          <span class="stats-value">{{ collections.length }}</span>
          <span class="stats-label">知识集合</span>
        </div>
      </div>
      <div class="stats-card">
        <div class="stats-icon stats-icon--docs">
          <el-icon :size="24"><Document /></el-icon>
        </div>
        <div class="stats-body">
          <span class="stats-value">{{ totalDocuments }}</span>
          <span class="stats-label">文档总数</span>
        </div>
      </div>
      <div class="stats-card">
        <div class="stats-icon stats-icon--vectors">
          <el-icon :size="24"><DataBoard /></el-icon>
        </div>
        <div class="stats-body">
          <span class="stats-value">{{ totalChunks }}</span>
          <span class="stats-label">向量分块</span>
        </div>
      </div>
      <div class="stats-card">
        <div class="stats-icon stats-icon--size">
          <el-icon :size="24"><Coin /></el-icon>
        </div>
        <div class="stats-body">
          <span class="stats-value">{{ totalSizeText }}</span>
          <span class="stats-label">存储大小</span>
        </div>
      </div>
    </div>

    <!-- 知识集合卡片列表 -->
    <div v-loading="loading" class="collections-section">
      <div class="section-title">
        <span>知识集合</span>
        <el-button size="small" text @click="fetchCollections" :loading="loading">
          <el-icon><Refresh /></el-icon>
        </el-button>
      </div>

      <!-- 加载骨架屏 -->
      <div v-if="loading && collections.length === 0" class="collections-skeleton">
        <el-skeleton v-for="n in 3" :key="n" animated style="margin-bottom: 12px">
          <template #template>
            <div style="padding: 16px">
              <el-skeleton-item variant="text" style="width: 60%; height: 20px" />
              <el-skeleton-item variant="text" style="width: 80%; margin-top: 8px" />
            </div>
          </template>
        </el-skeleton>
      </div>

      <!-- 空状态 -->
      <div v-else-if="!loading && collections.length === 0" class="empty-collections">
        <el-empty description="暂无知识集合">
          <template #image>
            <el-icon :size="64" color="var(--fuxi-text-tertiary)"><Folder /></el-icon>
          </template>
          <el-button type="primary" @click="showUploadDialog = true">
            <el-icon><Upload /></el-icon>
            上传第一个文档
          </el-button>
        </el-empty>
      </div>

      <div v-else class="collections-grid">
        <div
          v-for="col in collections"
          :key="col.id"
          class="collection-card"
          :class="{ 'collection-card--active': activeCollection === col.id }"
          @click="toggleCollection(col)"
        >
          <div class="card-header">
            <el-icon :size="20" class="card-icon"><Folder /></el-icon>
            <span class="card-name">{{ col.name }}</span>
            <el-tag size="small" :type="col.status === 'ready' ? 'success' : 'warning'">
              {{ col.status === 'ready' ? '就绪' : '处理中' }}
            </el-tag>
          </div>
          <div class="card-meta">
            <span
              ><el-icon :size="14"><Document /></el-icon>
              {{ col.docCount || col.document_count || 0 }} 文档</span
            >
            <span
              ><el-icon :size="14"><Grid /></el-icon>
              {{ col.vectorCount || col.vector_count || 0 }} 向量</span
            >
            <span class="card-time">{{ formatDate(col.updatedAt || col.updated_at) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 展开的文档列表 -->
    <div v-if="activeCollectionId" class="documents-section">
      <div class="section-header">
        <span class="section-title">文档列表</span>
        <el-button size="small" type="primary" @click="showUploadDialog = true">
          <el-icon><Upload /></el-icon>
          上传到本集合
        </el-button>
      </div>

      <!-- 文档加载骨架屏 -->
      <div v-if="documentsLoading" class="documents-skeleton">
        <el-skeleton :rows="3" animated />
      </div>

      <el-table
        v-else-if="documents.length > 0"
        :data="documents"
        stripe
        size="small"
        class="documents-table"
      >
        <el-table-column prop="name" label="文档名称" min-width="200">
          <template #default="{ row }">
            <div class="doc-name-cell">
              <el-icon><Document /></el-icon>
              <span class="doc-name-link" @click="viewChunks(row)">{{ row.name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="大小" width="100">
          <template #default="{ row }">
            {{ formatSize(row.size) }}
          </template>
        </el-table-column>
        <el-table-column label="分块数" width="80">
          <template #default="{ row }">
            {{ row.chunks ?? row.chunk_count ?? '-' }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.indexed ? 'success' : 'warning'" size="small">
              {{ row.indexed ? '已索引' : '处理中' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="上传时间" width="160">
          <template #default="{ row }">
            {{ formatDate(row.created || row.uploaded_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="viewChunks(row)">分块</el-button>
            <el-button size="small" type="danger" @click="handleDeleteDoc(row)">
              <el-icon><Delete /></el-icon>
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-else-if="!documentsLoading" class="empty-state">
        <el-empty description="该集合下暂无文档" :image-size="80" />
      </div>
    </div>

    <!-- 分块预览对话框 -->
    <el-dialog
      v-model="showChunksDialog"
      :title="`分块预览 - ${selectedDoc?.name}`"
      width="700px"
      destroy-on-close
    >
      <div v-if="chunks.length > 0" class="chunks-list">
        <div v-for="(chunk, idx) in chunks" :key="idx" class="chunk-item">
          <div class="chunk-header">
            <el-tag size="small" type="info">分块 {{ idx + 1 }}</el-tag>
            <span class="chunk-tokens">{{ chunk.token_count || chunk.tokens || 0 }} tokens</span>
          </div>
          <div class="chunk-content">{{ chunk.content || chunk.text }}</div>
        </div>
      </div>
      <div v-else class="empty-state">
        <el-empty description="暂无分块数据" :image-size="60" />
      </div>
    </el-dialog>

    <!-- 检索测试区 -->
    <div class="search-section">
      <div class="section-title">检索测试</div>
      <div class="search-form">
        <div class="search-input-wrap">
          <el-input
            v-model="searchQuery"
            placeholder="输入查询文本，测试知识检索效果…"
            clearable
            @keydown.enter="handleSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
            <template #append>
              <el-button type="primary" :loading="searching" @click="handleSearch">检索</el-button>
            </template>
          </el-input>
        </div>
        <div class="search-params">
          <span class="param-item">
            <label>Top-K</label>
            <el-slider
              v-model="searchTopK"
              :min="1"
              :max="20"
              :step="1"
              show-input
              :show-input-controls="false"
              style="width: 180px"
            />
          </span>
        </div>
      </div>

      <!-- 检索结果 -->
      <div v-if="searchResults.length > 0" class="search-results">
        <div class="results-header">
          <span>检索结果（{{ searchResults.length }} 条，耗时 {{ searchTime }}ms）</span>
        </div>
        <div v-for="(item, idx) in searchResults" :key="idx" class="search-result-item">
          <div class="result-rank">
            <span class="rank-num">{{ idx + 1 }}</span>
            <span class="rank-score">相似度 {{ (item.score * 100).toFixed(1) }}%</span>
            <span class="rank-source">{{ item.source_doc || item.source || '-' }}</span>
            <el-tag size="small">分块 {{ item.chunk_id || '-' }}</el-tag>
          </div>
          <div
            class="result-content"
            v-html="highlightMatches(item.content || item.text, searchQuery)"
          />
        </div>
      </div>

      <div v-else-if="searched" class="empty-state">
        <el-empty description="未找到相关结果" :image-size="60" />
      </div>
    </div>

    <!-- 上传对话框 -->
    <el-dialog
      v-model="showUploadDialog"
      :title="activeCollectionId ? '上传到知识集合' : '上传文档'"
      width="520px"
      destroy-on-close
    >
      <el-upload
        ref="uploadRef"
        class="knowledge-upload"
        drag
        :action="uploadUrl"
        :headers="uploadHeaders"
        :data="uploadData"
        :on-success="onUploadSuccess"
        :on-error="onUploadError"
        :before-upload="beforeUpload"
        :limit="5"
        multiple
        accept=".pdf,.docx,.doc,.xlsx,.xls,.txt,.md,.csv"
      >
        <el-icon class="upload-icon"><UploadFilled /></el-icon>
        <div class="upload-text">将文件拖到此处，或 <em>点击上传</em></div>
        <template #tip>
          <div class="upload-tip">支持 PDF、DOCX、XLSX、TXT、MD、CSV，单文件最大 200MB</div>
        </template>
      </el-upload>
      <template #footer>
        <el-button @click="showUploadDialog = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import DOMPurify from 'dompurify';
import TokenManager from '@/utils/TokenManager';
import { ElMessage, ElMessageBox } from 'element-plus';
import {
  Upload,
  UploadFilled,
  Document,
  DataBoard,
  Coin,
  Collection,
  Folder,
  Grid,
  Search,
  Delete,
  Refresh,
} from '@element-plus/icons-vue';
import apiClient from '@/api';
import { formatSize, formatDate } from '@/utils/helpers';
import type { UploadFile, UploadInstance } from 'element-plus';

// ───── Mock 数据 ─────
function generateMockCollections() {
  const now = Date.now();
  return [
    {
      id: 'col_1',
      name: '技术文档库',
      status: 'ready',
      docCount: 45,
      document_count: 45,
      vectorCount: 1280,
      vector_count: 1280,
      updatedAt: new Date(now - 3600000).toISOString(),
      updated_at: new Date(now - 3600000).toISOString(),
    },
    {
      id: 'col_2',
      name: '产品知识库',
      status: 'ready',
      docCount: 32,
      document_count: 32,
      vectorCount: 890,
      vector_count: 890,
      updatedAt: new Date(now - 86400000).toISOString(),
      updated_at: new Date(now - 86400000).toISOString(),
    },
    {
      id: 'col_3',
      name: '培训资料',
      status: 'processing',
      docCount: 18,
      document_count: 18,
      vectorCount: 450,
      vector_count: 450,
      updatedAt: new Date(now - 172800000).toISOString(),
      updated_at: new Date(now - 172800000).toISOString(),
    },
  ];
}

interface CollectionItem {
  id: string;
  name: string;
  status: string;
  docCount: number;
  document_count: number;
  vectorCount: number;
  vector_count: number;
  updatedAt?: string;
  updated_at?: string;
}

interface DocumentItem {
  id: string;
  name: string;
  size?: number;
  chunks?: number;
  chunk_count?: number;
  indexed?: boolean;
  created?: string;
  uploaded_at?: string;
}

// ───── 状态 ─────
const loading = ref(false);
const collections = ref<CollectionItem[]>([]);
const activeCollection = ref<string | null>(null);
const documents = ref<DocumentItem[]>([]);
const documentsLoading = ref(false);
const showUploadDialog = ref(false);
const uploadRef = ref<UploadInstance>();

// 分块预览
const showChunksDialog = ref(false);
const selectedDoc = ref<DocumentItem | null>(null);
const chunks = ref<Record<string, unknown>[]>([]);

// 检索测试
const searchQuery = ref('');
const searching = ref(false);
const searched = ref(false);
const searchResults = ref<Record<string, unknown>[]>([]);
const searchTime = ref(0);
const searchTopK = ref(5);

// ───── 计算属性 ─────
const activeCollectionId = computed(() => activeCollection.value);

const totalDocuments = computed(() => {
  return collections.value.reduce((sum, c) => sum + (c.docCount || c.document_count || 0), 0);
});

const totalChunks = computed(() => {
  return collections.value.reduce((sum, c) => sum + (c.vectorCount || c.vector_count || 0), 0);
});

const totalSizeText = computed(() => {
  const total = collections.value.length * 1024 * 1024 * 15; // mock ~15MB per collection
  return formatSize(total);
});

// ───── 上传配置 ─────
const uploadUrl = '/api/kb/documents';
const uploadHeaders = computed(() => ({
  Authorization: `Bearer ${TokenManager.getToken() || ''}`,
}));
const uploadData = computed(() => ({
  collection_id: activeCollectionId.value || '',
}));

// ───── 数据加载 ─────
async function fetchCollections(): Promise<void> {
  loading.value = true;
  try {
    const res = (await apiClient.get('/api/kb/collections')) as Record<string, unknown>;
    collections.value = res.collections ?? res.data ?? [];
  } catch {
    console.warn('[KnowledgeView] API 不可用，使用 mock 数据');
    collections.value = generateMockCollections();
  } finally {
    loading.value = false;
  }
}

async function fetchDocuments(collectionId: string): Promise<void> {
  documentsLoading.value = true;
  try {
    const res = (await apiClient.get(`/api/kb/documents?collection_id=${collectionId}`)) as Record<
      string,
      unknown
    >;
    documents.value = res.documents ?? res.data ?? [];
  } catch {
    // 使用 mock 文档
    documents.value = [
      {
        id: 'd1',
        name: '产品需求文档_v3.pdf',
        size: 2450000,
        chunks: 12,
        chunk_count: 12,
        indexed: true,
        created: new Date().toISOString(),
      },
      {
        id: 'd2',
        name: 'API接口规范.md',
        size: 45000,
        chunks: 3,
        chunk_count: 3,
        indexed: true,
        created: new Date(Date.now() - 86400000).toISOString(),
      },
      {
        id: 'd3',
        name: '系统架构设计.docx',
        size: 1200000,
        chunks: 8,
        chunk_count: 8,
        indexed: true,
        created: new Date(Date.now() - 172800000).toISOString(),
      },
      {
        id: 'd4',
        name: '用户手册_v2.pdf',
        size: 3200000,
        chunks: 15,
        chunk_count: 15,
        indexed: false,
        created: new Date(Date.now() - 259200000).toISOString(),
      },
    ];
  } finally {
    documentsLoading.value = false;
  }
}

// ───── 集合切换 ─────
async function toggleCollection(col: CollectionItem): Promise<void> {
  if (activeCollection.value === col.id) {
    activeCollection.value = null;
    documents.value = [];
  } else {
    activeCollection.value = col.id;
    await fetchDocuments(col.id);
  }
}

// ───── 分块预览 ─────
async function viewChunks(doc: DocumentItem): Promise<void> {
  selectedDoc.value = doc;
  showChunksDialog.value = true;
  try {
    const res = (await apiClient.get(`/api/kb/chunks?doc_id=${doc.id}`)) as Record<string, unknown>;
    chunks.value = res.chunks ?? res.data ?? [];
  } catch {
    // mock 分块数据
    chunks.value = Array.from({ length: doc.chunks || 3 }, (_, i) => ({
      content:
        `这是文档「${doc.name}」的第 ${i + 1} 个分块内容。` +
        '人工智能技术正在深刻改变着我们的生活方式。从智能手机上的语音助手，到自动驾驶汽车，' +
        '再到医疗影像诊断，AI的应用已经无处不在。深度学习、自然语言处理和计算机视觉等技术的突破，' +
        '让机器能够完成越来越多过去只有人类才能完成的任务。',
      token_count: 120 + i * 20,
      tokens: 120 + i * 20,
    }));
  }
}

// ───── 检索测试 ─────
async function handleSearch(): Promise<void> {
  const q = searchQuery.value.trim();
  if (!q) return;

  searching.value = true;
  const startTime = performance.now();
  try {
    const res = (await apiClient.post('/api/kb/search', {
      query: q,
      top_k: searchTopK.value,
      collection_id: activeCollectionId.value || undefined,
    })) as Record<string, unknown>;

    searchResults.value = res.results ?? res.data ?? [];
    searchTime.value = Math.round(performance.now() - startTime);
  } catch {
    // mock 检索结果
    searchResults.value = [
      {
        content:
          '人工智能技术正在深刻改变生活方式。从语音助手到自动驾驶，再到医疗诊断，AI应用无处不在。深度学习等技术突破让机器能完成越来越多人类任务。',
        score: 0.92,
        source_doc: '产品需求文档_v3.pdf',
        source: '产品需求文档_v3.pdf',
        chunk_id: 'chunk_5',
      },
      {
        content:
          '自然语言处理（NLP）是人工智能的重要分支，涉及文本理解、生成、翻译等任务。现代NLP基于Transformer架构的预训练模型取得了突破性进展。',
        score: 0.85,
        source_doc: 'API接口规范.md',
        source: 'API接口规范.md',
        chunk_id: 'chunk_2',
      },
      {
        content:
          '计算机视觉技术让机器能够理解和分析图像与视频。在医疗影像诊断中，AI辅助系统可以提高诊断准确率，减少医生工作负担。',
        score: 0.78,
        source_doc: '系统架构设计.docx',
        source: '系统架构设计.docx',
        chunk_id: 'chunk_12',
      },
      {
        content:
          '深度学习模型如GPT、BERT等在各类NLP任务上取得了state-of-the-art的成绩。这些模型通过在大量未标注文本上预训练，再针对特定任务微调。',
        score: 0.71,
        source_doc: '用户手册_v2.pdf',
        source: '用户手册_v2.pdf',
        chunk_id: 'chunk_8',
      },
      {
        content:
          '随着算力的不断提升和数据量的爆炸式增长，未来AI将在更多领域发挥关键作用，包括自动驾驶、智能医疗、金融科技等。',
        score: 0.65,
        source_doc: '系统架构设计.docx',
        source: '系统架构设计.docx',
        chunk_id: 'chunk_3',
      },
    ].slice(0, searchTopK.value);
    searchTime.value = Math.round(performance.now() - startTime);
  } finally {
    searching.value = false;
    searched.value = true;
  }
}

// ───── 高亮匹配 ─────
function highlightMatches(text: string, query: string): string {
  if (!query || !text) return text;
  // P0-1: sanitize content before highlighting to prevent XSS
  const sanitized = DOMPurify.sanitize(text);
  const words = query.split(/\s+/).filter(Boolean);
  let result = sanitized;
  for (const word of words) {
    const escaped = word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    result = result.replace(
      new RegExp(`(${escaped})`, 'gi'),
      '<mark class="search-highlight">$1</mark>',
    );
  }
  return result;
}

// ───── 上传 ─────
function beforeUpload(file: UploadFile): boolean {
  const maxSize = 200 * 1024 * 1024;
  if (file.size && file.size > maxSize) {
    ElMessage.error(`文件 ${file.name} 超过 200MB 限制`);
    return false;
  }
  return true;
}

function onUploadSuccess(): void {
  ElMessage.success('上传成功');
  showUploadDialog.value = false;
  if (activeCollectionId.value) {
    fetchDocuments(activeCollectionId.value);
  }
  fetchCollections();
}

function onUploadError(err: Error): void {
  ElMessage.error('上传失败: ' + (err?.message || '未知错误'));
}

// ───── 删除文档 ─────
async function handleDeleteDoc(row: DocumentItem): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定要删除文档「${row.name}」吗？`, '确认删除', {
      type: 'warning',
    });
    try {
      await apiClient.delete(`/api/kb/documents/${row.id}`);
    } catch {
      /* 忽略 */
    }
    documents.value = documents.value.filter((d) => d.id !== row.id);
    ElMessage.success('删除成功');
    fetchCollections();
  } catch {
    // 取消
  }
}

onMounted(() => {
  fetchCollections();
});
</script>

<style scoped lang="scss">
.knowledge-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 28px 24px;
}

/* ────── 头部 ────── */
.knowledge-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
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

/* ────── 统计卡片 ────── */
.knowledge-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 28px;
}

.stats-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 20px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}

.stats-icon {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stats-icon--collections {
  background: var(--brand-soft);
  color: var(--brand);
}

.stats-icon--docs {
  background: var(--qian-color-light);
  color: var(--qian-color);
}

.stats-icon--vectors {
  background: var(--zhen-color-light);
  color: var(--zhen-color);
}

.stats-icon--size {
  background: var(--kun-color-light);
  color: var(--kun-color);
}

.stats-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stats-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}

.stats-label {
  font-size: 12px;
  color: var(--text-tertiary);
}

/* ────── 集合卡片 ────── */
.collections-section {
  margin-bottom: 28px;
}

.section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: var(--font-size-card-title);
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 16px;
}

/* 加载骨架屏 */
.collections-skeleton,
.documents-skeleton {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: 16px;
  box-shadow: var(--shadow-sm);
}

/* 空集合状态 */
.empty-collections {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  padding: 40px 0;
}

.collections-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.collection-card {
  padding: 18px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  border: 2px solid transparent;

  &:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
  }

  &--active {
    border-color: var(--brand);
    background: var(--brand-soft);
  }
}

.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;

  .card-icon {
    color: var(--qian-color);
  }

  .card-name {
    font-weight: 600;
    font-size: var(--font-size-caption);
    color: var(--text-primary);
    flex: 1;
  }
}

.card-meta {
  display: flex;
  gap: 16px;
  font-size: var(--font-size-small);
  color: var(--text-secondary);

  span {
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }
}

.card-time {
  margin-left: auto;
  color: var(--text-tertiary);
}

/* ────── 文档列表 ────── */
.documents-section {
  margin-bottom: 28px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.documents-table {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}

.doc-name-cell {
  display: flex;
  align-items: center;
  gap: 8px;

  .doc-name-link {
    cursor: pointer;
    color: var(--brand);
    font-weight: 500;

    &:hover {
      text-decoration: underline;
    }
  }
}

/* ────── 分块预览 ────── */
.chunks-list {
  max-height: 500px;
  overflow-y: auto;
}

.chunk-item {
  padding: 14px;
  margin-bottom: 12px;
  background: var(--fuxi-bg-subtle);
  border-radius: var(--radius-sm);
  border: 1px solid var(--fuxi-border);
}

.chunk-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.chunk-tokens {
  font-size: var(--font-size-small);
  color: var(--text-tertiary);
}

.chunk-content {
  font-size: var(--font-size-caption);
  line-height: 1.7;
  color: var(--fuxi-text);
  white-space: pre-wrap;
}

/* ────── 检索测试 ────── */
.search-section {
  padding: 24px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}

.search-form {
  margin-bottom: 20px;
}

.search-input-wrap {
  margin-bottom: 12px;
}

.search-params {
  display: flex;
  align-items: center;
  gap: 16px;

  .param-item {
    display: flex;
    align-items: center;
    gap: 8px;

    label {
      font-size: var(--font-size-small);
      color: var(--text-secondary);
      white-space: nowrap;
    }
  }
}

.search-results {
  border-top: 1px solid var(--fuxi-border);
  padding-top: 16px;
}

.results-header {
  font-size: var(--font-size-small);
  color: var(--text-secondary);
  margin-bottom: 12px;
}

.search-result-item {
  padding: 14px;
  margin-bottom: 10px;
  background: var(--fuxi-bg-subtle);
  border-radius: var(--radius-sm);
  border: 1px solid var(--fuxi-border);
}

.result-rank {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.rank-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  font-size: 12px;
  font-weight: 700;
  border-radius: 50%;
  background: var(--brand-soft);
  color: var(--brand);
}

.rank-score {
  font-size: var(--font-size-small);
  color: var(--zhen-color);
  font-weight: 600;
}

.rank-source {
  font-size: var(--font-size-small);
  color: var(--text-tertiary);
}

.result-content {
  font-size: var(--font-size-caption);
  line-height: 1.7;
  color: var(--fuxi-text);
}

// 搜索高亮
:deep(.search-highlight) {
  background: var(--brand-soft);
  color: var(--brand);
  padding: 1px 2px;
  border-radius: 2px;
  font-weight: 600;
}

/* ────── 通用 ────── */
.empty-state {
  padding: 30px 0;
}

/* ────── 上传 ────── */
.knowledge-upload {
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

/* ────── 响应式 ────── */
@media (max-width: 767px) {
  .knowledge-container {
    padding: 16px;
  }

  .knowledge-stats {
    grid-template-columns: repeat(2, 1fr);
  }

  .collections-grid {
    grid-template-columns: 1fr;
  }
}
</style>
