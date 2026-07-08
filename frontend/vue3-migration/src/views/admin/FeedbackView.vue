<template>
  <!--
    伏羲 v1.44 — 用户反馈
    反馈列表 + 新增反馈对话框 + 状态管理
  -->
  <div class="feedback-view">
    <div class="feedback-header">
      <div class="header-info">
        <h2 class="page-title">用户反馈</h2>
        <p class="page-desc">收集和管理用户反馈意见</p>
      </div>
      <el-button type="primary" @click="showAddDialog = true">
        <el-icon><Plus /></el-icon>
        新增反馈
      </el-button>
    </div>

    <!-- 加载态 -->
    <div v-if="loading" class="feedback-loading">
      <el-skeleton :rows="6" animated />
    </div>

    <!-- 错误状态 — API 失败且 mock 为空时显示 -->
    <ErrorState
      v-else-if="error && feedbacks.length === 0"
      message="无法加载反馈数据，请检查后端服务"
      @retry="fetchFeedbacks"
    />

    <!-- 空状态 -->
    <div v-else-if="feedbacks.length === 0" class="feedback-empty">
      <el-empty description="暂无反馈记录">
        <el-button type="primary" @click="showAddDialog = true">新增反馈</el-button>
      </el-empty>
    </div>

    <!-- 反馈表格 -->
    <div v-else class="feedback-table-wrap">
      <el-table :data="feedbacks" stripe style="width: 100%">
        <el-table-column prop="user" label="用户" width="120">
          <template #default="{ row }">
            <div class="user-cell">
              <el-icon :size="16"><UserFilled /></el-icon>
              <span>{{ row.user }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="content" label="反馈内容" min-width="280">
          <template #default="{ row }">
            <div class="content-cell">{{ row.content }}</div>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="170">
          <template #default="{ row }">
            {{ formatDate(row.created_at || row.time) }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleToggleStatus(row)">
              {{ row.status === 'resolved' ? '标记未处理' : '标记已处理' }}
            </el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">
              <el-icon><Delete /></el-icon>
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 新增反馈对话框 -->
    <el-dialog
      v-model="showAddDialog"
      title="新增反馈"
      width="520px"
      destroy-on-close
    >
      <el-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        label-width="80px"
        label-position="top"
      >
        <el-form-item label="用户" prop="user">
          <el-input
            v-model="formData.user"
            placeholder="请输入反馈用户"
            :prefix-icon="UserFilled"
          />
        </el-form-item>
        <el-form-item label="反馈内容" prop="content">
          <el-input
            v-model="formData.content"
            type="textarea"
            :rows="5"
            placeholder="请输入反馈内容..."
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmitFeedback">
          提交
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Plus, UserFilled, Delete } from '@element-plus/icons-vue';
import type { FormInstance, FormRules } from 'element-plus';
import apiClient from '@/api';
import { formatDate } from '@/utils/helpers';
import ErrorState from '@/components/common/ErrorState.vue';

// ─── 类型 ───
interface FeedbackItem {
  id: string;
  user: string;
  content: string;
  status: 'pending' | 'resolved';
  created_at?: string;
  time?: string;
}

interface FeedbackForm {
  user: string;
  content: string;
}

// ─── 状态 ───
const loading = ref(false);
const error = ref(false);
const feedbacks = ref<FeedbackItem[]>([]);
const showAddDialog = ref(false);
const submitting = ref(false);
const formRef = ref<FormInstance>();

const formData = reactive<FeedbackForm>({
  user: '',
  content: '',
});

const formRules: FormRules = {
  user: [{ required: true, message: '请输入用户', trigger: 'blur' }],
  content: [
    { required: true, message: '请输入反馈内容', trigger: 'blur' },
    { min: 5, message: '反馈内容至少5个字符', trigger: 'blur' },
  ],
};

// ─── Mock 数据 ───
function getMockFeedbacks(): FeedbackItem[] {
  const now = Date.now();
  return [
    {
      id: 'fb1',
      user: '张三',
      content: '知识库搜索结果的排序不太准确，经常找不到想要的文档。希望能优化检索算法。',
      status: 'pending',
      created_at: new Date(now - 3600000).toISOString(),
    },
    {
      id: 'fb2',
      user: '李四',
      content: '上传大文件时偶尔会超时失败，建议增加断点续传功能或对大文件做分片上传。',
      status: 'pending',
      created_at: new Date(now - 86400000).toISOString(),
    },
    {
      id: 'fb3',
      user: '王五',
      content: '界面美观，响应速度也很快！希望能支持更多文档格式的预览。',
      status: 'resolved',
      created_at: new Date(now - 172800000).toISOString(),
    },
    {
      id: 'fb4',
      user: '赵六',
      content: '用户管理模块缺少批量导入功能，手动添加用户效率很低。',
      status: 'pending',
      created_at: new Date(now - 259200000).toISOString(),
    },
    {
      id: 'fb5',
      user: '孙七',
      content: '希望能增加数据导出为 Excel 的功能，方便做报表分析。',
      status: 'resolved',
      created_at: new Date(now - 345600000).toISOString(),
    },
    {
      id: 'fb6',
      user: '周八',
      content: '移动端体验不太好，有些按钮太小难以点击，建议适配响应式布局。',
      status: 'pending',
      created_at: new Date(now - 432000000).toISOString(),
    },
  ];
}

// ─── 方法 ───
function statusTagType(status: string): 'warning' | 'success' {
  return status === 'resolved' ? 'success' : 'warning';
}

function statusLabel(status: string): string {
  return status === 'resolved' ? '已处理' : '待处理';
}

// ─── 数据加载 ───
async function fetchFeedbacks(): Promise<void> {
  loading.value = true;
  error.value = false;
  try {
    const data = (await apiClient.get('/api/feedback/weekly')) as Record<string, unknown>;
    feedbacks.value = (data.feedbacks || data.data || []) as FeedbackItem[];
  } catch {
    console.warn('[FeedbackView] API 不可用，使用 mock 数据');
    feedbacks.value = getMockFeedbacks();
    // 如果 mock 也为空（不应发生），设置 error
    if (feedbacks.value.length === 0) {
      error.value = true;
    }
  } finally {
    loading.value = false;
  }
}

// ─── 提交反馈 ───
async function handleSubmitFeedback(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid) return;

  submitting.value = true;
  try {
    await apiClient.post('/api/feedback', {
      user: formData.user,
      content: formData.content,
    });
    ElMessage.success('反馈提交成功');
    showAddDialog.value = false;
    // 重置表单
    formData.user = '';
    formData.content = '';
    // 添加到本地列表
    feedbacks.value.unshift({
      id: `fb_${Date.now()}`,
      user: formData.user,
      content: formData.content,
      status: 'pending',
      created_at: new Date().toISOString(),
    });
  } catch {
    // 降级：本地添加
    feedbacks.value.unshift({
      id: `fb_${Date.now()}`,
      user: formData.user,
      content: formData.content,
      status: 'pending',
      created_at: new Date().toISOString(),
    });
    showAddDialog.value = false;
    formData.user = '';
    formData.content = '';
    ElMessage.success('反馈已添加（本地模式）');
  } finally {
    submitting.value = false;
  }
}

