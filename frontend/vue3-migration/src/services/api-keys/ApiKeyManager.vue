<template>
  <!--
    伏羲 v2.1 — API Key 管理器
    功能：Key 列表展示、创建/编辑/删除、权限范围设置、
          过期时间管理、使用量统计图表
  -->
  <div class="api-keys-manager">
    <!-- 顶部操作栏 -->
    <div class="api-keys-header">
      <div class="api-keys-header__info">
        <h2 class="api-keys-header__title">
          <el-icon :size="20"><Key /></el-icon>
          API Key 管理
        </h2>
        <span class="api-keys-header__count">
          共 {{ store.total }} 个 Key，{{ store.activeKeyCount }} 个活跃
          <template v-if="store.expiringSoonKeys.length > 0">
            <el-tag size="small" type="warning" effect="plain" style="margin-left: 8px">
              {{ store.expiringSoonKeys.length }} 个即将过期
            </el-tag>
          </template>
        </span>
      </div>
      <el-button type="primary" :icon="Plus" @click="handleCreate">
        创建 API Key
      </el-button>
    </div>

    <!-- 加载状态 -->
    <div v-if="store.loading" class="api-keys-loading">
      <el-skeleton :rows="5" animated />
    </div>

    <!-- 错误状态 -->
    <div v-else-if="store.error" class="api-keys-error">
      <el-result icon="error" title="加载失败" :sub-title="store.error">
        <template #extra>
          <el-button type="primary" @click="loadKeys">重试</el-button>
        </template>
      </el-result>
    </div>

    <!-- Key 列表 -->
    <div v-else-if="store.keys.length > 0" class="api-keys-table-wrapper">
      <el-table
        :data="store.keys"
        stripe
        style="width: 100%"
        :default-sort="{ prop: 'createdAt', order: 'descending' }"
        @row-click="handleRowClick"
      >
        <el-table-column prop="name" label="名称" min-width="180">
          <template #default="{ row }">
            <div class="key-name-cell">
              <el-icon :size="14" color="var(--brand)"><Key /></el-icon>
              <span class="key-name-cell__text">{{ row.name }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="Key 前缀" min-width="180">
          <template #default="{ row }">
            <code class="key-prefix">{{ row.keyPrefix }}***</code>
            <el-button
              link
              type="primary"
              size="small"
              :icon="CopyDocument"
              @click.stop="copyToClipboard(row.keyPrefix)"
              style="margin-left: 8px"
            />
          </template>
        </el-table-column>

        <el-table-column label="权限" min-width="200">
          <template #default="{ row }">
            <div class="permission-tags">
              <el-tag
                v-for="perm in row.permissions"
                :key="perm"
                size="small"
                effect="plain"
                class="permission-tag"
              >
                {{ getPermissionLabel(perm) }}
              </el-tag>
              <el-tooltip
                v-if="row.permissions.length > 3"
                :content="row.permissions.slice(3).map(p => getPermissionLabel(p)).join('、')"
                placement="top"
              >
                <el-tag size="small" effect="plain" type="info" class="permission-tag">
                  +{{ row.permissions.length - 3 }}
                </el-tag>
              </el-tooltip>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag
              :type="getStatusTagType(row.status)"
              size="small"
              effect="light"
            >
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="使用量" width="120" sortable prop="totalRequests">
          <template #default="{ row }">
            <span class="usage-count">{{ formatNumber(row.totalRequests) }}</span>
            <span class="usage-unit">次</span>
          </template>
        </el-table-column>

        <el-table-column label="过期时间" width="180" sortable prop="expiresAt">
          <template #default="{ row }">
            <span v-if="row.expiresAt" class="expiry-date" :class="{ 'expiry-warning': isExpiringSoon(row) }">
              <el-icon v-if="isExpiringSoon(row)" :size="14" color="#FF9500" style="margin-right: 4px">
                <Warning />
              </el-icon>
              {{ formatDate(row.expiresAt) }}
            </span>
            <span v-else class="no-expiry">永不过期</span>
          </template>
        </el-table-column>

        <el-table-column label="最后使用" width="180" sortable prop="lastUsedAt">
          <template #default="{ row }">
            <span v-if="row.lastUsedAt" class="last-used">
              {{ formatRelativeTime(row.lastUsedAt) }}
            </span>
            <span v-else class="never-used">从未使用</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-tooltip content="查看用量" placement="top">
                <el-button
                  link
                  type="primary"
                  :icon="DataLine"
                  size="small"
                  @click.stop="handleViewUsage(row)"
                />
              </el-tooltip>
              <el-tooltip content="编辑" placement="top">
                <el-button
                  link
                  type="primary"
                  :icon="Edit"
                  size="small"
                  @click.stop="handleEdit(row)"
                />
              </el-tooltip>
              <el-tooltip content="撤销 Key" placement="top" v-if="row.status === 'active'">
                <el-button
                  link
                  type="warning"
                  :icon="SwitchButton"
                  size="small"
                  @click.stop="handleRevoke(row)"
                />
              </el-tooltip>
              <el-tooltip content="重新激活" placement="top" v-if="row.status === 'revoked'">
                <el-button
                  link
                  type="success"
                  :icon="CircleCheck"
                  size="small"
                  @click.stop="handleReactivate(row)"
                />
              </el-tooltip>
              <el-tooltip content="删除" placement="top">
                <el-popconfirm
                  title="确定要删除此 API Key 吗？此操作不可恢复。"
                  confirm-button-text="删除"
                  cancel-button-text="取消"
                  confirm-button-type="danger"
                  @confirm="handleDelete(row)"
                >
                  <template #reference>
                    <el-button
                      link
                      type="danger"
                      :icon="Delete"
                      size="small"
                      @click.stop
                    />
                  </template>
                </el-popconfirm>
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 空状态 -->
    <div v-else class="api-keys-empty">
      <el-empty description="暂无 API Key，点击上方按钮创建">
        <template #image>
          <el-icon :size="64" color="var(--text-tertiary)"><Key /></el-icon>
        </template>
      </el-empty>
    </div>

    <!-- =========================== -->
    <!-- 创建/编辑 Key 弹窗          -->
    <!-- =========================== -->
    <el-dialog
      v-model="store.showCreateDialog"
      :title="'创建 API Key'"
      width="580px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form
        ref="createFormRef"
        :model="createForm"
        :rules="createFormRules"
        label-width="90px"
        label-position="top"
      >
        <el-form-item label="Key 名称" prop="name">
          <el-input
            v-model="createForm.name"
            placeholder="例如：生产环境 API、移动端集成"
            maxlength="50"
            show-word-limit
          />
        </el-form-item>

        <el-form-item label="权限范围" prop="permissions">
          <div class="permission-groups">
            <div
              v-for="group in permissionGroups"
              :key="group.label"
              class="permission-group"
            >
              <div class="permission-group__header">
                <el-checkbox
                  :model-value="isGroupFullySelected(group, createForm.permissions)"
                  :indeterminate="isGroupPartiallySelected(group, createForm.permissions)"
                  @change="(val: boolean) => togglePermissions(createForm.permissions, group, val)"
                >
                  {{ group.label }}
                </el-checkbox>
              </div>
              <div class="permission-group__items">
                <el-checkbox
                  v-for="perm in group.permissions"
                  :key="perm"
                  :model-value="createForm.permissions.includes(perm)"
                  size="small"
                  @change="(val: boolean) => togglePermission(createForm.permissions, perm, val)"
                >
                  {{ getPermissionLabel(perm) }}
                </el-checkbox>
              </div>
            </div>
          </div>
          <div v-if="showCreatePermError" class="perm-error-tip">请至少选择一个权限</div>
        </el-form-item>

        <el-form-item label="过期时间" prop="expiresAt">
          <el-radio-group v-model="expiryOption">
            <el-radio value="never">永不过期</el-radio>
            <el-radio value="30days">30 天后</el-radio>
            <el-radio value="90days">90 天后</el-radio>
            <el-radio value="custom">自定义</el-radio>
          </el-radio-group>
          <el-date-picker
            v-if="expiryOption === 'custom'"
            v-model="customExpiryDate"
            type="datetime"
            placeholder="选择过期时间"
            :disabled-date="disabledDate"
            style="margin-top: 12px; width: 100%"
          />
        </el-form-item>

        <el-form-item label="备注">
          <el-input
            v-model="createForm.description"
            type="textarea"
            placeholder="可选，描述此 Key 的用途"
            :rows="2"
            maxlength="200"
            show-word-limit
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="store.closeDialogs">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitCreate">
          创建
        </el-button>
      </template>
    </el-dialog>

    <!-- 编辑 Key 弹窗 -->
    <el-dialog
      v-model="store.showEditDialog"
      :title="'编辑 API Key'"
      width="580px"
      :close-on-click-modal="false"
      destroy-on-close
      @opened="initEditForm"
    >
      <el-form
        v-if="store.editingKey && editForm"
        ref="editFormRef"
        :model="editForm"
        :rules="editFormRules"
        label-width="90px"
        label-position="top"
      >
        <el-form-item label="Key 名称" prop="name">
          <el-input
            v-model="editForm.name"
            placeholder="Key 名称"
            maxlength="50"
            show-word-limit
          />
        </el-form-item>

        <el-form-item label="权限范围" prop="permissions">
          <div class="permission-groups">
            <div
              v-for="group in permissionGroups"
              :key="group.label"
              class="permission-group"
            >
              <div class="permission-group__header">
                <el-checkbox
                  :model-value="isGroupFullySelected(group, editForm.permissions)"
                  :indeterminate="isGroupPartiallySelected(group, editForm.permissions)"
                  @change="(val: boolean) => togglePermissions(editForm.permissions, group, val)"
                >
                  {{ group.label }}
                </el-checkbox>
              </div>
              <div class="permission-group__items">
                <el-checkbox
                  v-for="perm in group.permissions"
                  :key="perm"
                  :model-value="editForm.permissions.includes(perm)"
                  size="small"
                  @change="(val: boolean) => togglePermission(editForm.permissions, perm, val)"
                >
                  {{ getPermissionLabel(perm) }}
                </el-checkbox>
              </div>
            </div>
          </div>
        </el-form-item>

        <el-form-item label="过期时间" prop="expiresAt">
          <el-radio-group v-model="editExpiryOption">
            <el-radio value="never">永不过期</el-radio>
            <el-radio value="30days">30 天后</el-radio>
            <el-radio value="90days">90 天后</el-radio>
            <el-radio value="custom">自定义</el-radio>
          </el-radio-group>
          <el-date-picker
            v-if="editExpiryOption === 'custom'"
            v-model="editCustomExpiryDate"
            type="datetime"
            placeholder="选择过期时间"
            :disabled-date="disabledDate"
            style="margin-top: 12px; width: 100%"
          />
        </el-form-item>

        <el-form-item label="备注">
          <el-input
            v-model="editForm.description"
            type="textarea"
            placeholder="可选，描述此 Key 的用途"
            :rows="2"
            maxlength="200"
            show-word-limit
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="store.closeDialogs">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitEdit">
          保存
        </el-button>
      </template>
    </el-dialog>

    <!-- =========================== -->
    <!-- 新 Key 显示弹窗（一次性）   -->
    <!-- =========================== -->
    <el-dialog
      v-model="store.showNewKeyModal"
      title="API Key 创建成功"
      width="560px"
      :close-on-click-modal="false"
      @closed="store.closeNewKeyModal"
    >
      <div v-if="store.lastCreatedKey" class="new-key-display">
        <el-alert
          type="warning"
          :closable="false"
          show-icon
        >
          <template #title>
            <strong>请立即复制并保存此 API Key！</strong>关闭此窗口后将无法再次查看。
          </template>
        </el-alert>

        <div class="new-key-card">
          <div class="new-key-card__label">API Key</div>
          <div class="new-key-card__value">
            <code class="new-key-text">{{ store.lastCreatedKey.key || '' }}</code>
            <el-button
              type="primary"
              :icon="CopyDocument"
              size="small"
              @click="copyToClipboard(store.lastCreatedKey.key || '')"
            >
              复制
            </el-button>
          </div>
        </div>

        <div class="new-key-info">
          <div class="new-key-info__item">
            <span class="new-key-info__label">名称</span>
            <span>{{ store.lastCreatedKey.name }}</span>
          </div>
          <div class="new-key-info__item">
            <span class="new-key-info__label">权限</span>
            <span>
              <el-tag
                v-for="perm in store.lastCreatedKey.permissions"
                :key="perm"
                size="small"
                effect="plain"
                style="margin-right: 4px"
              >
                {{ getPermissionLabel(perm) }}
              </el-tag>
            </span>
          </div>
          <div class="new-key-info__item">
            <span class="new-key-info__label">过期</span>
            <span>{{ store.lastCreatedKey.expiresAt ? formatDate(store.lastCreatedKey.expiresAt) : '永不过期' }}</span>
          </div>
        </div>
      </div>

      <template #footer>
        <el-button type="primary" @click="store.closeNewKeyModal">
          我已保存，关闭
        </el-button>
      </template>
    </el-dialog>

    <!-- =========================== -->
    <!-- 使用量统计弹窗              -->
    <!-- =========================== -->
    <el-dialog
      v-model="store.showUsageDialog"
      :title="`使用量统计 - ${store.selectedKey?.name || ''}`"
      width="750px"
      :close-on-click-modal="false"
      destroy-on-close
      @opened="loadUsageData"
    >
      <div v-if="store.usageLoading" class="usage-loading">
        <el-skeleton :rows="4" animated />
      </div>
      <div v-else-if="store.usageData" class="usage-content">
        <!-- 汇总卡片 -->
        <div class="usage-summary">
          <div class="usage-summary__card">
            <span class="usage-summary__label">总请求数</span>
            <span class="usage-summary__value">{{ formatNumber(store.usageData.totalRequests) }}</span>
          </div>
          <div class="usage-summary__card">
            <span class="usage-summary__label">总 Token 数</span>
            <span class="usage-summary__value">{{ formatNumber(store.usageData.totalTokens) }}</span>
          </div>
          <div class="usage-summary__card">
            <span class="usage-summary__label">统计周期</span>
            <span class="usage-summary__value">{{ getPeriodLabel(store.usageData.period) }}</span>
          </div>
        </div>

        <!-- 图表 -->
        <div v-if="hasUsageData" class="usage-chart-container">
          <div class="usage-chart-header">
            <span class="usage-chart-title">每日使用量</span>
            <el-radio-group
              v-model="store.usagePeriod"
              size="small"
              @change="loadUsageData"
            >
              <el-radio-button value="day">日</el-radio-button>
              <el-radio-button value="week">周</el-radio-button>
              <el-radio-button value="month">月</el-radio-button>
            </el-radio-group>
          </div>
          <div ref="usageChartRef" class="usage-chart" />
        </div>
        <el-empty v-else description="该 Key 暂无使用数据" :image-size="80" />
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
/**
 * 伏羲 v2.1 — API Key 管理器
 *
 * 提供 API Key 的全生命周期管理：
 * - 创建/编辑/删除 Key
 * - 权限范围配置（分组选择）
 * - 过期时间设置（永不过期/预设/Custom）
 * - 使用量统计图表（ECharts 折线图）
 */
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue';
import { ElMessage, type FormInstance, type FormRules } from 'element-plus';
import {
  Key,
  Plus,
  CopyDocument,
  Edit,
  Delete,
  DataLine,
  SwitchButton,
  CircleCheck,
  Warning,
} from '@element-plus/icons-vue';
import * as echarts from 'echarts/core';
import { LineChart, BarChart } from 'echarts/charts';
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import * as apiKeysApi from './api';
import { useApiKeysStore } from './store';
import {
  PERMISSION_GROUPS,
  API_KEY_PERMISSION_LABELS,
  API_KEY_STATUS_LABELS,
} from './types';
import type {
  ApiKey,
  ApiKeyPermission,
  CreateApiKeyRequest,
  PermissionGroup,
} from './types';

// ───── ECharts 注册 ─────
echarts.use([
  LineChart,
  BarChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  CanvasRenderer,
]);

// ───── Store ─────
const store = useApiKeysStore();

// ───── 权限分组（响应式引用） ─────
const permissionGroups = ref<PermissionGroup[]>(PERMISSION_GROUPS);

// ───── 创建表单 ─────
const createFormRef = ref<FormInstance>();
const submitting = ref(false);
const showCreatePermError = ref(false);
const expiryOption = ref<'never' | '30days' | '90days' | 'custom'>('never');
const customExpiryDate = ref<Date | null>(null);

const createForm = reactive<{
  name: string;
  permissions: ApiKeyPermission[];
  description: string;
}>({
  name: '',
  permissions: [],
  description: '',
});

const createFormRules: FormRules = {
  name: [
    { required: true, message: '请输入 Key 名称', trigger: 'blur' },
    { min: 2, max: 50, message: '名称长度在 2-50 个字符', trigger: 'blur' },
  ],
};

// ───── 编辑表单 ─────
const editFormRef = ref<FormInstance>();
const editForm = reactive<{
  name: string;
  permissions: ApiKeyPermission[];
  description: string;
}>({
  name: '',
  permissions: [],
  description: '',
});
const editExpiryOption = ref<'never' | '30days' | '90days' | 'custom'>('never');
const editCustomExpiryDate = ref<Date | null>(null);

const editFormRules: FormRules = {
  name: [
    { required: true, message: '请输入 Key 名称', trigger: 'blur' },
  ],
};

// ───── 使用量图表 ─────
const usageChartRef = ref<HTMLDivElement | null>(null);
let usageChartInstance: echarts.ECharts | null = null;

const hasUsageData = computed(() => {
  return store.usageData && store.usageData.dailyUsage.length > 0;
});

// ═══════════════════════════════════════════
// 数据加载
// ═══════════════════════════════════════════

async function loadKeys(): Promise<void> {
  store.setLoading(true);
  store.setError(null);
  try {
    const res = await apiKeysApi.getApiKeys();
    store.setKeys(res.keys, res.total);
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : '加载 API Key 列表失败';
    store.setError(msg);
  } finally {
    store.setLoading(false);
  }
}

async function loadUsageData(): Promise<void> {
  const key = store.selectedKey;
  if (!key) return;

  store.usageLoading = true;
  try {
    const data = await apiKeysApi.getApiKeyUsage(key.id, store.usagePeriod);
    store.setUsageData(data);
    await nextTick();
    renderUsageChart();
  } catch {
    ElMessage.error('加载使用量数据失败');
  } finally {
    store.usageLoading = false;
  }
}

// ═══════════════════════════════════════════
// 创建/编辑操作
// ═══════════════════════════════════════════

function handleCreate(): void {
  createForm.name = '';
  createForm.permissions = [];
  createForm.description = '';
  expiryOption.value = 'never';
  customExpiryDate.value = null;
  showCreatePermError.value = false;
  store.openCreateDialog();
}

async function submitCreate(): Promise<void> {
  if (!createFormRef.value) return;

  // 手动验证权限
  if (createForm.permissions.length === 0) {
    showCreatePermError.value = true;
    return;
  }
  showCreatePermError.value = false;

  const valid = await createFormRef.value.validate().catch(() => false);
  if (!valid) return;

  submitting.value = true;
  try {
    const data: CreateApiKeyRequest = {
      name: createForm.name,
      permissions: [...createForm.permissions],
      description: createForm.description || undefined,
      expiresAt: getExpiresAtFromOption(expiryOption.value, customExpiryDate.value),
    };

    const result = await apiKeysApi.createApiKey(data);
    if (result.success && result.key) {
      store.addKey(result.key);
      store.setLastCreatedKey(result.key);
      store.closeDialogs();
      ElMessage.success('API Key 创建成功');
    } else {
      ElMessage.error(result.message || '创建失败');
    }
  } catch {
    ElMessage.error('创建 API Key 失败');
  } finally {
    submitting.value = false;
  }
}

function initEditForm(): void {
  const key = store.editingKey;
  if (!key) return;

  editForm.name = key.name;
  editForm.permissions = [...key.permissions];
  editForm.description = key.description || '';

  if (!key.expiresAt) {
    editExpiryOption.value = 'never';
    editCustomExpiryDate.value = null;
  } else {
    const expires = new Date(key.expiresAt);
    const now = new Date();
    const diffDays = Math.ceil((expires.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
    if (diffDays >= 85 && diffDays <= 95) {
      editExpiryOption.value = '90days';
    } else if (diffDays >= 25 && diffDays <= 35) {
      editExpiryOption.value = '30days';
    } else {
      editExpiryOption.value = 'custom';
      editCustomExpiryDate.value = expires;
    }
  }
}

function handleEdit(key: ApiKey): void {
  store.openEditDialog(key);
}

async function submitEdit(): Promise<void> {
  if (!editFormRef.value || !store.editingKey) return;
  if (editForm.permissions.length === 0) {
    ElMessage.warning('请至少选择一个权限');
    return;
  }

  const valid = await editFormRef.value.validate().catch(() => false);
  if (!valid) return;

  submitting.value = true;
  try {
    const expiresAt = editExpiryOption.value === 'never'
      ? null
      : getExpiresAtFromOption(editExpiryOption.value, editCustomExpiryDate.value);

    const result = await apiKeysApi.updateApiKey(store.editingKey.id, {
      name: editForm.name,
      permissions: [...editForm.permissions],
      description: editForm.description || undefined,
      expiresAt,
    });

    if (result.success) {
      // 乐观更新列表
      const updated = {
        ...store.editingKey,
        name: editForm.name,
        permissions: [...editForm.permissions],
        description: editForm.description,
        expiresAt,
      };
      store.updateKeyInList(updated as ApiKey);
      store.closeDialogs();
      ElMessage.success('API Key 更新成功');
    } else {
      ElMessage.error(result.message || '更新失败');
    }
  } catch {
    ElMessage.error('更新 API Key 失败');
  } finally {
    submitting.value = false;
  }
}

// ═══════════════════════════════════════════
// 删除/撤销/激活操作
// ═══════════════════════════════════════════

async function handleDelete(key: ApiKey): Promise<void> {
  try {
    const result = await apiKeysApi.deleteApiKey(key.id);
    if (result.success) {
      store.removeKeyFromList(key.id);
      ElMessage.success('API Key 已删除');
    } else {
      ElMessage.error(result.message || '删除失败');
    }
  } catch {
    ElMessage.error('删除 API Key 失败');
  }
}

async function handleRevoke(key: ApiKey): Promise<void> {
  try {
    const result = await apiKeysApi.updateApiKey(key.id, { status: 'revoked' });
    if (result.success) {
      store.updateKeyInList({ ...key, status: 'revoked' });
      ElMessage.success('API Key 已撤销');
    } else {
      ElMessage.error(result.message || '操作失败');
    }
  } catch {
    ElMessage.error('撤销 API Key 失败');
  }
}

async function handleReactivate(key: ApiKey): Promise<void> {
  try {
    const result = await apiKeysApi.updateApiKey(key.id, { status: 'active' });
    if (result.success) {
      store.updateKeyInList({ ...key, status: 'active' });
      ElMessage.success('API Key 已重新激活');
    } else {
      ElMessage.error(result.message || '操作失败');
    }
  } catch {
    ElMessage.error('激活 API Key 失败');
  }
}

// ═══════════════════════════════════════════
// 使用量图表渲染
// ═══════════════════════════════════════════

function renderUsageChart(): void {
  if (!usageChartRef.value || !store.usageData) return;

  const data = store.usageData.dailyUsage;
  const dates = data.map((d) => d.date);
  const requests = data.map((d) => d.requests);
  const tokens = data.map((d) => d.tokens);

  if (!usageChartInstance) {
    usageChartInstance = echarts.init(usageChartRef.value);
  }

  usageChartInstance.setOption({
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'var(--fuxi-bg-card)',
      borderColor: 'var(--fuxi-border)',
      textStyle: { color: 'var(--fuxi-text)' },
    },
    legend: {
      data: ['请求数', 'Token 数'],
      bottom: 0,
      textStyle: { color: 'var(--fuxi-text-secondary)' },
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '12%',
      top: '8%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: dates,
      boundaryGap: false,
      axisLine: { lineStyle: { color: 'var(--fuxi-border)' } },
      axisLabel: { color: 'var(--fuxi-text-secondary)', fontSize: 11 },
    },
    yAxis: [
      {
        type: 'value',
        name: '请求数',
        splitLine: { lineStyle: { color: 'var(--fuxi-border)', type: 'dashed' } },
        axisLabel: { color: 'var(--fuxi-text-secondary)', fontSize: 11 },
      },
      {
        type: 'value',
        name: 'Token',
        splitLine: { show: false },
        axisLabel: { color: 'var(--fuxi-text-secondary)', fontSize: 11 },
      },
    ],
    series: [
      {
        name: '请求数',
        type: 'line',
        data: requests,
        smooth: true,
        itemStyle: { color: '#FF6700' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#FF670030' },
            { offset: 1, color: '#FF670005' },
          ]),
        },
      },
      {
        name: 'Token 数',
        type: 'line',
        yAxisIndex: 1,
        data: tokens,
        smooth: true,
        itemStyle: { color: '#3A6B8C' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#3A6B8C30' },
            { offset: 1, color: '#3A6B8C05' },
          ]),
        },
      },
    ],
  });
}

