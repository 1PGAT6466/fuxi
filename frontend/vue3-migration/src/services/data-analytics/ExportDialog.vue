<template>
  <!--
    伏羲 v2.1 — 导出配置弹窗（增强版）
    支持 PDF / Excel / CSV / JSON 格式
    字段筛选 + 模板管理 + 分享设置
  -->
  <el-dialog
    v-model="localVisible"
    :title="dialogTitle"
    width="640px"
    :close-on-click-modal="false"
    destroy-on-close
    custom-class="export-dialog-wrapper"
  >
    <div class="export-dialog">
      <!-- ───── 模式切换 ───── -->
      <div v-if="showModeSwitch" class="export-mode-switch">
        <el-radio-group v-model="dialogMode" size="small">
          <el-radio-button value="export">
            <el-icon><Download /></el-icon>
            导出数据
          </el-radio-button>
          <el-radio-button value="share">
            <el-icon><Share /></el-icon>
            分享报表
          </el-radio-button>
        </el-radio-group>
      </div>

      <!-- ═══════════════════════════════════════════ -->
      <!-- 导出模式 -->
      <!-- ═══════════════════════════════════════════ -->
      <template v-if="dialogMode === 'export'">
        <!-- 导出格式 -->
        <div class="export-section">
          <label class="export-label">导出格式</label>
          <div class="export-format-grid">
            <div
              v-for="fmt in formatOptions"
              :key="fmt.value"
              class="format-card"
              :class="{ 'format-card--active': config.format === fmt.value }"
              @click="config.format = fmt.value"
            >
              <el-icon :size="24" class="format-card__icon">
                <component :is="fmt.icon" />
              </el-icon>
              <div class="format-card__info">
                <span class="format-card__name">{{ fmt.label }}</span>
                <span class="format-card__desc">{{ fmt.description }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 导出标题 -->
        <div class="export-section">
          <label class="export-label">导出标题（可选）</label>
          <el-input
            v-model="config.title"
            placeholder="输入导出文件标题"
            maxlength="100"
            show-word-limit
            clearable
          />
        </div>

        <!-- 时间范围 -->
        <div class="export-section">
          <label class="export-label">时间范围</label>
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </div>

        <!-- 字段选择 -->
        <div class="export-section">
          <div class="export-label-row">
            <label class="export-label">导出字段</label>
            <el-button text size="small" type="primary" @click="toggleSelectAll">
              {{ isAllFieldsSelected ? '取消全选' : '全选' }}
            </el-button>
          </div>
          <el-checkbox-group v-model="config.fields" class="export-fields">
            <el-checkbox
              v-for="field in allFields"
              :key="field.value"
              :value="field.value"
              :label="field.label"
            />
          </el-checkbox-group>
        </div>

        <!-- 模板快速选择 -->
        <div v-if="templates.length > 0" class="export-section">
          <label class="export-label">使用模板</label>
          <el-select
            v-model="selectedTemplateId"
            placeholder="选择预设模板（可选）"
            clearable
            style="width: 100%"
            @change="handleTemplateSelect"
          >
            <el-option
              v-for="tpl in templates"
              :key="tpl.id"
              :label="tpl.name"
              :value="tpl.id"
            >
              <span>{{ tpl.name }}</span>
              <span class="template-desc">{{ tpl.description }}</span>
            </el-option>
          </el-select>
        </div>
      </template>

      <!-- ═══════════════════════════════════════════ -->
      <!-- 分享模式 -->
      <!-- ═══════════════════════════════════════════ -->
      <template v-else>
        <div v-if="shareResult" class="share-result">
          <div class="share-result__header">
            <el-icon :size="32" color="var(--el-color-success)"><CircleCheckFilled /></el-icon>
            <span class="share-result__title">分享链接已生成</span>
          </div>

          <div class="share-result__url">
            <el-input
              v-model="shareResult.share_url"
              readonly
              class="share-url-input"
            >
              <template #append>
                <el-button @click="handleCopyUrl">
                  <el-icon><CopyDocument /></el-icon>
                  复制
                </el-button>
              </template>
            </el-input>
          </div>

          <div class="share-result__meta">
            <div class="share-meta-item">
              <span class="share-meta-label">权限</span>
              <span class="share-meta-value">
                {{ shareResult.permissions.map(p => permissionLabels[p]).join('、') }}
              </span>
            </div>
            <div class="share-meta-item">
              <span class="share-meta-label">有效期至</span>
              <span class="share-meta-value">
                {{ new Date(shareResult.expires_at).toLocaleString('zh-CN') }}
              </span>
            </div>
            <div class="share-meta-item">
              <span class="share-meta-label">创建时间</span>
              <span class="share-meta-value">
                {{ new Date(shareResult.created_at).toLocaleString('zh-CN') }}
              </span>
            </div>
          </div>

          <el-button type="primary" plain style="width: 100%" @click="resetShare">
            <el-icon><RefreshLeft /></el-icon>
            重新设置
          </el-button>
        </div>

        <template v-else>
          <!-- 权限设置 -->
          <div class="export-section">
            <label class="export-label">分享权限</label>
            <el-checkbox-group v-model="shareConfig.permissions" class="permission-list">
              <el-checkbox
                v-for="(perm, key) in permissionOptions"
                :key="key"
                :value="key"
                :label="perm.label"
                class="permission-item"
              >
                <div class="permission-item__content">
                  <span class="permission-item__label">{{ perm.label }}</span>
                  <span class="permission-item__desc">{{ perm.description }}</span>
                </div>
              </el-checkbox>
            </el-checkbox-group>
          </div>

          <!-- 过期时间 -->
          <div class="export-section">
            <label class="export-label">过期时间</label>
            <el-select v-model="expiryPreset" placeholder="选择过期时间" style="width: 100%">
              <el-option label="1 小时" value="1h" />
              <el-option label="24 小时" value="24h" />
              <el-option label="7 天" value="7d" />
              <el-option label="30 天" value="30d" />
              <el-option label="自定义" value="custom" />
            </el-select>
            <el-date-picker
              v-if="expiryPreset === 'custom'"
              v-model="customExpiryDate"
              type="datetime"
              placeholder="选择过期时间"
              value-format="YYYY-MM-DD HH:mm:ss"
              style="width: 100%; margin-top: 8px"
            />
          </div>

          <!-- 密码保护 -->
          <div class="export-section">
            <label class="export-label">
              密码保护
              <el-switch v-model="enablePassword" size="small" style="margin-left: 8px" />
            </label>
            <el-input
              v-if="enablePassword"
              v-model="shareConfig.password"
              type="password"
              placeholder="设置访问密码（6-20 位）"
              show-password
              maxlength="20"
            />
          </div>

          <!-- 备注 -->
          <div class="export-section">
            <label class="export-label">备注（可选）</label>
            <el-input
              v-model="shareConfig.note"
              type="textarea"
              :rows="2"
              placeholder="添加分享备注…"
              maxlength="200"
              show-word-limit
            />
          </div>
        </template>
      </template>
    </div>

    <!-- ───── 底部操作 ───── -->
    <template #footer>
      <div class="export-footer">
        <el-button @click="handleCancel">取消</el-button>

        <template v-if="dialogMode === 'export'">
          <el-button
            type="primary"
            :loading="exporting"
            :disabled="!canExport"
            @click="handleExport"
          >
            <el-icon><Download /></el-icon>
            导出 {{ config.format.toUpperCase() }}
          </el-button>
        </template>

        <template v-else-if="!shareResult">
          <el-button
            type="primary"
            :loading="sharing"
            :disabled="!canShare"
            @click="handleShare"
          >
            <el-icon><Share /></el-icon>
            生成分享链接
          </el-button>
        </template>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
/**
 * 伏羲 v2.1 — 导出配置弹窗（增强版）
 *
 * 功能：
 * - 多格式导出（PDF/Excel/CSV/JSON）
 * - 字段筛选 + 全选/取消全选
 * - 报表模板快速选择
 * - 报表分享（权限控制/过期时间/密码保护）
 * - 分享链接复制
 */
import { ref, reactive, computed, watch, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import {
  Download,
  Share,
  CircleCheckFilled,
  CopyDocument,
  RefreshLeft,
  Document,
  Grid,
  List,
  DataBoard,
} from '@element-plus/icons-vue';
import { exportService, ALL_EXPORT_FIELDS, EXPORT_FORMAT_CONFIG, SHARE_PERMISSION_CONFIG } from './ExportService';
import type {
  ExportFormat,
  SharePermission,
  ShareResponse,
  ReportTemplate,
} from './types';

// ───── Props & Emits ─────

const props = defineProps<{
  modelValue: boolean;
  defaultFormat?: ExportFormat;
  /** 报表 ID（分享时需要） */
  reportId?: string;
  /** 是否显示模式切换（导出/分享） */
  showModeSwitch?: boolean;
  /** 默认模式 */
  defaultMode?: 'export' | 'share';
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void;
  (e: 'exported', res: { download_url: string; filename: string; format: ExportFormat }): void;
  (e: 'shared', res: ShareResponse): void;
}>();

// ───── 对话框状态 ─────

const localVisible = ref(props.modelValue);
const dialogMode = ref<'export' | 'share'>(props.defaultMode || 'export');
const dialogTitle = computed(() => (dialogMode.value === 'export' ? '数据导出' : '分享报表'));

watch(() => props.modelValue, (val) => { localVisible.value = val; });
watch(localVisible, (val) => { emit('update:modelValue', val); });

// ───── 格式选项 ─────

const formatOptions = computed(() =>
  Object.entries(EXPORT_FORMAT_CONFIG).map(([value, config]) => ({
    value: value as ExportFormat,
    label: config.label,
    icon: config.icon,
    description: config.description,
  })),
);

// ───── 字段选择 ─────

const allFields = ALL_EXPORT_FIELDS.map((f) => ({ ...f }));

const config = reactive({
  format: props.defaultFormat || 'csv' as ExportFormat,
  fields: allFields.slice(0, 6).map((f) => f.value) as string[],
  title: '',
  date_range: {} as { start?: string; end?: string },
  template_id: undefined as string | undefined,
});

const dateRange = ref<[string, string] | null>(null);

const isAllFieldsSelected = computed(() => config.fields.length === allFields.length);
const canExport = computed(() => config.fields.length > 0);

function toggleSelectAll() {
  if (isAllFieldsSelected.value) {
    config.fields = [];
  } else {
    config.fields = allFields.map((f) => f.value);
  }
}

watch(dateRange, (val) => {
  if (val) {
    config.date_range = { start: val[0], end: val[1] };
  } else {
    config.date_range = {};
  }
});

// ───── 模板 ─────

const templates = ref<ReportTemplate[]>([]);
const selectedTemplateId = ref<string>();

function handleTemplateSelect(templateId: string | '') {
  if (!templateId) {
    config.template_id = undefined;
    return;
  }
  const tpl = templates.value.find((t) => t.id === templateId);
  if (tpl) {
    config.template_id = tpl.id;
    config.format = tpl.default_format;
    config.fields = [...tpl.default_fields];
  }
}

// ───── 导出操作 ─────

const exporting = ref(false);

async function handleExport() {
  if (!config.fields.length) {
    ElMessage.warning('请至少选择一个导出字段');
    return;
  }

  exporting.value = true;
  try {
    const res = await exportService.export(config);
    ElMessage.success(`导出成功：${res.filename}（${(res.size / 1024).toFixed(1)} KB）`);
    emit('exported', {
      download_url: res.download_url,
      filename: res.filename,
      format: res.format,
    });
    localVisible.value = false;
  } catch (err: any) {
    ElMessage.error(err?.message || '导出失败，请重试');
  } finally {
    exporting.value = false;
  }
}

// ───── 分享配置 ─────

const shareConfig = reactive({
  permissions: ['view'] as SharePermission[],
  password: '',
  note: '',
  expires_at: '',
});

const enablePassword = ref(false);
const expiryPreset = ref('7d');
const customExpiryDate = ref<string | null>(null);
const sharing = ref(false);
const shareResult = ref<ShareResponse | null>(null);

const permissionOptions = computed(() =>
  Object.entries(SHARE_PERMISSION_CONFIG).map(([key, val]) => ({
    key: key as SharePermission,
    label: val.label,
    description: val.description,
  })),
);

const permissionLabels: Record<SharePermission, string> = {
  view: '查看',
  edit: '编辑',
  download: '下载',
};

const canShare = computed(() => {
  if (!shareConfig.permissions.length) return false;
  if (enablePassword.value && (!shareConfig.password || shareConfig.password.length < 6)) return false;
  return true;
});

/** 计算过期时间 */
function computeExpiresAt(): string {
  if (expiryPreset.value === 'custom' && customExpiryDate.value) {
    return new Date(customExpiryDate.value).toISOString();
  }
  const now = new Date();
  const durations: Record<string, number> = {
    '1h': 60 * 60 * 1000,
    '24h': 24 * 60 * 60 * 1000,
    '7d': 7 * 24 * 60 * 60 * 1000,
    '30d': 30 * 24 * 60 * 60 * 1000,
  };
  const ms = durations[expiryPreset.value] || durations['7d'];
  return new Date(now.getTime() + ms).toISOString();
}

async function handleShare() {
  if (!props.reportId) {
    ElMessage.warning('请先生成报表');
    return;
  }
  if (!shareConfig.permissions.length) {
    ElMessage.warning('请至少选择一种分享权限');
    return;
  }

  sharing.value = true;
  try {
    const res = await exportService.shareReport({
      report_id: props.reportId,
      permissions: shareConfig.permissions,
      expires_at: computeExpiresAt(),
      password: enablePassword.value ? shareConfig.password : undefined,
      note: shareConfig.note || undefined,
    });

    if (res) {
      shareResult.value = res;
      emit('shared', res);
      ElMessage.success('分享链接已生成');
    } else {
      ElMessage.error('分享失败，请重试');
    }
  } catch (err: any) {
    ElMessage.error(err?.message || '分享失败，请重试');
  } finally {
    sharing.value = false;
  }
}

async function handleCopyUrl() {
  if (!shareResult.value) return;
  const ok = await exportService.copyToClipboard(shareResult.value.share_url);
  if (ok) {
    ElMessage.success('链接已复制到剪贴板');
  } else {
    ElMessage.warning('复制失败，请手动复制');
  }
}

function resetShare() {
  shareResult.value = null;
  shareConfig.permissions = ['view'];
  shareConfig.password = '';
  shareConfig.note = '';
  enablePassword.value = false;
  expiryPreset.value = '7d';
  customExpiryDate.value = null;
}

function handleCancel() {
  if (shareResult.value) {
    resetShare();
  }
  localVisible.value = false;
}

// ───── 初始化 ─────

onMounted(async () => {
  // 加载已有模板
  templates.value = await exportService.getTemplates();
});
</script>

<style scoped lang="scss">
// ═══════════════════════════════════════════
// 容器
// ═══════════════════════════════════════════

.export-dialog {
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
  max-height: 60vh;
  overflow-y: auto;
  padding-right: 4px;

  &::-webkit-scrollbar {
    width: 5px;
  }
  &::-webkit-scrollbar-thumb {
    background: var(--fuxi-border);
    border-radius: 3px;
  }
}

// ═══════════════════════════════════════════
// 模式切换
// ═══════════════════════════════════════════

.export-mode-switch {
  display: flex;
  justify-content: center;
  padding-bottom: var(--space-sm);
  border-bottom: 1px solid var(--fuxi-border);
}

// ═══════════════════════════════════════════
// 区块
// ═══════════════════════════════════════════

.export-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.export-label {
  font-weight: 600;
  font-size: var(--font-size-caption);
  color: var(--fuxi-text);
  display: flex;
  align-items: center;
}

.export-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;

  .export-label {
    margin-bottom: 0;
  }
}

// ═══════════════════════════════════════════
// 格式卡片
// ═══════════════════════════════════════════

.export-format-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-sm);

  @media (max-width: 480px) {
    grid-template-columns: 1fr;
  }
}

