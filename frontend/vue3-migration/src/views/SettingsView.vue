<template>
  <div class="settings-view">
    <div class="settings-header">
      <h2>⚙️ 设置</h2>
    </div>

    <div class="settings-content">
      <!-- 外观设置 -->
      <div class="settings-section">
        <h3>🎨 外观</h3>
        <div class="setting-item">
          <div class="setting-label">
            <span>主题模式</span>
            <span class="setting-desc">切换亮色/暗色主题</span>
          </div>
          <el-switch
            v-model="isDark"
            active-text="暗色"
            inactive-text="亮色"
            @change="toggleTheme"
          />
        </div>
      </div>

      <!-- 通知设置 -->
      <div class="settings-section">
        <h3>🔔 通知</h3>
        <div class="setting-item">
          <div class="setting-label">
            <span>推送通知</span>
            <span class="setting-desc">接收系统推送通知</span>
          </div>
          <el-switch v-model="prefs.push_enabled" @change="savePrefs" />
        </div>
        <div class="setting-item">
          <div class="setting-label">
            <span>声音提醒</span>
            <span class="setting-desc">通知时播放声音</span>
          </div>
          <el-switch v-model="prefs.sound_enabled" @change="savePrefs" />
        </div>
        <div class="setting-item">
          <div class="setting-label">
            <span>免打扰时段</span>
            <span class="setting-desc">{{ prefs.quiet_hours_start }} - {{ prefs.quiet_hours_end }}</span>
          </div>
          <el-time-picker
            v-model="quietRange"
            is-range
            range-separator="至"
            start-placeholder="开始"
            end-placeholder="结束"
            format="HH:mm"
            @change="onQuietChange"
          />
        </div>
      </div>

      <!-- 缓存管理 -->
      <div class="settings-section">
        <h3>💾 缓存</h3>
        <div class="setting-item">
          <div class="setting-label">
            <span>清除本地缓存</span>
            <span class="setting-desc">清除浏览器缓存的数据</span>
          </div>
          <el-button type="danger" plain @click="clearCache">清除缓存</el-button>
        </div>
      </div>

      <!-- 关于 -->
      <div class="settings-section">
        <h3>ℹ️ 关于</h3>
        <div class="setting-item">
          <div class="setting-label">
            <span>系统版本</span>
            <span class="setting-desc">伏羲 · 企业知识认知体系</span>
          </div>
          <el-tag>v2.1</el-tag>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import apiClient from '@/api';

const isDark = ref(false);
const prefs = ref({
  push_enabled: true,
  sound_enabled: true,
  quiet_hours_start: '22:00',
  quiet_hours_end: '08:00',
  email_enabled: false,
});
const quietRange = ref<[Date, Date] | null>(null);

function toggleTheme() {
  // 简单切换：通过 localStorage 和 body class
  document.documentElement.classList.toggle('dark', isDark.value);
  localStorage.setItem('fuxi-theme', isDark.value ? 'yin' : 'yang');
}

async function loadPrefs() {
  try {
    const resp = await apiClient.get('/api/notifications/preferences') as Record<string, unknown>;
    if (resp) {
      prefs.value = { ...prefs.value, ...resp };
    }
  } catch { /* use defaults */ }

  // 加载主题
  const savedTheme = localStorage.getItem('fuxi-theme');
  isDark.value = savedTheme === 'yin';
}

async function savePrefs() {
  try {
    await apiClient.put('/api/notifications/preferences', prefs.value);
    ElMessage.success('设置已保存');
  } catch {
    ElMessage.error('保存失败');
  }
}

function onQuietChange(val: [Date, Date] | null) {
  if (val) {
    const pad = (n: number) => String(n).padStart(2, '0');
    prefs.value.quiet_hours_start = `${pad(val[0].getHours())}:${pad(val[0].getMinutes())}`;
    prefs.value.quiet_hours_end = `${pad(val[1].getHours())}:${pad(val[1].getMinutes())}`;
    savePrefs();
  }
}

function clearCache() {
  localStorage.clear();
  ElMessage.success('缓存已清除，请刷新页面');
}

onMounted(loadPrefs);
</script>

<style scoped>
.settings-view {
  max-width: 700px;
  margin: 0 auto;
  padding: 24px;
}

.settings-header h2 {
  font-size: 24px;
  font-weight: 700;
  margin: 0 0 24px;
  color: var(--el-text-color-primary);
}

.settings-section {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 16px;
}

.settings-section h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 16px;
  color: var(--el-text-color-primary);
}

.setting-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 0;
  border-bottom: 1px solid var(--el-border-color-extra-light);
}

.setting-item:last-child {
  border-bottom: none;
}

.setting-label span:first-child {
  font-size: 14px;
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.setting-desc {
  display: block;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 2px;
}
</style>
