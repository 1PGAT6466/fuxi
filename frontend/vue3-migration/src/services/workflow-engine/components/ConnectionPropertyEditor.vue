<!--
  伏羲 v2.1 — 连接线属性编辑器
-->
<template>
  <div class="connection-property-editor">
    <div class="property-content">
      <PropertySection title="连接信息">
        <PropertyField label="连接 ID">
          <span class="prop-readonly">{{ connection.id }}</span>
        </PropertyField>
        <PropertyField label="源节点">
          <span class="prop-readonly">{{ connection.sourceNodeId }}</span>
        </PropertyField>
        <PropertyField label="源端口">
          <span class="prop-readonly">{{ connection.sourcePort }}</span>
        </PropertyField>
        <PropertyField label="目标节点">
          <span class="prop-readonly">{{ connection.targetNodeId }}</span>
        </PropertyField>
        <PropertyField label="目标端口">
          <span class="prop-readonly">{{ connection.targetPort }}</span>
        </PropertyField>
        <PropertyField label="连接标签">
          <input
            class="prop-input"
            :value="connection.label ?? ''"
            @input="updateField('label', ($event.target as HTMLInputElement).value)"
            placeholder="可选标签..."
          />
        </PropertyField>
      </PropertySection>

      <div class="property-actions">
        <button class="btn-delete" @click="$emit('delete')">
          🗑 删除连接
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { WorkflowConnection } from '../types';
import PropertySection from './PropertySection.vue';
import PropertyField from './PropertyField.vue';

const props = defineProps<{
  connection: WorkflowConnection;
}>();

const emit = defineEmits<{
  'update:connection': [connectionId: string, updates: Partial<WorkflowConnection>];
  delete: [];
}>();

function updateField<K extends keyof WorkflowConnection>(field: K, value: WorkflowConnection[K]) {
  emit('update:connection', props.connection.id, { [field]: value });
}
</script>

<style scoped>
.connection-property-editor {
  height: 100%;
}

.property-content {
  padding: 12px 16px;
}

.property-actions {
  padding: 16px 0;
}

.prop-input {
  width: 100%;
  padding: 6px 10px;
  border: 1px solid var(--el-border-color, #dcdfe6);
  border-radius: 4px;
  font-size: 13px;
  color: var(--el-text-color-primary, #303133);
  background: var(--el-bg-color, #fff);
  box-sizing: border-box;
}
.prop-input:focus {
  outline: none;
  border-color: var(--el-color-primary, #409eff);
}

.prop-readonly {
  font-size: 12px;
  color: var(--el-text-color-placeholder, #c0c4cc);
  font-family: monospace;
}

.btn-delete {
  width: 100%;
  padding: 8px;
  border: 1px solid var(--el-color-danger-light-5, #fab6b6);
  background: var(--el-color-danger-light-9, #fef0f0);
  color: var(--el-color-danger, #f56c6c);
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-delete:hover {
  background: var(--el-color-danger, #f56c6c);
  color: #fff;
}
</style>
