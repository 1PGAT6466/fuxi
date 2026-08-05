<template>
  <div class="report-center">
    <header class="page-header">
      <h1>📋 报告中心</h1>
      <el-button type="primary" @click="showGenerateDialog = true">
        <el-icon><Plus /></el-icon>
        生成报告
      </el-button>
    </header>

    <!-- 报告模板 -->
    <el-card class="templates-card">
      <template #header>
        <span>📄 报告模板</span>
      </template>
      <div class="templates-grid">
        <div v-for="template in templates" :key="template.id" class="template-item" @click="generateReport(template)">
          <div class="template-icon">{{ getTemplateIcon(template.category) }}</div>
          <div class="template-info">
            <div class="template-name">{{ template.name }}</div>
            <div class="template-desc">{{ template.description }}</div>
            <el-tag size="small">{{ template.schedule }}</el-tag>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 报告列表 -->
    <el-card class="reports-card">
      <template #header>
        <span>📊 已生成报告</span>
      </template>
      <el-table :data="reports" border v-loading="loading">
        <el-table-column prop="name" label="报告名称" min-width="200" />
        <el-table-column prop="category" label="分类" width="120">
          <template #default="{ row }">
            <el-tag size="small">{{ row.category }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'completed' ? 'success' : 'warning'" size="small">
              {{ row.status === 'completed' ? '已完成' : '生成中' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="生成时间" width="200">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button size="small" @click="viewReport(row)">查看</el-button>
            <el-button size="small" type="danger" @click="deleteReport(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && reports.length === 0" description="暂无报告" />
    </el-card>

    <!-- 报告详情对话框 -->
    <el-dialog v-model="showReportDialog" :title="currentReport?.name" width="800px">
      <div v-if="currentReport" class="report-detail">
        <div class="report-summary">
          <h4>摘要</h4>
          <p>{{ currentReport.content?.summary }}</p>
        </div>
        <div class="report-metrics">
          <h4>关键指标</h4>
          <div class="metrics-list">
            <div v-for="(value, key) in currentReport.content?.metrics" :key="key" class="metric-item">
              <span class="metric-key">{{ key }}</span>
              <span class="metric-value">{{ value }}</span>
            </div>
          </div>
        </div>
        <div v-if="currentReport.content?.recommendations?.length" class="report-recommendations">
          <h4>建议</h4>
          <ul>
            <li v-for="(rec, index) in currentReport.content.recommendations" :key="index">{{ rec }}</li>
          </ul>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import axios from 'axios'

const loading = ref(false)
const templates = ref<any[]>([])
const reports = ref<any[]>([])
const showGenerateDialog = ref(false)
const showReportDialog = ref(false)
const currentReport = ref<any>(null)

const refreshData = async () => {
  loading.value = true
  try {
    await Promise.all([
      fetchTemplates(),
      fetchReports(),
    ])
  } catch (error) {
    console.error('刷新失败:', error)
  } finally {
    loading.value = false
  }
}

const fetchTemplates = async () => {
  try {
    const resp = await axios.get('/api/reports/templates')
    templates.value = resp.data.data || []
  } catch (error) {
    console.error('获取模板失败:', error)
  }
}

const fetchReports = async () => {
  try {
    const resp = await axios.get('/api/reports')
    reports.value = resp.data.data || []
  } catch (error) {
    console.error('获取报告失败:', error)
  }
}

const generateReport = async (template: any) => {
  try {
    await axios.post('/api/reports/generate', { template_id: template.id })
    ElMessage.success(`报告 "${template.name}" 已生成`)
    fetchReports()
  } catch (error) {
    ElMessage.error('生成报告失败')
  }
}

const viewReport = (report: any) => {
  currentReport.value = report
  showReportDialog.value = true
}

const deleteReport = async (report: any) => {
  try {
    await ElMessageBox.confirm('确定要删除这个报告吗？', '确认删除')
    await axios.delete(`/api/reports/${report.id}`)
    ElMessage.success('报告已删除')
    fetchReports()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const getTemplateIcon = (category: string) => {
  const icons: Record<string, string> = {
    system: '🖥️',
    quality: '📊',
    analytics: '📈',
    security: '🔒',
    knowledge: '📚',
  }
  return icons[category] || '📄'
}

const formatTime = (timestamp: string) => {
  if (!timestamp) return '-'
  return new Date(timestamp).toLocaleString('zh-CN')
}

onMounted(() => {
  refreshData()
})
</script>

<style scoped>
.report-center {
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

.templates-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

.template-item {
  display: flex;
  gap: 16px;
  padding: 16px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.template-item:hover {
  border-color: #409eff;
  background: #f5f7fa;
}

.template-icon {
  font-size: 32px;
}

.template-name {
  font-weight: 500;
  margin-bottom: 4px;
}

.template-desc {
  color: #666;
  font-size: 14px;
  margin-bottom: 8px;
}

.reports-card {
  margin-top: 20px;
}

.report-detail {
  max-height: 60vh;
  overflow-y: auto;
}

.report-summary {
  margin-bottom: 20px;
}

.report-summary h4,
.report-metrics h4,
.report-recommendations h4 {
  margin-bottom: 8px;
}

.metrics-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}

.metric-item {
  display: flex;
  justify-content: space-between;
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 4px;
}

.metric-key {
  color: #666;
}

.metric-value {
  font-weight: 500;
}

.report-recommendations ul {
  padding-left: 20px;
}

.report-recommendations li {
  margin-bottom: 8px;
}
</style>
