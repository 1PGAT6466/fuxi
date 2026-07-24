<template>
  <!--
    伏羲 v2.1 — 布局管理器组件
    功能：布局预览、切换、保存、重置、导入/导出
  -->
  <div class="layout-manager" role="region" aria-label="窗口布局管理">
    <!-- ========== 标题栏 ========== -->
    <div class="layout-manager__header">
      <div class="layout-manager__title-row">
        <el-icon :size="18" class="layout-manager__icon"><Grid /></el-icon>
        <span class="layout-manager__title">窗口布局</span>
      </div>
      <div class="layout-manager__actions">
        <el-button
          size="small"
          text
          @click="handleSaveCurrent"
          :loading="isSaving"
        >
          <el-icon :size="14"><Plus /></el-icon>
          保存当前布局
        </el-button>
      </div>
    </div>

    <!-- ========== 显示器信息 ========== -->
    <div class="layout-manager__display-info" v-if="displayConfiguration">
      <el-tooltip :content="displayTooltip" placement="top">
        <div class="display-info-bar">
          <el-icon :size="14"><Monitor /></el-icon>
          <span class="display-info-text">
            {{ displayConfiguration.displays[0]?.width }}×{{ displayConfiguration.displays[0]?.height }}
            @{{ displayConfiguration.displays[0]?.devicePixelRatio }}x
            <template v-if="displayConfiguration.count > 1">
              （共 {{ displayConfiguration.count }} 个显示器）
            </template>
          </span>
        </div>
      </el-tooltip>
      <el-button size="small" text @click="refreshDisplayConfiguration">
        <el-icon :size="14"><Refresh /></el-icon>
      </el-button>
    </div>

    <!-- ========== 布局列表 ========== -->
    <div class="layout-manager__list" v-loading="isLoading">
      <!-- 空状态 -->
      <div v-if="!isLoading && layouts.length === 0" class="layout-manager__empty">
        <el-icon :size="40"><FolderOpened /></el-icon>
        <p class="empty-title">暂无布局方案</p>
        <p class="empty-desc">保存你的第一个窗口布局，随时恢复高效工作状态</p>
      </div>

      <!-- 布局卡片列表 -->
      <TransitionGroup name="layout-list" tag="div" class="layout-list-group">
        <div
          v-for="layout in sortedLayouts"
          :key="layout.id"
          class="layout-card"
          :class="{
            'layout-card--active': layout.id === activeLayoutId,
            'layout-card--default': layout.isDefault,
            'layout-card--incompatible': !isLayoutCompatible(layout.id),
          }"
          @click="handleLayoutClick(layout)"
        >
          <!-- 布局预览缩略图 -->
          <div class="layout-card__preview">
            <div class="preview-canvas" :style="getPreviewStyle(layout)">
              <div
                v-for="(snapshot, idx) in truncateSnapshots(layout.windows)"
                :key="idx"
                class="preview-window"
                :style="getPreviewWindowStyle(snapshot, layout)"
              >
                <span class="preview-window-title">{{ snapshot.title || snapshot.serviceId }}</span>
              </div>
            </div>
          </div>

          <!-- 布局信息 -->
          <div class="layout-card__info">
            <div class="layout-card__name-row">
              <span class="layout-card__name">{{ layout.name }}</span>
              <el-tag
                v-if="layout.id === activeLayoutId"
                size="small"
                type="success"
                effect="dark"
              >
                当前
              </el-tag>
              <el-tag
                v-if="layout.isDefault"
                size="small"
                type="info"
                effect="plain"
              >
                默认
              </el-tag>
            </div>
            <div class="layout-card__meta">
              <span>{{ layout.windows.length }} 个窗口</span>
              <span>·</span>
              <span>{{ formatDate(layout.updatedAt) }}</span>
            </div>
            <div class="layout-card__desc" v-if="layout.description">
              {{ layout.description }}
            </div>
          </div>

          <!-- 操作按钮 -->
          <div class="layout-card__actions" @click.stop>
            <el-tooltip
              :content="layout.id === activeLayoutId ? '当前布局' : '应用此布局'"
              placement="top"
            >
              <el-button
                size="small"
                circle
                :type="layout.id === activeLayoutId ? 'success' : 'primary'"
                :disabled="layout.id === activeLayoutId"
                @click="handleActivate(layout)"
              >
                <el-icon :size="14"><VideoPlay /></el-icon>
              </el-button>
            </el-tooltip>

            <el-dropdown trigger="click" @command="(cmd: string) => handleLayoutCommand(cmd, layout)">
              <el-button size="small" circle>
                <el-icon :size="14"><MoreFilled /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="rename">
                    <el-icon><Edit /></el-icon> 重命名
                  </el-dropdown-item>
                  <el-dropdown-item command="duplicate">
                    <el-icon><CopyDocument /></el-icon> 复制
                  </el-dropdown-item>
                  <el-dropdown-item
                    command="delete"
                    divided
                    :disabled="layout.isDefault"
                  >
                    <el-icon><Delete /></el-icon> 删除
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>

          <!-- 不兼容标签 -->
          <div v-if="!isLayoutCompatible(layout.id)" class="layout-card__incompatible-tag">
            <el-icon :size="12"><WarningFilled /></el-icon>
            显示器已变更
          </div>
        </div>
      </TransitionGroup>
    </div>

    <!-- ========== 底部操作栏 ========== -->
    <div class="layout-manager__footer">
      <div class="footer-left">
        <el-button size="small" text @click="handleExport">
          <el-icon :size="14"><Download /></el-icon>
          导出
        </el-button>
        <el-upload
          ref="importUploadRef"
          :auto-upload="false"
          :show-file-list="false"
          accept=".json"
          :on-change="handleImportFile"
        >
          <el-button size="small" text>
            <el-icon :size="14"><Upload /></el-icon>
            导入
          </el-button>
        </el-upload>
      </div>
      <div class="footer-right">
        <el-button size="small" text type="warning" @click="handleResetLayout" :disabled="!hasDefaultLayout">
          <el-icon :size="14"><RefreshLeft /></el-icon>
          重置为默认
        </el-button>
      </div>
    </div>

    <!-- ========== 保存对话 ========== -->
    <el-dialog
      v-model="showSaveDialog"
      title="保存当前窗口布局"
      width="420px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form :model="saveForm" label-position="top" @submit.prevent="confirmSaveLayout">
        <el-form-item label="布局名称" required>
          <el-input
            v-model="saveForm.name"
            placeholder="例如：日常办公布局"
            maxlength="30"
            show-word-limit
            ref="saveNameInput"
          />
        </el-form-item>
        <el-form-item label="描述（可选）">
          <el-input
            v-model="saveForm.description"
            type="textarea"
            :rows="2"
            placeholder="描述此布局的用途"
            maxlength="100"
            show-word-limit
          />
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="saveForm.setActive">保存后立即激活</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showSaveDialog = false">取消</el-button>
        <el-button type="primary" @click="confirmSaveLayout" :loading="isSaving" :disabled="!saveForm.name.trim()">
          保存
        </el-button>
      </template>
    </el-dialog>

    <!-- ========== 重命名对话 ========== -->
    <el-dialog
      v-model="showRenameDialog"
      title="重命名布局"
      width="380px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-input
        v-model="renameForm.name"
        placeholder="输入新名称"
        maxlength="30"
        show-word-limit
        ref="renameInput"
        @keyup.enter="confirmRename"
      />
      <template #footer>
        <el-button @click="showRenameDialog = false">取消</el-button>
        <el-button type="primary" @click="confirmRename" :disabled="!renameForm.name.trim()">
          确认
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import {
  Grid,
  Plus,
  Monitor,
  Refresh,
  FolderOpened,
  VideoPlay,
  MoreFilled,
  Edit,
  CopyDocument,
  Delete,
  WarningFilled,
  Download,
  Upload,
  RefreshLeft,
} from '@element-plus/icons-vue';
import { useLayoutStore } from '@/stores/layout';
import { useWindowManager } from '@/stores/windowManager';
import type { LayoutPlan, WindowSnapshot } from '@/types/layout';
import layoutService from '@/services/layout-store/LayoutService';

