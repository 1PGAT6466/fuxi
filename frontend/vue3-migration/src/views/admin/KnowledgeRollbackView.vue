<template>
  <!--
    伏羲 v2.1 — 知识回滚界面
    来源筛选 + 时间筛选 + 版本列表 + 批量回滚
  -->
  <div class="knowledge-rollback-view">
    <h2 class="page-title">知识回滚</h2>

    <!-- 统计 -->
    <div class="stats-bar">
      <el-tag type="info" size="large">
        共 {{ store.total }} 条版本记录
      </el-tag>
      <el-tag v-if="store.hasSelection" type="warning" size="large">
        已选 {{ store.selectedCount }} 条
      </el-tag>
    </div>

    <!-- 筛选工具栏 -->
    <div class="toolbar">
      <el-input
        v-model="searchKeyword"
        placeholder="搜索知识内容..."
        :prefix-icon="Search"
        clearable
        class="search-input"
        @keyup.enter="handleSearch"
      />
      <el-select
        v-model="filterSource"
        placeholder="选择来源"
        clearable
        filterable
        class="filter-select"
      >
        <el-option
          v-for="src in store.sourceOptions"
          :key="src"
          :label="src"
          :value="src"
        />
      </el-select>
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
      <el-date-picker
        v-model="dateRange"
        type="daterange"
        range-separator="至"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        value-format="YYYY-MM-DD"
        class="date-picker"
      />
      <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
      <el-button @click="handleResetFilter">重置</el-button>

      <div class="toolbar-right">
        <el-button
          type="warning"
          :disabled="!store.hasSelection"
          @click="showBatchRollbackDialog = true"
        >
          <el-icon><RefreshLeft /></el-icon>
          批量回滚 ({{ store.selectedCount }})
        </el-button>
        <el-button @click="store.selectAll()">全选</el-button>
        <el-button @click="store.clearSelection()">清除选择</el-button>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="store.loading" class="loading-state">
      <el-skeleton :rows="5" animated />
    </div>

    <!-- 空状态 -->
    <div v-else-if="!store.hasVersions" class="empty-state">
      <el-icon :size="48"><FolderOpened /></el-icon>
      <span>暂无版本记录</span>
    </div>

    <!-- 版本表格 -->
    <div v-else class="table-wrapper">
      <el-table
        :data="store.versions"
        style="width: 100%"
        size="default"
        :default-sort="{ prop: 'operatedAt', order: 'descending' }"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="50" :selectable="isSelectable" />

        <el-table-column label="版本" width="80" align="center">
          <template #default="{ row }">
            <el-tag size="small" type="info">v{{ row.version }}</el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="content" label="知识内容" min-width="280">
          <template #default="{ row }">
            <div class="content-cell">{{ row.content }}</div>
          </template>
        </el-table-column>

        <el-table-column prop="source" label="来源" width="150">
          <template #default="{ row }">
            <span class="source-text">{{ row.source }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="sourceType" label="来源类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="sourceTypeTagType(row.sourceType)">
              {{ sourceTypeLabel(row.sourceType) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="action" label="操作类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="actionTagType(row.action)">
              {{ actionLabel(row.action) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="operatedBy" label="操作者" width="100" />

        <el-table-column prop="operatedAt" label="操作时间" width="160" sortable>
          <template #default="{ row }">
            <span class="time-text">{{ formatTime(row.operatedAt) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button
              type="primary"
              link
              size="small"
              @click="openDiffDialog(row)"
            >
              对比
            </el-button>
            <el-button
              type="warning"
              link
              size="small"
              @click="handleRollback(row.id)"
            >
              回滚
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 分页 -->
    <div v-if="store.total > store.pageSize" class="pagination">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="store.pageSize"
        :total="store.total"
        layout="total, prev, pager, next"
        @current-change="handlePageChange"
      />
    </div>

    <!-- 版本对比对话框 -->
    <el-dialog v-model="showDiffDialog" title="版本对比" width="800px" top="5vh">
      <div v-if="store.diffLoading" class="diff-loading">
        <el-skeleton :rows="6" animated />
      </div>
      <div v-else-if="store.diffData" class="diff-content">
        <div class="diff-header">
          <span>知识 ID: {{ store.diffData.knowledgeId }}</span>
          <span>v{{ store.diffData.currentVersion.version }} → v{{ store.diffData.targetVersion.version }}</span>
        </div>
        <div class="diff-body">
          <div
            v-for="(line, idx) in store.diffData.changes"
            :key="idx"
            class="diff-line"
            :class="`diff-${line.type}`"
          >
            <span class="line-num">{{ line.lineNum }}</span>
            <span class="line-prefix">{{ line.type === 'add' ? '+' : line.type === 'remove' ? '-' : ' ' }}</span>
            <span class="line-content">{{ line.content }}</span>
          </div>
        </div>
      </div>
      <div v-else class="diff-empty">暂无对比数据</div>
      <template #footer>
        <el-button @click="showDiffDialog = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 批量回滚确认对话框 -->
    <el-dialog v-model="showBatchRollbackDialog" title="批量回滚" width="420px">
      <p>将回滚选中的 {{ store.selectedCount }} 个版本</p>
      <el-form label-width="0">
        <el-form-item>
          <el-input
            v-model="batchRollbackNote"
            type="textarea"
            :rows="3"
            placeholder="回滚说明（可选）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showBatchRollbackDialog = false">取消</el-button>
        <el-button type="warning" @click="handleBatchRollback">
          确认批量回滚
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { Search, RefreshLeft, FolderOpened } from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { useKnowledgeRollbackStore, type KnowledgeVersion } from '@/stores/knowledgeRollback';

const store = useKnowledgeRollbackStore();

// ─── 筛选状态 ───
const searchKeyword = ref('');
const filterSource = ref('');
const filterSourceType = ref('');
const dateRange = ref<[string, string] | null>(null);
const currentPage = ref(1);

// ─── 对话框状态 ───
const showDiffDialog = ref(false);
const showBatchRollbackDialog = ref(false);
const batchRollbackNote = ref('');

// ─── 工具函数 ───
function sourceTypeLabel(type: string): string {
  const map: Record<string, string> = { upload: '上传', crawl: '爬取', api: 'API' };
  return map[type] ?? type;
}

function sourceTypeTagType(type: string): '' | 'success' | 'warning' | 'info' {
  const map: Record<string, '' | 'success' | 'warning' | 'info'> = {
    upload: '',
    crawl: 'warning',
    api: 'info',
  };
  return map[type] ?? '';
}

function actionLabel(action: string): string {
  const map: Record<string, string> = {
    create: '创建',
    update: '更新',
    delete: '删除',
    rollback: '回滚',
  };
  return map[action] ?? action;
}

function actionTagType(action: string): '' | 'success' | 'danger' | 'warning' | 'info' {
  const map: Record<string, '' | 'success' | 'danger' | 'warning' | 'info'> = {
    create: 'success',
    update: '',
    delete: 'danger',
    rollback: 'warning',
  };
  return map[action] ?? '';
}

function formatTime(iso: string): string {
  if (!iso) return '-';
  try {
    return new Date(iso).toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function isSelectable(row: KnowledgeVersion): boolean {
  return row.action !== 'rollback';
}

// ─── 操作 ───
function handleSearch(): void {
  const startDate = dateRange.value?.[0] ?? '';
  const endDate = dateRange.value?.[1] ?? '';
  store.setFilter({
    source: filterSource.value,
    sourceType: filterSourceType.value,
    startDate,
    endDate,
    keyword: searchKeyword.value,
  });
  currentPage.value = 1;
}

function handleResetFilter(): void {
  searchKeyword.value = '';
  filterSource.value = '';
  filterSourceType.value = '';
  dateRange.value = null;
  store.resetFilter();
  currentPage.value = 1;
}

function handlePageChange(page: number): void {
  store.fetchVersions({ page });
}

function handleSelectionChange(rows: KnowledgeVersion[]): void {
  store.clearSelection();
  for (const row of rows) {
    store.toggleSelect(row.id);
  }
}

async function handleRollback(versionId: string): Promise<void> {
  try {
    await ElMessageBox.confirm(
      '确认回滚此版本？此操作将恢复该版本的知识内容。',
      '回滚确认',
      { confirmButtonText: '确认回滚', cancelButtonText: '取消', type: 'warning' },
    );
    await store.rollbackVersion(versionId);
  } catch {
    // 用户取消
  }
}

function openDiffDialog(version: KnowledgeVersion): void {
  // 打开对比对话框，使用当前版本号和上一版本号
  store.fetchDiff(version.knowledgeId, version.version, version.version - 1);
  showDiffDialog.value = true;
}

async function handleBatchRollback(): Promise<void> {
  await store.batchRollback(undefined, batchRollbackNote.value || undefined);
  showBatchRollbackDialog.value = false;
  batchRollbackNote.value = '';
}

onMounted(() => {
  store.fetchVersions();
});
</script>

<style scoped lang="scss">
.knowledge-rollback-view {
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
  width: 240px;
}

.filter-select {
  width: 140px;
}

.date-picker {
  max-width: 320px;
}

.toolbar-right {
  margin-left: auto;
  display: flex;
  gap: 8px;
}

.loading-state {
  padding: 20px 0;
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

.table-wrapper {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.content-cell {
  font-size: var(--font-size-body);
  color: var(--text-primary);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.source-text {
  font-size: var(--font-size-small);
  color: var(--text-secondary);
}

.time-text {
  font-size: var(--font-size-small);
  color: var(--text-tertiary);
}

.pagination {
  display: flex;
  justify-content: center;
  margin-top: 24px;
}

/* ─── Diff 样式 ─── */
.diff-loading {
  padding: 20px 0;
}

.diff-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 16px;
  font-size: var(--font-size-small);
  color: var(--text-tertiary);
}

.diff-body {
  font-family: 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  background: var(--bg-subtle);
  border-radius: var(--radius-sm);
  padding: 12px;
  overflow-x: auto;
}

.diff-line {
  display: flex;
  gap: 8px;
  padding: 2px 0;

  &.diff-add {
    background: rgba(52, 199, 89, 0.1);
    color: var(--el-color-success);
  }

  &.diff-remove {
    background: rgba(255, 59, 48, 0.1);
    color: var(--el-color-danger);
  }

  &.diff-same {
    color: var(--text-secondary);
  }
}

.line-num {
  width: 40px;
  text-align: right;
  color: var(--text-tertiary);
  user-select: none;
}

.line-prefix {
  width: 16px;
  text-align: center;
  user-select: none;
}

.line-content {
  flex: 1;
  white-space: pre-wrap;
  word-break: break-all;
}

.diff-empty {
  text-align: center;
  padding: 40px 0;
  color: var(--text-tertiary);
}

/* ─── 响应式 ─── */
@media (max-width: 767px) {
  .knowledge-rollback-view {
    padding: 16px 12px;
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
  .filter-select,
  .date-picker {
    width: 100%;
    max-width: 100%;
  }
}
</style>
