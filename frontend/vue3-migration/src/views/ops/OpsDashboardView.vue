<template>
  <div class="ops-dashboard">
    <header class="page-header">
      <h1>🎛️ 运维仪表板</h1>
      <div class="header-actions">
        <el-button @click="refreshAll" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <span class="last-update">最后更新: {{ lastUpdate }}</span>
      </div>
    </header>

    <!-- 顶部指标卡片 -->
    <div class="metrics-row">
      <el-card v-for="metric in metrics" :key="metric.key" class="metric-card">
        <div class="metric-icon">{{ metric.icon }}</div>
        <div class="metric-info">
          <div class="metric-value">{{ metric.value }}</div>
          <div class="metric-label">{{ metric.label }}</div>
        </div>
      </el-card>
    </div>

    <!-- 中部图表区 -->
    <div class="charts-row">
      <el-card class="chart-card">
        <template #header>
          <span>📈 文档分类统计</span>
        </template>
        <div v-if="categories.length" class="categories-list">
          <div v-for="cat in categories" :key="cat.name" class="category-item">
            <span class="cat-name">{{ cat.name }}</span>
            <el-progress :percentage="cat.percent" :stroke-width="16" />
            <span class="cat-count">{{ cat.count }}</span>
          </div>
        </div>
        <el-empty v-else description="暂无分类数据" />
      </el-card>

      <el-card class="chart-card">
        <template #header>
          <span>🏛️ 系统状态</span>
        </template>
        <div class="system-status">
          <div class="status-item">
            <span class="status-label">版本</span>
            <span class="status-value">{{ systemInfo.version }}</span>
          </div>
          <div class="status-item">
            <span class="status-label">运行时间</span>
            <span class="status-value">{{ systemInfo.uptime }}</span>
          </div>
          <div class="status-item">
            <span class="status-label">用户数</span>
            <span class="status-value">{{ systemInfo.users }}</span>
          </div>
          <div class="status-item">
            <span class="status-label">API 密钥</span>
            <span class="status-value">{{ systemInfo.apiKeys }}</span>
          </div>
          <div class="status-item">
            <span class="status-label">Webhook</span>
            <span class="status-value">{{ systemInfo.webhooks }}</span>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 底部列表区 -->
    <div class="lists-row">
      <el-card class="list-card">
        <template #header>
          <span>📊 四象系统状态</span>
        </template>
        <div class="symbols-grid">
          <div v-for="(data, name) in symbols" :key="name" class="symbol-item">
            <div class="symbol-name">{{ symbolLabel(name) }}</div>
            <div class="symbol-stats">
              <span>查询: {{ data.query_count }}</span>
              <span>延迟: {{ data.avg_latency_ms }}ms</span>
              <span>置信度: {{ (data.avg_confidence * 100).toFixed(1) }}%</span>
            </div>
          </div>
        </div>
      </el-card>

      <el-card class="list-card">
        <template #header>
          <span>📈 总体统计</span>
        </template>
        <div class="summary-stats">
          <div class="summary-item">
            <span class="summary-label">总查询数</span>
            <span class="summary-value">{{ summary.total_queries }}</span>
          </div>
          <div class="summary-item">
            <span class="summary-label">平均延迟</span>
            <span class="summary-value">{{ summary.avg_latency_ms }}ms</span>
          </div>
          <div class="summary-item">
            <span class="summary-label">平均置信度</span>
            <span class="summary-value">{{ (summary.avg_confidence * 100).toFixed(1) }}%</span>
          </div>
          <div class="summary-item">
            <span class="summary-label">缓存命中率</span>
            <span class="summary-value">{{ (summary.cache_hit_rate * 100).toFixed(1) }}%</span>
          </div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import axios from 'axios'

const loading = ref(false)
const lastUpdate = ref('')
const metrics = ref<Array<{key: string, icon: string, value: string | number, label: string}>>([])
const categories = ref<Array<{name: string, count: number, percent: number}>>([])
const symbols = ref<Record<string, any>>({})
const summary = ref<any>({})
const systemInfo = ref<any>({})