// ============================
// Props & Emits
// ============================

const props = defineProps<{
  /** 组件显隐控制 */
  visible?: boolean;
}>();

const emit = defineEmits<{
  (e: 'apply-snapshots', snapshots: WindowSnapshot[]): void;
  (e: 'close'): void;
}>();

// ============================
// Stores
// ============================

const layoutStore = useLayoutStore();
const windowManager = useWindowManager();

// ============================
// 本地状态
// ============================

const isLoading = ref(false);
const isSaving = ref(false);
const showSaveDialog = ref(false);
const showRenameDialog = ref(false);
const saveNameInput = ref<InstanceType<typeof import('element-plus').ElInput>>();
const renameInput = ref<InstanceType<typeof import('element-plus').ElInput>>();
const importUploadRef = ref();
const renameTargetId = ref<string | null>(null);

const saveForm = ref({
  name: '',
  description: '',
  setActive: true,
});

const renameForm = ref({
  name: '',
});

// ============================
// 计算属性
// ============================

const layouts = computed(() => layoutStore.layouts);
const activeLayoutId = computed(() => layoutStore.activeLayoutId);
const displayConfiguration = computed(() => layoutStore.displayConfiguration);
const hasDefaultLayout = computed(() => layoutStore.defaultLayout !== null);

/** 排序后的布局列表（默认排第一，激活的排第二，按更新时间倒序） */
const sortedLayouts = computed(() => {
  return [...layouts.value].sort((a, b) => {
    if (a.isDefault) return -1;
    if (b.isDefault) return 1;
    if (a.id === activeLayoutId.value) return -1;
    if (b.id === activeLayoutId.value) return 1;
    return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime();
  });
});

