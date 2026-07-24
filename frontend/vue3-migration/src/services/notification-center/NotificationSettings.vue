<!--
  伏羲 v2.1 — 通知设置面板
  P2 增强：推送通知偏好设置
-->
<template>
  <el-drawer
    v-model="visible"
    title="通知设置"
    direction="rtl"
    size="380px"
    :close-on-click-modal="true"
    @closed="$emit('close')"
  >
    <div class="notif-settings">
      <!-- ═══ 推送订阅 ═══ -->
      <section class="notif-settings-section">
        <h3 class="notif-settings-section-title">推送通知</h3>

        <div class="notif-settings-row">
          <div class="notif-settings-row-info">
            <span class="notif-settings-row-label">浏览器推送</span>
            <span class="notif-settings-row-desc">
              通过浏览器接收实时推送通知
            </span>
          </div>
          <el-switch
            v-model="preferences.pushEnabled"
            :disabled="!notifService.isSupported.value"
            @change="handlePushToggle"
          />
        </div>

        <div class="notif-settings-row">
          <div class="notif-settings-row-info">
            <span class="notif-settings-row-label">桌面通知</span>
            <span class="notif-settings-row-desc">
              在桌面显示通知弹窗
            </span>
          </div>
          <el-switch
            v-model="preferences.desktopEnabled"
            :disabled="permissionStatus !== 'granted'"
            @change="handleDesktopToggle"
          />
        </div>

        <!-- 权限状态 -->
        <div class="notif-settings-permission">
          <el-tag
            :type="permissionTagType"
            size="small"
          >
            {{ permissionLabel }}
          </el-tag>
          <el-button
            v-if="permissionStatus !== 'granted'"
            size="small"
            text
            type="primary"
            @click="handleRequestPermission"
          >
            重新请求权限
          </el-button>
        </div>
      </section>

      <!-- ═══ 通知类型 ═══ -->
      <section class="notif-settings-section">
        <h3 class="notif-settings-section-title">通知类型</h3>

        <div class="notif-settings-row">
          <div class="notif-settings-row-info">
            <span class="notif-settings-row-label">信息通知</span>
            <span class="notif-settings-row-desc">系统更新、功能提示等</span>
          </div>
          <el-switch
            v-model="preferences.typeFilters.info"
            @change="handleTypeFilterChange"
          />
        </div>

        <div class="notif-settings-row">
          <div class="notif-settings-row-info">
            <span class="notif-settings-row-label">警告通知</span>
            <span class="notif-settings-row-desc">需要注意的事项</span>
          </div>
          <el-switch
            v-model="preferences.typeFilters.warning"
            @change="handleTypeFilterChange"
          />
        </div>

        <div class="notif-settings-row">
          <div class="notif-settings-row-info">
            <span class="notif-settings-row-label">错误通知</span>
            <span class="notif-settings-row-desc">任务失败、系统错误等</span>
          </div>
          <el-switch
            v-model="preferences.typeFilters.error"
            @change="handleTypeFilterChange"
          />
        </div>

        <div class="notif-settings-row">
          <div class="notif-settings-row-info">
            <span class="notif-settings-row-label">成功通知</span>
            <span class="notif-settings-row-desc">任务完成、操作成功等</span>
          </div>
          <el-switch
            v-model="preferences.typeFilters.success"
            @change="handleTypeFilterChange"
          />
        </div>
      </section>

      <!-- ═══ 免打扰 ═══ -->
      <section class="notif-settings-section">
        <h3 class="notif-settings-section-title">免打扰</h3>

        <div class="notif-settings-row">
          <div class="notif-settings-row-info">
            <span class="notif-settings-row-label">开启免打扰</span>
            <span class="notif-settings-row-desc">
              {{ preferences.doNotDisturb.enabled ? '已开启' : '关闭状态' }}
            </span>
          </div>
          <el-switch v-model="preferences.doNotDisturb.enabled" @change="saveAll" />
        </div>

        <div v-if="preferences.doNotDisturb.enabled" class="notif-settings-dnd-time">
          <div class="notif-settings-row">
            <span class="notif-settings-row-label">开始时间</span>
            <el-time-select
              v-model="startTime"
              :max-time="endTime"
              placeholder="开始"
              start="00:00"
              step="01:00"
              end="23:00"
              size="small"
              style="width: 120px"
              @change="handleDndTimeChange"
            />
          </div>
          <div class="notif-settings-row">
            <span class="notif-settings-row-label">结束时间</span>
            <el-time-select
              v-model="endTime"
              :min-time="startTime"
              placeholder="结束"
              start="01:00"
              step="01:00"
              end="24:00"
              size="small"
              style="width: 120px"
              @change="handleDndTimeChange"
            />
          </div>
        </div>
      </section>

      <!-- ═══ 声音 ═══ -->
      <section class="notif-settings-section">
        <div class="notif-settings-row">
          <div class="notif-settings-row-info">
            <span class="notif-settings-row-label">声音提醒</span>
            <span class="notif-settings-row-desc">收到通知时播放提示音</span>
          </div>
          <el-switch v-model="preferences.soundEnabled" @change="saveAll" />
        </div>
      </section>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue';
