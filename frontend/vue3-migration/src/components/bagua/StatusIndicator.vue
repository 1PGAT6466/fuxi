<template>
  <div
    class="status-indicator"
    :class="[`status-indicator--${status}`, { 'status-indicator--animated': animated }]"
    role="status"
    :aria-label="`状态: ${statusText}`"
  >
    <span class="status-indicator__dot" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { TrigramStatus } from '@/constants/bagua';

const props = withDefaults(
  defineProps<{
    /** 状态类型 */
    status: TrigramStatus;
    /** 是否播放动画 */
    animated?: boolean;
    /** 尺寸 (px) */
    size?: number;
  }>(),
  {
    animated: true,
    size: 10,
  },
);

const statusText = computed<string>(() => {
  const map: Record<TrigramStatus, string> = {
    healthy: '健康',
    warning: '降级',
    error: '故障',
    offline: '离线',
  };
  return map[props.status];
});
</script>

<style scoped>
/* ────── 容器 ────── */
.status-indicator {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

/* ────── 圆点 ────── */
.status-indicator__dot {
  display: block;
  width: v-bind('props.size + "px"');
  height: v-bind('props.size + "px"');
  border-radius: 50%;
  transition:
    background-color var(--duration-normal) var(--ease-out),
    box-shadow var(--duration-normal) var(--ease-out);
}

/* ────── 四个状态色 ────── */
.status-indicator--healthy .status-indicator__dot {
  background-color: var(--status-healthy);
  box-shadow: 0 0 6px rgba(52, 199, 89, 0.4);
}
.status-indicator--warning .status-indicator__dot {
  background-color: var(--status-warning);
  box-shadow: 0 0 6px rgba(255, 149, 0, 0.4);
}
.status-indicator--error .status-indicator__dot {
  background-color: var(--status-error);
  box-shadow: 0 0 6px rgba(255, 59, 48, 0.4);
}
.status-indicator--offline .status-indicator__dot {
  background-color: var(--status-offline);
  box-shadow: none;
}

/* ────── 动画（纯CSS） ────── */
/* 健康 — 呼吸光晕（pulse 2.5s） */
.status-indicator--animated.status-indicator--healthy .status-indicator__dot {
  animation: pulse-healthy 2.5s ease-in-out infinite;
}

/* 降级 — 慢闪烁（pulse 1.8s） */
.status-indicator--animated.status-indicator--warning .status-indicator__dot {
  animation: pulse-warning 1.8s ease-in-out infinite;
}

/* 故障 — 快脉冲（pulse 1.0s） */
.status-indicator--animated.status-indicator--error .status-indicator__dot {
  animation: pulse-error 1s ease-in-out infinite;
}

/* 离线 — 无动画 */
.status-indicator--animated.status-indicator--offline .status-indicator__dot {
  animation: none;
}

/* ────── 关键帧 ────── */
@keyframes pulse-healthy {
  0%,
  100% {
    box-shadow: 0 0 4px rgba(52, 199, 89, 0.4);
    transform: scale(1);
  }
  50% {
    box-shadow: 0 0 12px rgba(52, 199, 89, 0.7);
    transform: scale(1.15);
  }
}

@keyframes pulse-warning {
  0%,
  100% {
    opacity: 1;
    box-shadow: 0 0 4px rgba(255, 149, 0, 0.3);
  }
  50% {
    opacity: 0.5;
    box-shadow: 0 0 8px rgba(255, 149, 0, 0.6);
  }
}

@keyframes pulse-error {
  0%,
  100% {
    opacity: 1;
    box-shadow: 0 0 4px rgba(255, 59, 48, 0.5);
  }
  25% {
    opacity: 0.3;
    box-shadow: 0 0 10px rgba(255, 59, 48, 0.8);
  }
  50% {
    opacity: 1;
    box-shadow: 0 0 4px rgba(255, 59, 48, 0.5);
  }
  75% {
    opacity: 0.3;
    box-shadow: 0 0 10px rgba(255, 59, 48, 0.8);
  }
}
</style>