const displayTooltip = computed(() => {
  const config = displayConfiguration.value;
  if (config.count <= 1) return '当前显示器配置';
  return config.displays.map((d) => `${d.name}: ${d.width}×${d.height}`).join('\n');
});

// ============================
// 兼容性检查
// ============================

function isLayoutCompatible(layoutId: string): boolean {
  return layoutStore.isLayoutCompatible(layoutId);
}

// ============================
// 预览样式
// ============================

/**
 * 生成布局预览画布样式（等比例缩放）
 */
function getPreviewStyle(layout: LayoutPlan): Record<string, string> {
  const display = layout.displayConfiguration.displays[0];
  if (!display) return { width: '100%', height: '100%' };

  const maxPreviewWidth = 280;
  const maxPreviewHeight = 160;
  const scale = Math.min(
    maxPreviewWidth / display.width,
    maxPreviewHeight / display.height,
  );

  return {
    width: `${Math.round(display.width * scale)}px`,
    height: `${Math.round(display.height * scale)}px`,
  };
}

/**
 * 生成预览窗口样式
 */
function getPreviewWindowStyle(
  snapshot: WindowSnapshot,
  layout: LayoutPlan,
): Record<string, string> {
  const display = layout.displayConfiguration.displays[0];
  if (!display) return {};

  const maxPreviewWidth = 280;
  const maxPreviewHeight = 160;
  const scale = Math.min(
    maxPreviewWidth / display.width,
    maxPreviewHeight / display.height,
  );

  return {
    left: `${Math.round(snapshot.position.x * scale)}px`,
    top: `${Math.round(snapshot.position.y * scale)}px`,
    width: `${Math.round(snapshot.size.width * scale)}px`,
    height: `${Math.round(snapshot.size.height * scale)}px`,
  };
}

/**
 * 截断过多的窗口预览（最多显示 8 个）
 */
function truncateSnapshots(snapshots: WindowSnapshot[]): WindowSnapshot[] {
  return snapshots.slice(0, 8);
}

// ============================
// 事件处理
// ============================

/**
 * 点击布局卡片
 */
