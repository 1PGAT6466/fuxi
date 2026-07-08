<template>
  <!--
    伏羲 v2.1 — LayerPanel：图层列表侧边抽屉
    开关/颜色/锁定状态管理
  -->
  <el-drawer v-model="visible" title="图层管理" direction="ltr" size="280px" :with-header="true">
    <template #header>
      <div class="layer-drawer-header">
        <el-icon :size="18"><Grid /></el-icon>
        <span>图层管理</span>
        <span class="layer-count">{{ store.layers.length }} 层</span>
      </div>
    </template>

    <div class="layer-list">
      <div
        v-for="layer in store.layers"
        :key="layer.name"
        class="layer-item"
        :class="{ 'layer-item--locked': layer.locked }"
      >
        <!-- 颜色指示 -->
        <div class="layer-color" :style="{ background: layer.color }" />

        <!-- 图层名 -->
        <span class="layer-name">{{ layer.name }}</span>
        <span class="layer-entity-count">{{ layer.entityCount }}</span>

        <!-- 可见开关 -->
        <el-tooltip :content="layer.visible ? '隐藏' : '显示'" placement="top">
          <el-button
            :icon="layer.visible ? View : Hide"
            size="small"
            text
            :disabled="layer.locked"
            @click="store.toggleLayerVisibility(layer.name)"
          />
        </el-tooltip>

        <!-- 锁定按钮 -->
        <el-tooltip :content="layer.locked ? '解锁' : '锁定'" placement="top">
          <el-button
            :icon="layer.locked ? Lock : Unlock"
            size="small"
            text
            @click="store.toggleLayerLock(layer.name)"
          />
        </el-tooltip>
      </div>

      <!-- 空状态 -->
      <div v-if="store.layers.length === 0" class="layer-empty">
        <span>暂无图层数据</span>
      </div>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { Grid, View, Hide, Lock, Unlock } from '@element-plus/icons-vue';
import { useDxfViewerStore } from './store';

const store = useDxfViewerStore();

// ─── 可见性控制 ───
const visible = ref(false);

function open(): void {
  visible.value = true;
}

function close(): void {
  visible.value = false;
}

function toggle(): void {
  visible.value = !visible.value;
}

defineExpose({ open, close, toggle });
</script>

<style scoped lang="scss">
.layer-drawer-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--font-size-caption);
  font-weight: 600;

  .layer-count {
    margin-left: auto;
    font-size: var(--font-size-small);
    color: var(--text-tertiary);
    font-weight: 400;
    background: var(--bg-subtle);
    padding: 2px 8px;
    border-radius: 10px;
  }
}

.layer-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.layer-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  background: var(--bg-subtle);
  transition: all var(--duration-fast) var(--ease-out);

  &:hover {
    background: var(--bg-hover);
  }

  &--locked {
    opacity: 0.5;
  }
}

.layer-color {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex-shrink: 0;
  border: 1px solid rgba(0, 0, 0, 0.1);
}

.layer-name {
  flex: 1;
  font-size: var(--font-size-caption);
  font-weight: 500;
  color: var(--text-primary);
}

.layer-entity-count {
  font-size: var(--font-size-small);
  color: var(--text-tertiary);
  min-width: 24px;
  text-align: right;
}

.layer-empty {
  text-align: center;
  padding: 40px 0;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}
</style>
