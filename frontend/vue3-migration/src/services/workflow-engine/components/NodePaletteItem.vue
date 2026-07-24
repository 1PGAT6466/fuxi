<!--
  伏羲 v2.1 — 节点面板拖拽项
  可拖拽至画布创建新节点
-->
<template>
  <div
    class="palette-item"
    :class="{ dragging: isDragging }"
    draggable="true"
    @dragstart="onDragStart"
    @dragend="onDragEnd"
  >
    <span class="palette-item-icon">{{ template.icon }}</span>
    <span class="palette-item-label">{{ template.label }}</span>
    <span class="palette-item-type">{{ typeLabel }}</span>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import type { NodeTemplate } from '../types';

const props = defineProps<{
  template: NodeTemplate;
}>();

const emit = defineEmits<{
  'drag-start': [template: NodeTemplate];
}>();

const isDragging = ref(false);

const typeLabel = computed(() => {
  const labels: Record<string, string> = {
    trigger: '触发器',
    condition: '条件',
    action: '动作',
    loop: '循环',
  };
  return labels[props.template.type] ?? props.template.type;
});

function onDragStart(e: DragEvent) {
  isDragging.value = true;
  if (e.dataTransfer) {
    e.dataTransfer.effectAllowed = 'copy';
    e.dataTransfer.setData('application/workflow-template-type', props.template.type);
    e.dataTransfer.setData('application/workflow-template-label', props.template.label);
  }
  emit('drag-start', props.template);
}

function onDragEnd() {
  isDragging.value = false;
}
</script>

<style scoped>
.palette-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: grab;
  transition: all 0.15s ease;
  border: 1px solid transparent;
  user-select: none;
}

.palette-item:hover {
  background: var(--el-color-primary-light-9, #ecf5ff);
  border-color: var(--el-color-primary-light-5, #a0cfff);
}

.palette-item.dragging {
  opacity: 0.5;
}

.palette-item:active {
  cursor: grabbing;
}

.palette-item-icon {
  font-size: 16px;
  width: 24px;
  text-align: center;
}

.palette-item-label {
  font-size: 13px;
  color: var(--el-text-color-regular, #606266);
  flex: 1;
}

.palette-item-type {
  font-size: 10px;
  color: var(--el-text-color-placeholder, #c0c4cc);
  text-transform: uppercase;
}
</style>
