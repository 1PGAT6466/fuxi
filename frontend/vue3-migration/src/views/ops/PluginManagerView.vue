<template>
  <div class="plugin-manager">
    <h2 class="page-title">🧩 插件管理中心</h2>
    <p class="page-desc">管理已安装的插件，查看状态、配置和路由信息</p>

    <!-- 插件统计 -->
    <div class="stats-bar">
      <el-statistic title="总插件" :value="stats.total" />
      <el-statistic title="已激活" :value="stats.active" />
      <el-statistic title="已安装" :value="stats.installed" />
      <el-statistic title="已停用" :value="stats.inactive" />
    </div>

    <!-- 操作栏 -->
    <div class="toolbar">
      <el-input
        v-model="searchQuery"
        placeholder="搜索插件名称..."
        prefix-icon="Search"
        clearable
        class="search-input"
      />
      <el-button type="primary" @click="refreshPlugins">
        <el-icon><Refresh /></el-icon>
        刷新
      </el-button>
      <el-button type="success" @click="showInstallDialog = true">
        <el-icon><Upload /></el-icon>
        安装插件
      </el-button>
    </div>

    <!-- 插件列表 -->
    <el-table
      v-loading="loading"
      :data="filteredPlugins"
      stripe
      border
      class="plugin-table"
      empty-text="暂无已安装的插件"
    >
      <el-table-column prop="icon" label="" width="60">
        <template #default="{ row }">
          <span class="plugin-icon">{{ row.manifest?.icon || '📦' }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="name" label="插件名称" min-width="150">
        <template #default="{ row }">
          <div>
            <strong>{{ row.display_name || row.name }}</strong>
            <div class="plugin-version">v{{ row.version }}</div>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="type" label="类型" width="100">
        <template #default="{ row }">
          <el-tag size="small" :type="typeColor(row.type)">{{ row.type }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag size="small" :type="statusColor(row.status)">
            {{ statusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
      <el-table-column label="操作" width="280" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="viewDetail(row)">详情</el-button>
          <el-button
            v-if="row.status === 'installed' || row.status === 'inactive'"
            type="success"
            size="small"
            @click="activatePlugin(row)"
          >
            激活
          </el-button>
          <el-button
            v-if="row.status === 'active'"
            type="warning"
            size="small"
            @click="deactivatePlugin(row)"
          >
            停用
          </el-button>
          <el-button
            v-if="row.status === 'active'"
            type="primary"
            size="small"
            @click="usePlugin(row)"
          >
            使用
          </el-button>
          <el-button
            type="danger"
            size="small"
            @click="uninstallPlugin(row)"
          >
            卸载
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 插件详情对话框 -->
    <el-dialog
      v-model="showDetailDialog"
      :title="`插件详情 - ${currentPlugin?.display_name || currentPlugin?.name}`"
      width="800px"
    >
      <div v-if="currentPlugin" class="plugin-detail">
        <el-tabs>
          <!-- 基本信息 -->
          <el-tab-pane label="基本信息">
            <el-descriptions :column="2" border>
              <el-descriptions-item label="名称">{{ currentPlugin.name }}</el-descriptions-item>
              <el-descriptions-item label="显示名称">{{ currentPlugin.display_name }}</el-descriptions-item>
              <el-descriptions-item label="版本">{{ currentPlugin.version }}</el-descriptions-item>
              <el-descriptions-item label="类型">
                <el-tag :type="typeColor(currentPlugin.type)">{{ currentPlugin.type }}</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="状态">
                <el-tag :type="statusColor(currentPlugin.status)">
                  {{ statusLabel(currentPlugin.status) }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="作者">{{ currentPlugin.author || '未知' }}</el-descriptions-item>
              <el-descriptions-item label="描述" :span="2">{{ currentPlugin.description }}</el-descriptions-item>
              <el-descriptions-item label="安装时间">{{ formatTime(currentPlugin.installed_at) }}</el-descriptions-item>
              <el-descriptions-item label="更新时间">{{ formatTime(currentPlugin.updated_at) }}</el-descriptions-item>
            </el-descriptions>
          </el-tab-pane>

          <!-- 路由信息 -->
          <el-tab-pane label="API 路由">
            <div v-if="currentPlugin.manifest?.routes?.length">
              <el-table :data="currentPlugin.manifest.routes" border>
                <el-table-column prop="path" label="路径" min-width="200" />
                <el-table-column prop="method" label="方法" width="100">
                  <template #default="{ row }">
                    <el-tag size="small" :type="methodColor(row.method)">{{ row.method }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="description" label="描述" min-width="200" />
                <el-table-column label="测试" width="100">
                  <template #default="{ row }">
                    <el-button size="small" @click="testRoute(row)">测试</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
            <el-empty v-else description="暂无路由信息" />
          </el-tab-pane>

          <!-- 配置信息 -->
          <el-tab-pane label="配置">
            <div v-if="currentPlugin.config && Object.keys(currentPlugin.config).length">
              <pre class="config-json">{{ JSON.stringify(currentPlugin.config, null, 2) }}</pre>
            </div>
            <el-empty v-else description="暂无配置" />
          </el-tab-pane>

          <!-- 健康检查 -->
          <el-tab-pane label="健康状态">
            <div v-if="healthInfo">
              <el-descriptions :column="2" border>
                <el-descriptions-item label="状态">
                  <el-tag :type="healthInfo.status === 'ok' ? 'success' : 'danger'">
                    {{ healthInfo.status }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="版本">{{ healthInfo.version || '未知' }}</el-descriptions-item>
              </el-descriptions>
            </div>
            <el-button v-else type="primary" @click="checkHealth">检查健康状态</el-button>
          </el-tab-pane>
        </el-tabs>
      </div>
    </el-dialog>

    <!-- 路由测试对话框 -->
    <el-dialog
      v-model="showTestDialog"
      :title="`测试路由 - ${currentRoute?.path}`"
      width="600px"
    >
      <div v-if="currentRoute" class="route-test">
        <el-form label-width="100px">
          <el-form-item label="路径">
            <el-input v-model="currentRoute.path" disabled />
          </el-form-item>
          <el-form-item label="方法">
            <el-tag>{{ currentRoute.method }}</el-tag>
          </el-form-item>
          <el-form-item label="请求体" v-if="currentRoute.method === 'POST'">
            <el-input
              v-model="testBody"
              type="textarea"
              :rows="6"
              placeholder='{"key": "value"}'
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="executeTest">执行测试</el-button>
          </el-form-item>
        </el-form>

        <div v-if="testResult" class="test-result">
          <h4>测试结果</h4>
          <el-tag :type="testResult.success ? 'success' : 'danger'" class="result-status">
            {{ testResult.success ? '成功' : '失败' }}
          </el-tag>
          <pre class="result-content">{{ testResult.content }}</pre>
        </div>
      </div>
    </el-dialog>

    <!-- 安装插件对话框 -->
    <el-dialog v-model="showInstallDialog" title="安装插件" width="500px">
      <el-form label-width="100px">
        <el-form-item label="插件路径">
          <el-input v-model="installPath" placeholder="插件目录的绝对路径" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="installPlugin">安装</el-button>
        </el-form-item>
      </el-form>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Upload } from '@element-plus/icons-vue'
import axios from 'axios'

interface Plugin {
  name: string
  version: string
  type: string
  display_name: string
  description: string
  author: string
  status: string
  manifest: any
  config: any
  installed_at: string
  updated_at: string
}

interface Route {
  path: string
  method: string
  handler: string
  description: string
}

const loading = ref(false)
const plugins = ref<Plugin[]>([])
const searchQuery = ref('')
const showDetailDialog = ref(false)
const showTestDialog = ref(false)
const showInstallDialog = ref(false)
const currentPlugin = ref<Plugin | null>(null)
const currentRoute = ref<Route | null>(null)
const healthInfo = ref<any>(null)
const testBody = ref('')
const testResult = ref<any>(null)
const installPath = ref('')

const stats = computed(() => {
  const total = plugins.value.length
  const active = plugins.value.filter(p => p.status === 'active').length
  const installed = plugins.value.filter(p => p.status === 'installed').length
  const inactive = plugins.value.filter(p => p.status === 'inactive').length
  return { total, active, installed, inactive }
})

const filteredPlugins = computed(() => {
  if (!searchQuery.value) return plugins.value
  const query = searchQuery.value.toLowerCase()
  return plugins.value.filter(p =>
    p.name.toLowerCase().includes(query) ||
    p.display_name?.toLowerCase().includes(query) ||
    p.description?.toLowerCase().includes(query)
  )
})

const refreshPlugins = async () => {
  loading.value = true
  try {
    const resp = await axios.get('/api/plugins/installed')
    plugins.value = resp.data.plugins || []
  } catch (error) {
    ElMessage.error('获取插件列表失败')
  } finally {
    loading.value = false
  }
}

const viewDetail = async (plugin: Plugin) => {
  currentPlugin.value = plugin
  healthInfo.value = null
  showDetailDialog.value = true
}

const checkHealth = async () => {
  if (!currentPlugin.value) return
  try {
    const resp = await axios.get(`/api/plugins/health/${currentPlugin.value.name}`)
    healthInfo.value = resp.data
  } catch (error) {
    ElMessage.error('健康检查失败')
  }
}

const activatePlugin = async (plugin: Plugin) => {
  try {
    await axios.post(`/api/plugins/activate/${plugin.name}`)
    ElMessage.success(`插件 ${plugin.display_name} 已激活`)
    refreshPlugins()
  } catch (error) {
    ElMessage.error('激活失败')
  }
}

const deactivatePlugin = async (plugin: Plugin) => {
  try {
    await axios.post(`/api/plugins/deactivate/${plugin.name}`)
    ElMessage.success(`插件 ${plugin.display_name} 已停用`)
    refreshPlugins()
  } catch (error) {
    ElMessage.error('停用失败')
  }
}

const uninstallPlugin = async (plugin: Plugin) => {
  try {
    await ElMessageBox.confirm(
      `确定要卸载插件 "${plugin.display_name}" 吗？`,
      '确认卸载',
      { type: 'warning' }
    )
    await axios.post(`/api/plugins/uninstall/${plugin.name}`)
    ElMessage.success(`插件 ${plugin.display_name} 已卸载`)
    refreshPlugins()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('卸载失败')
    }
  }
}

const usePlugin = (plugin: Plugin) => {
  // 跳转到插件功能页面
  window.location.hash = `#/ops/plugin-function/${plugin.name}`
}

const testRoute = (route: Route) => {
  currentRoute.value = route
  testBody.value = ''
  testResult.value = null
  showTestDialog.value = true
}

const executeTest = async () => {
  if (!currentRoute.value) return
  
  try {
    let resp
    if (currentRoute.value.method === 'POST') {
      const body = testBody.value ? JSON.parse(testBody.value) : {}
      resp = await axios.post(currentRoute.value.path, body)
    } else {
      resp = await axios.get(currentRoute.value.path)
    }
    
    testResult.value = {
      success: true,
      content: JSON.stringify(resp.data, null, 2)
    }
  } catch (error: any) {
    testResult.value = {
      success: false,
      content: error.response?.data ? JSON.stringify(error.response.data, null, 2) : error.message
    }
  }
}

const installPlugin = async () => {
  if (!installPath.value) {
    ElMessage.warning('请输入插件路径')
    return
  }
  
  try {
    // 这里需要先读取 manifest.json，简化处理
    ElMessage.info('安装功能开发中...')
    showInstallDialog.value = false
  } catch (error) {
    ElMessage.error('安装失败')
  }
}

const typeColor = (type: string) => {
  const colors: Record<string, string> = {
    api: 'primary',
    service: 'success',
    ui: 'warning',
    llm: 'danger',
    storage: 'info'
  }
  return colors[type] || ''
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

const formatTime = (time: string) => {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}

onMounted(() => {
  refreshPlugins()
})
</script>

<style scoped>
.plugin-manager {
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

.stats-bar {
  display: flex;
  gap: 40px;
  margin-bottom: 20px;
  padding: 20px;
  background: #f5f7fa;
  border-radius: 8px;
}

.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.search-input {
  width: 300px;
}

.plugin-table {
  width: 100%;
}

.plugin-icon {
  font-size: 24px;
}

.plugin-version {
  font-size: 12px;
  color: #999;
}

.plugin-detail {
  max-height: 60vh;
  overflow-y: auto;
}

.config-json {
  background: #f5f7fa;
  padding: 16px;
  border-radius: 4px;
  font-family: monospace;
  white-space: pre-wrap;
  word-break: break-all;
}

.route-test {
  padding: 10px 0;
}

.test-result {
  margin-top: 20px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 4px;
}

.result-status {
  margin-bottom: 12px;
}

.result-content {
  background: #fff;
  padding: 12px;
  border-radius: 4px;
  font-family: monospace;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 300px;
  overflow-y: auto;
}
</style>
