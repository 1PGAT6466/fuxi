<template>
  <!--
    伏羲 v2.1 — 九宫格动态仪表盘首页
    后天八卦 3×3 布局，每个宫格是「活卡片」
    读取 /api/symbols/status 获取器官状态
  -->
  <div class="home-view">
    <!-- 平台标题 -->
    <div class="home-header">
      <div class="home-brand">
        <span class="home-brand__icon">☯</span>
        <h1 class="home-brand__title">伏羲 v2.1</h1>
      </div>
      <p class="home-brand__subtitle">八卦九宫 · 万象归一</p>
    </div>

    <!-- 3×3 九宫格 -->
    <div class="bagua-dashboard" role="grid" aria-label="伏羲八卦九宫仪表面板">
      <template v-for="pos in 9" :key="pos">
        <!-- 中宫 (pos=5) — 特殊渲染 -->
        <div
          v-if="pos === 5"
          class="bagua-palace bagua-palace--center"
          role="gridcell"
          tabindex="0"
          :aria-label="`中宫·胃·首页中枢`"
          @click="navigateTo('/')"
          @keydown.enter="navigateTo('/')"
          @keydown.space.prevent="navigateTo('/')"
        >
          <div class="bagua-palace__center-inner">
            <!-- 太极旋转图标 -->
            <div class="bagua-palace__taiji-spin">
              <span class="taiji-spin__symbol">☯</span>
            </div>
            <div class="bagua-palace__center-label">中宫</div>
            <div class="bagua-palace__center-organ">胃</div>
            <div class="bagua-palace__center-stats">
              <div class="center-stat">
                <span class="center-stat__num">{{ zhonggongData.activeWindowCount }}</span>
                <span class="center-stat__label">活跃窗口</span>
              </div>
              <div class="center-stat__divider" />
              <div class="center-stat">
                <span class="center-stat__num">{{ zhonggongData.pendingTaskCount }}</span>
                <span class="center-stat__label">待处理</span>
              </div>
            </div>
            <span class="bagua-palace__center-shortcut">⌘5</span>
          </div>
        </div>

        <!-- 普通卦格 -->
        <div
          v-else
          class="bagua-palace"
          :class="{
            'bagua-palace--active': isCellActive(pos),
            'bagua-palace--warning': isCellWarning(pos),
            'bagua-palace--error': isCellError(pos),
          }"
          :style="getCellVars(pos)"
          role="gridcell"
          tabindex="0"
          :aria-label="`${getCellLabel(pos)}卦·${getCellOrgan(pos)}·${getCellFunction(pos)}`"
          @click="navigateTo(getCellRoute(pos))"
          @keydown.enter="navigateTo(getCellRoute(pos))"
          @keydown.space.prevent="navigateTo(getCellRoute(pos))"
        >
          <!-- 状态指示灯（右上角） -->
          <div class="bagua-palace__status">
            <span
              class="status-dot"
              :class="`status-dot--${getCellStatus(pos)}`"
              :title="statusLabel(getCellStatus(pos))"
            />
          </div>

          <!-- 左侧卦色装饰线 -->
          <div class="bagua-palace__accent" />

          <!-- 卦符号 -->
          <div class="bagua-palace__symbol">{{ getCellSymbol(pos) }}</div>
          <!-- 卦名 -->
          <div class="bagua-palace__name">{{ getCellLabel(pos) }}</div>
          <!-- 器官（副标题） -->
          <div class="bagua-palace__organ">{{ getCellOrgan(pos) }}</div>
          <!-- 功能描述 -->
          <div class="bagua-palace__function">{{ getCellFunction(pos) }}</div>

          <!-- 活跃任务角标 -->
          <div v-if="getCellTaskCount(pos) > 0" class="bagua-palace__badge">
            {{ getCellTaskCount(pos) }}
          </div>

          <!-- 快捷键提示 -->
          <span class="bagua-palace__shortcut">{{ getCellShortcut(pos) }}</span>
        </div>
      </template>
    </div>

    <!-- 底部提示 -->
    <div class="home-footer">
      <span>⌘K 打开伏羲令搜索</span>
      <span class="home-footer__dot">·</span>
      <span>⌘1-9 切换宫位</span>
      <span class="home-footer__dot">·</span>
      <span>⌘/ 快捷键帮助</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue';
