<!--
  伏羲 v2.1 — 属性编辑面板 — 通用分组容器
-->
<template>
  <div class="property-section">
    <h3 class="section-title">{{ title }}</h3>
    <div class="section-body">
      <slot></slot>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string;
}>();
</script>

<style scoped>
.property-section {
  margin-bottom: 16px;
  border-bottom: 1px solid var(--el-border-color-extra-light, #f2f6fc);
  padding-bottom: 12px;
}

.property-section:last-child {
  border-bottom: none;
  margin-bottom: 0;
}

.section-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-secondary, #909399);
  margin: 0 0 10px 0;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.section-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
</style>