function handleLayoutClick(layout: LayoutPlan): void {
  // 默认激活
  handleActivate(layout);
}

/**
 * 激活布局
 */
async function handleActivate(layout: LayoutPlan): Promise<void> {
  if (layout.id === activeLayoutId.value) {
    ElMessage.info('当前已是此布局');
    return;
  }

  // 如果显示器不兼容，先提示
  if (!isLayoutCompatible(layout.id)) {
    try {
      await ElMessageBox.confirm(
        '该布局方案创建时的显示器配置与当前不同，恢复后窗口位置将被自动适配。是否继续？',
        '显示器配置不匹配',
        {
          confirmButtonText: '继续恢复',
          cancelButtonText: '取消',
          type: 'warning',
        },
      );
    } catch {
      return;
    }
  }

  const result = await layoutStore.activateLayout(layout.id);
  if (result.success && result.snapshots.length > 0) {
    emit('apply-snapshots', result.snapshots);
    ElMessage.success(result.message || '布局已激活');
  } else {
    ElMessage.error(result.message || '激活布局失败');
  }
}

/**
 * 保存当前布局
 */
function handleSaveCurrent(): void {
  saveForm.value = {
    name: `我的布局 ${layouts.value.length + 1}`,
    description: '',
    setActive: true,
  };
  showSaveDialog.value = true;
  nextTick(() => {
    saveNameInput.value?.focus();
  });
}

/**
 * 确认保存
 */
async function confirmSaveLayout(): Promise<void> {
  if (!saveForm.value.name.trim()) return;

  isSaving.value = true;
  try {
    const result = await layoutStore.saveLayout(
      saveForm.value.name.trim(),
      windowManager.windows,
      {
        description: saveForm.value.description || undefined,
        setActive: saveForm.value.setActive,
      },
    );

    if (result.success) {
      ElMessage.success(result.message || '布局已保存');
      showSaveDialog.value = false;
    } else {
      ElMessage.error(result.message || '保存失败');
    }
  } finally {
    isSaving.value = false;
  }
}

/**
 * 布局操作菜单
 */
async function handleLayoutCommand(command: string, layout: LayoutPlan): Promise<void> {
  switch (command) {
    case 'rename':
      renameTargetId.value = layout.id;
      renameForm.value.name = layout.name;
      showRenameDialog.value = true;
      nextTick(() => renameInput.value?.focus());
      break;

    case 'duplicate':
      await handleDuplicateLayout(layout);
      break;

    case 'delete':
      await handleDeleteLayout(layout);
      break;
  }
}

/**
 * 确认重命名
 */
async function confirmRename(): Promise<void> {
  if (!renameForm.value.name.trim() || !renameTargetId.value) return;

  try {
    const { updateLayout } = await import('@/api/layout');
    const result = await updateLayout(renameTargetId.value, {
      name: renameForm.value.name.trim(),
    });

    if (result.success) {
      ElMessage.success('布局已重命名');
      await layoutStore.loadLayouts();
    } else {
      ElMessage.error('重命名失败');
    }
  } catch {
    ElMessage.error('重命名失败');
  }

  showRenameDialog.value = false;
  renameTargetId.value = null;
}

/**
 * 复制布局
 */
async function handleDuplicateLayout(layout: LayoutPlan): Promise<void> {
  try {
    const result = await layoutStore.saveLayout(
      `${layout.name} (副本)`,
      windowManager.windows,
      { description: layout.description },
    );
    if (result.success) {
      ElMessage.success('布局已复制');
    }
  } catch {
    ElMessage.error('复制布局失败');
  }
}

/**
 * 删除布局
 */
async function handleDeleteLayout(layout: LayoutPlan): Promise<void> {
  if (layout.isDefault) {
    ElMessage.warning('不能删除默认布局');
    return;
  }

  try {
    await ElMessageBox.confirm(
      `确定要删除布局方案「${layout.name}」吗？此操作不可撤销。`,
      '删除布局',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      },
    );
  } catch {
    return;
  }

  const result = await layoutStore.deleteLayout(layout.id);
  if (result.success) {
    ElMessage.success('布局已删除');
  } else {
    ElMessage.error(result.message || '删除失败');
  }
}

