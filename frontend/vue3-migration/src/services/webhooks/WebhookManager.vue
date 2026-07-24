<template>
  <div class="webhook-manager">
    <div class="webhook-header">
      <div class="webhook-header__info">
        <h2 class="webhook-header__title">
          <el-icon :size="20"><Link /></el-icon>
          Webhook 配置
        </h2>
        <span class="webhook-header__count">
          共 {{ store.total }} 个 Webhook，{{ store.activeWebhookCount }} 个活跃
          <template v-if="store.failedWebhookCount > 0">
            <el-tag size="small" type="danger" effect="plain" style="margin-left: 8px">
              {{ store.failedWebhookCount }} 个失败
            </el-tag>
          </template>
        </span>
      </div>
      <el-button type="primary" :icon="Plus" @click="handleCreate">创建 Webhook</el-button>
    </div>

    <div v-if="store.activeEventTypes.length > 0" class="webhook-event-overview">
      <span class="webhook-event-overview__label">已订阅事件：</span>
      <div class="webhook-event-overview__tags">
        <el-tag v-for="et in store.activeEventTypes" :key="et" size="small" type="info" effect="plain"
          class="event-tag-mini">{{ getEventLabel(et) }}</el-tag>
      </div>
    </div>

    <div v-if="store.loading" class="webhook-loading"><el-skeleton :rows="5" animated /></div>

    <div v-else-if="store.error" class="webhook-error">
      <el-result icon="error" title="加载失败" :sub-title="store.error">
        <template #extra><el-button type="primary" @click="loadWebhooks">重试</el-button></template>
      </el-result>
    </div>

    <div v-else-if="store.webhooks.length > 0" class="webhook-table-wrapper">
      <el-table :data="store.webhooks" stripe style="width: 100%" :default-sort="{ prop: 'createdAt', order: 'descending' }">
        <el-table-column prop="name" label="名称" min-width="160">
          <template #default="{ row }">
            <div class="webhook-name-cell">
              <el-icon :size="14" :color="row.status === 'active' ? 'var(--brand)' : 'var(--text-tertiary)'"><Link /></el-icon>
              <span class="webhook-name-cell__text">{{ row.name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="回调 URL" min-width="260">
          <template #default="{ row }">
            <div class="webhook-url-cell">
              <code class="webhook-url">{{ row.url }}</code>
              <el-button link type="primary" size="small" :icon="CopyDocument" @click.stop="copy(row.url)" />
            </div>
          </template>
        </el-table-column>
        <el-table-column label="订阅事件" min-width="220">
          <template #default="{ row }">
            <div class="event-tags">
              <el-tag v-for="e in row.events.slice(0, 3)" :key="e" size="small" effect="plain" class="event-tag">
                {{ getEventLabel(e) }}
              </el-tag>
              <el-tooltip v-if="row.events.length > 3"
                :content="row.events.slice(3).map(e => getEventLabel(e)).join('、')" placement="top">
                <el-tag size="small" effect="plain" type="info" class="event-tag">+{{ row.events.length - 3 }}</el-tag>
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="tagType(row.status)" size="small" effect="light">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="签名" width="80" align="center">
          <template #default="{ row }">
            <el-tooltip :content="row.signatureEnabled ? '算法: ' + row.signatureAlgorithm.toUpperCase() : '未启用'" placement="top">
              <span class="sig-ind" :class="{ active: row.signatureEnabled }">{{ row.signatureEnabled ? '✓' : '—' }}</span>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="发送统计" width="120" align="center">
          <template #default="{ row }">
            <div class="send-stats">
              <span class="send-stats__ok">{{ row.totalSent - row.totalFailed }}</span>
              <span class="send-stats__sep">/</span>
              <span class="send-stats__total">{{ row.totalSent }}</span>
              <span v-if="row.totalFailed > 0" class="send-stats__fail">({{ row.totalFailed }})</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="最后发送" width="160" sortable prop="lastSentAt">
          <template #default="{ row }">
            <div v-if="row.lastSentAt" class="last-sent">
              <span class="last-sent__dot" :class="row.lastSentStatus === 'success' ? 'dot-ok' : 'dot-fail'" />
              <span>{{ formatRelative(row.lastSentAt) }}</span>
            </div>
            <span v-else class="never-sent">未发送</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-tooltip content="测试发送" placement="top">
                <el-button link type="primary" :icon="Promotion" size="small" @click.stop="handleTest(row)" />
              </el-tooltip>
              <el-tooltip content="投递记录" placement="top">
                <el-button link type="primary" :icon="DocumentCopy" size="small" @click.stop="handleDeliveries(row)" />
              </el-tooltip>
              <el-tooltip content="编辑" placement="top">
                <el-button link type="primary" :icon="Edit" size="small" @click.stop="handleEdit(row)" />
              </el-tooltip>
              <el-tooltip :content="row.status === 'active' ? '暂停' : '启用'" placement="top">
                <el-button link :type="row.status === 'active' ? 'warning' : 'success'"
                  :icon="row.status === 'active' ? VideoPause : VideoPlay" size="small" @click.stop="handleToggle(row)" />
              </el-tooltip>
              <el-tooltip content="删除" placement="top">
                <el-popconfirm title="确定删除此 Webhook？" confirm-button-text="删除"
                  cancel-button-text="取消" confirm-button-type="danger" @confirm="handleDelete(row)">
                  <template #reference><el-button link type="danger" :icon="Delete" size="small" @click.stop /></template>
                </el-popconfirm>
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div v-else class="webhook-empty">
      <el-empty description="暂无 Webhook，点击上方按钮创建">
        <template #image><el-icon :size="64" color="var(--text-tertiary)"><Link /></el-icon></template>
      </el-empty>
    </div>

    <!-- Create dialog -->
    <el-dialog v-model="store.showCreateDialog" title="创建 Webhook" width="640px"
      :close-on-click-modal="false" destroy-on-close>
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-position="top">
        <el-form-item label="名称" prop="name">
          <el-input v-model="createForm.name" placeholder="例如：生产环境通知" maxlength="50" show-word-limit />
        </el-form-item>
        <el-form-item label="URL" prop="url">
          <el-input v-model="createForm.url" placeholder="https://your-server.com/api/webhook" maxlength="500" show-word-limit />
        </el-form-item>
        <el-form-item label="订阅事件" prop="events">
          <div class="event-groups">
            <div v-for="group in eventGroups" :key="group.label" class="event-group">
              <div class="event-group__header">
                <el-checkbox :model-value="isGroupFull(group, createForm.events)"
                  :indeterminate="isGroupPartial(group, createForm.events)"
                  @change="(val) => toggleGroup(createForm.events, group, val)">{{ group.label }}</el-checkbox>
              </div>
              <div class="event-group__items">
                <el-checkbox v-for="evt in group.events" :key="evt"
                  :model-value="createForm.events.includes(evt)" size="small"
                  @change="(val) => toggleEvent(createForm.events, evt, val)">
                  {{ getEventLabel(evt) }}
                </el-checkbox>
              </div>
            </div>
          </div>
          <div v-if="createEventError" class="event-error-tip">请至少选择一个事件</div>
        </el-form-item>
        <el-form-item label="安全设置">
          <div class="advanced-section">
            <div class="advanced-item">
              <div class="advanced-item__left">
                <span class="advanced-item__label">签名验证</span>
                <span class="advanced-item__desc">HMAC-SHA256 验证请求来源</span>
              </div>
              <el-switch v-model="createForm.signatureEnabled" />
            </div>
            <div v-if="createForm.signatureEnabled" class="advanced-item">
              <div class="advanced-item__left"><span class="advanced-item__label">签名算法</span></div>
              <el-select v-model="createForm.signatureAlgorithm" size="small" style="width:160px">
                <el-option label="HMAC-SHA256" value="sha256" />
                <el-option label="HMAC-SHA512" value="sha512" />
              </el-select>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="重试配置">
          <div class="advanced-section">
            <div class="advanced-row">
              <div class="advanced-row__item">
                <span class="advanced-row__label">最大重试次数</span>
                <el-input-number v-model="createForm.retryConfig.maxRetries" :min="0" :max="10" size="small" />
              </div>
              <div class="advanced-row__item">
                <span class="advanced-row__label">重试间隔 (ms)</span>
                <el-input-number v-model="createForm.retryConfig.retryDelayMs" :min="500" :max="60000" :step="500" size="small" />
              </div>
            </div>
            <div class="advanced-item">
              <div class="advanced-item__left">
                <span class="advanced-item__label">指数退避</span>
                <span class="advanced-item__desc">每次重试间隔翻倍</span>
              </div>
              <el-switch v-model="createForm.retryConfig.exponentialBackoff" size="small" />
            </div>
          </div>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="createForm.description" type="textarea" placeholder="可选描述" :rows="2" maxlength="200" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="store.closeDialogs">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- Edit dialog -->
    <el-dialog v-model="store.showEditDialog" title="编辑 Webhook" width="640px"
      :close-on-click-modal="false" destroy-on-close @opened="initEdit">
      <el-form v-if="store.editingWebhook" ref="editFormRef" :model="editForm" :rules="editRules" label-position="top">
        <el-form-item label="名称" prop="name">
          <el-input v-model="editForm.name" maxlength="50" show-word-limit />
        </el-form-item>
        <el-form-item label="URL" prop="url">
          <el-input v-model="editForm.url" maxlength="500" show-word-limit />
        </el-form-item>
        <el-form-item label="订阅事件" prop="events">
          <div class="event-groups">
            <div v-for="group in eventGroups" :key="group.label" class="event-group">
              <div class="event-group__header">
                <el-checkbox :model-value="isGroupFull(group, editForm.events)"
                  :indeterminate="isGroupPartial(group, editForm.events)"
                  @change="(val) => toggleGroup(editForm.events, group, val)">{{ group.label }}</el-checkbox>
              </div>
              <div class="event-group__items">
                <el-checkbox v-for="evt in group.events" :key="evt"
                  :model-value="editForm.events.includes(evt)" size="small"
                  @change="(val) => toggleEvent(editForm.events, evt, val)">{{ getEventLabel(evt) }}</el-checkbox>
              </div>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="重试配置">
          <div class="advanced-section">
            <div class="advanced-row">
              <div class="advanced-row__item">
                <span class="advanced-row__label">最大重试次数</span>
                <el-input-number v-model="editForm.retryConfig.maxRetries" :min="0" :max="10" size="small" />
              </div>
              <div class="advanced-row__item">
                <span class="advanced-row__label">重试间隔 (ms)</span>
                <el-input-number v-model="editForm.retryConfig.retryDelayMs" :min="500" :max="60000" :step="500" size="small" />
              </div>
            </div>
            <div class="advanced-item">
              <div class="advanced-item__left"><span class="advanced-item__label">指数退避</span></div>
              <el-switch v-model="editForm.retryConfig.exponentialBackoff" size="small" />
            </div>
          </div>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="editForm.description" type="textarea" placeholder="可选描述" :rows="2" maxlength="200" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="store.closeDialogs">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- Test dialog -->
    <el-dialog v-model="store.showTestDialog" title="测试 Webhook 发送" width="580px"
      :close-on-click-modal="false" destroy-on-close>
      <div v-if="store.selectedWebhook" class="test-dialog">
        <el-alert type="info" :closable="false" show-icon style="margin-bottom:16px">
          <template #title>将向 <strong>{{ store.selectedWebhook.url }}</strong> 发送测试事件</template>
        </el-alert>
        <el-form label-position="top">
          <el-form-item label="测试事件">
            <el-select v-model="testEventType" placeholder="选择事件" style="width:100%">
              <el-option v-for="evt in store.selectedWebhook.events" :key="evt"
                :label="getEventLabel(evt)" :value="evt" />
            </el-select>
          </el-form-item>
          <el-form-item label="自定义 Payload (可选)">
            <el-input v-model="testPayload" type="textarea" placeholder='{"key":"value"}' :rows="3" />
          </el-form-item>
        </el-form>
        <div v-if="store.testResult" class="test-result" :class="store.testResult.success ? 'test-ok' : 'test-fail'">
          <div class="test-result__header">
            <el-icon :size="18"><CircleCheck v-if="store.testResult.success" /><CircleClose v-else /></el-icon>
            <span>{{ store.testResult.success ? '成功' : '失败' }}</span>
          </div>
          <div class="test-result__details">
            <div><span>状态码</span><span>{{ store.testResult.statusCode }}</span></div>
            <div><span>响应时间</span><span>{{ store.testResult.responseTimeMs }}ms</span></div>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="store.closeDialogs">关闭</el-button>
        <el-button type="primary" :loading="store.testLoading" @click="submitTest">发送测试</el-button>
      </template>
    </el-dialog>

    <!-- Delivery dialog -->
    <el-dialog v-model="store.showDeliveryDialog"
      :title="'投递记录 - ' + (store.selectedWebhook?.name || '')" width="700px"
      :close-on-click-modal="false" destroy-on-close @opened="loadDeliveries">
      <div v-if="store.deliveriesLoading" class="delivery-loading"><el-skeleton :rows="4" animated /></div>
      <div v-else-if="store.deliveries.length > 0" class="delivery-list">
        <div v-for="d in store.deliveries" :key="d.id" class="delivery-item">
          <span class="delivery-dot" :class="'dot-' + d.status" />
          <div class="delivery-item__info">
            <span class="delivery-item__event">{{ getEventLabel(d.eventType) }}</span>
            <span class="delivery-item__time">{{ formatRelative(d.sentAt) }}</span>
          </div>
          <div class="delivery-item__meta">
            <el-tag :type="d.status==='success'?'success':d.status==='failed'?'danger':'info'" size="small">
              HTTP {{ d.statusCode }}</el-tag>
            <span>{{ d.responseTimeMs }}ms</span>
            <span v-if="d.attempt>0">重试{{ d.attempt }}次</span>
          </div>
          <div v-if="d.error" class="delivery-item__error">{{ d.error }}</div>
        </div>
      </div>
      <el-empty v-else description="暂无投递记录" :image-size="80" />
    </el-dialog>

    <!-- New secret dialog -->
    <el-dialog v-model="store.showNewWebhookModal" title="Webhook 创建成功" width="560px"
      :close-on-click-modal="false" @closed="store.closeNewWebhookModal">
      <div v-if="store.lastCreatedWebhook" class="new-secret-display">
        <el-alert type="warning" :closable="false" show-icon>
          <template #title><strong>请立即保存签名密钥！</strong>关闭后无法再次查看。</template>
        </el-alert>
        <div v-if="store.lastCreatedWebhook.secret" class="new-secret-card">
          <div class="new-secret-card__label">签名密钥 (Secret)</div>
          <div class="new-secret-card__value">
            <code class="new-secret-text">{{ store.lastCreatedWebhook.secret }}</code>
            <el-button type="primary" :icon="CopyDocument" size="small"
              @click="copy(store.lastCreatedWebhook.secret||'')">复制</el-button>
          </div>
        </div>
        <div class="new-secret-info">
          <div><span class="lbl">名称</span><span>{{ store.lastCreatedWebhook.name }}</span></div>
          <div><span class="lbl">URL</span><code>{{ store.lastCreatedWebhook.url }}</code></div>
          <div><span class="lbl">事件</span>
            <el-tag v-for="evt in store.lastCreatedWebhook.events" :key="evt" size="small"
              effect="plain" style="margin-right:4px">{{ getEventLabel(evt) }}</el-tag>
          </div>
        </div>
      </div>
      <template #footer><el-button type="primary" @click="store.closeNewWebhookModal">我已保存</el-button></template>
    </el-dialog>
  </div>
</template>


<script setup lang="ts">
/**
 * Webhook 配置管理器
 * Webhook CRUD, 14 event types, test sending, HMAC signature verification,
 * retry with exponential backoff, delivery history viewer
 */
import { ref, reactive, onMounted, nextTick } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import {
  Link, Plus, CopyDocument, Edit, Delete,
  Promotion, DocumentCopy, VideoPause, VideoPlay,
  CircleCheck, CircleClose,
} from '@element-plus/icons-vue'
import * as api from './api'
import { useWebhooksStore } from './store'
import {
  WEBHOOK_EVENT_GROUPS, WEBHOOK_EVENT_LABELS,
  WEBHOOK_STATUS_LABELS, WEBHOOK_STATUS_TAG_TYPES,
  DEFAULT_RETRY_CONFIG,
} from './types'
import type {
  Webhook, WebhookEventType, WebhookRetryConfig,
  CreateWebhookRequest, TestWebhookRequest,
} from './types'
import type { WebhookEventGroup } from './types'

const store = useWebhooksStore()
const eventGroups = ref<WebhookEventGroup[]>(WEBHOOK_EVENT_GROUPS)

// Create form
const createFormRef = ref<FormInstance>()
const submitting = ref(false)
const createEventError = ref(false)

const createForm = reactive<{
  name: string; url: string; events: WebhookEventType[]
  signatureEnabled: boolean; signatureAlgorithm: string
  retryConfig: WebhookRetryConfig; description: string
}>({
  name: '', url: '', events: [],
  signatureEnabled: true, signatureAlgorithm: 'sha256',
  retryConfig: { ...DEFAULT_RETRY_CONFIG }, description: '',
})

const createRules: FormRules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }, { min: 2, max: 50 }],
  url: [{ required: true, message: '请输入 URL', trigger: 'blur' }, { type: 'url', message: '无效 URL' }],
}