.format-card {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-sm) var(--space-md);
  border: 2px solid var(--fuxi-border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.2s ease;
  background: var(--fuxi-bg-card);

  &:hover {
    border-color: var(--fuxi-primary-light);
    background: var(--fuxi-bg-subtle);
  }

  &--active {
    border-color: var(--fuxi-primary);
    background: var(--fuxi-primary-light);
    box-shadow: 0 0 0 2px rgba(var(--fuxi-primary-rgb), 0.15);
  }

  &__icon {
    color: var(--fuxi-primary);
    flex-shrink: 0;
  }

  &__info {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  &__name {
    font-weight: 600;
    font-size: var(--font-size-caption);
    color: var(--fuxi-text);
  }

  &__desc {
    font-size: var(--font-size-small);
    color: var(--fuxi-text-tertiary);
  }
}

// ═══════════════════════════════════════════
// 字段网格
// ═══════════════════════════════════════════

.export-fields {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-sm);

  @media (max-width: 400px) {
    grid-template-columns: repeat(2, 1fr);
  }
}

// ═══════════════════════════════════════════
// 模板选择
// ═══════════════════════════════════════════

.template-desc {
  font-size: var(--font-size-small);
  color: var(--fuxi-text-tertiary);
  margin-left: var(--space-sm);
}

