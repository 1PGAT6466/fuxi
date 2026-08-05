<template>
  <!--
    伏羲 v2.1 — 知识审批界面
    卡片式展示待审批知识，支持通过/拒绝/批量操作
  -->
  <div class="knowledge-approval-view">
    <h2 class="page-title">知识审批</h2>

    <!-- 统计概览 -->
    <div class="stats-bar">
      <el-tag type="warning" size="large">
        待审批 {{ pendingCount }}
      </el-tag>
      <el-tag type="success" size="large">
        已通过 {{ approvedCount }}
      </el-tag>
      <el-tag type="danger" size="large">
        已拒绝 {{ rejectedCount }}
      </el-tag>
    </div>

    <!-- 筛选工具栏 -->
    <section class="toolbar" aria-label="筛选条件">
      <el-input
        v-model="searchKeyword"
        placeholder="搜索知识内容或来源..."
        :prefix-icon="Search"
        clearable
        class="search-input"
        @keyup.enter="handleSearch"
      />
      <el-select
        v-model="filterSourceType"
        placeholder="来源类型"
        clearable
        class="filter-select"
      >
        <el-option label="上传" value="upload" />
        <el-option label="爬取" value="crawl" />
        <el-option label="API 导入" value="api" />
      </el-select>
      <el-select
        v-model="filterStatus"
        placeholder="审批状态"
        clearable
        class="filter-select"
      >
        <el-option label="待审批" value="pending" />
        <el-option label="已通过" value="approved" />
        <el-option label="已拒绝" value="rejected" />
      </el-select>
      <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
      <el-button @click="handleResetFilter">重置</el-button>

      <div class="toolbar-right">
        <el-button
          type="success"
          :disabled="!store.hasSelection"
          aria-label="批量通过选中的知识条目"
          @click="handleBatchApprove"
        >
          <el-icon><Check /></el-icon>
          批量通过 ({{ store.selectedCount }})
        </el-button>
        <el-button
          type="danger"
          :disabled="!store.hasSelection"
          aria-label="批量拒绝选中的知识条目"
          @click="showBatchRejectDialog = true"
        >
          <el-icon><Close /></el-icon>
          批量拒绝
        </el-button>
        <el-button @click="store.selectAll()">全选待审批</el-button>
        <el-button @click="store.clearSelection()">清除选择</el-button>
      </div>
    </section>

    <!-- 加载状态 -->
    <div v-if="store.loading" class="loading-state">
      <el-skeleton :rows="3" animated />
    </div>

    <!-- 空状态 -->
    <div v-else-if="!store.hasItems" class="empty-state">
      <el-icon :size="48"><CircleCheck /></el-icon>
      <span>暂无待审批的知识条目</span>
    </div>

    <!-- 知识卡片列表 -->
    <div v-else ref="cardsGridRef" class="cards-grid" @scroll="handleScroll">
      <div
        v-for="item in store.items"
        :key="item.id"
        class="knowledge-card"
        role="article"
        :aria-label="`知识条目 ${item.content.slice(0, 50)}`"
        :class="{
          'card-selected': store.isSelected(item.id),
          'card-approved': item.status === 'approved',
          'card-rejected': item.status === 'rejected',
        }"
      >
        <!-- 卡片头部 -->
        <div class="card-header">
          <el-checkbox
            :model-value="store.isSelected(item.id)"
            :disabled="item.status !== 'pending'"
            @change="store.toggleSelect(item.id)"
          />
          <el-tag :type="statusTagType(item.status)" size="small">
            {{ statusLabel(item.status) }}
          </el-tag>
          <el-tag size="small" type="info">{{ sourceTypeLabel(item.sourceType) }}</el-tag>
          <span class="card-id">#{{ item.id.slice(0, 8) }}</span>
        </div>

        <!-- 卡片内容 -->
        <div class="card-body">
          <div class="card-content">{{ item.content }}</div>
          <div class="card-meta">
            <span><el-icon><Document /></el-icon> {{ item.source }}</span>
            <span><el-icon><User /></el-icon> {{ item.submittedBy }}</span>
            <span><el-icon><Clock /></el-icon> {{ formatTime(item.submittedAt) }}</span>
          </div>
          <div v-if="item.tags && item.tags.length" class="card-tags">
            <el-tag v-for="tag in item.tags" :key="tag" size="small" effect="plain">
              {{ tag }}
            </el-tag>
          </div>
        </div>

        <!-- 卡片操作 -->
        <div v-if="item.status === 'pending'" class="card-actions">
          <el-button
            type="success"
            size="small"
            aria-label="通过此知识条目"
            @click="handleApprove(item.id)"
          >
            <el-icon><Check /></el-icon> 通过
          </el-button>
          <el-button
            type="danger"
            size="small"
            aria-label="拒绝此知识条目"
            @click="openRejectDialog(item.id)"
          >
            <el-icon><Close /></el-icon> 拒绝
          </el-button>
        </div>

        <!-- 已审批信息 -->
        <div v-else class="card-reviewed">
          <span>{{ item.reviewedBy }} 于 {{ formatTime(item.reviewedAt ?? '') }}</span>
          <span v-if="item.reviewNote" class="review-note">{{ item.reviewNote }}</span>
        </div>
      </div>
    </div>

    <!-- 分页 + 无限滚动 -->
    <div v-if="store.total > store.pageSize" class="pagination" aria-label="审批列表分页">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="store.pageSize"
        :total="store.total"
        layout="total, prev, pager, next"
        @current-change="handlePageChange"
      />
    </div>
    <!-- 无限滚动加载更多指示器 -->
    <div v-if="hasMoreItems" ref="loadMoreTriggerRef" class="load-more">
      <el-button :loading="loadingMore" @click="loadMore">
        {{ loadingMore ? '加载中...' : '加载更多' }}
      </el-button>
    </div>

    <!-- 拒绝对话框 -->
    <el-dialog v-model="showRejectDialog" title="拒绝原因" width="420px">
      <el-form label-width="0">
        <el-form-item>
          <el-input
            v-model="rejectReason"
            type="textarea"
            :rows="3"
            placeholder="请输入拒绝原因（必填）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRejectDialog = false">取消</el-button>
        <el-button type="danger" :disabled="!rejectReason.trim()" @click="handleReject">
          确认拒绝
        </el-button>
      </template>
    </el-dialog>

    <!-- 批量拒绝对话框 -->
    <el-dialog v-model="showBatchRejectDialog" title="批量拒绝" width="420px">
      <p>将拒绝选中的 {{ store.selectedCount }} 条知识条目</p>
      <el-form label-width="0">
        <el-form-item>
          <el-input
            v-model="batchRejectReason"
            type="textarea"
            :rows="3"
            placeholder="请输入拒绝原因（必填）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showBatchRejectDialog = false">取消</el-button>
        <el-button
          type="danger"
          :disabled="!batchRejectReason.trim()"
          @click="handleBatchReject"
        >
          确认批量拒绝
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue';
import { Search, Check, Close, Document, User, Clock, CircleCheck } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { useKnowledgeApprovalStore, type ApprovalStatus } from '@/stores/knowledgeApproval';