// Edit form
const editFormRef = ref<FormInstance>()
const editForm = reactive<{
  name: string; url: string; events: WebhookEventType[]
  retryConfig: WebhookRetryConfig; description: string
}>({
  name: '', url: '', events: [],
  retryConfig: { ...DEFAULT_RETRY_CONFIG }, description: '',
})

const editRules: FormRules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  url: [{ required: true, message: '请输入 URL', trigger: 'blur' }, { type: 'url' }],
}

// Test
const testEventType = ref<string>('')
const testPayload = ref<string>('')

// === Data Loading ===
async function loadWebhooks(): Promise<void> {
  store.setLoading(true); store.setError(null)
  try {
    const res = await api.getWebhooks()
    store.setWebhooks(res.webhooks, res.total)
  } catch (err: any) { store.setError(err?.message || '加载失败') }
  finally { store.setLoading(false) }
}

async function loadDeliveries(): Promise<void> {
  const w = store.selectedWebhook; if (!w) return
  store.deliveriesLoading = true
  try {
    const res = await api.getWebhookDeliveries(w.id)
    store.setDeliveries(res.deliveries, res.total)
  } catch { ElMessage.error('加载投递记录失败') }
  finally { store.deliveriesLoading = false }
}

// === CRUD ===
function handleCreate(): void {
  createForm.name = ''; createForm.url = ''; createForm.events = []
  createForm.signatureEnabled = true; createForm.signatureAlgorithm = 'sha256'
  createForm.retryConfig = { ...DEFAULT_RETRY_CONFIG }; createForm.description = ''
  createEventError.value = false
  store.openCreateDialog()
}

