<template>
  <div class="profile-view">
    <div class="profile-header">
      <h2>👤 用户中心</h2>
    </div>

    <div class="profile-content">
      <!-- 用户信息卡片 -->
      <div class="user-card">
        <div class="user-avatar">
          <el-avatar :size="80">{{ form.display_name?.charAt(0) || 'U' }}</el-avatar>
        </div>
        <div class="user-info">
          <h3>{{ form.display_name || form.username || '未知用户' }}</h3>
          <el-tag :type="form.role === 'admin' ? 'danger' : 'info'" size="small">
            {{ form.role === 'admin' ? '管理员' : '普通用户' }}
          </el-tag>
          <p class="user-email">{{ form.email || '未设置邮箱' }}</p>
        </div>
      </div>

      <!-- 编辑资料表单 -->
      <div class="section-card">
        <h3>✏️ 编辑资料</h3>
        <el-form :model="form" label-width="100px" class="edit-form">
          <el-form-item label="用户名">
            <el-input v-model="form.username" disabled />
          </el-form-item>
          <el-form-item label="显示名称">
            <el-input v-model="form.display_name" placeholder="请输入显示名称" />
          </el-form-item>
          <el-form-item label="邮箱">
            <el-input v-model="form.email" placeholder="请输入邮箱" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="saving" @click="handleSave">
              保存修改
            </el-button>
            <el-button @click="handleReset">重置</el-button>
          </el-form-item>
        </el-form>
      </div>

      <!-- 最近访问 -->
      <div class="section-card">
        <h3>📋 最近访问</h3>
        <div v-if="history.length === 0" class="empty-section">
          <el-empty description="暂无访问记录" :image-size="60" />
        </div>
        <div v-else class="history-list">
          <div v-for="item in history" :key="item.id" class="history-item">
            <div class="history-icon">{{ getTypeIcon(item.type) }}</div>
            <div class="history-info">
              <div class="history-title">{{ item.title }}</div>
              <div class="history-time">{{ formatDate(item.visited_at) }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 统计概览 -->
      <div class="section-card">
        <h3>📊 使用统计</h3>
        <div class="stats-grid">
          <div class="stat-item">
            <div class="stat-num">{{ userStats.sessions || 0 }}</div>
            <div class="stat-name">对话会话</div>
          </div>
          <div class="stat-item">
            <div class="stat-num">{{ userStats.favorites || 0 }}</div>
            <div class="stat-name">收藏数量</div>
          </div>
          <div class="stat-item">
            <div class="stat-num">{{ userStats.history || 0 }}</div>
            <div class="stat-name">访问记录</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import apiClient from '@/api';

interface UserInfo {
  username: string;
  display_name?: string;
  role?: string;
  email?: string;
}

interface HistoryItem {
  id: string;
  title: string;
  type?: string;
  visited_at?: string;
}

const user = ref<UserInfo>({ username: '' });
const history = ref<HistoryItem[]>([]);
const userStats = ref({ sessions: 0, favorites: 0, history: 0 });
const saving = ref(false);

const form = reactive({
  username: '',
  display_name: '',
  email: '',
  role: '',
});

function syncFormFromUser() {
  form.username = user.value.username || '';
  form.display_name = user.value.display_name || '';
  form.email = user.value.email || '';
  form.role = user.value.role || '';
}

async function loadProfile() {
  try {
    // 加载用户信息
    const authResp = await apiClient.get('/api/auth/me') as Record<string, unknown>;
    if (authResp) {
      user.value = {
        username: String(authResp.username || ''),
        display_name: String(authResp.display_name || authResp.username || ''),
        role: String(authResp.role || 'user'),
        email: authResp.email ? String(authResp.email) : undefined,
      };
      syncFormFromUser();
    }
  } catch {
    // 使用本地存储的用户信息
    try {
      const stored = localStorage.getItem('fuxi-user');
      if (stored) {
        user.value = JSON.parse(stored);
        syncFormFromUser();
      }
    } catch { /* ignore */ }
  }

  try {
    // 加载访问历史
    const histResp = await apiClient.get('/api/history?page_size=10') as { items?: HistoryItem[] };
    if (histResp?.items) {
      history.value = histResp.items;
    }
  } catch { /* ignore */ }

  try {
    // 加载统计数据
    const sessionsResp = await apiClient.get('/api/chat/sessions') as { total?: number };
    userStats.value.sessions = sessionsResp?.total || 0;

    const favResp = await apiClient.get('/api/favorites') as { items?: unknown[] };
    userStats.value.favorites = favResp?.items?.length || 0;

    userStats.value.history = history.value.length;
  } catch { /* ignore */ }
}

function getTypeIcon(type?: string): string {
  const icons: Record<string, string> = {
    document: '📄', wiki: '📖', chat: '💬', search: '🔍',
  };
  return icons[type || ''] || '📌';
}

function formatDate(dateStr?: string): string {
  if (!dateStr) return '';
  try {
    return new Date(dateStr).toLocaleString('zh-CN');
  } catch {
    return dateStr;
  }
}

async function handleSave() {
  saving.value = true;
  try {
    // 尝试 PUT /api/auth/me
    await apiClient.put('/api/auth/me', {
      display_name: form.display_name,
      email: form.email,
    });
    // 更新本地 user
    user.value.display_name = form.display_name;
    user.value.email = form.email;
    localStorage.setItem('fuxi-user', JSON.stringify(user.value));
    ElMessage.success('资料已保存');
  } catch (err: unknown) {
    // 如果是 404，提示后端暂未支持
    const axiosErr = err as { response?: { status?: number } };
    if (axiosErr?.response?.status === 404) {
      try {
        // 尝试 PUT /api/auth/profile
        await apiClient.put('/api/auth/profile', {
          display_name: form.display_name,
          email: form.email,
        });
        user.value.display_name = form.display_name;
        user.value.email = form.email;
        localStorage.setItem('fuxi-user', JSON.stringify(user.value));
        ElMessage.success('资料已保存');
      } catch {
        ElMessage.warning('后端暂未支持资料修改，已保存到本地');
        user.value.display_name = form.display_name;
        user.value.email = form.email;
        localStorage.setItem('fuxi-user', JSON.stringify(user.value));
      }
    } else {
      ElMessage.error('保存失败，请稍后重试');
    }
  } finally {
    saving.value = false;
  }
}

function handleReset() {
  syncFormFromUser();
  ElMessage.info('已重置为原始数据');
}

onMounted(loadProfile);
</script>

<style scoped>
.profile-view {
  max-width: 800px;
  margin: 0 auto;
  padding: 24px;
}

.profile-header h2 {
  font-size: 24px;
  font-weight: 700;
  margin: 0 0 24px;
  color: var(--el-text-color-primary);
}

.user-card {
  display: flex;
  align-items: center;
  gap: 20px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 20px;
}

.user-info h3 {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 8px;
  color: var(--el-text-color-primary);
}

.user-email {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin: 8px 0 0;
}

.section-card {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 16px;
}

.section-card h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 16px;
  color: var(--el-text-color-primary);
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.history-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px;
  border-radius: 8px;
  background: var(--el-fill-color-lighter);
}

.history-icon {
  font-size: 20px;
}

.history-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.history-time {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 2px;
}

.stats-grid {
  display: flex;
  gap: 16px;
}

.stat-item {
  flex: 1;
  text-align: center;
  padding: 16px;
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
}

.stat-num {
  font-size: 28px;
  font-weight: 700;
  color: var(--el-color-primary);
}

.stat-name {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}

.empty-section {
  padding: 20px 0;
}

.edit-form {
  max-width: 500px;
}

.edit-form :deep(.el-form-item__label) {
  font-weight: 500;
}
</style>