import { useRouter } from 'vue-router';
import { fetchSymbolStatus, getMockSymbolStatus } from '@/api/symbols';
import { BAGUA_GRID, type TrigramStatus } from '@/constants/bagua';
import type { OrganStatus } from '@/constants/bagua';

const router = useRouter();

// ── 状态 ──
const statusMap = ref<Record<string, OrganStatus>>({});
const zhonggongData = ref({
  activeWindowCount: 0,
  pendingTaskCount: 0,
  evolutionLevel: 1,
  evolutionProgress: 0,
});

/** 定时刷新句柄 */
let refreshTimer: ReturnType<typeof setInterval> | null = null;

/** 拉取并更新器官状态 */
async function loadStatus(): Promise<void> {
  try {
    const res = await fetchSymbolStatus();
    for (const s of res.data.statuses) {
      statusMap.value[s.trigramId] = s;
    }
    zhonggongData.value = res.data.zhonggong;
  } catch {
    // 后端不可用时使用 mock 数据
    const mock = getMockSymbolStatus();
    for (const s of mock.data.statuses) {
      statusMap.value[s.trigramId] = s;
    }
    zhonggongData.value = mock.data.zhonggong;
  }
}

// ── 加载器官状态 + 定时刷新 ──
onMounted(async () => {
  await loadStatus();
  // 每 30 秒自动刷新一次状态
  refreshTimer = setInterval(loadStatus, 30_000);
});

onBeforeUnmount(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer);
    refreshTimer = null;
  }
});

// ── 工具方法 ──
function getCellByPos(pos: number) {
  return BAGUA_GRID[pos];
}

function getCellSymbol(pos: number): string {
  return getCellByPos(pos)?.symbol ?? '?';
}

function getCellLabel(pos: number): string {
  return getCellByPos(pos)?.label ?? '?';
}

function getCellOrgan(pos: number): string {
  return getCellByPos(pos)?.organ ?? '';
}

function getCellFunction(pos: number): string {
  return getCellByPos(pos)?.functionDesc ?? '';
}

function getCellRoute(pos: number): string {
  return getCellByPos(pos)?.route ?? '/';
}

function getCellShortcut(pos: number): string {
  return `⌘${pos}`;
}

function getCellStatus(pos: number): TrigramStatus {
  const cell = getCellByPos(pos);
  if (!cell) return 'healthy';
  return statusMap.value[cell.id]?.status ?? 'healthy';
}

function getCellTaskCount(pos: number): number {
  const cell = getCellByPos(pos);
  if (!cell) return 0;
  return statusMap.value[cell.id]?.activeTaskCount ?? 0;
}

function isCellActive(pos: number): boolean {
  return getCellTaskCount(pos) > 0;
}

function isCellWarning(pos: number): boolean {
  return getCellStatus(pos) === 'warning';
}

function isCellError(pos: number): boolean {
  return getCellStatus(pos) === 'error';
}

function getCellVars(pos: number) {
  const cell = getCellByPos(pos);
  if (!cell) return {};
  return {
    '--cell-color': cell.color,
  };
}

function statusLabel(status: TrigramStatus): string {
  const map: Record<TrigramStatus, string> = {
    healthy: '正常',
    warning: '活跃',
    error: '异常',
    offline: '离线',
  };
  return map[status];
}

function navigateTo(route: string): void {
  router.push(route);
}
</script>

<style scoped>
/* ═══════════════════════════════════════════
   HomeView v2.1 — 九宫格仪表盘
   小米简约 · 八卦呼吸动画 · 状态驱动
   ═══════════════════════════════════════════ */

.home-view {
  max-width: 1000px;
  margin: 0 auto;
  padding: 40px 24px 48px;
}

/* ── 页头 ── */
.home-header {
  text-align: center;
  margin-bottom: 40px;
}

.home-brand {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
}

