<template>
  <!--
    快捷键帮助面板 — Cmd+/ 触发
  -->
  <Teleport to="body">
    <Transition name="shortcut-help">
      <div v-if="visible" class="shortcut-help-overlay" @click.self="$emit('close')">
        <div class="shortcut-help-panel" role="dialog" aria-label="快捷键帮助" aria-modal="true">
          <div class="shortcut-help-header">
            <span class="shortcut-help-title">⌨ 快捷键速查</span>
            <button class="shortcut-help-close" aria-label="关闭" @click="$emit('close')">✕</button>
          </div>

          <div class="shortcut-help-section">
            <div class="shortcut-help-section-title">全局操作</div>
            <div
              v-for="shortcut in SHORTCUT_LIST"
              :key="shortcut.keys"
              class="shortcut-help-row"
            >
              <kbd class="shortcut-help-keys">{{ shortcut.keys }}</kbd>
              <span class="shortcut-help-desc">{{ shortcut.description }}</span>
            </div>
          </div>

          <div class="shortcut-help-section">
            <div class="shortcut-help-section-title">九宫格宫位 (⌘/Ctrl + 数字)</div>
            <div class="shortcut-help-grid">
              <div
                v-for="item in guaItems"
                :key="item.id"
                class="shortcut-help-gua"
              >
                <span class="shortcut-help-gua-key">{{ item.shortcutKey }}</span>
                <span class="shortcut-help-gua-symbol">{{ item.symbol }}</span>
                <span class="shortcut-help-gua-label">{{ item.label }}·{{ item.organ }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { BAGUA_LIST, ZHONGGONG } from '@/constants/bagua';
import { SHORTCUT_LIST } from '@/composables/useShortcuts';

defineProps<{
  visible: boolean;
}>();

defineEmits<{
  (e: 'close'): void;
}>();

const guaItems = [...BAGUA_LIST.slice(0, 8), ZHONGGONG].sort(
  (a, b) => parseInt(a.shortcutKey, 10) - parseInt(b.shortcutKey, 10),
);
</script>

<style scoped>
.shortcut-help-overlay {
  position: fixed;
  inset: 0;
  z-index: 9998;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(4px);
}

.shortcut-help-panel {
  width: 500px;
  max-width: calc(100vw - 32px);
  max-height: 80vh;
  overflow-y: auto;
  background: var(--fuxi-bg-card, #ffffff);
  border-radius: var(--radius-lg, 16px);
  box-shadow: var(--fuxi-shadow-lg, 0 8px 32px rgba(0, 0, 0, 0.06));
  border: 1px solid var(--fuxi-border, #eeeeee);
  padding: 0;
}

.shortcut-help-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  border-bottom: 1px solid var(--fuxi-border, #eeeeee);
  position: sticky;
  top: 0;
  background: var(--fuxi-bg-card, #ffffff);
  z-index: 1;
}

.shortcut-help-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--fuxi-text, #333333);
}

.shortcut-help-close {
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 50%;
  background: var(--fuxi-bg-subtle, #f0ede5);
  color: var(--fuxi-text-secondary, #999999);
  cursor: pointer;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 150ms ease;
}

.shortcut-help-close:hover {
  background: var(--fuxi-primary-light, #fff3e8);
  color: var(--fuxi-primary, #ff6700);
}

.shortcut-help-section {
  padding: 16px 24px;
}

.shortcut-help-section + .shortcut-help-section {
  border-top: 1px solid var(--fuxi-border, #eeeeee);
}

.shortcut-help-section-title {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--fuxi-text-tertiary, #cccccc);
  margin-bottom: 12px;
}

.shortcut-help-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
}

.shortcut-help-keys {
  font-size: 12px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  color: var(--fuxi-text, #333333);
  background: var(--fuxi-bg-subtle, #f0ede5);
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid var(--fuxi-border, #eeeeee);
  min-width: 110px;
  text-align: center;
  white-space: nowrap;
}

.shortcut-help-desc {
  font-size: 14px;
  color: var(--fuxi-text-secondary, #999999);
}

/* ── 九宫格快捷键 ── */
.shortcut-help-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.shortcut-help-gua {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: var(--radius-sm, 8px);
  background: var(--fuxi-bg-subtle, #f0ede5);
}

.shortcut-help-gua-key {
  font-size: 14px;
  font-weight: 800;
  font-family: 'SF Mono', monospace;
  color: var(--fuxi-primary, #ff6700);
  min-width: 20px;
}

.shortcut-help-gua-symbol {
  font-size: 18px;
}

.shortcut-help-gua-label {
  font-size: 12px;
  color: var(--fuxi-text-secondary, #999999);
}

/* ── 过渡动画 ── */
.shortcut-help-enter-active {
  transition: opacity 200ms ease;
}
.shortcut-help-leave-active {
  transition: opacity 150ms ease;
}
.shortcut-help-enter-from,
.shortcut-help-leave-to {
  opacity: 0;
}
.shortcut-help-enter-active .shortcut-help-panel {
  animation: help-slide-in 200ms ease;
}
@keyframes help-slide-in {
  from {
    opacity: 0;
    transform: scale(0.95);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}
</style>
