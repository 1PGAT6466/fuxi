<template>
  <div class="symbols-view">
    <header class="page-header">
      <h1>🏛️ 四象状态</h1>
      <el-button @click="refreshSymbols" :loading="loading">
        <el-icon><Refresh /></el-icon>
        刷新
      </el-button>
    </header>

    <div class="symbols-grid" v-loading="loading">
      <el-card
        v-for="(data, name) in symbols"
        :key="name"
        class="symbol-card"
        :class="`status-${data.status}`"
      >
        <div class="symbol-header">
          <div class="symbol-icon">{{ data.symbol }}</div>
          <div class="symbol-info">
            <h3>{{ data.name }} · {{ data.element }}</h3>
            <el-tag :type="statusType(data.status)" size="small">
              {{ statusLabel(data.status) }}
            </el-tag>
          </div>
        </div>
        <div class="symbol-component">{{ data.component }}</div>
        <div class="symbol-desc">{{ data.description }}</div>
        <div class="symbol-metrics">
          <div class="metric">
            <span class="metric-label">查询数</span>
            <span class="metric-value">{{ data.metrics?.query_count || 0 }}</span>
          </div>
          <div class="metric">
            <span class="metric-label">平均延迟</span>
            <span class="metric-value">{{ data.metrics?.avg_latency_ms || 0 }}ms</span>
          </div>
          <div class="metric">
            <span class="metric-label">成功率</span>
            <span class="metric-value">{{ ((data.metrics?.success_rate || 1) * 100).toFixed(1) }}%</span>
          </div>
        </div>
        <div class="symbol-endpoints">
          <div class="endpoints-title">端点</div>
          <div v-for="ep in data.endpoints_status" :key="ep.endpoint" class="endpoint-item">
            <span class="endpoint-status" :class="`status-${ep.status}`" />
            <span class="endpoint-path">{{ ep.endpoint }}</span>
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
const symbols = ref<Record<string, any>>({})

const refreshSymbols = async () => {
  loading.value = true
  try {
    const resp = await axios.get('/api/symbols/status')
    symbols.value = resp.data.data || {}
  } catch (error) {
    console.error('获取四象状态失败:', error)
    ElMessage.error('获取四象状态失败')
  } finally {
    loading.value = false
  }
}

const statusType = (status: string) => {
  const types: Record<string, string> = {
    online: 'success',
    degraded: 'warning',
    offline: 'danger',
  }
  return types[status] || 'info'
}

const statusLabel = (status: string) => {
  const labels: Record<string, string> = {
    online: '在线',
    degraded: '降级',
    offline: '离线',
  }
  return labels[status] || status
}

onMounted(() => {
  refreshSymbols()
})
</script>

<style scoped>
.symbols-view {
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

.symbols-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
}

.symbol-card {
  transition: all 0.3s;
}

.symbol-card.status-online {
  border-left: 4px solid #67c23a;
}

.symbol-card.status-degraded {
  border-left: 4px solid #e6a23c;
}

.symbol-card.status-offline {
  border-left: 4px solid #f56c6c;
}

.symbol-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 12px;
}

.symbol-icon {
  font-size: 48px;
}

.symbol-info h3 {
  margin: 0 0 8px 0;
  font-size: 18px;
}

.symbol-component {
  font-weight: 500;
  color: #409eff;
  margin-bottom: 8px;
}

.symbol-desc {
  color: #666;
  font-size: 14px;
  margin-bottom: 16px;
}

.symbol-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.metric {
  text-align: center;
  padding: 8px;
  background: #f5f7fa;
  border-radius: 4px;
}

.metric-label {
  display: block;
  font-size: 12px;
  color: #999;
  margin-bottom: 4px;
}

.metric-value {
  font-size: 16px;
  font-weight: bold;
}

.symbol-endpoints {
  border-top: 1px solid #ebeef5;
  padding-top: 12px;
}

.endpoints-title {
  font-size: 12px;
  color: #999;
  margin-bottom: 8px;
}

.endpoint-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
}

.endpoint-status {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.endpoint-status.status-online,
.endpoint-status.status-healthy {
  background: #67c23a;
}

.endpoint-status.status-degraded {
  background: #e6a23c;
}

.endpoint-status.status-offline {
  background: #f56c6c;
}

.endpoint-path {
  font-family: monospace;
  font-size: 13px;
}
</style>
