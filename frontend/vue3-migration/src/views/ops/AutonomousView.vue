<template>
  <div class="autonomous-page">
    <header class="page-header">
      <h1>🤖 自主运行中心</h1>
      <p class="subtitle">伏羲自主运行、自检、自修复管理</p>
    </header>

    <!-- 全维度自检状态概览 -->
    <section class="status-overview">
      <div class="status-card" :class="fullCheckStatus.color">
        <div class="status-icon">🔍</div>
        <div class="status-info">
          <h3>全维度自检</h3>
          <p class="status-text">{{ fullCheckStatus.text }}</p>
          <p class="status-detail">{{ fullCheckStatus.detail }}</p>
        </div>
      </div>
    </section>

    <!-- 状态概览 -->
    <section class="status-overview">
      <div class="status-card" :class="schedulerStatus.color">
        <div class="status-icon">⏰</div>
        <div class="status-info">
          <h3>调度器</h3>
          <p class="status-text">{{ schedulerStatus.text }}</p>
          <p class="status-detail">{{ schedulerStatus.detail }}</p>
        </div>
      </div>
      <div class="status-card" :class="monitorStatus.color">
        <div class="status-icon">📊</div>
        <div class="status-info">
          <h3>健康监控</h3>
          <p class="status-text">{{ monitorStatus.text }}</p>
          <p class="status-detail">{{ monitorStatus.detail }}</p>
        </div>
      </div>
      <div class="status-card" :class="healerStatus.color">
        <div class="status-icon">🔧</div>
        <div class="status-info">
          <h3>自修复引擎</h3>
          <p class="status-text">{{ healerStatus.text }}</p>
          <p class="status-detail">{{ healerStatus.detail }}</p>
        </div>
      </div>
      <div class="status-card" :class="syncStatus.color">
        <div class="status-icon">🔄</div>
        <div class="status-info">
          <h3>数据同步</h3>
          <p class="status-text">{{ syncStatus.text }}</p>
          <p class="status-detail">{{ syncStatus.detail }}</p>
        </div>
      </div>
    </section>

    <!-- 调度任务管理 -->
    <section class="section">
      <div class="section-header">
        <h2>⏰ 调度任务</h2>
        <button class="btn btn-primary" @click="refreshJobs" :disabled="loading">刷新</button>
      </div>
      <div v-if="error" class="error-message">{{ error }}</div>
      <div class="jobs-grid">
        <div v-for="job in jobs" :key="job.id" class="job-card" :class="job.status">
          <div class="job-header">
            <span class="job-icon">{{ job.icon }}</span>
            <span class="job-name">{{ job.name }}</span>
            <span class="job-status-badge" :class="job.status">{{ job.statusText }}</span>
          </div>
          <p class="job-description">{{ job.description }}</p>
          <div class="job-meta">
            <span>优先级: {{ job.priority }}</span>
            <span>调度: {{ job.schedule }}</span>
            <span v-if="job.lastRun">上次: {{ formatTime(job.lastRun) }}</span>
          </div>
          <div class="job-actions">
            <button class="btn btn-small" @click="runJob(job.id)" :disabled="loading">手动执行</button>
            <button class="btn btn-small btn-secondary" @click="viewJobHistory(job.id)">历史</button>
          </div>
        </div>
      </div>
    </section>

    <!-- 系统健康指标 -->
    <section class="section">
      <div class="section-header">
        <h2>📊 系统健康指标</h2>
        <button class="btn btn-primary" @click="refreshMetrics" :disabled="loading">刷新</button>
      </div>
      <div class="metrics-grid">
        <div class="metric-card">
          <h4>CPU 使用率</h4>
          <div class="metric-bar">
            <div class="metric-fill" :style="{ width: metrics.cpu + '%' }" :class="getMetricClass(metrics.cpu)"></div>
          </div>
          <span class="metric-value">{{ metrics.cpu }}%</span>
        </div>
        <div class="metric-card">
          <h4>内存使用率</h4>
          <div class="metric-bar">
            <div class="metric-fill" :style="{ width: metrics.memory + '%' }" :class="getMetricClass(metrics.memory)"></div>
          </div>
          <span class="metric-value">{{ metrics.memory }}%</span>
        </div>
        <div class="metric-card">
          <h4>磁盘使用率</h4>
          <div class="metric-bar">
            <div class="metric-fill" :style="{ width: metrics.disk + '%' }" :class="getMetricClass(metrics.disk)"></div>
          </div>
          <span class="metric-value">{{ metrics.disk }}%</span>
        </div>
        <div class="metric-card">
          <h4>API 响应时间</h4>
          <div class="metric-value-large">{{ metrics.apiLatency }}ms</div>
          <span class="metric-label">平均</span>
        </div>
      </div>
    </section>

    <!-- 自修复动作 -->
    <section class="section">
      <div class="section-header">
        <h2>🔧 自修复动作</h2>
        <button class="btn btn-primary" @click="refreshActions" :disabled="loading">刷新</button>
      </div>
      <div class="actions-list">
        <div v-for="action in healerActions" :key="action.id" class="action-card">
          <div class="action-header">
            <span class="action-icon">{{ action.icon }}</span>
            <span class="action-name">{{ action.name }}</span>
            <span class="action-status" :class="action.status">{{ action.statusText }}</span>
          </div>
          <p class="action-description">{{ action.description }}</p>
          <div class="action-meta">
            <span>风险等级: {{ action.riskLevel }}</span>
            <span>触发条件: {{ action.trigger }}</span>
          </div>
          <div class="action-actions">
            <button class="btn btn-small btn-warning" @click="runAction(action.id)" :disabled="loading">执行修复</button>
            <button class="btn btn-small btn-secondary" @click="viewActionHistory(action.id)">历史</button>
          </div>
        </div>
      </div>
    </section>

    <!-- 最近告警 -->
    <section class="section">
      <div class="section-header">
        <h2>🔔 最近告警</h2>
        <button class="btn btn-primary" @click="refreshAlerts" :disabled="loading">刷新</button>
      </div>
      <div class="alerts-list">
        <div v-for="alert in alerts" :key="alert.id" class="alert-card" :class="alert.level">
          <div class="alert-header">
            <span class="alert-icon">{{ alert.icon }}</span>
            <span class="alert-title">{{ alert.title }}</span>
            <span class="alert-time">{{ formatTime(alert.time) }}</span>
          </div>
          <p class="alert-message">{{ alert.message }}</p>
          <div class="alert-actions">
            <button class="btn btn-small" @click="handleAlert(alert.id)">处理</button>
            <button class="btn btn-small btn-secondary" @click="dismissAlert(alert.id)">忽略</button>
          </div>
        </div>
        <div v-if="alerts.length === 0" class="empty-state">
          <p>✅ 暂无告警</p>
        </div>
      </div>
    </section>

    <!-- 全维度自检面板 -->
    <section class="section">
      <div class="section-header">
        <h2>🔍 全维度自检</h2>
        <div class="check-controls">
          <select v-model="selectedCheckType" class="check-type-select">
            <option value="quick">快速自检</option>
            <option value="full">完整自检</option>
            <option value="deep">深度自检</option>
          </select>
          <button class="btn btn-primary" @click="runFullCheck" :disabled="fullCheckRunning || loading">
            {{ fullCheckRunning ? '运行中...' : '运行自检' }}
          </button>
          <button class="btn btn-secondary" @click="refreshFullCheckReport" :disabled="loading">刷新报告</button>
          <button class="btn btn-secondary" @click="refreshFullCheckHistory" :disabled="loading">历史记录</button>
        </div>
      </div>

      <!-- 自检状态 -->
      <div class="check-status-bar">
        <div class="status-item">
          <span class="status-label">状态:</span>
          <span class="status-value" :class="fullCheckStatus.color">{{ fullCheckStatus.text }}</span>
        </div>
        <div class="status-item">
          <span class="status-label">详情:</span>
          <span class="status-value">{{ fullCheckStatus.detail }}</span>
        </div>
      </div>

      <!-- 自检报告 -->
      <div v-if="fullCheckReport" class="check-report">
        <div class="report-header">
          <h3>📊 自检报告</h3>
          <div class="report-meta">
            <span class="report-score" :class="formatCheckScore(fullCheckReport.score).color">
              分数: {{ fullCheckReport.score }} ({{ formatCheckScore(fullCheckReport.score).text }})
            </span>
            <span class="report-time">
              时间: {{ fullCheckReport.start_time ? new Date(fullCheckReport.start_time).toLocaleString() : '-' }}
            </span>
            <span class="report-duration">
              耗时: {{ fullCheckReport.duration || 0 }}秒
            </span>
          </div>
        </div>

        <!-- 检查结果统计 -->
        <div class="report-summary">
          <div class="summary-item">
            <span class="summary-label">总检查项:</span>
            <span class="summary-value">{{ fullCheckReport.summary?.total || 0 }}</span>
          </div>
          <div class="summary-item pass">
            <span class="summary-label">通过:</span>
            <span class="summary-value">{{ fullCheckReport.summary?.pass || 0 }}</span>
          </div>
          <div class="summary-item warning">
            <span class="summary-label">警告:</span>
            <span class="summary-value">{{ fullCheckReport.summary?.warning || 0 }}</span>
          </div>
          <div class="summary-item fail">
            <span class="summary-label">失败:</span>
            <span class="summary-value">{{ fullCheckReport.summary?.fail || 0 }}</span>
          </div>
          <div class="summary-item error">
            <span class="summary-label">错误:</span>
            <span class="summary-value">{{ fullCheckReport.summary?.error || 0 }}</span>
          </div>
        </div>

        <!-- 建议 -->
        <div v-if="fullCheckReport.recommendations && fullCheckReport.recommendations.length > 0" class="report-recommendations">
          <h4>💡 建议</h4>
          <ul>
            <li v-for="(rec, index) in fullCheckReport.recommendations" :key="index">
              {{ rec }}
            </li>
          </ul>
        </div>

        <!-- 检查结果详情 -->
        <div v-if="fullCheckReport.results && fullCheckReport.results.length > 0" class="report-details">
          <h4>📋 检查详情</h4>
          <div class="details-grid">
            <div v-for="result in fullCheckReport.results" :key="result.id" class="detail-card" :class="result.status">
              <div class="detail-header">
                <span class="detail-name">{{ result.name }}</span>
                <span class="detail-status" :class="result.status">
                  {{ result.status === 'pass' ? '✅' : result.status === 'warning' ? '⚠️' : result.status === 'fail' ? '❌' : '❓' }}
                </span>
              </div>
              <p class="detail-message">{{ result.message }}</p>
              <div class="detail-meta">
                <span>类别: {{ result.category }}</span>
                <span>时间: {{ result.timestamp ? new Date(result.timestamp).toLocaleTimeString() : '-' }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 自检历史 -->
      <div v-if="fullCheckHistory.length > 0" class="check-history">
        <h4>📜 自检历史</h4>
        <div class="history-list">
          <div v-for="history in fullCheckHistory" :key="history.check_id" class="history-item">
            <div class="history-header">
              <span class="history-id">{{ history.check_id }}</span>
              <span class="history-type">{{ history.check_type }}</span>
              <span class="history-score" :class="formatCheckScore(history.score).color">
                {{ history.score }}分
              </span>
            </div>
            <div class="history-meta">
              <span>状态: {{ history.status }}</span>
              <span>耗时: {{ history.duration || 0 }}秒</span>
              <span>时间: {{ history.start_time ? new Date(history.start_time).toLocaleString() : '-' }}</span>
            </div>
            <div class="history-actions">
              <button class="btn btn-small" @click="viewFullCheckDetail(history.check_id)">查看详情</button>
            </div>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-if="!fullCheckReport && fullCheckHistory.length === 0" class="empty-state">
        <p>🔍 暂无自检记录，点击"运行自检"开始</p>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'

// 状态数据
const schedulerStatus = ref({ text: '加载中', detail: '...', color: 'success' })
const monitorStatus = ref({ text: '加载中', detail: '...', color: 'success' })
const healerStatus = ref({ text: '加载中', detail: '...', color: 'success' })
const syncStatus = ref({ text: '加载中', detail: '...', color: 'success' })
const fullCheckStatus = ref({ text: '就绪', detail: '点击运行全维度自检', color: 'success' })

const loading = ref(false)
const error = ref('')

// 调度任务
const jobs = ref<any[]>([])

// 系统指标
const metrics = ref({ cpu: 0, memory: 0, disk: 0, apiLatency: 0 })

// 自修复动作
const healerActions = ref<any[]>([])

// 告警
const alerts = ref<any[]>([])

// 全维度自检
const fullCheckRunning = ref(false)
const fullCheckReport = ref<any>(null)
const fullCheckHistory = ref<any[]>([])
const selectedCheckType = ref('full')

// 获取任务图标
const getJobIcon = (jobId: string) => {
  const icons: Record<string, string> = {
    'health_check': '💓',
    'knowledge_sync': '📚',
    'log_cleanup': '📝',
    'vector_index_rebuild': '🔍',
    'backup_database': '💾'
  }
  return icons[jobId] || '⚙️'
}

// 格式化时间
const formatTime = (time: Date | null) => {
  if (!time) return '-'
  const now = new Date()
  const diff = now.getTime() - time.getTime()
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  return `${Math.floor(diff / 86400000)}天前`
}

// 获取指标颜色
const getMetricClass = (value: number) => {
  if (value < 60) return 'good'
  if (value < 80) return 'warning'
  return 'danger'
}

// 刷新调度任务
const refreshJobs = async () => {
  loading.value = true
  error.value = ''
  try {
    const resp = await axios.get('/api/scheduler/jobs')
    const data = resp.data
    if (data.status === 'success' && data.data) {
      // API 返回 data 数组
      const jobList = Array.isArray(data.data) ? data.data : []
      jobs.value = jobList.map((job: any) => ({
        id: job.id,
        name: job.name,
        icon: getJobIcon(job.id),
        description: job.description,
        status: job.status === 'active' ? 'running' : job.status === 'error' ? 'error' : 'idle',
        statusText: job.status === 'active' ? '运行中' : job.status === 'error' ? '异常' : '空闲',
        priority: job.priority === 0 ? '高' : job.priority === 1 ? '中' : '低',
        schedule: job.schedule || '-',
        lastRun: job.last_run ? new Date(job.last_run) : null
      }))
      schedulerStatus.value = {
        text: '运行中',
        detail: `${jobList.length}个任务已注册`,
        color: 'success'
      }
    }
  } catch (e: any) {
    error.value = `获取任务列表失败: ${e.message}`
    schedulerStatus.value = { text: '异常', detail: e.message, color: 'error' }
  } finally {
    loading.value = false
  }
}

// 手动执行任务
const runJob = async (jobId: string) => {
  try {
    loading.value = true
    await axios.post(`/api/scheduler/jobs/${jobId}/run`)
    alert(`任务 ${jobId} 已触发执行`)
    await refreshJobs()
  } catch (e: any) {
    alert(`执行失败: ${e.message}`)
  } finally {
    loading.value = false
  }
}

// 查看任务历史
const viewJobHistory = async (jobId: string) => {
  try {
    const resp = await axios.get(`/api/scheduler/jobs/${jobId}/history`)
    console.log('任务历史:', resp.data)
    alert(`任务历史: ${JSON.stringify(resp.data.data?.history?.slice(0, 3) || [], null, 2)}`)
  } catch (e: any) {
    alert(`获取历史失败: ${e.message}`)
  }
}

// 刷新系统指标
const refreshMetrics = async () => {
  try {
    const resp = await axios.get('/api/monitoring/metrics')
    const data = resp.data.data
    if (data) {
      metrics.value = {
        cpu: data.cpu?.percent || 0,
        memory: data.memory?.percent || 0,
        disk: data.disk?.percent || 0,
        apiLatency: data.api?.avg_latency_ms || 0
      }
      monitorStatus.value = {
        text: '监控中',
        detail: `最近检查: ${new Date().toLocaleTimeString()}`,
        color: 'success'
      }
    }
  } catch (e: any) {
    console.error('获取指标失败:', e)
    monitorStatus.value = { text: '异常', detail: e.message, color: 'error' }
  }
}

// 刷新修复动作
const refreshActions = async () => {
  try {
    const resp = await axios.get('/api/scheduler/healer/actions')
    const data = resp.data
    if (data.status === 'success' && data.data) {
      const actionList = Array.isArray(data.data) ? data.data : []
      healerActions.value = actionList.map((action: any) => ({
        id: action.id,
        name: action.name,
        icon: '🔧',
        description: action.description,
        status: action.enabled ? 'ready' : 'disabled',
        statusText: action.enabled ? '就绪' : '已禁用',
        riskLevel: action.risk_level === 'low' ? '低' : action.risk_level === 'medium' ? '中' : '高',
        trigger: action.alert_rules?.join(', ') || '-'
      }))
      healerStatus.value = {
        text: '待命',
        detail: `${actionList.length}个修复动作可用`,
        color: 'success'
      }
    }
  } catch (e: any) {
    console.error('获取修复动作失败:', e)
    healerStatus.value = { text: '异常', detail: e.message, color: 'error' }
  }
}

// 执行修复动作
const runAction = async (actionId: string) => {
  if (!confirm(`确定要执行修复动作 "${actionId}" 吗？`)) return
  try {
    loading.value = true
    await axios.post(`/api/scheduler/healer/actions/${actionId}/run`)
    alert(`修复动作 ${actionId} 已触发执行`)
  } catch (e: any) {
    alert(`执行失败: ${e.message}`)
  } finally {
    loading.value = false
  }
}

// 查看修复历史
const viewActionHistory = async (actionId: string) => {
  try {
    const resp = await axios.get('/api/scheduler/healer/actions/history')
    console.log('修复历史:', resp.data)
    alert(`修复历史: ${JSON.stringify(resp.data.data?.history?.slice(0, 3) || [], null, 2)}`)
  } catch (e: any) {
    alert(`获取历史失败: ${e.message}`)
  }
}

// 刷新告警
const refreshAlerts = async () => {
  try {
    const resp = await axios.get('/api/monitoring/alerts')
    const data = resp.data
    if (data.status === 'success' && data.data) {
      const alertList = Array.isArray(data.data) ? data.data : []
      alerts.value = alertList.map((alert: any, index: number) => ({
        id: index,
        level: alert.level || 'info',
        icon: alert.level === 'error' ? '❌' : alert.level === 'warning' ? '⚠️' : 'ℹ️',
        title: alert.title || alert.message?.substring(0, 50) || '告警',
        message: alert.message || '',
        time: alert.timestamp ? new Date(alert.timestamp) : new Date()
      }))
    }
  } catch (e: any) {
    console.error('获取告警失败:', e)
  }
}

// 处理告警
const handleAlert = (alertId: number) => {
  alert('处理告警功能开发中')
}

// 忽略告警
const dismissAlert = (alertId: number) => {
  alerts.value = alerts.value.filter(a => a.id !== alertId)
}

// ============ 全维度自检 ============

// 运行全维度自检
const runFullCheck = async () => {
  if (fullCheckRunning.value) {
    alert('自检任务正在运行，请等待完成')
    return
  }
  
  if (!confirm(`确定要运行 ${selectedCheckType.value} 自检吗？`)) return
  
  try {
    fullCheckRunning.value = true
    fullCheckStatus.value = { text: '运行中', detail: '正在执行全维度自检...', color: 'warning' }
    
    const resp = await axios.post(`/api/ops/full-check/run?check_type=${selectedCheckType.value}`)
    const data = resp.data
    
    if (data.status === 'started') {
      alert(`自检已启动: ${data.check_id}`)
      // 轮询检查状态
      await pollFullCheckStatus(data.check_id)
    } else {
      alert(`启动失败: ${data.message}`)
    }
  } catch (e: any) {
    alert(`运行自检失败: ${e.message}`)
    fullCheckStatus.value = { text: '异常', detail: e.message, color: 'error' }
  } finally {
    fullCheckRunning.value = false
  }
}

// 轮询自检状态
const pollFullCheckStatus = async (checkId: string) => {
  const maxAttempts = 60 // 最多轮询 60 次（5 分钟）
  let attempts = 0
  
  while (attempts < maxAttempts) {
    try {
      await new Promise(resolve => setTimeout(resolve, 5000)) // 等待 5 秒
      
      const resp = await axios.get('/api/ops/full-check/status')
      const data = resp.data
      
      if (data.status === 'idle') {
        // 自检完成，获取报告
        await refreshFullCheckReport()
        fullCheckStatus.value = { text: '已完成', detail: '全维度自检已完成', color: 'success' }
        return
      } else if (data.status === 'running') {
        fullCheckStatus.value = { 
          text: '运行中', 
          detail: `进度: ${data.progress || 0} 项`, 
          color: 'warning' 
        }
      }
    } catch (e: any) {
      console.error('轮询自检状态失败:', e)
    }
    
    attempts++
  }
  
  fullCheckStatus.value = { text: '超时', detail: '自检任务超时', color: 'error' }
}

// 刷新自检报告
const refreshFullCheckReport = async () => {
  try {
    const resp = await axios.get('/api/ops/full-check/report')
    const data = resp.data
    
    if (data.status === 'success' && data.data) {
      fullCheckReport.value = data.data
      fullCheckStatus.value = { 
        text: '已完成', 
        detail: `分数: ${data.data.score || 0}`, 
        color: data.data.score >= 80 ? 'success' : data.data.score >= 60 ? 'warning' : 'error'
      }
    }
  } catch (e: any) {
    console.error('获取自检报告失败:', e)
  }
}

// 刷新自检历史
const refreshFullCheckHistory = async () => {
  try {
    const resp = await axios.get('/api/ops/full-check/history?limit=10')
    const data = resp.data
    
    if (data.status === 'success' && data.data) {
      fullCheckHistory.value = data.data
    }
  } catch (e: any) {
    console.error('获取自检历史失败:', e)
  }
}

// 查看自检详情
const viewFullCheckDetail = async (checkId: string) => {
  try {
    const resp = await axios.get(`/api/ops/full-check/report?check_id=${checkId}`)
    const data = resp.data
    
    if (data.status === 'success' && data.data) {
      alert(`自检详情:\n${JSON.stringify(data.data, null, 2)}`)
    }
  } catch (e: any) {
    alert(`获取详情失败: ${e.message}`)
  }
}

// 格式化自检分数
const formatCheckScore = (score: number) => {
  if (score >= 90) return { text: '优秀', color: 'success' }
  if (score >= 80) return { text: '良好', color: 'success' }
  if (score >= 60) return { text: '一般', color: 'warning' }
  return { text: '较差', color: 'error' }
}

onMounted(() => {
  refreshJobs()
  refreshMetrics()
  refreshActions()
  refreshAlerts()
  refreshFullCheckReport()
  refreshFullCheckHistory()
})
</script>

<style scoped>
.autonomous-page {
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 32px;
}

.page-header h1 {
  font-size: 28px;
  color: #1a1a1a;
  margin: 0 0 8px 0;
}

.subtitle {
  color: #666;
  margin: 0;
}

.error-message {
  background: #fff2f0;
  border: 1px solid #ffccc7;
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 16px;
  color: #ff4d4f;
}

/* 状态概览 */
.status-overview {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 16px;
  margin-bottom: 32px;
}

.status-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  border-left: 4px solid #ccc;
}