async function submitCreate(): Promise<void> {
  if (!createFormRef.value) return
  if (createForm.events.length === 0) { createEventError.value = true; return }
  createEventError.value = false
  const valid = await createFormRef.value.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    const data: CreateWebhookRequest = {
      name: createForm.name, url: createForm.url,
      events: [...createForm.events],
      signatureEnabled: createForm.signatureEnabled,
      signatureAlgorithm: createForm.signatureAlgorithm,
      retryConfig: { ...createForm.retryConfig },
      description: createForm.description || undefined,
    }
    const result = await api.createWebhook(data)
    if (result.success && result.webhook) {
      store.addWebhook(result.webhook)
      store.setLastCreatedWebhook(result.webhook)
      store.closeDialogs()
      ElMessage.success('创建成功')
      await nextTick()
    } else { ElMessage.error(result.message || '创建失败') }
  } catch { ElMessage.error('创建失败') }
  finally { submitting.value = false }
}

function initEdit(): void {
  const w = store.editingWebhook; if (!w) return
  editForm.name = w.name; editForm.url = w.url
  editForm.events = [...w.events]
  editForm.retryConfig = { ...w.retryConfig }
  editForm.description = w.description || ''
}

function handleEdit(webhook: Webhook): void { store.openEditDialog(webhook) }

