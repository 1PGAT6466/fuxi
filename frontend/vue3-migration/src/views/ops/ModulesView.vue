<template>
  <div class="modules-manager">
    <h2 class="page-title">🧩 功能模块中心</h2>
    <p class="page-desc">统一管理所有功能模块：内置服务、外部插件、AI 工具</p>

    <!-- 统计卡片 -->
    <div class="stats-cards">
      <el-card class="stat-card">
        <el-statistic title="总模块" :value="stats.total" />
      </el-card>
      <el-card class="stat-card">
        <el-statistic title="已启用" :value="stats.enabled" />
      </el-card>
      <el-card class="stat-card">
        <el-statistic title="内置服务" :value="stats.builtin" />
      </el-card>
      <el-card class="stat-card">
        <el-statistic title="外部插件" :value="stats.plugin" />
      </el-card>
    </div>

    <!-- 分类筛选 -->
    <div class="filter-bar">
      <el-radio-group v-model="selectedCategory" @change="filterModules">
        <el-radio-button label="">全部</el-radio-button>
        <el-radio-button v-for="cat in categories" :key="cat" :label="cat">
          {{ categoryLabel(cat) }}
        </el-radio-button>
      </el-radio-group>
      <el-input
        v-model="searchQuery"
        placeholder="搜索模块..."
        prefix-icon="Search"
        clearable
        class="search-input"
      />
    </div>

    <!-- 模块列表 -->
    <div class="modules-grid">
      <el-card
        v-for="module in filteredModules"
        :key="module.id"
        class="module-card"
        :class="{ 'is-disabled': !module.enabled }"
      >
        <template #header>
          <div class="card-header">
            <div class="module-info">
              <span class="module-icon">{{ module.icon }}</span>
              <div>
                <h3 class="module-name">{{ module.name }}</h3>
                <el-tag size="small" :type="typeColor(module.type)">{{ module.type }}</el-tag>
              </div>
            </div>
            <el-switch
              v-model="module.enabled"
              @change="(val: boolean) => toggleModule(module.id, val)"
            />
          </div>
        </template>

        <div class="module-content">
          <p class="module-desc">{{ module.description }}</p>
          
          <div class="module-meta">
            <span class="meta-item">
              <el-icon><InfoFilled /></el-icon>
              v{{ module.version }}
            </span>
            <span class="meta-item" v-if="module.endpoints?.length">
              <el-icon><Link /></el-icon>
              {{ module.endpoints.length }} 个接口
            </span>
          </div>

          <!-- 操作按钮 -->
          <div class="module-actions">
            <el-button
              v-if="module.endpoints?.length"
              type="primary"
              size="small"
              @click="openUseDialog(module)"
            >
              <el-icon><VideoPlay /></el-icon>
              使用
            </el-button>
            <el-button
              size="small"
              @click="openConfigDialog(module)"
            >
              <el-icon><Setting /></el-icon>
              配置
            </el-button>
            <el-button
              size="small"
              @click="checkHealth(module)"
            >
              <el-icon><CircleCheck /></el-icon>
              健康
            </el-button>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 使用模块对话框 -->
    <el-dialog
      v-model="showUseDialog"
      :title="`使用 - ${currentModule?.name}`"
      width="900px"
      top="5vh"
    >
      <div v-if="currentModule" class="use-dialog">
        <!-- 选择功能 -->
        <div class="function-selector">
          <h4>选择功能</h4>
          <div class="function-list">
            <el-button
              v-for="ep in currentModule.endpoints"
              :key="ep.path"
              :type="selectedEndpoint?.path === ep.path ? 'primary' : 'default'"
              @click="selectEndpoint(ep)"
            >
              {{ ep.name }}
              <el-tag size="small" class="method-tag">{{ ep.method }}</el-tag>
            </el-button>
          </div>
        </div>

        <!-- 输入区域 -->
        <div v-if="selectedEndpoint" class="input-section">
          <h4>输入参数</h4>
          
          <!-- AI 工具集专用表单 -->
          <template v-if="currentModule.id === 'ai-tools'">
            <el-form label-width="100px">
              <el-form-item label="输入文本">
                <el-input
                  v-model="inputData.text"
                  type="textarea"
                  :rows="6"
                  placeholder="请输入要处理的文本..."
                />
              </el-form-item>
              
              <!-- 翻译参数 -->
              <template v-if="selectedEndpoint.path === '/api/ai/translate'">
                <el-form-item label="源语言">
                  <el-select v-model="inputData.source_lang">
                    <el-option label="中文" value="zh" />
                    <el-option label="英语" value="en" />
                    <el-option label="日语" value="ja" />
                    <el-option label="韩语" value="ko" />
                  </el-select>
                </el-form-item>
                <el-form-item label="目标语言">
                  <el-select v-model="inputData.target_lang">
                    <el-option label="中文" value="zh" />
                    <el-option label="英语" value="en" />
                    <el-option label="日语" value="ja" />
                    <el-option label="韩语" value="ko" />
                  </el-select>
                </el-form-item>
              </template>
              
              <!-- 摘要参数 -->
              <el-form-item v-if="selectedEndpoint.path === '/api/ai/summarize'" label="最大长度">
                <el-input-number v-model="inputData.max_length" :min="50" :max="2000" />
              </el-form-item>
            </el-form>
          </template>

          <!-- 文本分析器专用表单 -->
          <template v-else-if="currentModule.id === 'text-analyzer'">
            <el-form label-width="100px">
              <el-form-item label="输入文本">
                <el-input
                  v-model="inputData.text"
                  type="textarea"
                  :rows="6"
                  placeholder="请输入要分析的文本..."
                />
              </el-form-item>
              <el-form-item v-if="selectedEndpoint.path.includes('keywords')" label="关键词数量">
                <el-input-number v-model="inputData.top_n" :min="1" :max="50" />
              </el-form-item>
            </el-form>
          </template>

          <!-- 数据导出器专用表单 -->
          <template v-else-if="currentModule.id === 'data-exporter'">
            <el-form label-width="100px">
              <el-form-item label="导出格式">
                <el-select v-model="inputData.format">
                  <el-option label="CSV" value="csv" />
                  <el-option label="JSON" value="json" />
                  <el-option label="Markdown" value="markdown" />
                  <el-option label="Excel" value="excel" />
                </el-select>
              </el-form-item>
              <el-form-item label="数据 (JSON)">
                <el-input
                  v-model="inputData.data"
                  type="textarea"
                  :rows="6"
                  placeholder='[{"name": "张三", "age": 25}]'
                />
              </el-form-item>
            </el-form>
          </template>

          <!-- 通用表单 -->
          <template v-else>
            <el-form label-width="100px">
              <el-form-item v-if="selectedEndpoint.method === 'POST'" label="请求体 (JSON)">
                <el-input
                  v-model="inputData.body"
                  type="textarea"
                  :rows="6"
                  placeholder='{"key": "value"}'
                />
              </el-form-item>
            </el-form>
          </template>

          <div class="execute-btn">
            <el-button type="primary" @click="executeFunction" :loading="executing">
              <el-icon><VideoPlay /></el-icon>
              执行
            </el-button>
          </div>
        </div>

        <!-- 结果区域 -->
        <div v-if="executeResult" class="result-section">
          <div class="result-header">
            <h4>执行结果</h4>
            <el-tag :type="executeResult.success ? 'success' : 'danger'">
              {{ executeResult.success ? '成功' : '失败' }}
            </el-tag>
            <span class="result-time">{{ executeResult.time }}ms</span>
          </div>

          <!-- AI 工具集结果可视化 -->
          <div v-if="currentModule.id === 'ai-tools' && executeResult.success" class="ai-result">
            <!-- 摘要结果 -->
            <div v-if="selectedEndpoint.path === '/api/ai/summarize'" class="summary-result">
              <div class="result-field">
                <label>摘要结果：</label>
                <div class="result-text">{{ executeResult.data.summary }}</div>
              </div>
              <div class="result-stats">
                <span>原文长度: {{ executeResult.data.original_length }} 字</span>
                <span>摘要长度: {{ executeResult.data.summary_length }} 字</span>
                <span>压缩率: {{ Math.round(executeResult.data.summary_length / executeResult.data.original_length * 100) }}%</span>
              </div>
            </div>

            <!-- 翻译结果 -->
            <div v-else-if="selectedEndpoint.path === '/api/ai/translate'" class="translate-result">
              <div class="result-field">
                <label>翻译结果：</label>
                <div class="result-text">{{ executeResult.data.translation }}</div>
              </div>
              <div class="result-stats">
                <span>{{ executeResult.data.source_lang }} → {{ executeResult.data.target_lang }}</span>
                <span>原文长度: {{ executeResult.data.original_length }} 字</span>
              </div>
            </div>

            <!-- 关键词结果 -->
            <div v-else-if="selectedEndpoint.path === '/api/ai/keywords'" class="keywords-result">
              <div class="result-field">
                <label>关键词：</label>
                <div class="keywords-cloud">
                  <el-tag
                    v-for="(kw, index) in executeResult.data.keywords"
                    :key="index"
                    :type="keywordColor(index)"
                    class="keyword-tag"
                  >
                    {{ kw }}
                  </el-tag>
                </div>
              </div>
              <div class="result-stats">
                <span>共 {{ executeResult.data.count }} 个关键词</span>
              </div>
            </div>

            <!-- 实体识别结果 -->
            <div v-else-if="selectedEndpoint.path === '/api/ai/entities'" class="entities-result">
              <div class="result-field">
                <label>识别结果：</label>
                <el-table :data="executeResult.data.entities" border size="small">
                  <el-table-column prop="name" label="实体" width="150" />
                  <el-table-column prop="type" label="类型" width="120">
                    <template #default="{ row }">
                      <el-tag size="small" :type="entityTypeColor(row.type)">{{ row.type }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="description" label="说明" />
                </el-table>
              </div>
              <div class="result-stats">
                <span>共 {{ executeResult.data.count }} 个实体</span>
                <span v-for="(count, type) in executeResult.data.type_counts" :key="type">
                  {{ type }}: {{ count }}
                </span>
              </div>
            </div>

            <!-- 分类结果 -->
            <div v-else-if="selectedEndpoint.path === '/api/ai/classify'" class="classify-result">
              <div class="result-field">
                <label>分类结果：</label>
                <div class="classify-result-content">
                  <el-tag type="primary" size="large">{{ executeResult.data.category }}</el-tag>
                  <span class="confidence">置信度: {{ Math.round(executeResult.data.confidence * 100) }}%</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 通用结果展示 -->
          <div v-else class="generic-result">
            <pre class="result-json">{{ executeResult.content }}</pre>
          </div>
        </div>
      </div>
    </el-dialog>

    <!-- 配置对话框 -->
    <el-dialog
      v-model="showConfigDialog"
      :title="`配置 - ${currentModule?.name}`"
      width="600px"
    >
      <div v-if="currentModule">
        <el-form label-width="120px">
          <el-form-item
            v-for="(schema, key) in currentModule.config_schema"
            :key="key"
            :label="schema.description || key"
          >
            <el-input-number
              v-if="schema.type === 'number'"
              v-model="moduleConfig[key]"
            />
            <el-switch
              v-else-if="schema.type === 'boolean'"
              v-model="moduleConfig[key]"
            />
            <el-input
              v-else
              v-model="moduleConfig[key]"
            />
          </el-form-item>
        </el-form>
        <div class="dialog-footer">
          <el-button @click="showConfigDialog = false">取消</el-button>
          <el-button type="primary" @click="saveConfig">保存</el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { InfoFilled, Link, VideoPlay, Setting, CircleCheck } from '@element-plus/icons-vue'
import axios from 'axios'

interface Module {
  id: string
  name: string
  icon: string
  category: string
  type: string
  description: string
  version: string
  endpoints: Array<{ path: string; method: string; name: string }>
  config_schema: Record<string, any>
  enabled: boolean
  config: Record<string, any>
  status?: string
}

const modules = ref<Module[]>([])
const categories = ref<string[]>([])
const selectedCategory = ref('')
const searchQuery = ref('')
const showUseDialog = ref(false)
const showConfigDialog = ref(false)
const currentModule = ref<Module | null>(null)
const selectedEndpoint = ref<any>(null)
const inputData = ref<Record<string, any>>({})
const moduleConfig = ref<Record<string, any>>({})
const executeResult = ref<any>(null)
const executing = ref(false)

const stats = computed(() => {
  const total = modules.value.length
  const enabled = modules.value.filter(m => m.enabled).length
  const builtin = modules.value.filter(m => m.type === 'builtin').length
  const plugin = modules.value.filter(m => m.type === 'plugin').length
  return { total, enabled, builtin, plugin }
})

const filteredModules = computed(() => {
  let result = modules.value
  if (selectedCategory.value) {
    result = result.filter(m => m.category === selectedCategory.value)
  }
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter(m =>
      m.name.toLowerCase().includes(query) ||
      m.description.toLowerCase().includes(query)
    )
  }
  return result
})