.status-card.success {
  border-left-color: #52c41a;
}

.status-card.warning {
  border-left-color: #faad14;
}

.status-card.error {
  border-left-color: #ff4d4f;
}

.status-icon {
  font-size: 32px;
}

.status-info h3 {
  margin: 0 0 4px 0;
  font-size: 16px;
  color: #333;
}

.status-text {
  margin: 0;
  font-weight: 600;
  color: #1a1a1a;
}

.status-detail {
  margin: 4px 0 0 0;
  font-size: 12px;
  color: #888;
}

/* 区块 */
.section {
  background: white;
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.section-header h2 {
  margin: 0;
  font-size: 20px;
  color: #1a1a1a;
}

/* 任务网格 */
.jobs-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 16px;
}

.job-card {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 16px;
  border: 1px solid #e8e8e8;
}

.job-card.running {
  border-color: #52c41a;
  background: #f6ffed;
}

.job-card.error {
  border-color: #ff4d4f;
  background: #fff2f0;
}

.job-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.job-icon {
  font-size: 20px;
}

.job-name {
  font-weight: 600;
  flex: 1;
}

.job-status-badge {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 10px;
  background: #f0f0f0;
}

.job-status-badge.running {
  background: #b7eb8f;
  color: #135200;
}

.job-status-badge.idle {
  background: #f0f0f0;
  color: #666;
}