async function submitEdit(): Promise<void> {
  if (!editFormRef.value || !store.editingWebhook) return
  if (editForm.events.length === 0) { ElMessage.warning('请至少选择一个事件'); return }
  const valid = await editFormRef.value.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    const result = await api.updateWebhook(store.editingWebhook.id, {
      name: editForm.name, url: editForm.url,
      events: [...editForm.events],
      retryConfig: { ...editForm.retryConfig },
      description: editForm.description || undefined,
    })
    if (result.success) {
      store.updateWebhookInList({
        ...store.editingWebhook,
        name: editForm.name, url: editForm.url,
        events: [...editForm.events],
        retryConfig: { ...editForm.retryConfig },
        description: editForm.description,
      } as Webhook)
      store.closeDialogs(); ElMessage.success('更新成功')
    } else { ElMessage.error(result.message || '更新失败') }
  } catch { ElMessage.error('更新失败') }
  finally { submitting.value = false }
}

async function handleDelete(webhook: Webhook): Promise<void> {
  try {
    const result = await api.deleteWebhook(webhook.id)
    if (result.success) { store.removeWebhookFromList(webhook.id); ElMessage.success('已删除') }
    else { ElMessage.error(result.message || '删除失败') }
  } catch { ElMessage.error('删除失败') }
}