/**
 * 重置为默认布局
 */
async function handleResetLayout(): Promise<void> {
  if (!hasDefaultLayout.value) return;

  try {
    await ElMessageBox.confirm(
      '确定要重置所有窗口为默认布局吗？未保存的窗口位置将丢失。',
      '重置布局',
      {
        confirmButtonText: '重置',
        cancelButtonText: '取消',
        type: 'warning',
      },
    );
  } catch {
    return;
  }

  const defaultLayoutId = layoutStore.defaultLayout!.id;
  const result = await layoutStore.activateLayout(defaultLayoutId);
  if (result.success && result.snapshots.length > 0) {
    emit('apply-snapshots', result.snapshots);
    ElMessage.success('布局已重置为默认');
  }
}

/**
 * 导出布局
 */
async function handleExport(): Promise<void> {
  try {
    const result = await layoutStore.exportLayouts();
    if (result && result.blobs && result.blobs.length > 0) {
      const blob = result.blobs[0]!;
      // 创建下载
      const url = URL.createObjectURL(
        new Blob([blob.content], { type: 'application/json' }),
      );
      const a = document.createElement('a');
      a.href = url;
      a.download = blob.filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      ElMessage.success('布局已导出');
    } else {
      ElMessage.error('导出失败');
    }
  } catch {
    ElMessage.error('导出失败');
  }
}

/**
 * 导入布局文件
 */
async function handleImportFile(uploadFile: any): Promise<void> {
  const file = uploadFile?.raw;
  if (!file) return;

  try {
    const text = await file.text();
    const result = await layoutStore.importLayouts(text, false);

    if (result.success) {
      ElMessage.success(result.message || '布局已导入');
      // 清空上传组件
      importUploadRef.value?.clearFiles();
    } else {
      ElMessage.error(result.message || '导入失败');
    }
  } catch {
    ElMessage.error('文件读取失败');
  }
}

/**
 * 刷新显示器配置
 */
function refreshDisplayConfiguration(): void {
  layoutStore.refreshDisplayConfiguration();
  ElMessage.success('显示器配置已刷新');
}

// ============================
// 工具函数
// ============================

