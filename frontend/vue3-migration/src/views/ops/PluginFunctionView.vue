<template>
  <div class="plugin-function">
    <h2 class="page-title">
      <span class="plugin-icon">{{ pluginInfo?.icon || '🧩' }}</span>
      {{ pluginInfo?.display_name || pluginInfo?.name || '插件功能' }}
    </h2>
    <p class="page-desc">{{ pluginInfo?.description }}</p>

    <div v-if="loading" class="loading-state">
      <el-skeleton :rows="5" animated />
    </div>

    <div v-else-if="pluginInfo" class="plugin-content">
      <!-- 插件信息卡片 -->
      <el-card class="info-card">
        <template #header>
          <div class="card-header">
            <span>插件信息</span>
            <el-tag :type="statusColor(pluginInfo.status)">
              {{ statusLabel(pluginInfo.status) }}
            </el-tag>
          </div>
        </template>
        <el-descriptions :column="3" border>
          <el-descriptions-item label="名称">{{ pluginInfo.name }}</el-descriptions-item>
          <el-descriptions-item label="版本">v{{ pluginInfo.version }}</el-descriptions-item>
          <el-descriptions-item label="类型">{{ pluginInfo.type }}</el-descriptions-item>
          <el-descriptions-item label="作者">{{ pluginInfo.author || '未知' }}</el-descriptions-item>
          <el-descriptions-item label="安装时间">{{ formatTime(pluginInfo.installed_at) }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ formatTime(pluginInfo.updated_at) }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 功能区域 -->
      <el-card class="function-card">
        <template #header>
          <div class="card-header">
            <span>可用功能</span>
          </div>
        </template>

        <div v-if="pluginInfo.manifest?.routes?.length" class="function-list">
          <div
            v-for="route in pluginInfo.manifest.routes"
            :key="route.path"
            class="function-item"
            @click="selectFunction(route)"
          >
            <div class="function-header">
              <el-tag size="small" :type="methodColor(route.method)">{{ route.method }}</el-tag>
              <span class="function-path">{{ route.path }}</span>
            </div>
            <div class="function-desc">{{ route.description }}</div>
          </div>
        </div>
        <el-empty v-else description="暂无可用功能" />
      </el-card>

      <!-- 功能执行区域 -->
      <el-card v-if="selectedFunction" class="execute-card">
        <template #header>
          <div class="card-header">
            <span>执行功能: {{ selectedFunction.description }}</span>
          </div>
        </template>

        <el-form label-width="100px" class="execute-form">
          <el-form-item label="API 路径">
            <el-input v-model="selectedFunction.path" disabled />
          </el-form-item>
          <el-form-item label="请求方法">
            <el-tag>{{ selectedFunction.method }}</el-tag>
          </el-form-item>

          <!-- 文本分析器专用表单 -->
          <template v-if="pluginName === 'text-analyzer'">
            <el-form-item label="输入文本">
              <el-input
                v-model="inputText"
                type="textarea"
                :rows="6"
                placeholder="请输入要分析的文本..."
              />
            </el-form-item>
            <el-form-item v-if="selectedFunction.path.includes('keywords')" label="关键词数量">
              <el-input-number v-model="topN" :min="1" :max="50" />
            </el-form-item>
          </template>

          <!-- 数据导出器专用表单 -->
          <template v-else-if="pluginName === 'data-exporter'">
            <el-form-item label="导出格式">
              <el-select v-model="exportFormat">
                <el-option label="CSV" value="csv" />
                <el-option label="JSON" value="json" />
                <el-option label="Markdown" value="markdown" />
                <el-option label="Excel" value="excel" />
              </el-select>
            </el-form-item>
            <el-form-item label="数据 (JSON)">
              <el-input
                v-model="inputData"
                type="textarea"
                :rows="6"
                placeholder='[{"name": "张三", "age": 25}, {"name": "李四", "age": 30}]'
              />
            </el-form-item>
          </template>

          <!-- 通用表单 -->
          <template v-else>
            <el-form-item label="请求体 (JSON)" v-if="selectedFunction.method === 'POST'">
              <el-input
                v-model="requestBody"
                type="textarea"
                :rows="6"
                placeholder='{"key": "value"}'
              />
            </el-form-item>
          </template>

          <el-form-item>
            <el-button type="primary" @click="executeFunction" :loading="executing">
              执行
            </el-button>
            <el-button @click="clearResult">清空结果</el-button>
          </el-form-item>
        </el-form>

        <!-- 执行结果 -->
        <div v-if="executeResult" class="execute-result">
          <div class="result-header">
            <h4>执行结果</h4>
            <el-tag :type="executeResult.success ? 'success' : 'danger'">
              {{ executeResult.success ? '成功' : '失败' }}
            </el-tag>
            <span class="result-time">{{ executeResult.time }}ms</span>
          </div>
          
          <!-- 文本分析结果可视化 -->
          <div v-if="pluginName === 'text-analyzer' && executeResult.success" class="analysis-visual">
            <el-row :gutter="20">
              <el-col :span="6">
                <el-statistic title="字符数" :value="executeResult.data?.char_count || 0" />
              </el-col>
              <el-col :span="6">
                <el-statistic title="句子数" :value="executeResult.data?.sentence_count || 0" />
              </el-col>
              <el-col :span="6">
                <el-statistic title="段落数" :value="executeResult.data?.paragraph_count || 0" />
              </el-col>
              <el-col :span="6">
                <div class="sentiment-display">
                  <div class="sentiment-label">情感倾向</div>
                  <el-tag :type="sentimentColor(executeResult.data?.sentiment?.label)" size="large">
                    {{ sentimentLabel(executeResult.data?.sentiment?.label) }}
                  </el-tag>
                </div>
              </el-col>
            </el-row>

            <!-- 关键词展示 -->
            <div v-if="executeResult.data?.keywords?.length" class="keywords-section">
              <h5>关键词</h5>
              <div class="keywords-cloud">
                <el-tag
                  v-for="(kw, index) in executeResult.data.keywords"
                  :key="index"
                  :size="keywordSize(kw.count)"
                  :type="keywordColor(index)"
                  class="keyword-tag"
                >
                  {{ kw.word }} ({{ kw.count }})
                </el-tag>
              </div>
            </div>
          </div>

          <!-- 数据导出结果 -->
          <div v-if="pluginName === 'data-exporter' && executeResult.success" class="export-visual">
            <div v-if="executeResult.isDownload" class="download-info">
              <el-icon><Download /></el-icon>
              <span>文件已下载</span>
            </div>
            <pre v-else class="result-json">{{ executeResult.content }}</pre>
          </div>

          <!-- 通用结果展示 -->
          <pre v-else class="result-json">{{ executeResult.content }}</pre>
        </div>
      </el-card>
    </div>

    <el-empty v-else description="插件不存在或未加载" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Download } from '@element-plus/icons-vue'