async function handleToggle(webhook: Webhook): Promise<void> {
  const ns = webhook.status === 'active' ? 'paused' : 'active'
  try {
    const result = await api.updateWebhook(webhook.id, { status: ns })
    if (result.success) {
      store.updateWebhookInList({ ...webhook, status: ns })
      ElMessage.success(ns === 'active' ? '已启用' : '已暂停')
    } else { ElMessage.error(result.message || '操作失败') }
  } catch { ElMessage.error('操作失败') }
}

// === Test Send ===
function handleTest(webhook: Webhook): void {
  testEventType.value = webhook.events[0] || ''
  testPayload.value = ''
  store.openTestDialog(webhook)
}

async function submitTest(): Promise<void> {
  if (!store.selectedWebhook) return
  store.testLoading = true
  try {
    const data: TestWebhookRequest = {
      eventType: testEventType.value as WebhookEventType || undefined,
    }
    if (testPayload.value) {
      try { data.customPayload = JSON.parse(testPayload.value) } catch { /* ignore */ }
    }
    const result = await api.testWebhook(store.selectedWebhook.id, data)
    store.testResult = {
      success: result.success,
      statusCode: result.statusCode,
      responseTimeMs: result.responseTimeMs,
    }
  } catch { ElMessage.error('测试发送失败') }
  finally { store.testLoading = false }
}

