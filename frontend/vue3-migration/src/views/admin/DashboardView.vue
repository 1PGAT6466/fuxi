<template>
  <div class="dashboard-view">
    <header class="page-header">
      <h1>📊 管理仪表板</h1>
      <el-button @click="refreshDashboard" :loading="loading">
        <el-icon><Refresh /></el-icon>
        刷新
      </el-button>
    </header>

    <!-- 核心指标卡片 -->
    <div class="metrics-grid">
      <el-card class="metric-card">
        <div class="metric-icon">📄</div>
        <div class="metric-info">
          <div class="metric-value">{{ stats.total_documents }}</div>
          <div class="metric-label">文档数</div>
        </div>
      </el-card>
      <el-card class="metric-card">
        <div class="metric-icon">🧩</div>
        <div class="metric-info">
          <div class="metric-value">{{ stats.total_chunks }}</div>
          <div class="metric-label">分块数</div>
        </div>
      </el-card>
      <el-card class="metric-card">
        <div class="metric-icon">🔮</div>
        <div class="metric-info">
          <div class="metric-value">{{ stats.total_vectors }}</div>
          <div class="metric-label">向量数</div>
        </div>
      </el-card>
      <el-card class="metric-card">
        <div class="metric-icon">👥</div>
        <div class="metric-info">
          <div class="metric-value">{{ stats.total_users }}</div>
          <div class="metric-label">用户数</div>
        </div>
      </el-card>
    </div>

    <!-- 详细信息 -->
    <div class="detail-grid">
      <el-card>
        <template #header>
          <span>📈 系统信息</span>
        </template>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="版本">{{ stats.version }}</el-descriptions-item>
          <el-descriptions-item label="运行时间">{{ stats.uptime_formatted }}</el-descriptions-item>
          <el-descriptions-item label="会话数">{{ stats.total_sessions }}</el-descriptions-item>
          <el-descriptions-item label="Wiki 页面">{{ stats.total_wiki_pages }}</el-descriptions-item>
          <el-descriptions-item label="API 密钥">{{ stats.total_api_keys }}</el-descriptions-item>
          <el-descriptions-item label="Webhook">{{ stats.total_webhooks }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card>
        <template #header>
          <span>🏷️ 文档分类</span>
        </template>
        <div v-if="categories.length" class="categories-list">
          <div v-for="cat in categories" :key="cat.name" class="category-item">
            <span class="cat-name">{{ cat.name }}</span>
            <el-progress :percentage="cat.percent" :stroke-width="14" />
            <span class="cat-count">{{ cat.count }}</span>
          </div>
        </div>
        <el-empty v-else description="暂无分类数据" />
      </el-card>
    </div>

    <!-- 用户列表 -->
    <el-card class="users-card">
      <template #header>
        <span>👥 用户列表</span>
      </template>
      <el-table :data="users" border stripe>
        <el-table-column prop="username" label="用户名" width="150" />
        <el-table-column prop="role" label="角色" width="120">
          <template #default="{ row }">
            <el-tag :type="row.role === 'admin' ? 'danger' : 'info'" size="small">
              {{ row.role }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="200" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active !== false ? 'success' : 'danger'" size="small">
              {{ row.is_active !== false ? '活跃' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import axios from 'axios'

const loading = ref(false)
const stats = ref<any>({})
const categories = ref<Array<{name: string, count: number, percent: number}>>([])
const users = ref<any[]>([])

const refreshDashboard = async () => {
  loading.value = true
  try {
    await Promise.all([
      fetchStats(),
      fetchUsers(),
    ])
  } catch (error) {
    console.error('刷新失败:', error)
  } finally {
    loading.value = false
  }
}

const fetchStats = async () => {
  try {
    const resp = await axios.get('/api/dashboard/stats')
    stats.value = resp.data.data || {}
    
    // 处理分类数据
    if (stats.value.categories) {
      const total = Object.values(stats.value.categories).reduce((a: number, b: any) => a + (b as number), 0) as number
      categories.value = Object.entries(stats.value.categories).map(([name, count]) => ({
        name,
        count: count as number,
        percent: total > 0 ? Math.round(((count as number) / total) * 100) : 0,
      }))
    }
  } catch (error) {
    console.error('获取统计失败:', error)
    ElMessage.error('获取统计数据失败')
  }
}

const fetchUsers = async () => {
  try {
    const resp = await axios.get('/api/admin/users')
    users.value = resp.data.users || resp.data || []
  } catch (error) {
    console.error('获取用户列表失败:', error)
  }
}

onMounted(() => {
  refreshDashboard()
})
</script>

<style scoped>
.dashboard-view {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h1 {
  margin: 0;
  font-size: 24px;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 20px;
}

.metric-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
}

.metric-icon {
  font-size: 36px;
}

.metric-value {
  font-size: 28px;
  font-weight: bold;
}

.metric-label {
  color: #666;
  font-size: 14px;
}

.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 20px;
}

.categories-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.category-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.cat-name {
  width: 100px;
  font-weight: 500;
}

.cat-count {
  width: 50px;
  text-align: right;
  color: #666;
}

.users-card {
  margin-top: 20px;
}
</style>