import axios from 'axios'

const route = useRoute()

const pluginName = ref(route.params.pluginName as string || '')
const loading = ref(false)
const pluginInfo = ref<any>(null)
const selectedFunction = ref<any>(null)
const executing = ref(false)
const executeResult = ref<any>(null)

// 文本分析器
const inputText = ref('')
const topN = ref(10)

// 数据导出器
const exportFormat = ref('json')
const inputData = ref('')

// 通用
const requestBody = ref('')

const loadPluginInfo = async () => {
  if (!pluginName.value) return
  
  loading.value = true
  try {
    const resp = await axios.get(`/api/plugins/installed/${pluginName.value}`)
    pluginInfo.value = resp.data
  } catch (error) {
    ElMessage.error('加载插件信息失败')
  } finally {
    loading.value = false
  }
}

const selectFunction = (func: any) => {
  selectedFunction.value = func
  executeResult.value = null
}

const executeFunction = async () => {
  if (!selectedFunction.value) return
  
  executing.value = true
  const startTime = Date.now()
  
  try {
    let body: any = {}
    
    // 根据插件类型构建请求体
    if (pluginName.value === 'text-analyzer') {
      if (selectedFunction.value.path.includes('keywords')) {
        body = { text: inputText.value, top_n: topN.value }
      } else {
        body = { text: inputText.value }
      }
    } else if (pluginName.value === 'data-exporter') {
      if (selectedFunction.value.path.includes('formats')) {
        body = {}
      } else {
        body = {
          data: JSON.parse(inputData.value),
          format: exportFormat.value
        }
      }
    } else {
      body = requestBody.value ? JSON.parse(requestBody.value) : {}
    }
    
    let resp
    if (selectedFunction.value.method === 'POST') {
      resp = await axios.post(selectedFunction.value.path, body)
    } else {
      resp = await axios.get(selectedFunction.value.path)
    }
    
    const elapsed = Date.now() - startTime
    
    // 处理下载响应
    if (resp.headers['content-type']?.includes('application/octet-stream') ||
        resp.headers['content-disposition']) {
      executeResult.value = {
        success: true,
        isDownload: true,
        content: '文件已下载',
        time: elapsed
      }
    } else {
      executeResult.value = {
        success: true,
        data: resp.data.data || resp.data,
        content: JSON.stringify(resp.data, null, 2),
        time: elapsed
      }
    }
  } catch (error: any) {
    executeResult.value = {
      success: false,
      content: error.response?.data ? JSON.stringify(error.response.data, null, 2) : error.message,
      time: Date.now() - startTime
    }
  } finally {
    executing.value = false
  }
}