function handleDeliveries(webhook: Webhook): void { store.openDeliveryDialog(webhook) }

// === Helpers ===
function getEventLabel(et: string): string {
  return WEBHOOK_EVENT_LABELS[et as WebhookEventType] || et
}
function tagType(s: string): string {
  return WEBHOOK_STATUS_TAG_TYPES[s as any] || 'info'
}
function statusLabel(s: string): string {
  return WEBHOOK_STATUS_LABELS[s as any] || s
}

function isGroupFull(group: WebhookEventGroup, selected: WebhookEventType[]): boolean {
  return group.events.every(e => selected.includes(e))
}
function isGroupPartial(group: WebhookEventGroup, selected: WebhookEventType[]): boolean {
  const hasSome = group.events.some(e => selected.includes(e))
  return hasSome && !group.events.every(e => selected.includes(e))
}
function toggleGroup(arr: WebhookEventType[], group: WebhookEventGroup, checked: boolean): void {
  group.events.forEach(e => {
    const i = arr.indexOf(e)
    if (checked && i === -1) arr.push(e)
    else if (!checked && i !== -1) arr.splice(i, 1)
  })
}
function toggleEvent(arr: WebhookEventType[], evt: WebhookEventType, checked: boolean): void {
  const i = arr.indexOf(evt)
  if (checked && i === -1) arr.push(evt)
  else if (!checked && i !== -1) arr.splice(i, 1)
}

