<template>
  <!--
    伏羲 v2.1 — 插件源管理
    顶部：搜索框 + 添加源按钮
    中部：插件源列表（表格）
    底部：同步历史列表
    弹窗：添加/编辑插件源
  -->
  <div class="plugin-source-view">
    <h2 class="page-title">插件源管理</h2>
    <p class="page-desc">管理插件仓库源，支持同步、测试连接等操作</p>

    <!-- ─── 顶部操作栏 ─── -->
    <div class="toolbar">
      <el-input
        v-model="searchQuery"
        placeholder="搜索插件源名称或地址..."
        prefix-icon="Search"
        clearable
        class="search-input"
      />
      <el-button type="primary" @click="openAddDialog">
        <el-icon><Plus /></el-icon>
        添加源
      </el-button>
    </div>

    <!-- ─── 插件源列表 ─── -->
    <el-table
      v-loading="store.pluginLoading"
      :data="filteredSources"
      stripe
      border
      class="source-table"
      empty-text="暂无插件源数据"
    >
      <el-table-column prop="name" label="名称" min-width="140" show-overflow-tooltip />
      <el-table-column prop="type" label="类型" width="100">
        <template #default="{ row }">
          <el-tag size="small" :type="typeTagColor(row.type)">{{ row.type }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="url" label="地址" min-width="220" show-overflow-tooltip />
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag size="small" :type="statusTagColor(row.status)">
            {{ statusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="lastSync" label="最后同步" width="170">
        <template #default="{ row }">
          {{ row.lastSync ? formatTime(row.lastSync) : '—' }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="260" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openEditDialog(row)">编辑</el-button>
          <el-button size="small" type="success" :loading="syncingId === row.id" @click="handleSync(row.id)">
            同步
          </el-button>
          <el-button size="small" type="warning" :loading="testingId === row.id" @click="handleTest(row.id)">
            测试
          </el-button>
          <el-popconfirm
            title="确定删除该插件源？"
            confirm-button-text="删除"
            cancel-button-text="取消"
            @confirm="handleDelete(row.id)"
          >
            <template #reference>
              <el-button size="small" type="danger">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <!-- ─── 同步历史 ─── -->
    <div class="section-header">
      <h3>同步历史</h3>
      <el-button text @click="store.fetchSyncHistory()">
        <el-icon><Refresh /></el-icon>
        刷新
      </el-button>
    </div>

    <el-table
      :data="store.syncHistory"
      stripe
      border
      class="history-table"
      empty-text="暂无同步记录"
    >
      <el-table-column prop="sourceName" label="插件源" min-width="140" show-overflow-tooltip />
      <el-table-column prop="startTime" label="开始时间" width="170">
        <template #default="{ row }">{{ formatTime(row.startTime) }}</template>
      </el-table-column>
      <el-table-column prop="endTime" label="结束时间" width="170">
        <template #default="{ row }">{{ row.endTime ? formatTime(row.endTime) : '进行中...' }}</template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag size="small" :type="syncStatusColor(row.status)">
            {{ syncStatusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="itemsSynced" label="同步条目" width="100" />
      <el-table-column prop="error" label="错误信息" min-width="180" show-overflow-tooltip />
    </el-table>

    <!-- ─── 添加/编辑弹窗 ─── -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEditing ? '编辑插件源' : '添加插件源'"
      width="520px"
      destroy-on-close
    >
      <el-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        label-width="90px"
      >
        <el-form-item label="名称" prop="name">
          <el-input v-model="formData.name" placeholder="请输入插件源名称" />
        </el-form-item>
        <el-form-item label="类型" prop="type">
          <el-select v-model="formData.type" placeholder="选择类型" style="width: 100%">
            <el-option label="Git" value="git" />
            <el-option label="NPM" value="npm" />
            <el-option label="PyPI" value="pypi" />
            <el-option label="自定义" value="custom" />
          </el-select>
        </el-form-item>
        <el-form-item label="地址" prop="url">
          <el-input v-model="formData.url" placeholder="https://..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">
          {{ isEditing ? '保存' : '添加' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
/**
 * 伏羲 v2.1 — 插件源管理页面
 */
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
import { useOpsStore } from '@/stores/ops';
import { ElMessage } from 'element-plus';
import { Plus, Refresh, Search } from '@element-plus/icons-vue';
import type { FormInstance, FormRules } from 'element-plus';
import type { PluginSource } from '@/api/ops';

const store = useOpsStore();

// ─── 搜索 ───
const searchQuery = ref('');

const filteredSources = computed(() => {
  const q = searchQuery.value.toLowerCase().trim();
  if (!q) return store.pluginSources;
  return store.pluginSources.filter(
    s => s.name.toLowerCase().includes(q) || s.url.toLowerCase().includes(q),
  );
});

// ─── 操作状态 ───
const syncingId = ref<string | null>(null);
const testingId = ref<string | null>(null);

async function handleSync(sourceId: string): Promise<void> {
  syncingId.value = sourceId;
  try {
    await store.triggerSync(sourceId);
  } finally {
    syncingId.value = null;
  }
}

async function handleTest(sourceId: string): Promise<void> {
  testingId.value = sourceId;
  try {
    await store.testConnection(sourceId);
  } finally {
    testingId.value = null;
  }
}

async function handleDelete(sourceId: string): Promise<void> {
  await store.removePluginSource(sourceId);
}

// ─── 弹窗 ───
const dialogVisible = ref(false);
const isEditing = ref(false);
const editingId = ref<string | null>(null);
const submitting = ref(false);
const formRef = ref<FormInstance | null>(null);

const formData = ref({
  name: '',
  type: 'git',
  url: '',
});

const formRules: FormRules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  type: [{ required: true, message: '请选择类型', trigger: 'change' }],
  url: [
    { required: true, message: '请输入地址', trigger: 'blur' },
    { type: 'url', message: '请输入有效的 URL', trigger: 'blur' },
  ],
};

function openAddDialog(): void {
  isEditing.value = false;
  editingId.value = null;
  formData.value = { name: '', type: 'git', url: '' };
  dialogVisible.value = true;
}

function openEditDialog(source: PluginSource): void {
  isEditing.value = true;
  editingId.value = source.id;
  formData.value = {
    name: source.name,
    type: source.type,
    url: source.url,
  };
  dialogVisible.value = true;
}

async function handleSubmit(): Promise<void> {
  if (!formRef.value) return;
  const valid = await formRef.value.validate().catch(() => false);
  if (!valid) return;

  submitting.value = true;
  try {
    if (isEditing.value && editingId.value) {
      await store.modifyPluginSource(editingId.value, formData.value);
    } else {
      await store.createPluginSource(formData.value);
    }
    dialogVisible.value = false;
  } finally {
    submitting.value = false;
  }
}

// ─── 辅助函数 ───

function typeTagColor(type: string): string {
  switch (type) {
    case 'git': return '';
    case 'npm': return 'success';
    case 'pypi': return 'warning';
    default: return 'info';
  }
}

function statusTagColor(status: string): string {
  switch (status) {
    case 'active': return 'success';
    case 'error': return 'danger';
    case 'syncing': return 'warning';
    default: return 'info';
  }
}

function statusLabel(status: string): string {
  switch (status) {
    case 'active': return '活跃';
    case 'error': return '异常';
    case 'syncing': return '同步中';
    case 'idle': return '空闲';
    default: return status;
  }
}

function syncStatusColor(status: string): string {
  switch (status) {
    case 'success': return 'success';
    case 'failed': return 'danger';
    case 'running': return 'warning';
    default: return 'info';
  }
}

function syncStatusLabel(status: string): string {
  switch (status) {
    case 'success': return '成功';
    case 'failed': return '失败';
    case 'running': return '进行中';
    default: return status;
  }
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return iso;
  }
}

// ─── 生命周期 ───

onMounted(() => {
  store.fetchAllPlugins();
});
</script>

<style scoped>
.plugin-source-view {
  padding: 20px;
}

.page-title {
  font-size: 22px;
  font-weight: 600;
  margin: 0 0 4px;
}

.page-desc {
  color: #999;
  font-size: 14px;
  margin: 0 0 20px;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.search-input {
  max-width: 360px;
}

.source-table {
  margin-bottom: 32px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 24px 0 12px;
}

.section-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.history-table {
  margin-bottom: 20px;
}
</style>