const refreshAll = async () => {
  loading.value = true
  try {
    await Promise.all([
      fetchDashboardStats(),
      fetchGrowthOverview(),
    ])
    lastUpdate.value = new Date().toLocaleTimeString('zh-CN')
  } catch (error) {
    console.error('刷新失败:', error)
  } finally {
    loading.value = false
  }
}

const fetchDashboardStats = async () => {
  try {
    const resp = await axios.get('/api/dashboard/stats')
    const data = resp.data.data
    
    // 更新指标卡片
    metrics.value = [
      { key: 'documents', icon: '📄', value: data.total_documents || 0, label: '文档数' },
      { key: 'chunks', icon: '🧩', value: data.total_chunks || 0, label: '分块数' },
      { key: 'vectors', icon: '🔮', value: data.total_vectors || 0, label: '向量数' },
      { key: 'users', icon: '👥', value: data.total_users || 0, label: '用户数' },
      { key: 'sessions', icon: '💬', value: data.total_sessions || 0, label: '会话数' },
      { key: 'wiki', icon: '📚', value: data.total_wiki_pages || 0, label: 'Wiki 页面' },
    ]
    
    // 更新分类
    if (data.categories) {
      const total = Object.values(data.categories).reduce((a: number, b: any) => a + (b as number), 0) as number
      categories.value = Object.entries(data.categories).map(([name, count]) => ({
        name,
        count: count as number,
        percent: total > 0 ? Math.round(((count as number) / total) * 100) : 0,
      }))
    }
    
    // 更新系统信息
    systemInfo.value = {
      version: data.version || '未知',
      uptime: data.uptime_formatted || '未知',
      users: data.total_users || 0,
      apiKeys: data.total_api_keys || 0,
      webhooks: data.total_webhooks || 0,
    }
  } catch (error) {
    console.error('获取仪表板统计失败:', error)
    ElMessage.error('获取仪表板数据失败')
  }
}

const fetchGrowthOverview = async () => {
  try {
    const resp = await axios.get('/api/growth/overview')
    const data = resp.data.data
    
    // 更新四象状态
    symbols.value = data.symbols || {}
    
    // 更新总体统计
    summary.value = data.summary || {}
  } catch (error) {
    console.error('获取成长概览失败:', error)
  }
}

const symbolLabel = (name: string) => {
  const labels: Record<string, string> = {
    shaoyang: '少阳 ☰',
    taiyang: '太阳 ☱',
    shaoyin: '少阴 ☲',
    taiyin: '太阴 ☳',
  }
  return labels[name] || name
}

onMounted(() => {
  refreshAll()
})
</script>

<style scoped>
.ops-dashboard {
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

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.last-update {
  color: #999;
  font-size: 14px;
}

.metrics-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
  margin-bottom: 20px;
}

.metric-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
}

.metric-icon {
  font-size: 32px;
}

.metric-value {
  font-size: 24px;
  font-weight: bold;
}

.metric-label {
  color: #666;
  font-size: 14px;
}

.charts-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 20px;
}

.chart-card {
  min-height: 300px;
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

.system-status {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.status-item {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.status-label {
  color: #666;
}

.status-value {
  font-weight: 500;
}

.lists-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.symbols-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.symbol-item {
  padding: 12px;
  background: #f5f7fa;
  border-radius: 8px;
}

.symbol-name {
  font-weight: 500;
  margin-bottom: 8px;
}

.symbol-stats {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 14px;
  color: #666;
}

.summary-stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.summary-item {
  padding: 12px;
  background: #f5f7fa;
  border-radius: 8px;
  text-align: center;
}

.summary-label {
  display: block;
  color: #666;
  font-size: 14px;
  margin-bottom: 4px;
}

.summary-value {
  font-size: 20px;
  font-weight: bold;
}
</style>