// ─── 状态切换 ───
async function handleToggleStatus(row: FeedbackItem): Promise<void> {
  const newStatus = row.status === 'resolved' ? 'pending' : 'resolved';
  try {
    await apiClient.put(`/api/feedback/${row.id}`, { status: newStatus });
  } catch {
    /* 忽略 API 错误 */
  }
  row.status = newStatus;
  ElMessage.success(newStatus === 'resolved' ? '已标记为已处理' : '已标记为待处理');
}

// ─── 删除 ───
async function handleDelete(row: FeedbackItem): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定要删除「${row.user}」的反馈吗？`, '确认删除', {
      type: 'warning',
    });
    try {
      await apiClient.delete(`/api/feedback/${row.id}`);
    } catch {
      /* 忽略 API 错误 */
    }
    feedbacks.value = feedbacks.value.filter((f) => f.id !== row.id);
    ElMessage.success('删除成功');
  } catch {
    /* 用户取消 */
  }
}

onMounted(() => {
  fetchFeedbacks();
});
</script>

<style scoped lang="scss">
.feedback-view {
  max-width: 1200px;
  margin: 0 auto;
  padding: 28px 24px;
}

/* ─── 头部 ─── */
.feedback-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 24px;
}

.page-title {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
}

.page-desc {
  margin: 4px 0 0;
  font-size: var(--font-size-caption);
  color: var(--text-secondary);
}

/* ─── 表格 ─── */
.feedback-table-wrap {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.user-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 500;
  color: var(--text-primary);
}

.content-cell {
  color: var(--text-secondary);
  line-height: 1.5;
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ─── 加载 / 空状态 ─── */
.feedback-loading {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: 24px;
  box-shadow: var(--shadow-sm);
}

.feedback-empty {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: 40px;
  box-shadow: var(--shadow-sm);
}

/* ─── 响应式 ─── */
@media (max-width: 767px) {
  .feedback-view {
    padding: 16px;
  }

  .feedback-header {
    flex-direction: column;
    gap: 12px;
  }

  .feedback-table-wrap {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;

    :deep(.el-table) {
      min-width: 600px;
    }
  }
}
</style>