function handleResize(): void {
  usageChartInstance?.resize();
}

// ═══════════════════════════════════════════
// 辅助方法
// ═══════════════════════════════════════════

function getPermissionLabel(perm: ApiKeyPermission): string {
  return API_KEY_PERMISSION_LABELS[perm] || perm;
}

function getStatusLabel(status: string): string {
  return API_KEY_STATUS_LABELS[status as keyof typeof API_KEY_STATUS_LABELS] || status;
}

function getStatusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  const map: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
    active: 'success',
    expired: 'warning',
    revoked: 'danger',
  };
  return map[status] || 'info';
}

function getPeriodLabel(period: string): string {
  const map: Record<string, string> = { day: '日', week: '周', month: '月' };
  return map[period] || period;
}

function isExpiringSoon(key: ApiKey): boolean {
  if (!key.expiresAt || key.status !== 'active') return false;
  const expires = new Date(key.expiresAt).getTime();
  const sevenDays = 7 * 24 * 60 * 60 * 1000;
  return expires - Date.now() <= sevenDays;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatRelativeTime(iso: string): string {
  const now = Date.now();
  const then = new Date(iso).getTime();
  const diff = now - then;
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return '刚刚';
  if (minutes < 60) return `${minutes} 分钟前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小时前`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} 天前`;
  return formatDate(iso);
}

function formatNumber(num: number): string {
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
  return num.toLocaleString();
}

function isGroupFullySelected(group: PermissionGroup, selected: ApiKeyPermission[]): boolean {
  return group.permissions.every((p) => selected.includes(p));
}

function isGroupPartiallySelected(group: PermissionGroup, selected: ApiKeyPermission[]): boolean {
  const hasSome = group.permissions.some((p) => selected.includes(p));
  const hasAll = group.permissions.every((p) => selected.includes(p));
  return hasSome && !hasAll;
}

function togglePermissions(
  target: ApiKeyPermission[],
  group: PermissionGroup,
  checked: boolean,
): void {
  group.permissions.forEach((perm) => {
    const idx = target.indexOf(perm);
    if (checked && idx === -1) {
      target.push(perm);
    } else if (!checked && idx !== -1) {
      target.splice(idx, 1);
    }
  });
}

function togglePermission(
  target: ApiKeyPermission[],
  perm: ApiKeyPermission,
  checked: boolean,
): void {
  const idx = target.indexOf(perm);
  if (checked && idx === -1) {
    target.push(perm);
  } else if (!checked && idx !== -1) {
    target.splice(idx, 1);
  }
}

function getExpiresAtFromOption(
  option: string,
  customDate: Date | null,
): string | null {
  const now = new Date();
  switch (option) {
    case '30days':
      return new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000).toISOString();
    case '90days':
      return new Date(now.getTime() + 90 * 24 * 60 * 60 * 1000).toISOString();
    case 'custom':
      return customDate ? customDate.toISOString() : null;
    default:
      return null;
  }
}

function disabledDate(time: Date): boolean {
  return time.getTime() < Date.now() - 8.64e7;
}

function copyToClipboard(text: string): void {
  navigator.clipboard
    .writeText(text)
    .then(() => ElMessage.success('已复制到剪贴板'))
    .catch(() => ElMessage.error('复制失败'));
}

function handleRowClick(): void {
  // 点击行不做特殊处理，由列内的按钮处理操作
}

function handleViewUsage(key: ApiKey): void {
  store.openUsageDialog(key);
}

// ═══════════════════════════════════════════
// 生命周期
// ═══════════════════════════════════════════

onMounted(() => {
  window.addEventListener('resize', handleResize);
  loadKeys();
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize);
  usageChartInstance?.dispose();
});

watch(
  () => store.usagePeriod,
  () => {
    usageChartInstance?.dispose();
    usageChartInstance = null;
  },
);
</script>

<style scoped lang="scss">
.api-keys-manager {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 24px;
  gap: 20px;
}

// ────── 顶部操作栏 ──────
.api-keys-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;

  &__info {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  &__title {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 0;
    font-size: 18px;
    font-weight: 700;
    color: var(--text-primary);
  }

  &__count {
    font-size: 13px;
    color: var(--text-tertiary);
  }
}

// ────── 加载 / 错误 / 空状态 ──────
.api-keys-loading {
  padding: 20px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
}

.api-keys-error {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 300px;
}

.api-keys-empty {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 350px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
}

// ────── 表格 ──────
.api-keys-table-wrapper {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  overflow: hidden;
  box-shadow: var(--shadow-sm);

  :deep(.el-table th) {
    background: var(--bg-subtle);
    color: var(--text-secondary);
    font-weight: 600;
    font-size: 13px;
  }

  :deep(.el-table tr) {
    cursor: pointer;
  }

  :deep(.el-table .cell) {
    display: flex;
    align-items: center;
  }
}

.key-name-cell {
  display: flex;
  align-items: center;
  gap: 8px;

  &__text {
    font-weight: 600;
    color: var(--text-primary);
  }
}

.key-prefix {
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
  font-size: 12px;
  padding: 2px 6px;
  background: var(--bg-subtle);
  border-radius: 4px;
  color: var(--text-secondary);
}

.permission-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.permission-tag {
  flex-shrink: 0;
}

.usage-count {
  font-weight: 700;
  color: var(--brand);
  font-size: 14px;
}

.usage-unit {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-left: 4px;
}

.expiry-date {
  font-size: 13px;
  color: var(--text-secondary);

  &.expiry-warning {
    color: #FF9500;
    font-weight: 600;
    display: flex;
    align-items: center;
  }
}

.no-expiry {
  font-size: 13px;
  color: var(--text-tertiary);
}

.last-used {
  font-size: 13px;
  color: var(--text-secondary);
}

.never-used {
  font-size: 13px;
  color: var(--text-tertiary);
  font-style: italic;
}

.action-buttons {
  display: flex;
  align-items: center;
  gap: 4px;
  justify-content: center;
}

// ────── 权限分组 ──────
.permission-groups {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.permission-group {
  padding: 12px;
  background: var(--bg-subtle);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-color);

  &__header {
    margin-bottom: 8px;
    font-weight: 600;
    color: var(--text-primary);
  }

  &__items {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    padding-left: 24px;
  }
}

.perm-error-tip {
  margin-top: 8px;
  font-size: 12px;
  color: var(--el-color-danger);
}

// ────── 新 Key 显示 ──────
.new-key-display {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.new-key-card {
  padding: 16px;
  background: var(--bg-subtle);
  border-radius: var(--radius-sm);
  border: 1px dashed var(--brand);

  &__label {
    font-size: 12px;
    color: var(--text-tertiary);
    margin-bottom: 8px;
  }

  &__value {
    display: flex;
    align-items: center;
    gap: 12px;
  }
}

.new-key-text {
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
  font-size: 13px;
  padding: 8px 12px;
  background: var(--bg-card);
  border-radius: 4px;
  word-break: break-all;
  flex: 1;
  color: var(--text-primary);
}

.new-key-info {
  display: flex;
  flex-direction: column;
  gap: 8px;

  &__item {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 13px;
  }

  &__label {
    color: var(--text-tertiary);
    font-weight: 600;
    min-width: 50px;
  }
}

// ────── 使用量统计 ──────
.usage-loading {
  padding: 24px;
  min-height: 200px;
}

.usage-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.usage-summary {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;

  &__card {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 16px 12px;
    background: var(--bg-subtle);
    border-radius: var(--radius-sm);
    gap: 4px;
  }

  &__label {
    font-size: 12px;
    color: var(--text-tertiary);
  }

  &__value {
    font-size: 22px;
    font-weight: 700;
    color: var(--brand);
  }
}

.usage-chart-container {
  background: var(--bg-subtle);
  border-radius: var(--radius-sm);
  padding: 16px;
}

.usage-chart-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.usage-chart-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.usage-chart {
  width: 100%;
  height: 300px;
  min-height: 250px;
}

// ────── 响应式 ──────
@media (max-width: 1023px) {
  .api-keys-manager {
    padding: 16px;
  }

  .usage-summary {
    grid-template-columns: 1fr;
  }

  .api-keys-table-wrapper {
    :deep(.el-table) {
      font-size: 12px;
    }
  }
}

@media (max-width: 767px) {
  .api-keys-manager {
    padding: 12px 8px;
  }

  .api-keys-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .permission-group__items {
    flex-direction: column;
    gap: 8px;
    padding-left: 12px;
  }

  .api-keys-table-wrapper {
    overflow-x: auto;
  }
}
</style>