const store = useKnowledgeApprovalStore();

// ─── 筛选状态 ───
const searchKeyword = ref('');
const filterSourceType = ref('');
const filterStatus = ref<ApprovalStatus | ''>('');
const currentPage = ref(1);

// ─── 对话框状态 ───
const showRejectDialog = ref(false);
const showBatchRejectDialog = ref(false);
const rejectReason = ref('');
const batchRejectReason = ref('');
const rejectTargetId = ref('');

// ─── 无限滚动状态 ───
const cardsGridRef = ref<HTMLDivElement | null>(null);
const loadMoreTriggerRef = ref<HTMLDivElement | null>(null);
const loadingMore = ref(false);
const allItems = ref<typeof store.items.value>([]);
let intersectionObserver: IntersectionObserver | null = null;
const currentPageInternal = ref(1);

/** 是否还有更多数据 */
const hasMoreItems = computed(() => {
  return store.items.length < store.total;
});

// ─── 统计 ───
const pendingCount = computed(() => store.items.filter((i) => i.status === 'pending').length);
const approvedCount = computed(() => store.items.filter((i) => i.status === 'approved').length);
const rejectedCount = computed(() => store.items.filter((i) => i.status === 'rejected').length);

// ─── 工具函数 ───
function statusTagType(status: ApprovalStatus): '' | 'success' | 'danger' | 'warning' {
  const map: Record<ApprovalStatus, '' | 'success' | 'danger' | 'warning'> = {
    pending: 'warning',
    approved: 'success',
    rejected: 'danger',
  };
  return map[status] ?? '';
}

