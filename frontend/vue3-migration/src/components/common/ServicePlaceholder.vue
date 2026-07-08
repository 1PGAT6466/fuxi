<template>
  <!--
    伏羲 v2.1 — 服务路由占位组件
    这个组件作为路由的临时占位符，实际的窗口 UI
    由窗口管理器通过 ServiceWindowShell 渲染。
  -->
  <div class="service-placeholder">
    <div class="placeholder-content">
      <el-icon class="placeholder-icon" :size="48">
        <Loading />
      </el-icon>
      <p class="placeholder-text">正在加载服务窗口…</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Loading } from '@element-plus/icons-vue';
</script>

<style scoped lang="scss">
.service-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  min-height: 300px;
  background: var(--bg-primary);
}

.placeholder-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.placeholder-icon {
  color: var(--brand);
  animation: spin 1.2s linear infinite;
}

.placeholder-text {
  font-size: var(--font-size-caption);
  color: var(--text-tertiary);
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