function formatRelative(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const min = Math.floor(diff / 60000)
  if (min < 1) return '刚刚'
  if (min < 60) return min + '分钟前'
  const h = Math.floor(min / 60)
  if (h < 24) return h + '小时前'
  const d = Math.floor(h / 24)
  if (d < 30) return d + '天前'
  return new Date(iso).toLocaleDateString('zh-CN')
}

function copy(text: string): void {
  navigator.clipboard.writeText(text)
    .then(() => ElMessage.success('已复制'))
    .catch(() => ElMessage.error('复制失败'))
}

onMounted(() => { loadWebhooks() })
</script>


<style scoped lang="scss">
.webhook-manager {
  display: flex; flex-direction: column; height: 100%;
  padding: 24px; gap: 20px;
}

.webhook-header {
  display: flex; align-items: center; justify-content: space-between;
  flex-wrap: wrap; gap: 12px;

  &__info { display: flex; flex-direction: column; gap: 4px; }
  &__title {
    display: flex; align-items: center; gap: 8px;
    margin: 0; font-size: 18px; font-weight: 700; color: var(--text-primary);
  }
  &__count { font-size: 13px; color: var(--text-tertiary); }
}

.webhook-event-overview {
  padding: 10px 14px; background: var(--bg-subtle);
  border-radius: var(--radius-sm); display: flex; align-items: center; gap: 10px;

  &__label { font-size: 13px; color: var(--text-secondary); white-space: nowrap; }
  &__tags { display: flex; flex-wrap: wrap; gap: 6px; }
}

.webhook-loading { padding: 20px; background: var(--bg-card); border-radius: var(--radius-md); }
.webhook-error { display: flex; justify-content: center; min-height: 300px; }
.webhook-empty { display: flex; justify-content: center; min-height: 350px;
  background: var(--bg-card); border-radius: var(--radius-md); }

.webhook-table-wrapper {
  background: var(--bg-card); border-radius: var(--radius-md);
  overflow: hidden; box-shadow: var(--shadow-sm);

  :deep(.el-table th) {
    background: var(--bg-subtle); color: var(--text-secondary);
    font-weight: 600; font-size: 13px;
  }
  :deep(.el-table .cell) { display: flex; align-items: center; }
  :deep(.el-table tr) { cursor: pointer; }
}

.webhook-name-cell {
  display: flex; align-items: center; gap: 8px;
  &__text { font-weight: 600; color: var(--text-primary); }
}

.webhook-url-cell { display: flex; align-items: center; gap: 4px; }

