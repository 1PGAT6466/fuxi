<!--
  伏羲 v2.1 — 流式输出指示器（打字动画）
  三点跳动 + 渐变闪烁
-->
<template>
  <div class="streaming-indicator">
    <div class="indicator-content">
      <div class="typing-dots">
        <span class="dot" />
        <span class="dot" />
        <span class="dot" />
      </div>
      <span class="indicator-text">正在生成...</span>
    </div>
  </div>
</template>

<script setup lang="ts">
// 纯展示组件，无 props/emits
</script>

<style scoped lang="scss">
.streaming-indicator {
  display: flex;
  align-items: center;
  padding: 8px 0 8px 48px;
}

.indicator-content {
  display: flex;
  align-items: center;
  gap: 8px;
}

.typing-dots {
  display: flex;
  gap: 4px;
  align-items: center;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--fuxi-primary);
  animation: dotBounce 1.4s infinite ease-in-out;

  &:nth-child(1) {
    animation-delay: -0.32s;
  }

  &:nth-child(2) {
    animation-delay: -0.16s;
  }

  &:nth-child(3) {
    animation-delay: 0s;
  }
}

@keyframes dotBounce {
  0%,
  80%,
  100% {
    transform: scale(0.4);
    opacity: 0.3;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

.indicator-text {
  font-size: 12px;
  color: var(--fuxi-text-tertiary);
}
</style>