// ═══════════════════════════════════════════
// 权限列表
// ═══════════════════════════════════════════

.permission-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.permission-item {
  display: flex;
  align-items: flex-start;

  &__content {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  &__label {
    font-weight: 600;
    font-size: var(--font-size-caption);
    color: var(--fuxi-text);
  }

  &__desc {
    font-size: var(--font-size-small);
    color: var(--fuxi-text-tertiary);
  }
}

// ═══════════════════════════════════════════
// 分享结果
// ═══════════════════════════════════════════

.share-result {
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);

  &__header {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-sm);
  }

  &__title {
    font-size: var(--font-size-card-title);
    font-weight: 600;
    color: var(--fuxi-text);
  }

  &__url {
    .share-url-input :deep(.el-input__inner) {
      font-family: monospace;
      font-size: var(--font-size-small);
    }
  }

  &__meta {
    display: flex;
    flex-direction: column;
    gap: var(--space-sm);
    padding: var(--space-md);
    background: var(--fuxi-bg-subtle);
    border-radius: var(--radius-md);
  }
}

.share-meta-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.share-meta-label {
  font-size: var(--font-size-caption);
  color: var(--fuxi-text-secondary);
}

.share-meta-value {
  font-size: var(--font-size-caption);
  font-weight: 600;
  color: var(--fuxi-text);
}

// ═══════════════════════════════════════════
// 底部
// ═══════════════════════════════════════════

.export-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-sm);
}
</style>

<style lang="scss">
// 非 scoped 样式 — 用于 el-dialog 自定义类
.export-dialog-wrapper {
  .el-dialog__body {
    max-height: 65vh;
    overflow-y: auto;
  }
}
</style>
