<template>
  <div class="monitoring-view">
    <header class="page-header">
      <h1>📊 监控中心</h1>
      <el-button @click="refreshMetrics" :loading="loading">
        <el-icon><Refresh /></el-icon>
        刷新
      </el-button>
    </header>

    <!-- 系统指标卡片 -->
    <div class="metrics-grid">
      <el-card class="metric-card">
        <div class="metric-header">
          <span class="metric-icon">🖥️</span>
          <span class="metric-title">CPU</span>
        </div>
        <div class="metric-value">{{ metrics.cpu?.percent?.toFixed(1) || 0 }}%</div>
        <el-progress :percentage="metrics.cpu?.percent || 0" :stroke-width="8" :status="cpuStatus" />
        <div class="metric-detail">{{ metrics.cpu?.count || 0 }} 核心</div>
      </el-card>

      <el-card class="metric-card">
        <div class="metric-header">
          <span class="metric-icon">💾</span>
          <span class="metric-title">内存</span>
        </div>
        <div class="metric-value">{{ metrics.memory?.percent?.toFixed(1) || 0 }}%</div>
        <el-progress :percentage="metrics.memory?.percent || 0" :stroke-width="8" :status="memoryStatus" />
        <div class="metric-detail">{{ formatBytes(metrics.memory?.used || 0) }} / {{ formatBytes(metrics.memory?.total || 0) }}</div>
      </el-card>

      <el-card class="metric-card">
        <div class="metric-header">
          <span class="metric-icon">💿</span>
          <span class="metric-title">磁盘</span>
        </div>
        <div class="metric-value">{{ metrics.disk?.percent?.toFixed(1) || 0 }}%</div>
        <el-progress :percentage="metrics.disk?.percent || 0" :stroke-width="8" :status="diskStatus" />
        <div class="metric-detail">{{ formatBytes(metrics.disk?.used || 0) }} / {{ formatBytes(metrics.disk?.total || 0) }}</div>
      </el-card>

      <el-card class="metric-card">
        <div class="metric-header">
          <span class="metric-icon">🌐</span>
          <span class="metric-title">网络</span>
        </div>
        <div class="metric-value">{{ metrics.processes?.total || 0 }}</div>
        <div class="metric-detail">进程数</div>
        <div class="metric-sub">
          ↑ {{ formatBytes(metrics.network?.bytes_sent || 0) }}
          ↓ {{ formatBytes(metrics.network?.bytes_recv || 0) }}
        </div>
      </el-card>
    </div>

    <!-- 告警和日志 -->
    <div class="detail-grid">
      <el-card>
        <template #header>
          <div class="card-header">
            <span>🔔 告警列表</span>
            <el-tag :type="alerts.length > 0 ? 'danger' : 'success'" size="small">
              {{ alerts.length }}
            </el-tag>
          </div>
        </template>
        <div v-if="alerts.length" class="alerts-list">
          <div v-for="alert in alerts" :key="alert.id" class="alert-item" :class="`alert-${alert.level}`">
            <span class="alert-icon">{{ alert.level === 'critical' ? '🔴' : alert.level === 'warning' ? '🟡' : '🔵' }}</span>
            <span class="alert-message">{{ alert.message }}</span>
            <span class="alert-time">{{ formatTime(alert.timestamp) }}</span>
          </div>
        </div>
        <el-empty v-else description="暂无告警" />
      </el-card>

      <el-card>
        <template #header>
          <span>📝 日志分析</span>
        </template>
        <div v-if="logAnalysis.total_files > 0" class="log-analysis">
          <div class="log-stat">
            <span class="stat-label">日志文件数</span>
            <span class="stat-value">{{ logAnalysis.total_files }}</span>
          </div>
          <div class="log-stat">
            <span class="stat-label">总大小</span>
            <span class="stat-value">{{ formatBytes(logAnalysis.total_size) }}</span>
          </div>
          <div class="log-stat">
            <span class="stat-label">INFO</span>
            <span class="stat-value">{{ logAnalysis.by_level?.INFO || 0 }}</span>
          </div>
          <div class="log-stat">
            <span class="stat-label">WARNING</span>
            <span class="stat-value text-warning">{{ logAnalysis.by_level?.WARNING || 0 }}</span>
          </div>
          <div class="log-stat">
            <span class="stat-label">ERROR</span>
            <span class="stat-value text-danger">{{ logAnalysis.by_level?.ERROR || 0 }}</span>
          </div>
        </div>
        <el-empty v-else description="暂无日志数据" />
      </el-card>
    </div>

    <!-- 告警规则 -->
    <el-card class="rules-card">
      <template #header>
        <span>⚙️ 告警规则</span>
      </template>
      <el-table :data="alertRules" border>
        <el-table-column prop="name" label="规则名称" />
        <el-table-column prop="condition" label="条件" />
        <el-table-column prop="level" label="级别">
          <template #default="{ row }">
            <el-tag :type="row.level === 'critical' ? 'danger' : 'warning'" size="small">
              {{ row.level }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="enabled" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
              {{ row.enabled ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import axios from 'axios'

const loading = ref(false)
const metrics = ref<any>({})
const alerts = ref<any[]>([])
const alertRules = ref<any[]>([])
const logAnalysis = ref<any>({})

const cpuStatus = computed(() => {
  const percent = metrics.value.cpu?.percent || 0
  if (percent > 90) return 'exception'
  if (percent > 70) return 'warning'
  return 'success'
})

const memoryStatus = computed(() => {
  const percent = metrics.value.memory?.percent || 0
  if (percent > 90) return 'exception'
  if (percent > 70) return 'warning'
  return 'success'
})

const diskStatus = computed(() => {
  const percent = metrics.value.disk?.percent || 0
  if (percent > 90) return 'exception'
  if (percent > 70) return 'warning'
  return 'success'
})

const refreshMetrics = async () => {
  loading.value = true
  try {
    await Promise.all([
      fetchMetrics(),
      fetchAlerts(),
      fetchAlertRules(),
      fetchLogAnalysis(),
    ])
  } catch (error) {
    console.error('刷新失败:', error)
  } finally {
    loading.value = false
  }
}

const fetchMetrics = async () => {
  try {
    const resp = await axios.get('/api/monitoring/metrics')
    metrics.value = resp.data.data || {}
  } catch (error) {
    console.error('获取系统指标失败:', error)
    ElMessage.error('获取系统指标失败')
  }
}

const fetchAlerts = async () => {
  try {
    const resp = await axios.get('/api/monitoring/alerts')
    alerts.value = resp.data.data || []
  } catch (error) {
    console.error('获取告警失败:', error)
  }
}

const fetchAlertRules = async () => {
  try {
    const resp = await axios.get('/api/monitoring/alerts/rules')
    alertRules.value = resp.data.data || []
  } catch (error) {
    console.error('获取告警规则失败:', error)
  }
}

const fetchLogAnalysis = async () => {
  try {
    const resp = await axios.get('/api/monitoring/logs/analysis')
    logAnalysis.value = resp.data.data || {}
  } catch (error) {
    console.error('获取日志分析失败:', error)
  }
}

const formatBytes = (bytes: number) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const formatTime = (timestamp: string) => {
  if (!timestamp) return '-'
  return new Date(timestamp).toLocaleString('zh-CN')
}

onMounted(() => {
  refreshMetrics()
})
</script>

<style scoped>
.monitoring-view {
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
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
  margin-bottom: 20px;
}

.metric-card {
  text-align: center;
}

.metric-header {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-bottom: 12px;
}

.metric-icon {
  font-size: 24px;
}

.metric-title {
  font-weight: 500;
}

.metric-value {
  font-size: 28px;
  font-weight: bold;
  margin-bottom: 8px;
}

.metric-detail {
  color: #666;
  font-size: 14px;
  margin-top: 8px;
}

.metric-sub {
  color: #999;
  font-size: 12px;
  margin-top: 4px;
}

.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.alerts-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.alert-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  border-radius: 4px;
  background: #f5f7fa;
}

.alert-critical {
  background: #fef0f0;
}

.alert-warning {
  background: #fdf6ec;
}

.alert-icon {
  font-size: 16px;
}

.alert-message {
  flex: 1;
}

.alert-time {
  color: #999;
  font-size: 12px;
}

.log-analysis {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.log-stat {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.stat-label {
  color: #666;
}

.stat-value {
  font-weight: 500;
}

.text-warning {
  color: #e6a23c;
}

.text-danger {
  color: #f56c6c;
}
</style>
