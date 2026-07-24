<!--
  伏羲 v2.1 — 属性编辑面板 — 单个属性字段
-->
<template>
  <div class="property-field">
    <label class="field-label">{{ label }}</label>
    <div class="field-value">
      <slot></slot>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  label: string;
}>();
</script>

<style scoped>
.property-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.field-label {
  font-size: 11px;
  color: var(--el-text-color-secondary, #909399);
  font-weight: 500;
}

.field-value {
  display: flex;
  align-items: center;
}
</style>
