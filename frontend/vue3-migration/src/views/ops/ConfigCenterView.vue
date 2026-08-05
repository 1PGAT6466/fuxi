<template>
  <div class="config-center">
    <header class="page-header">
      <h1>⚙️ 配置中心</h1>
      <el-button @click="refreshConfig" :loading="loading">
        <el-icon><Refresh /></el-icon>
        刷新
      </el-button>
    </header>

    <div v-loading="loading">
      <el-tabs v-model="activeCategory">
        <el-tab-pane
          v-for="(catData, catKey) in config"
          :key="catKey"
          :label="catData.name"
          :name="catKey"
        >
          <el-card>
            <el-table :data="catData.items" border>
              <el-table-column prop="name" label="配置项" width="200" />
              <el-table-column prop="key" label="Key" width="250">
                <template #default="{ row }">
                  <code>{{ row.key }}</code>
                </template>
              </el-table-column>
              <el-table-column prop="description" label="说明" min-width="200" />
              <el-table-column label="当前值" width="200">
                <template #default="{ row }">
                  <el-input
                    v-if="row.type === 'string' || row.type === 'password'"
                    v-model="row.value"
                    :type="row.type === 'password' ? 'password' : 'text'"
                    :disabled="row.readonly"
                    size="small"
                    @change="updateConfig(row)"
                  />
                  <el-input-number
                    v-else-if="row.type === 'number'"
                    v-model="row.value"
                    :min="row.min"
                    :max="row.max"
                    :disabled="row.readonly"
                    size="small"
                    @change="updateConfig(row)"
                  />
                  <el-switch
                    v-else-if="row.type === 'boolean'"
                    v-model="row.value"
                    :disabled="row.readonly"
                    @change="updateConfig(row)"
                  />
                  <el-select
                    v-else-if="row.type === 'select'"
                    v-model="row.value"
                    :disabled="row.readonly"
                    size="small"
                    @change="updateConfig(row)"
                  >
                    <el-option
                      v-for="opt in row.options"
                      :key="opt"
                      :label="opt"
                      :value="opt"
                    />
                  </el-select>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="100">
                <template #default="{ row }">
                  <el-button
                    size="small"
                    :disabled="row.readonly"
                    @click="resetToDefault(row)"
                  >
                    重置
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import axios from 'axios'

const loading = ref(false)
const activeCategory = ref('system')
const config = ref<Record<string, any>>({})

const refreshConfig = async () => {
  loading.value = true
  try {
    const resp = await axios.get('/api/config')
    config.value = resp.data.data || {}
  } catch (error) {
    console.error('获取配置失败:', error)
    ElMessage.error('获取配置失败')
  } finally {
    loading.value = false
  }
}

const updateConfig = async (item: any) => {
  try {
    await axios.put(`/api/config/${item.key}`, { value: item.value })
    ElMessage.success(`${item.name} 已更新`)
  } catch (error) {
    ElMessage.error('更新失败')
    refreshConfig()
  }
}

const resetToDefault = async (item: any) => {
  try {
    await axios.put(`/api/config/${item.key}`, { value: item.default })
    item.value = item.default
    ElMessage.success(`${item.name} 已重置为默认值`)
  } catch (error) {
    ElMessage.error('重置失败')
  }
}

onMounted(() => {
  refreshConfig()
})
</script>

<style scoped>
.config-center {
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

code {
  background: #f5f7fa;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
}
</style>