const clearResult = () => {
  executeResult.value = null
}

const statusColor = (status: string) => {
  const colors: Record<string, string> = {
    active: 'success',
    installed: 'info',
    inactive: 'warning',
    error: 'danger'
  }
  return colors[status] || ''
}

const statusLabel = (status: string) => {
  const labels: Record<string, string> = {
    active: '已激活',
    installed: '已安装',
    inactive: '已停用',
    error: '错误'
  }
  return labels[status] || status
}

const methodColor = (method: string) => {
  const colors: Record<string, string> = {
    GET: 'success',
    POST: 'primary',
    PUT: 'warning',
    DELETE: 'danger'
  }
  return colors[method] || ''
}

const sentimentColor = (label: string) => {
  const colors: Record<string, string> = {
    positive: 'success',
    negative: 'danger',
    neutral: 'info'
  }
  return colors[label] || 'info'
}

const sentimentLabel = (label: string) => {
  const labels: Record<string, string> = {
    positive: '积极 😊',
    negative: '消极 😔',
    neutral: '中性 😐'
  }
  return labels[label] || label
}

const keywordSize = (count: number) => {
  if (count >= 5) return 'large'
  if (count >= 3) return 'default'
  return 'small'
}

const keywordColor = (index: number) => {
  const colors = ['', 'success', 'warning', 'danger', 'info']
  return colors[index % colors.length]
}

const formatTime = (time: string) => {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}

watch(() => route.params.pluginName, (newName) => {
  pluginName.value = newName as string
  loadPluginInfo()
})

onMounted(() => {
  loadPluginInfo()
})
</script>

<style scoped>
.plugin-function {
  padding: 20px;
}

.page-title {
  font-size: 24px;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.plugin-icon {
  font-size: 32px;
}

.page-desc {
  color: #666;
  margin-bottom: 20px;
}

.loading-state {
  padding: 40px;
}

.info-card,
.function-card,
.execute-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.function-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.function-item {
  padding: 16px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.function-item:hover {
  border-color: #409eff;
  background: #f5f7fa;
}

.function-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.function-path {
  font-family: monospace;
  font-weight: 500;
}

.function-desc {
  color: #666;
  font-size: 14px;
}

.execute-form {
  max-width: 800px;
}

.execute-result {
  margin-top: 20px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
}

.result-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.result-header h4 {
  margin: 0;
}

.result-time {
  color: #999;
  font-size: 14px;
}

.analysis-visual {
  margin-top: 16px;
}

.sentiment-display {
  text-align: center;
}

.sentiment-label {
  font-size: 12px;
  color: #999;
  margin-bottom: 8px;
}

.keywords-section {
  margin-top: 20px;
}

.keywords-section h5 {
  margin-bottom: 12px;
}

.keywords-cloud {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.keyword-tag {
  transition: all 0.2s;
}

.keyword-tag:hover {
  transform: scale(1.1);
}

.result-json {
  background: #fff;
  padding: 12px;
  border-radius: 4px;
  font-family: monospace;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 400px;
  overflow-y: auto;
}

.download-info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  color: #67c23a;
}
</style>
