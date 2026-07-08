<template>
  <div v-if="appLoading" class="app-loader">
    <div class="app-loader-spinner">
      <span />
      <span />
      <span />
    </div>
  </div>
  <router-view v-else />
</template>

<script setup lang="ts">
import { ref, onMounted, onErrorCaptured } from 'vue';
import { useAuthStore } from '@/stores/auth';

// 【修复】全局错误边界 — App 层级捕获子组件错误
onErrorCaptured((err, instance, info) => {
  console.error('[伏羲 App 错误捕获]', err, info, instance);
  // 返回 false 阻止错误继续向上传播
  return false;
});

const authStore = useAuthStore();
const appLoading = ref<boolean>(false);

onMounted(async () => {
  // v2.1: 路由守卫 (router/index.ts) 统一处理认证
  // App.vue 仅负责初始 loading，避免与路由守卫产生竞态
  if (authStore.token) {
    appLoading.value = true;
    try {
      await authStore.initAuth();
    } catch {
      // initAuth 内部已处理 logout
    } finally {
      appLoading.value = false;
    }
  }
});
</script>

<style>
:focus-visible {
  outline: 2px solid var(--fuxi-primary);
  outline-offset: 2px;
}
:focus:not(:focus-visible) {
  outline: none;
}

.app-loader {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background: var(--fuxi-bg);
}

.app-loader-spinner {
  display: flex;
  gap: 8px;
}

.app-loader-spinner span {
  width: 12px;
  height: 12px;
  background: var(--fuxi-primary, #FF6700);
  border-radius: 50%;
  animation: app-loader-bounce 1.4s infinite ease-in-out;
}

.app-loader-spinner span:nth-child(1) {
  animation-delay: -0.32s;
}
.app-loader-spinner span:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes app-loader-bounce {
  0%,
  80%,
  100% {
    transform: scale(0);
  }
  40% {
    transform: scale(1);
  }
}
</style>