.job-status-badge.error {
  background: #ffccc7;
  color: #cf1322;
}

.job-description {
  margin: 0 0 8px 0;
  font-size: 14px;
  color: #666;
}

.job-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #888;
  margin-bottom: 12px;
}

.job-actions {
  display: flex;
  gap: 8px;
}

/* 指标网格 */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
}

.metric-card {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 16px;
  text-align: center;
}

.metric-card h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  color: #666;
}

.metric-bar {
  height: 8px;
  background: #e8e8e8;
  border-radius: 4px;
  margin-bottom: 8px;
  overflow: hidden;
}

.metric-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s;
}

.metric-fill.good {
  background: #52c41a;
}

.metric-fill.warning {
  background: #faad14;
}

.metric-fill.danger {
  background: #ff4d4f;
}

.metric-value {
  font-size: 24px;
  font-weight: 600;
  color: #1a1a1a;
}

.metric-value-large {
  font-size: 32px;
  font-weight: 600;
  color: #1a1a1a;
}

.metric-label {
  font-size: 12px;
  color: #888;
}

/* 修复动作列表 */
.actions-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 16px;
}

.action-card {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 16px;
  border: 1px solid #e8e8e8;
}

.action-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.action-icon {
  font-size: 20px;
}

.action-name {
  font-weight: 600;
  flex: 1;
}