function statusLabel(status: ApprovalStatus): string {
  const map: Record<ApprovalStatus, string> = {
    pending: '待审批',
    approved: '已通过',
    rejected: '已拒绝',
  };
  return map[status] ?? status;
}

function sourceTypeLabel(type: string): string {
  const map: Record<string, string> = {
    upload: '上传',
    crawl: '爬取',
    api: 'API',
  };
  return map[type] ?? type;
}

function formatTime(iso: string): string {
  if (!iso) return '-';
  try {
    return new Date(iso).toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

// ─── 操作 ───
function handleSearch(): void {
  store.setFilter(
    filterStatus.value as ApprovalStatus,
    filterSourceType.value,
    searchKeyword.value,
  );
  currentPage.value = 1;
  currentPageInternal.value = 1;
  nextTick(() => setupInfiniteScroll());
}

function handleResetFilter(): void {
  searchKeyword.value = '';
  filterSourceType.value = '';
  filterStatus.value = '';
  store.resetFilter();
  currentPage.value = 1;
  currentPageInternal.value = 1;
  nextTick(() => setupInfiniteScroll());
}

function handlePageChange(page: number): void {
  currentPageInternal.value = page;
  store.fetchPendingList({ page });
  nextTick(() => setupInfiniteScroll());
}

/** 处理 .cards-grid 滚动事件（兜底：滚动到底部触发加载更多） */
function handleScroll(): void {
  if (!cardsGridRef.value || !hasMoreItems.value || loadingMore.value) return;
  const el = cardsGridRef.value;
  const threshold = 100;
  if (el.scrollHeight - el.scrollTop - el.clientHeight < threshold) {
    loadMore();
  }
}

async function handleApprove(id: string): Promise<void> {
  await store.approveItem(id);
}

function openRejectDialog(id: string): void {
  rejectTargetId.value = id;
  rejectReason.value = '';
  showRejectDialog.value = true;
}

async function handleReject(): Promise<void> {
  if (!rejectTargetId.value || !rejectReason.value.trim()) return;
  await store.rejectItem(rejectTargetId.value, rejectReason.value.trim());
  showRejectDialog.value = false;
  rejectReason.value = '';
  rejectTargetId.value = '';
}

async function handleBatchApprove(): Promise<void> {
  await store.batchApprove();
}

async function handleBatchReject(): Promise<void> {
  if (!batchRejectReason.value.trim()) return;
  await store.batchReject([], batchRejectReason.value.trim());
  showBatchRejectDialog.value = false;
  batchRejectReason.value = '';
}

onMounted(async () => {
  await store.fetchPendingList();
  await nextTick();
  setupInfiniteScroll();
});

onUnmounted(() => {
  if (intersectionObserver) {
    intersectionObserver.disconnect();
    intersectionObserver = null;
  }
});

// ─── 无限滚动 ───

/** 设置 IntersectionObserver 监听滚动到底部 */
function setupInfiniteScroll(): void {
  if (intersectionObserver) {
    intersectionObserver.disconnect();
  }
  if (!loadMoreTriggerRef.value) return;

  intersectionObserver = new IntersectionObserver(
    (entries) => {
      const entry = entries[0];
      if (entry && entry.isIntersecting && hasMoreItems.value && !loadingMore.value) {
        loadMore();
      }
    },
    { root: cardsGridRef.value, rootMargin: '100px', threshold: 0.1 },
  );
  intersectionObserver.observe(loadMoreTriggerRef.value);
}

/** 加载更多数据（追加模式） */
async function loadMore(): Promise<void> {
  if (loadingMore.value || !hasMoreItems.value) return;
  loadingMore.value = true;
  const nextPage = currentPageInternal.value + 1;
  try {
    await store.fetchPendingList({ page: nextPage });
    currentPageInternal.value = nextPage;
    await nextTick();
    // 重新观察新的触发元素
    setupInfiniteScroll();
  } catch {
    ElMessage.error('加载更多失败');
  } finally {
    loadingMore.value = false;
  }
}
</script>

<style scoped lang="scss">
.knowledge-approval-view {
  max-width: 1400px;
  margin: 0 auto;
  padding: 28px 24px;
}

.page-title {
  margin: 0 0 20px;
  font-size: var(--font-size-page-title);
  font-weight: 700;
  color: var(--text-primary);
}

.stats-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.search-input {
  width: 280px;
}

.filter-select {
  width: 140px;
}

.toolbar-right {
  margin-left: auto;
  display: flex;
  gap: 8px;
}

.loading-state {
  padding: 40px 0;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 80px 0;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}

/* ─── 卡片网格 ─── */
.cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
  gap: 16px;
  max-height: calc(100vh - 300px);
  overflow-y: auto;
  padding-right: 4px;

  &::-webkit-scrollbar { width: 6px; }
  &::-webkit-scrollbar-thumb { background: var(--bg-divider, #d9d9d9); border-radius: 3px; }
}

.knowledge-card {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  padding: 16px;
  border: 2px solid transparent;
  transition: border-color 0.2s, box-shadow 0.2s;

  &:hover {
    box-shadow: var(--shadow-md);
  }

  &.card-selected {
    border-color: var(--brand);
  }

  &.card-approved {
    border-left: 4px solid var(--el-color-success);
  }

  &.card-rejected {
    border-left: 4px solid var(--el-color-danger);
  }
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.card-id {
  margin-left: auto;
  font-family: monospace;
  font-size: 12px;
  color: var(--text-tertiary);
}

.card-body {
  margin-bottom: 12px;
}

.card-content {
  font-size: var(--font-size-body);
  color: var(--text-primary);
  line-height: 1.6;
  margin-bottom: 10px;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  font-size: var(--font-size-small);
  color: var(--text-tertiary);

  span {
    display: flex;
    align-items: center;
    gap: 4px;
  }
}

.card-tags {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.card-actions {
  display: flex;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid var(--border-light);
}

.card-reviewed {
  padding-top: 12px;
  border-top: 1px solid var(--border-light);
  font-size: var(--font-size-small);
  color: var(--text-tertiary);

  .review-note {
    display: block;
    margin-top: 4px;
    color: var(--text-secondary);
    font-style: italic;
  }
}

.pagination {
  display: flex;
  justify-content: center;
  margin-top: 24px;
}

/* ─── 无限滚动加载更多 ─── */
.load-more {
  display: flex;
  justify-content: center;
  padding: 16px 0 8px;
}

/* ─── 响应式 ─── */
@media (max-width: 767px) {
  .knowledge-approval-view {
    padding: 16px 12px;
  }

  .cards-grid {
    grid-template-columns: 1fr;
  }

  .toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .toolbar-right {
    margin-left: 0;
    flex-wrap: wrap;
  }

  .search-input,
  .filter-select {
    width: 100%;
  }
}
</style>