import { ElMessage } from 'element-plus';
import { useNotificationStore } from './store';
import { useNotification } from '@/composables/useNotification';
import type { PermissionStatus } from './types';

// ════════════════════════════════
// Props & Emits
// ════════════════════════════════

defineProps<{ visible: boolean }>();
const emit = defineEmits<{ close: [] }>();

// ════════════════════════════════
// Stores & Composable
// ════════════════════════════════

const store = useNotificationStore();
const notifService = useNotification();

// ════════════════════════════════
// 本地状态
// ════════════════════════════════

const preferences = ref({ ...store.preferences });
const startTime = ref(formatHour(preferences.value.doNotDisturb.startHour));
const endTime = ref(formatHour(preferences.value.doNotDisturb.endHour));

// ════════════════════════════════
// 权限状态显示
// ════════════════════════════════

const permissionStatus = computed<PermissionStatus>(() => notifService.permissionStatus.value);

const permissionLabel = computed(() => {
  switch (permissionStatus.value) {
    case 'granted': return '已授权';
    case 'denied': return '已拒绝';
    default: return '未授权';
  }
});

const permissionTagType = computed(() => {
  switch (permissionStatus.value) {
    case 'granted': return 'success';
    case 'denied': return 'danger';
    default: return 'warning';
  }
});

// ════════════════════════════════
// 格式化工具
// ════════════════════════════════

function formatHour(hour: number): string {
  return `${String(hour).padStart(2, '0')}:00`;
}

function parseHour(timeStr: string): number {
  return parseInt(timeStr.split(':')[0], 10);
}

// ════════════════════════════════
// 保存设置
// ════════════════════════════════

function saveAll(): void {
  store.savePreferences({ ...preferences.value });
}

async function handlePushToggle(val: boolean): Promise<void> {
  if (val) {
    // 需要先请求权限再订阅
    const perm = await notifService.requestPermission();
    if (perm !== 'granted') {
      ElMessage.warning('需要先授予通知权限');
      preferences.value.pushEnabled = false;
      return;
    }
    const userId = 'current'; // TODO: 从 auth store 获取真实 userId
    const subscribed = await notifService.subscribe(userId);
    if (!subscribed) {
      ElMessage.error('推送订阅失败');
      preferences.value.pushEnabled = false;
    } else {
      ElMessage.success('推送订阅成功');
      preferences.value.pushEnabled = true;
    }
  } else {
    const userId = 'current';
    await notifService.unsubscribe(userId);
  }
  saveAll();
}

function handleDesktopToggle(_val: boolean): void {
  saveAll();
}

function handleTypeFilterChange(): void {
  saveAll();
}

function handleDndTimeChange(): void {
  preferences.value.doNotDisturb.startHour = parseHour(startTime.value);
  preferences.value.doNotDisturb.endHour = parseHour(endTime.value);
  saveAll();
}

async function handleRequestPermission(): Promise<void> {
  const perm = await notifService.requestPermission();
  if (perm === 'granted') {
    ElMessage.success('通知权限已授予');
  } else if (perm === 'denied') {
    ElMessage.error('通知权限被拒绝，请在浏览器设置中手动开启');
  }
}

// ════════════════════════════════
// 监听 store 同步
// ════════════════════════════════

watch(
  () => store.preferences,
  (newVal) => {
    preferences.value = { ...newVal };
    startTime.value = formatHour(newVal.doNotDisturb.startHour);
    endTime.value = formatHour(newVal.doNotDisturb.endHour);
  },
  { deep: true },
);
</script>

<style scoped lang="scss">
.notif-settings {
  padding: 0 8px;
}

.notif-settings-section {
  margin-bottom: 24px;

  &:last-child {
    margin-bottom: 0;
  }
}

.notif-settings-section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--fuxi-text-tertiary, #cccccc);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin: 0 0 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--fuxi-border, #eeeeee);
}

.notif-settings-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 0;
  min-height: 44px;
}

.notif-settings-row-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
  padding-right: 12px;
}

.notif-settings-row-label {
  font-size: 14px;
  color: var(--fuxi-text, #333333);
  font-weight: 500;
}

.notif-settings-row-desc {
  font-size: 12px;
  color: var(--fuxi-text-tertiary, #cccccc);
}

.notif-settings-permission {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
}

.notif-settings-dnd-time {
  padding: 8px 0 8px 12px;
  background: var(--fuxi-bg-subtle, #f0ede5);
  border-radius: 8px;
  margin-top: 4px;
}
</style>