.action-status {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 10px;
  background: #f0f0f0;
}

.action-status.ready {
  background: #b7eb8f;
  color: #135200;
}

.action-status.disabled {
  background: #f0f0f0;
  color: #999;
}

.action-description {
  margin: 0 0 8px 0;
  font-size: 14px;
  color: #666;
}

.action-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #888;
  margin-bottom: 12px;
}

.action-actions {
  display: flex;
  gap: 8px;
}

/* 告警列表 */
.alerts-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.alert-card {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 16px;
  border: 1px solid #e8e8e8;
}

.alert-card.warning {
  border-color: #faad14;
  background: #fffbe6;
}

.alert-card.error {
  border-color: #ff4d4f;
  background: #fff2f0;
}

.alert-card.info {
  border-color: #1890ff;
  background: #e6f7ff;
}

.alert-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.alert-icon {
  font-size: 20px;
}

.alert-title {
  font-weight: 600;
  flex: 1;
}

.alert-time {
  font-size: 12px;
  color: #888;
}

.alert-message {
  margin: 0 0 12px 0;
  font-size: 14px;
  color: #666;
}

.alert-actions {
  display: flex;
  gap: 8px;
}

.empty-state {
  text-align: center;
  padding: 40px;
  color: #888;
}

/* 按钮 */
.btn {
  padding: 8px 16px;
  border-radius: 6px;
  border: none;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-primary {
  background: #1890ff;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #40a9ff;
}

.btn-secondary {
  background: #f0f0f0;
  color: #666;
}

.btn-secondary:hover:not(:disabled) {
  background: #d9d9d9;
}

.btn-warning {
  background: #faad14;
  color: white;
}

.btn-warning:hover:not(:disabled) {
  background: #ffc53d;
}

.btn-small {
  padding: 4px 12px;
  font-size: 12px;
}

/* ============ 全维度自检样式 ============ */

.check-controls {
  display: flex;
  gap: 12px;
  align-items: center;
}

.check-type-select {
  padding: 8px 12px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  font-size: 14px;
  background: white;
}

.check-status-bar {
  display: flex;
  gap: 24px;
  padding: 12px 16px;
  background: #f8f9fa;
  border-radius: 8px;
  margin-bottom: 20px;
}

.status-item {
  display: flex;
  gap: 8px;
  align-items: center;
}

.status-label {
  font-size: 14px;
  color: #666;
}

.status-value {
  font-weight: 600;
  color: #1a1a1a;
}

.status-value.success {
  color: #52c41a;
}

.status-value.warning {
  color: #faad14;
}

.status-value.error {
  color: #ff4d4f;
}

.check-report {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
}

.report-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.report-header h3 {
  margin: 0;
  font-size: 18px;
  color: #1a1a1a;
}

.report-meta {
  display: flex;
  gap: 16px;
  font-size: 14px;
  color: #666;
}

.report-score {
  font-weight: 600;
  padding: 4px 12px;
  border-radius: 16px;
  background: #f0f0f0;
}

.report-score.success {
  background: #b7eb8f;
  color: #135200;
}

.report-score.warning {
  background: #ffe58f;
  color: #614700;
}

.report-score.error {
  background: #ffccc7;
  color: #cf1322;
}

.report-summary {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.summary-item {
  text-align: center;
  padding: 12px;
  background: white;
  border-radius: 8px;
}

.summary-label {
  display: block;
  font-size: 12px;
  color: #666;
  margin-bottom: 4px;
}

.summary-value {
  display: block;
  font-size: 24px;
  font-weight: 600;
  color: #1a1a1a;
}

.summary-item.pass .summary-value {
  color: #52c41a;
}

.summary-item.warning .summary-value {
  color: #faad14;
}

.summary-item.fail .summary-value {
  color: #ff4d4f;
}

.summary-item.error .summary-value {
  color: #ff4d4f;
}

.report-recommendations {
  margin-bottom: 16px;
}

.report-recommendations h4 {
  margin: 0 0 12px 0;
  font-size: 16px;
  color: #1a1a1a;
}

.report-recommendations ul {
  margin: 0;
  padding-left: 20px;
}

.report-recommendations li {
  margin-bottom: 8px;
  font-size: 14px;
  color: #666;
}

.report-details h4 {
  margin: 0 0 12px 0;
  font-size: 16px;
  color: #1a1a1a;
}

.details-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 12px;
}

.detail-card {
  background: white;
  border-radius: 8px;
  padding: 16px;
  border: 1px solid #e8e8e8;
}

.detail-card.pass {
  border-color: #b7eb8f;
}

.detail-card.warning {
  border-color: #ffe58f;
}

.detail-card.fail {
  border-color: #ffccc7;
}

.detail-card.error {
  border-color: #ffccc7;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.detail-name {
  font-weight: 600;
  color: #1a1a1a;
}

.detail-status {
  font-size: 20px;
}

.detail-message {
  margin: 0 0 8px 0;
  font-size: 14px;
  color: #666;
}

.detail-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #888;
}

.check-history h4 {
  margin: 0 0 12px 0;
  font-size: 16px;
  color: #1a1a1a;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.history-item {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 16px;
  border: 1px solid #e8e8e8;
}

.history-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.history-id {
  font-weight: 600;
  color: #1a1a1a;
  font-family: monospace;
}

.history-type {
  padding: 2px 8px;
  background: #e6f7ff;
  border-radius: 4px;
  font-size: 12px;
  color: #1890ff;
}

.history-score {
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 10px;
  background: #f0f0f0;
}

.history-score.success {
  background: #b7eb8f;
  color: #135200;
}

.history-score.warning {
  background: #ffe58f;
  color: #614700;
}

.history-score.error {
  background: #ffccc7;
  color: #cf1322;
}

.history-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #888;
  margin-bottom: 8px;
}

.history-actions {
  display: flex;
  gap: 8px;
}
</style>