const loadModules = async () => {
  try {
    const resp = await axios.get('/api/modules')
    modules.value = resp.data.modules || []
    categories.value = resp.data.categories || []
  } catch (error) {
    ElMessage.error('获取模块列表失败')
  }
}

const filterModules = () => {
  // 触发 computed 重新计算
}

const toggleModule = async (moduleId: string, enabled: boolean) => {
  try {
    await axios.put(`/api/modules/${moduleId}/toggle`, { enabled })
    ElMessage.success(`模块已${enabled ? '启用' : '禁用'}`)
    loadModules()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

const openUseDialog = (module: Module) => {
  currentModule.value = module
  selectedEndpoint.value = null
  inputData.value = {}
  executeResult.value = null
  showUseDialog.value = true
}

const openConfigDialog = (module: Module) => {
  currentModule.value = module
  moduleConfig.value = { ...module.config }
  showConfigDialog.value = true
}

const selectEndpoint = (endpoint: any) => {
  selectedEndpoint.value = endpoint
  inputData.value = {}
  executeResult.value = null
}

const executeFunction = async () => {
  if (!currentModule.value || !selectedEndpoint.value) return
  
  executing.value = true
  const startTime = Date.now()
  
  try {
    let body: any = {}
    
    // 根据模块类型构建请求体
    if (currentModule.value.id === 'ai-tools') {
      body = {
        text: inputData.value.text,
        max_length: inputData.value.max_length,
        source_lang: inputData.value.source_lang || 'zh',
        target_lang: inputData.value.target_lang || 'en',
      }
    } else if (currentModule.value.id === 'text-analyzer') {
      body = {
        text: inputData.value.text,
        top_n: inputData.value.top_n,
      }
    } else if (currentModule.value.id === 'data-exporter') {
      body = {
        data: inputData.value.data ? JSON.parse(inputData.value.data) : [],
        format: inputData.value.format,
      }
    } else {
      body = inputData.value.body ? JSON.parse(inputData.value.body) : {}
    }
    
    let resp
    if (selectedEndpoint.value.method === 'POST') {
      resp = await axios.post(selectedEndpoint.value.path, body)
    } else {
      resp = await axios.get(selectedEndpoint.value.path)
    }
    
    executeResult.value = {
      success: true,
      data: resp.data,
      content: JSON.stringify(resp.data, null, 2),
      time: Date.now() - startTime,
    }
  } catch (error: any) {
    executeResult.value = {
      success: false,
      content: error.response?.data ? JSON.stringify(error.response.data, null, 2) : error.message,
      time: Date.now() - startTime,
    }
  } finally {
    executing.value = false
  }
}

const saveConfig = async () => {
  if (!currentModule.value) return
  
  try {
    await axios.put(`/api/modules/${currentModule.value.id}/config`, {
      config: moduleConfig.value,
    })
    ElMessage.success('配置已保存')
    showConfigDialog.value = false
    loadModules()
  } catch (error) {
    ElMessage.error('保存失败')
  }
}

const checkHealth = async (module: Module) => {
  try {
    const resp = await axios.get(`/api/modules/${module.id}/health`)
    ElMessage.success(`${module.name} 健康状态: ${resp.data.status}`)
  } catch (error) {
    ElMessage.error('健康检查失败')
  }
}

const categoryLabel = (category: string) => {
  const labels: Record<string, string> = {
    ai: 'AI 工具',
    analytics: '数据分析',
    engineering: '工程',
    document: '文档',
    search: '搜索',
    automation: '自动化',
    knowledge: '知识',
    quality: '质量',
    security: '安全',
    performance: '性能',
    plugin: '插件',
  }
  return labels[category] || category
}

const typeColor = (type: string) => {
  const colors: Record<string, string> = {
    builtin: 'primary',
    plugin: 'success',
  }
  return colors[type] || ''
}

const keywordColor = (index: number) => {
  const colors = ['', 'success', 'warning', 'danger', 'info']
  return colors[index % colors.length]
}

const entityTypeColor = (type: string) => {
  const colors: Record<string, string> = {
    PERSON: 'primary',
    LOCATION: 'success',
    ORGANIZATION: 'warning',
    TIME: 'info',
    QUANTITY: 'danger',
  }
  return colors[type] || ''
}

onMounted(() => {
  loadModules()
})
</script>

<style scoped>
.modules-manager {
  padding: 20px;
}

.page-title {
  font-size: 24px;
  margin-bottom: 8px;
}

.page-desc {
  color: #666;
  margin-bottom: 20px;
}

.stats-cards {
  display: flex;
  gap: 16px;
  margin-bottom: 20px;
}

.stat-card {
  flex: 1;
  text-align: center;
}

.filter-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.search-input {
  width: 300px;
}

.modules-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 16px;
}

.module-card {
  transition: all 0.3s;
}

.module-card.is-disabled {
  opacity: 0.6;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.module-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.module-icon {
  font-size: 32px;
}

.module-name {
  margin: 0 0 4px 0;
  font-size: 16px;
}

.module-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.module-desc {
  color: #666;
  font-size: 14px;
  margin: 0;
}

.module-meta {
  display: flex;
  gap: 16px;
  color: #999;
  font-size: 12px;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.module-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.use-dialog {
  max-height: 70vh;
  overflow-y: auto;
}

.function-selector {
  margin-bottom: 20px;
}

.function-selector h4 {
  margin-bottom: 12px;
}

.function-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.method-tag {
  margin-left: 8px;
}

.input-section {
  margin-bottom: 20px;
}

.input-section h4 {
  margin-bottom: 12px;
}

.execute-btn {
  text-align: center;
  margin-top: 16px;
}

.result-section {
  background: #f5f7fa;
  padding: 16px;
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

.ai-result {
  background: #fff;
  padding: 16px;
  border-radius: 4px;
}

.result-field {
  margin-bottom: 16px;
}

.result-field label {
  font-weight: 500;
  display: block;
  margin-bottom: 8px;
}

.result-text {
  font-size: 16px;
  line-height: 1.6;
  padding: 12px;
  background: #f9f9f9;
  border-radius: 4px;
}

.result-stats {
  display: flex;
  gap: 16px;
  color: #666;
  font-size: 14px;
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

.classify-result-content {
  display: flex;
  align-items: center;
  gap: 12px;
}

.confidence {
  color: #666;
}

.generic-result {
  background: #fff;
  padding: 12px;
  border-radius: 4px;
}

.result-json {
  font-family: monospace;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 400px;
  overflow-y: auto;
  margin: 0;
}

.dialog-footer {
  text-align: right;
  margin-top: 20px;
}
</style>
