<template>
  <!--
    伏羲 v2.1 — 用户管理
    用户列表表格 + 创建/编辑/启用禁用
  -->
  <div class="user-management">
    <h2 class="page-title">用户管理</h2>

    <div class="toolbar">
      <el-input
        v-model="searchQuery"
        placeholder="搜索用户名..."
        :prefix-icon="Search"
        clearable
        class="search-input"
      />
      <span class="toolbar-stats"> 共 {{ users.length }} 位用户 </span>
      <el-button type="primary" size="small" @click="showCreateDialog = true">
        <el-icon><Plus /></el-icon> 创建用户
      </el-button>
    </div>

    <!-- 用户表格 -->
    <div class="table-wrapper">
      <el-table
        :data="filteredUsers"
        style="width: 100%"
        size="small"
        :default-sort="{ prop: 'registered_at', order: 'descending' }"
      >
        <el-table-column prop="username" label="用户名" min-width="120">
          <template #default="{ row }">
            <div class="user-cell">
              <div class="user-avatar" :style="{ background: avatarColor(row.username) }">
                {{ row.username.charAt(0).toUpperCase() }}
              </div>
              <span class="user-name">{{ row.username }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="role" label="角色" width="120">
          <template #default="{ row }">
            <el-tag
              :type="row.role === 'admin' ? 'danger' : row.role === 'editor' ? 'warning' : 'info'"
              size="small"
            >
              {{ roleLabel(row.role) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="registered_at" label="注册时间" width="140" sortable>
          <template #default="{ row }">
            <span class="cell-meta">{{ row.registered_at }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="last_login" label="最后登录" width="140" sortable>
          <template #default="{ row }">
            <span class="cell-meta">{{ row.last_login }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-switch
              v-model="row.status_active"
              size="small"
              active-color="#34C759"
              inactive-color="#D1D1D6"
              active-text="启用"
              inactive-text="禁用"
              inline-prompt
              @change="handleStatusChange(row)"
            />
          </template>
        </el-table-column>

        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="editUser(row)">编辑</el-button>
            <el-button type="danger" link size="small" @click="deleteUser(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 空状态 -->
    <div v-if="filteredUsers.length === 0 && !loading" class="empty-state">
      <el-icon :size="48"><User /></el-icon>
      <span>未找到匹配的用户</span>
    </div>

    <!-- 创建/编辑对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      :title="editingUser ? '编辑用户' : '创建用户'"
      width="460px"
    >
      <el-form :model="userForm" label-width="80px">
        <el-form-item label="用户名">
          <el-input
            v-model="userForm.username"
            placeholder="输入用户名"
            :disabled="!!editingUser"
          />
        </el-form-item>
        <el-form-item v-if="!editingUser" label="密码">
          <el-input
            v-model="userForm.password"
            type="password"
            placeholder="输入密码"
            show-password
          />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="userForm.role" style="width: 100%">
            <el-option label="管理员 (admin)" value="admin" />
            <el-option label="编辑者 (editor)" value="editor" />
            <el-option label="用户 (user)" value="user" />
            <el-option label="观察者 (viewer)" value="viewer" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="editingUser" label="状态">
          <el-switch v-model="userForm.status_active" active-text="启用" inactive-text="禁用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="closeDialog">取消</el-button>
        <el-button type="primary" @click="saveUser">
          {{ editingUser ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { Search, Plus, User } from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import apiClient from '@/api';

// ─── 类型 ───
interface UserInfo {
  id: string;
  username: string;
  role: string;
  registered_at: string;
  last_login: string;
  status_active: boolean;
}

// ─── State ───
const users = ref<UserInfo[]>([]);
const searchQuery = ref('');
const loading = ref(false);
const showCreateDialog = ref(false);
const editingUser = ref<UserInfo | null>(null);

const userForm = ref({
  username: '',
  password: '',
  role: 'user',
  status_active: true,
});

// ─── Computed ───
const filteredUsers = computed(() => {
  const q = searchQuery.value.toLowerCase().trim();
  if (!q) return users.value;
  return users.value.filter(
    (u) => u.username.toLowerCase().includes(q) || u.role.toLowerCase().includes(q),
  );
});

// ─── Mock ───
const mockUsers: UserInfo[] = [
  {
    id: '1',
    username: 'admin',
    role: 'admin',
    registered_at: '2026-01-15 10:00',
    last_login: '2026-07-06 18:25',
    status_active: true,
  },
  {
    id: '2',
    username: 'zhangsan',
    role: 'editor',
    registered_at: '2026-03-20 14:30',
    last_login: '2026-07-06 16:10',
    status_active: true,
  },
  {
    id: '3',
    username: 'lisi',
    role: 'editor',
    registered_at: '2026-04-05 09:15',
    last_login: '2026-07-05 11:45',
    status_active: true,
  },
  {
    id: '4',
    username: 'wangwu',
    role: 'user',
    registered_at: '2026-05-12 16:00',
    last_login: '2026-07-04 08:30',
    status_active: false,
  },
  {
    id: '5',
    username: 'zhaoliu',
    role: 'viewer',
    registered_at: '2026-06-01 08:00',
    last_login: '2026-06-28 15:20',
    status_active: true,
  },
  {
    id: '6',
    username: 'sunqi',
    role: 'user',
    registered_at: '2026-06-15 11:20',
    last_login: '2026-07-06 14:05',
    status_active: true,
  },
  {
    id: '7',
    username: 'zhouba',
    role: 'user',
    registered_at: '2026-06-28 13:45',
    last_login: '2026-07-06 09:00',
    status_active: true,
  },
];

// ─── Helpers ───
function roleLabel(role: string): string {
  const map: Record<string, string> = {
    admin: '管理员',
    editor: '编辑者',
    user: '用户',
    viewer: '观察者',
  };
  return map[role] || role;
}

const avatarColors = ['#FF6700', '#3A6B8C', '#5B8C5A', '#C44B3C', '#D4A574', '#C9A84C']; // 品牌色系
function avatarColor(username: string): string {
  let hash = 0;
  for (let i = 0; i < username.length; i++) {
    hash = username.charCodeAt(i) + ((hash << 5) - hash);
  }
  return avatarColors[Math.abs(hash) % avatarColors.length];
}

// ─── Fetch ───
async function fetchUsers(): Promise<void> {
  loading.value = true;
  try {
    users.value = (await apiClient.get('/api/admin/users')) as UserInfo[];
  } catch {
    console.warn('[UserManagement] API 不可用，使用 mock 数据');
    users.value = mockUsers;
  } finally {
    loading.value = false;
  }
}

// ─── Actions ───
function editUser(user: UserInfo): void {
  editingUser.value = user;
  userForm.value = {
    username: user.username,
    password: '',
    role: user.role,
    status_active: user.status_active,
  };
  showCreateDialog.value = true;
}

function closeDialog(): void {
  showCreateDialog.value = false;
  editingUser.value = null;
  userForm.value = { username: '', password: '', role: 'user', status_active: true };
}

function saveUser(): void {
  if (!userForm.value.username.trim()) {
    ElMessage.warning('请输入用户名');
    return;
  }

  if (editingUser.value) {
    // 编辑
    const idx = users.value.findIndex((u) => u.id === editingUser.value!.id);
    if (idx !== -1) {
      users.value[idx] = {
        ...users.value[idx],
        role: userForm.value.role,
        status_active: userForm.value.status_active,
      };
    }
    ElMessage.success('用户已更新');
  } else {
    // 创建
    if (!userForm.value.password) {
      ElMessage.warning('请输入密码');
      return;
    }
    const newUser: UserInfo = {
      id: String(Date.now()),
      username: userForm.value.username,
      role: userForm.value.role,
      registered_at: new Date().toLocaleString('zh-CN').replace(/\//g, '-'),
      last_login: '—',
      status_active: true,
    };
    users.value.unshift(newUser);
    ElMessage.success('用户创建成功');
  }

  closeDialog();
}

async function handleStatusChange(user: UserInfo): Promise<void> {
  const action = user.status_active ? '启用' : '禁用';
  try {
    await ElMessageBox.confirm(`确认${action}用户「${user.username}」？`, '操作确认', {
      confirmButtonText: '确认',
      cancelButtonText: '取消',
      type: 'warning',
    });
    ElMessage.success(`用户「${user.username}」已${action}`);
  } catch {
    // 取消 — 恢复
    user.status_active = !user.status_active;
  }
}

async function deleteUser(user: UserInfo): Promise<void> {
  if (user.username === 'admin') {
    ElMessage.warning('不能删除主管理员');
    return;
  }
  try {
    await ElMessageBox.confirm(`确认删除用户「${user.username}」？此操作不可撤销。`, '删除确认', {
      confirmButtonText: '确认删除',
      cancelButtonText: '取消',
      type: 'error',
    });
    users.value = users.value.filter((u) => u.id !== user.id);
    ElMessage.success('用户已删除');
  } catch {
    /* cancelled */
  }
}

onMounted(fetchUsers);
</script>

<style scoped lang="scss">
.user-management {
  max-width: 1200px;
  margin: 0 auto;
  padding: 28px 24px;
}

.page-title {
  margin: 0 0 24px;
  font-size: var(--font-size-page-title);
  font-weight: 700;
  color: var(--text-primary);
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.search-input {
  max-width: 280px;
}

.toolbar-stats {
  font-size: var(--font-size-caption);
  color: var(--text-tertiary);
  flex: 1;
}

.table-wrapper {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.user-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.user-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #FFFFFF; // Brand contrast text
  font-size: 13px;
  font-weight: 600;
  flex-shrink: 0;
}

.user-name {
  font-weight: 500;
  color: var(--text-primary);
}

.cell-meta {
  font-size: var(--font-size-small);
  color: var(--text-tertiary);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 60px 0;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}

/* ─── 响应式 ─── */
@media (max-width: 767px) {
  .user-management {
    padding: 16px 12px;
  }
  .toolbar {
    flex-wrap: wrap;
  }
  .search-input {
    max-width: 100%;
    flex: 1;
  }
}
</style>