function formatDate(isoString: string): string {
  const d = new Date(isoString);
  const pad = (n: number): string => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// ============================
// 生命周期
// ============================

onMounted(async () => {
  await layoutStore.loadLayouts();
});
</script>

<style scoped lang="scss">
.layout-manager {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--fuxi-bg-card, #ffffff);

  // ========== 标题栏 ==========
  &__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    border-bottom: 1px solid var(--fuxi-border, #eeeeee);
  }

  &__title-row {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  &__icon {
    color: var(--fuxi-primary, #ff6700);
  }

  &__title {
    font-size: 15px;
    font-weight: 600;
    color: var(--fuxi-text, #333333);
  }

  &__actions {
    flex-shrink: 0;
  }

  // ========== 显示器信息 ==========
  &__display-info {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 16px;
    background: var(--fuxi-bg-subtle, #f7f5f0);
    border-bottom: 1px solid var(--fuxi-border, #eeeeee);
  }

  .display-info-bar {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--fuxi-text-secondary, #999999);
    cursor: default;
  }

  .display-info-text {
    font-family: 'SF Mono', 'Cascadia Code', monospace;
    font-size: 11px;
  }

  // ========== 列表 ==========
  &__list {
    flex: 1;
    overflow-y: auto;
    padding: 12px 16px;

    &::-webkit-scrollbar { width: 5px; }
    &::-webkit-scrollbar-thumb {
      background: var(--fuxi-border, #eeeeee);
      border-radius: 3px;
    }
  }

  &__empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 40px 20px;
    color: var(--fuxi-text-tertiary, #cccccc);
    text-align: center;

    .empty-title {
      font-size: 14px;
      font-weight: 500;
      margin: 12px 0 4px;
      color: var(--fuxi-text-secondary, #999999);
    }

    .empty-desc {
      font-size: 12px;
      line-height: 1.5;
    }
  }

  // ========== 布局卡片 ==========
  .layout-list-group {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .layout-card {
    position: relative;
    display: flex;
    gap: 12px;
    padding: 10px 12px;
    border: 1.5px solid var(--fuxi-border, #eeeeee);
    border-radius: 10px;
    cursor: pointer;
    transition: all 0.2s ease;
    background: var(--fuxi-bg-card, #ffffff);

    &:hover {
      border-color: var(--fuxi-primary-light, #ffb380);
      box-shadow: 0 2px 12px rgba(255, 103, 0, 0.08);
    }

    &--active {
      border-color: var(--fuxi-primary, #ff6700);
      background: var(--fuxi-bg-subtle, #fafaf5);
      box-shadow: 0 2px 8px rgba(255, 103, 0, 0.1);
    }

    &--default {
      border-style: dashed;
    }

    &--incompatible {
      border-color: var(--el-color-warning, #e6a23c);
      background: #fefaf6;
    }

    &__preview {
      flex-shrink: 0;
      width: 100px;
      height: 64px;
      border-radius: 4px;
      overflow: hidden;
      background: var(--fuxi-bg-subtle, #f0ede5);
      border: 1px solid var(--fuxi-border, #eeeeee);
    }

    .preview-canvas {
      position: relative;
      transform-origin: top left;
      transform: scale(1);
    }

    .preview-window {
      position: absolute;
      background: var(--fuxi-bg-card, #ffffff);
      border: 1px solid var(--fuxi-primary-light, #ffb380);
      border-radius: 2px;
      display: flex;
      align-items: flex-start;
      padding: 1px 3px;
      overflow: hidden;
    }

    .preview-window-title {
      font-size: 6px;
      color: var(--fuxi-text-tertiary, #cccccc);
      line-height: 1;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    &__info {
      flex: 1;
      min-width: 0;
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    &__name-row {
      display: flex;
      align-items: center;
      gap: 6px;
    }

    &__name {
      font-size: 13px;
      font-weight: 500;
      color: var(--fuxi-text, #333333);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    &__meta {
      font-size: 11px;
      color: var(--fuxi-text-tertiary, #cccccc);
      display: flex;
      gap: 4px;
    }

    &__desc {
      font-size: 11px;
      color: var(--fuxi-text-secondary, #999999);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      max-width: 180px;
    }

    &__actions {
      display: flex;
      align-items: center;
      gap: 4px;
      flex-shrink: 0;
      opacity: 0;
      transition: opacity 0.2s ease;
    }

    &:hover &__actions {
      opacity: 1;
    }

    &--active &__actions {
      opacity: 1;
    }

    &__incompatible-tag {
      position: absolute;
      top: 6px;
      right: 6px;
      display: flex;
      align-items: center;
      gap: 3px;
      font-size: 10px;
      color: var(--el-color-warning, #e6a23c);
      background: rgba(230, 162, 60, 0.1);
      padding: 1px 6px;
      border-radius: 10px;
    }
  }

  // ========== 底部操作栏 ==========
  &__footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 16px;
    border-top: 1px solid var(--fuxi-border, #eeeeee);
  }

  .footer-left {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .footer-right {
    flex-shrink: 0;
  }

  // ========== 列表过渡动画 ==========
  .layout-list-enter-active,
  .layout-list-leave-active {
    transition: all 0.3s ease;
  }

  .layout-list-enter-from {
    opacity: 0;
    transform: translateY(-8px);
  }

  .layout-list-leave-to {
    opacity: 0;
    transform: translateX(20px);
  }

  .layout-list-move {
    transition: transform 0.3s ease;
  }
}

// ============================
// Dialog 内部 Element Plus 全局覆盖
// ============================
:deep(.el-dialog) {
  border-radius: 12px;
}
</style>