.home-brand__icon {
  font-size: 36px;
  color: var(--fuxi-primary, #ff6700);
  animation: taiji-spin 8s linear infinite;
}

@keyframes taiji-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.home-brand__title {
  font-size: 36px;
  font-weight: 800;
  color: var(--fuxi-text, #333333);
  margin: 0;
  letter-spacing: 0.06em;
}

.home-brand__subtitle {
  font-size: 14px;
  color: var(--fuxi-text-tertiary, #cccccc);
  margin-top: 6px;
  letter-spacing: 0.15em;
}

/* ═══════════════════════════════════════════
   3×3 Grid
   ═══════════════════════════════════════════ */
.bagua-dashboard {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  grid-template-rows: repeat(3, auto);
  gap: 20px;
  min-height: 640px;
}

/* ═══════════════════════════════════════════
   卦格卡片
   ═══════════════════════════════════════════ */
.bagua-palace {
  position: relative;
  background: var(--fuxi-bg-card, #ffffff);
  border-radius: var(--radius-lg, 12px);
  box-shadow: 0 2px 16px rgba(255, 103, 0, 0.06);
  border: 1.5px solid transparent;
  padding: 24px 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
  overflow: hidden;
  user-select: none;
  -webkit-tap-highlight-color: transparent;
  min-height: 170px;

  /* 活卡片呼吸动画 (2s 周期) */
  animation: palace-breathe 2s ease-in-out infinite;

  transition:
    transform 0.35s cubic-bezier(0.25, 0.46, 0.45, 0.94),
    box-shadow 0.35s cubic-bezier(0.25, 0.46, 0.45, 0.94),
    border-color 0.35s cubic-bezier(0.25, 0.46, 0.45, 0.94);
}

/* ── 活卡片呼吸动画（opacity 0.85-1.0, 2s） ── */
@keyframes palace-breathe {
  0%, 100% { opacity: 0.85; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.008); }
}

/* ── Hover 磁性上浮 ── */
.bagua-palace:hover {
  transform: translateY(-4px);
  box-shadow: 0 6px 28px rgba(255, 103, 0, 0.1);
  border-color: rgba(255, 103, 0, 0.15);
}

.bagua-palace:active {
  transform: translateY(-2px) scale(0.98);
  transition: transform 100ms ease;
}

/* ── 活跃状态（暖橙呼吸光晕 2s） ── */
.bagua-palace--active {
  animation: palace-glow 2s ease-in-out infinite;
  border-color: rgba(255, 103, 0, 0.2);
}

@keyframes palace-glow {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(255, 103, 0, 0);
  }
  50% {
    box-shadow: 0 0 28px 6px rgba(255, 103, 0, 0.15);
  }
}

.bagua-palace--warning {
  border-color: rgba(255, 149, 0, 0.2);
}

.bagua-palace--error {
  border-color: rgba(255, 59, 48, 0.2);
  animation: palace-glow 1.5s ease-in-out infinite;
}

/* ── 状态指示灯 ── */
.bagua-palace__status {
  position: absolute;
  top: 12px;
  right: 12px;
}

.status-dot {
  display: block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  transition: background 0.3s ease, box-shadow 0.3s ease;
}

.status-dot--healthy {
  background: #34C759;
  box-shadow: 0 0 6px rgba(52, 199, 89, 0.4);
}

.status-dot--warning {
  background: #FF9500;
  box-shadow: 0 0 8px rgba(255, 149, 0, 0.5);
  animation: dot-pulse 1.8s ease-in-out infinite;
}

.status-dot--error {
  background: #FF3B30;
  box-shadow: 0 0 8px rgba(255, 59, 48, 0.5);
  animation: dot-pulse 1s ease-in-out infinite;
}

.status-dot--offline {
  background: #D1D1D6;
  box-shadow: none;
}

@keyframes dot-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* ── 左侧卦色装饰线 ── */
.bagua-palace__accent {
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 4px;
  height: 36px;
  border-radius: 0 2px 2px 0;
  background: var(--cell-color, #CCCCCC); /* 阳模式禁用文字色 */
  transition: height 0.35s ease;
}

.bagua-palace:hover .bagua-palace__accent {
  height: 48px;
}

/* ── 卦符号 ── */
.bagua-palace__symbol {
  font-size: 28px;
  font-weight: 600;
  line-height: 1;
  color: var(--fuxi-text, #333333);
  transition: transform 0.35s ease;
}

.bagua-palace:hover .bagua-palace__symbol {
  transform: scale(1.15);
}

/* ── 卦名 ── */
.bagua-palace__name {
  font-size: 18px;
  font-weight: 700;
  color: var(--fuxi-text, #333333);
  letter-spacing: 0.06em;
}

/* ── 器官名（副标题） ── */
.bagua-palace__organ {
  font-size: 13px;
  color: var(--fuxi-text-secondary, #999999);
  letter-spacing: 0.04em;
}

/* ── 功能描述 ── */
.bagua-palace__function {
  font-size: 11px;
  color: var(--fuxi-text-tertiary, #cccccc);
  letter-spacing: 0.04em;
  margin-top: 2px;
}

/* ── 活跃任务角标 ── */
.bagua-palace__badge {
  position: absolute;
  bottom: 10px;
  right: 10px;
  font-size: 11px;
  font-weight: 700;
  color: #fff;
  background: var(--fuxi-primary, #ff6700);
  min-width: 20px;
  height: 20px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 6px;
}

/* ── 快捷键提示 ── */
.bagua-palace__shortcut {
  position: absolute;
  bottom: 10px;
  left: 10px;
  font-size: 10px;
  font-family: 'SF Mono', monospace;
  color: var(--fuxi-text-tertiary, #cccccc);
  opacity: 0;
  transition: opacity 0.3s ease;
}

.bagua-palace:hover .bagua-palace__shortcut {
  opacity: 0.6;
}

/* ═══════════════════════════════════════════
   中宫特殊样式
   ═══════════════════════════════════════════ */
.bagua-palace--center {
  background: linear-gradient(135deg, #ff6700, #e55a2b);
  color: #fff;
  border: none;
  box-shadow: 0 4px 20px rgba(255, 103, 0, 0.25);
  animation: none;
}

.bagua-palace--center:hover {
  transform: translateY(-6px);
  box-shadow: 0 8px 32px rgba(255, 103, 0, 0.35);
}

.bagua-palace__center-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  width: 100%;
}

.bagua-palace__taiji-spin {
  margin-bottom: 2px;
}

.taiji-spin__symbol {
  font-size: 32px;
  line-height: 1;
  animation: taiji-center-spin 8s linear infinite;
  display: inline-block;
}

@keyframes taiji-center-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.bagua-palace__center-label {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.bagua-palace__center-organ {
  font-size: 13px;
  opacity: 0.8;
}

.bagua-palace__center-stats {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 6px;
  padding: 8px 16px;
  background: rgba(255, 255, 255, 0.15);
  border-radius: 8px;
}

.center-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.center-stat__num {
  font-size: 20px;
  font-weight: 800;
  line-height: 1;
}

.center-stat__label {
  font-size: 10px;
  opacity: 0.7;
  letter-spacing: 0.04em;
}

.center-stat__divider {
  width: 1px;
  height: 24px;
  background: rgba(255, 255, 255, 0.25);
}

.bagua-palace__center-shortcut {
  position: absolute;
  bottom: 8px;
  right: 10px;
  font-size: 10px;
  font-family: 'SF Mono', monospace;
  color: rgba(255, 255, 255, 0.5);
}

/* ═══════════════════════════════════════════
   底部提示
   ═══════════════════════════════════════════ */
.home-footer {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 40px;
  font-size: 12px;
  color: var(--fuxi-text-tertiary, #cccccc);
}

.home-footer__dot {
  color: var(--fuxi-border, #eeeeee);
}

/* ═══════════════════════════════════════════
   响应式
   ═══════════════════════════════════════════ */
@media (max-width: 1023px) {
  .home-view {
    padding: 32px 16px 36px;
  }

  .home-brand__title {
    font-size: 28px;
  }

  .bagua-dashboard {
    grid-template-columns: repeat(2, 1fr);
    grid-template-rows: auto;
    gap: 16px;
    min-height: auto;
  }

  .bagua-palace--center {
    grid-column: span 2;
  }
}

@media (max-width: 767px) {
  .home-view {
    padding: 24px 12px 28px;
  }

  .home-brand__title {
    font-size: 24px;
  }

  .home-brand__icon {
    font-size: 28px;
  }

  .bagua-dashboard {
    grid-template-columns: 1fr;
    gap: 12px;
  }

  .bagua-palace--center {
    grid-column: span 1;
  }

  .bagua-palace {
    min-height: 140px;
  }
}
</style>
