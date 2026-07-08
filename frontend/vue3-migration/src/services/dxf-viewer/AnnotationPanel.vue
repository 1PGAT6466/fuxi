<template>
  <!--
    伏羲 v2.1 — AnnotationPanel：文字标注面板
    点击添加 + 编辑/删除
  -->
  <div class="annotation-panel">
    <div class="annotation-header">
      <el-icon :size="16"><EditPen /></el-icon>
      <span>标注管理</span>
    </div>

    <!-- 添加提示 -->
    <div class="annotation-hint">
      <el-tag size="small" type="info">点击画布添加标注</el-tag>
    </div>

    <!-- 标注列表 -->
    <div class="annotation-list">
      <div v-for="ann in store.annotations" :key="ann.id" class="annotation-item">
        <!-- 颜色标记 -->
        <div class="ann-marker" :style="{ background: ann.color }" />

        <!-- 可编辑内容 -->
        <div class="ann-body">
          <input
            v-if="editingId === ann.id"
            ref="editInputRef"
            v-model="editContent"
            class="ann-input"
            @blur="saveEdit(ann.id)"
            @keydown.enter="saveEdit(ann.id)"
            @keydown.escape="cancelEdit"
          />
          <span v-else class="ann-content" @dblclick="startEdit(ann)">
            {{ ann.content }}
          </span>
          <span class="ann-coords"> ({{ Math.round(ann.x) }}, {{ Math.round(ann.y) }}) </span>
        </div>

        <!-- 操作 -->
        <div class="ann-actions">
          <el-button :icon="Edit" size="small" text @click="startEdit(ann)" />
          <el-button
            :icon="Delete"
            size="small"
            text
            type="danger"
            @click="store.removeAnnotation(ann.id)"
          />
        </div>
      </div>

      <div v-if="store.annotations.length === 0" class="annotation-empty">
        <span>暂无标注</span>
        <span class="hint">切换到标注工具后点击画布添加</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue';
import { EditPen, Edit, Delete } from '@element-plus/icons-vue';
import { useDxfViewerStore } from './store';
import type { Annotation } from './types';

const store = useDxfViewerStore();

// ─── 编辑状态 ───
const editingId = ref<string | null>(null);
const editContent = ref('');
const editInputRef = ref<HTMLInputElement | null>(null);

function startEdit(ann: Annotation): void {
  editingId.value = ann.id;
  editContent.value = ann.content;
  nextTick(() => {
    editInputRef.value?.focus();
    editInputRef.value?.select();
  });
}

function saveEdit(id: string): void {
  if (editContent.value.trim()) {
    store.updateAnnotation(id, editContent.value.trim());
  }
  editingId.value = null;
  editContent.value = '';
}

function cancelEdit(): void {
  editingId.value = null;
  editContent.value = '';
}
</script>

<style scoped lang="scss">
.annotation-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 16px;
}

.annotation-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--font-size-caption);
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
}

.annotation-hint {
  margin-bottom: 12px;
}

.annotation-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;

  &::-webkit-scrollbar {
    width: 4px;
  }
  &::-webkit-scrollbar-thumb {
    background: var(--bg-divider);
    border-radius: 4px;
  }
}

.annotation-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  background: var(--bg-subtle);
  border-radius: var(--radius-sm);
  transition: all var(--duration-fast) var(--ease-out);

  &:hover {
    background: var(--bg-hover);
  }
}

.ann-marker {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-top: 5px;
  flex-shrink: 0;
}

.ann-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.ann-content {
  font-size: var(--font-size-caption);
  color: var(--text-primary);
  cursor: pointer;
  word-break: break-all;
}

.ann-input {
  width: 100%;
  padding: 4px 8px;
  border: 1px solid var(--brand);
  border-radius: 4px;
  font-size: var(--font-size-caption);
  background: var(--bg-card);
  color: var(--text-primary);
  outline: none;
}

.ann-coords {
  font-size: var(--font-size-small);
  color: var(--text-tertiary);
  font-family: monospace;
}

.ann-actions {
  display: flex;
  flex-shrink: 0;
}

.annotation-empty {
  text-align: center;
  padding: 32px 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);

  .hint {
    font-size: var(--font-size-small);
    opacity: 0.6;
  }
}
</style>
