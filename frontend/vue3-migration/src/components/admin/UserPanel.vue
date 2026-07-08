<template>
  <div class="user-panel">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>{{ $t('userPanel.title') }}</span>
          <el-button type="primary" size="small" @click="showAddUser = true">
            <el-icon><Plus /></el-icon> {{ $t('userPanel.addUser') }}
          </el-button>
        </div>
      </template>

      <el-table v-loading="loading" :data="users">
        <el-table-column prop="username" :label="$t('userPanel.username')" min-width="120" />
        <el-table-column prop="display_name" :label="$t('userPanel.displayName')" min-width="120" />
        <el-table-column prop="role" :label="$t('userPanel.role')" width="100">
          <template #default="{ row }">
            <el-tag :type="row.role === 'admin' ? 'danger' : 'info'">
              {{ row.role === 'admin' ? $t('userPanel.admin') : $t('userPanel.normalUser') }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="$t('userPanel.registerTime')" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created) }}
          </template>
        </el-table-column>
        <el-table-column :label="$t('userPanel.lastLogin')" width="180">
          <template #default="{ row }">
            {{ row.last_login ? formatDate(row.last_login) : $t('userPanel.neverLogin') }}
          </template>
        </el-table-column>
        <el-table-column :label="$t('userPanel.actions')" width="220" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="editUser(row)">
              <el-icon><Edit /></el-icon> {{ $t('userPanel.edit') }}
            </el-button>
            <el-button size="small" @click="resetPassword(row)">{{
              $t('userPanel.resetPassword')
            }}</el-button>
            <el-button size="small" type="danger" @click="deleteUser(row)">
              <el-icon><Delete /></el-icon>
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && users.length === 0" :description="$t('userPanel.noUsers')" />
    </el-card>

    <!-- 添加/编辑用户对话框 -->
    <el-dialog
      v-model="showAddUser"
      :title="editingUser ? $t('userPanel.editUser') : $t('userPanel.addUserTitle')"
      width="500px"
    >
      <el-form ref="userFormRef" :model="newUser" :rules="userRules" label-width="80px">
        <el-form-item :label="$t('userPanel.username')" prop="username">
          <el-input
            v-model="newUser.username"
            :placeholder="$t('userPanel.usernamePlaceholder')"
            :disabled="!!editingUser"
          />
        </el-form-item>
        <el-form-item :label="$t('userPanel.displayName')" prop="display_name">
          <el-input
            v-model="newUser.display_name"
            :placeholder="$t('userPanel.displayNamePlaceholder')"
          />
        </el-form-item>
        <el-form-item
          :label="editingUser ? $t('userPanel.newPassword') : $t('userPanel.password')"
          prop="password"
        >
          <el-input
            v-model="newUser.password"
            type="password"
            :placeholder="
              editingUser ? $t('userPanel.passwordKeepHint') : $t('userPanel.passwordPlaceholder')
            "
            show-password
          />
        </el-form-item>
        <el-form-item :label="$t('userPanel.role')" prop="role">
          <el-select v-model="newUser.role" :placeholder="$t('userPanel.rolePlaceholder')">
            <el-option :label="$t('userPanel.normalUser')" value="user" />
            <el-option :label="$t('userPanel.admin')" value="admin" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="closeDialog">{{ $t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="submitUser">
          {{ editingUser ? $t('common.save') : $t('userPanel.add') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue';
import apiClient from '@/api';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Plus, Edit, Delete } from '@element-plus/icons-vue';
import { formatDate } from '@/utils/helpers';
import type { FormInstance, FormRules } from 'element-plus';

interface User {
  id: string;
  username: string;
  display_name: string;
  role: 'admin' | 'user';
  created: string;
  last_login?: string;
}

interface NewUserForm {
  username: string;
  display_name: string;
  password: string;
  role: 'admin' | 'user';
}

const users = ref<User[]>([]);
const loading = ref<boolean>(false);
const saving = ref<boolean>(false);
const showAddUser = ref<boolean>(false);
const editingUser = ref<User | null>(null);
const userFormRef = ref<FormInstance>();

const newUser = reactive<NewUserForm>({
  username: '',
  display_name: '',
  password: '',
  role: 'user',
});

const userRules = computed<FormRules<NewUserForm>>(() => ({
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  display_name: [{ required: true, message: '请输入显示名称', trigger: 'blur' }],
  password: editingUser.value ? [] : [{ required: true, message: '请输入密码', trigger: 'blur' }],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }],
}));

onMounted(async () => {
  await fetchUsers();
});

async function fetchUsers(): Promise<void> {
  loading.value = true;
  try {
    const data = (await apiClient.get('/api/admin/users')) as { users?: User[] };
    users.value = data.users || [];
  } catch (error) {
    console.error('获取用户列表失败:', error);
    ElMessage.error('获取用户列表失败');
  } finally {
    loading.value = false;
  }
}

function closeDialog(): void {
  showAddUser.value = false;
  editingUser.value = null;
  resetForm();
}

function resetForm(): void {
  newUser.username = '';
  newUser.display_name = '';
  newUser.password = '';
  newUser.role = 'user';
}

function editUser(user: User): void {
  editingUser.value = user;
  newUser.username = user.username;
  newUser.display_name = user.display_name;
  newUser.password = '';
  newUser.role = user.role;
  showAddUser.value = true;
}

async function submitUser(): Promise<void> {
  if (!userFormRef.value) return;

  try {
    await userFormRef.value.validate();
    saving.value = true;

    const payload: Record<string, string> = {
      display_name: newUser.display_name,
      role: newUser.role,
    };
    if (newUser.password) payload.password = newUser.password;

    if (editingUser.value) {
      await apiClient.put(`/api/admin/users/${editingUser.value.id}`, payload);
      ElMessage.success('用户更新成功');
    } else {
      payload.username = newUser.username;
      payload.password = newUser.password;
      await apiClient.post('/api/admin/users', payload);
      ElMessage.success('用户添加成功');
    }

    closeDialog();
    await fetchUsers();
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(editingUser.value ? '用户更新失败' : '用户添加失败');
    }
  } finally {
    saving.value = false;
  }
}

async function resetPassword(user: User): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定要重置用户 ${user.username} 的密码吗？`, '确认');
    await apiClient.post(`/api/admin/users/${user.id}/reset-password`);
    ElMessage.success('密码重置成功');
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('密码重置失败');
    }
  }
}

async function deleteUser(user: User): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定要删除用户 ${user.username} 吗？此操作不可撤销。`, '确认删除', {
      type: 'warning',
    });
    await apiClient.delete(`/api/admin/users/${user.id}`);
    ElMessage.success('用户删除成功');
    await fetchUsers();
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('用户删除失败');
    }
  }
}
</script>

<style scoped lang="scss">
.user-panel {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