.webhook-url {
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 12px; padding: 2px 6px; background: var(--bg-subtle);
  border-radius: 4px; color: var(--text-secondary); max-width: 200px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

.event-tags { display: flex; flex-wrap: wrap; gap: 4px; }
.event-tag { flex-shrink: 0; }

.sig-ind {
  font-weight: 700; color: var(--text-tertiary);
  &.active { color: var(--status-healthy); }
}

.send-stats {
  display: flex; align-items: center; gap: 2px; font-size: 13px;
  &__ok { color: var(--status-healthy); font-weight: 600; }
  &__sep { color: var(--text-tertiary); margin: 0 1px; }
  &__total { color: var(--text-primary); font-weight: 600; }
  &__fail { color: var(--status-offline); margin-left: 4px; font-size: 11px; }
}

.last-sent {
  display: flex; align-items: center; gap: 6px;
  &__dot {
    width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0;
    &.dot-ok { background: var(--status-healthy); }
    &.dot-fail { background: var(--status-offline); }
  }
  span { font-size: 13px; color: var(--text-secondary); }
}

.never-sent { font-size: 13px; color: var(--text-tertiary); font-style: italic; }

.action-buttons {
  display: flex; align-items: center; gap: 4px; justify-content: center;
}

// Event groups
.event-groups { display: flex; flex-direction: column; gap: 12px; }

.event-group {
  padding: 12px; background: var(--bg-subtle);
  border-radius: var(--radius-sm); border: 1px solid var(--border-color);

  &__header { margin-bottom: 8px; font-weight: 600; color: var(--text-primary); }
  &__items { display: flex; flex-wrap: wrap; gap: 12px; padding-left: 24px; }
}

.event-error-tip { margin-top: 8px; font-size: 12px; color: var(--el-color-danger); }

// Advanced section
.advanced-section {
  background: var(--bg-subtle); border-radius: var(--radius-sm);
  padding: 12px 16px; display: flex; flex-direction: column; gap: 10px;
}

.advanced-item {
  display: flex; align-items: center; justify-content: space-between;
  &__left { display: flex; flex-direction: column; gap: 2px; }
  &__label { font-size: 14px; color: var(--text-primary); }
  &__desc { font-size: 12px; color: var(--text-tertiary); }
}

.advanced-row {
  display: flex; gap: 16px;
  &__item {
    display: flex; flex-direction: column; gap: 4px; flex: 1;
  }
  &__label { font-size: 12px; color: var(--text-secondary); }
}

// Test result
.test-result {
  margin-top: 16px; padding: 12px 16px; border-radius: var(--radius-sm);
  display: flex; flex-direction: column; gap: 8px;

  &.test-ok { background: rgba(52,199,89,0.1); border: 1px solid var(--status-healthy); }
  &.test-fail { background: rgba(255,59,48,0.1); border: 1px solid var(--status-offline); }

  &__header {
    display: flex; align-items: center; gap: 8px;
    font-weight: 600; font-size: 14px;
    .test-ok & { color: var(--status-healthy); }
    .test-fail & { color: var(--status-offline); }
  }

  &__details {
    display: flex; flex-direction: column; gap: 4px; font-size: 13px;
    div { display: flex; gap: 12px; }
    div span:first-child { color: var(--text-tertiary); min-width: 60px; }
    div span:last-child { color: var(--text-primary); font-weight: 600; }
  }
}

// Delivery list
.delivery-loading { padding: 24px; min-height: 200px; }

.delivery-list { display: flex; flex-direction: column; gap: 8px; max-height: 400px; overflow-y: auto; }

.delivery-item {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 12px; background: var(--bg-subtle);
  border-radius: var(--radius-sm); font-size: 13px;

  &__info { display: flex; flex-direction: column; gap: 2px; flex: 1; }
  &__event { font-weight: 600; color: var(--text-primary); }
  &__time { font-size: 11px; color: var(--text-tertiary); }
  &__meta { display: flex; align-items: center; gap: 8px; }
  &__response-time { color: var(--text-secondary); font-size: 12px; }
  &__attempt { color: var(--text-tertiary); font-size: 11px; }
  &__error { color: var(--status-offline); font-size: 11px;
    margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    max-width: 300px; }
}

.delivery-dot {
  width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
  &.dot-success { background: var(--status-healthy); }
  &.dot-failed { background: var(--status-offline); }
  &.dot-pending { background: var(--status-warning); }
}

// New secret display
.new-secret-display { display: flex; flex-direction: column; gap: 16px; }

.new-secret-card {
  padding: 16px; background: var(--bg-subtle);
  border-radius: var(--radius-sm); border: 1px dashed var(--brand);

  &__label { font-size: 12px; color: var(--text-tertiary); margin-bottom: 8px; }
  &__value { display: flex; align-items: center; gap: 12px; }
}

.new-secret-text {
  font-family: 'SF Mono', 'Fira Code', monospace; font-size: 13px;
  padding: 8px 12px; background: var(--bg-card); border-radius: 4px;
  word-break: break-all; flex: 1; color: var(--text-primary);
}

.new-secret-info {
  display: flex; flex-direction: column; gap: 8px;
  div { display: flex; align-items: center; gap: 12px; font-size: 13px; }
  .lbl { color: var(--text-tertiary); font-weight: 600; min-width: 50px; }
  code { font-size: 12px; padding: 2px 6px; background: var(--bg-subtle);
    border-radius: 4px; color: var(--text-secondary); }
}

// Responsive
@media (max-width: 1023px) {
  .webhook-manager { padding: 16px; }
  .webhook-header { flex-direction: column; align-items: flex-start; }
  .event-group__items { flex-direction: column; gap: 8px; padding-left: 12px; }
}

@media (max-width: 767px) {
  .webhook-manager { padding: 12px 8px; }
  .webhook-table-wrapper { overflow-x: auto; }
  .advanced-row { flex-direction: column; gap: 8px; }
}
</style>

