<template>
  <!--
    伏羲 v2.1 — MeasureTool：距离测量工具
    两点点击 → 显示距离标注
  -->
  <div class="measure-tool">
    <div class="measure-header">
      <el-icon :size="16"><Aim /></el-icon>
      <span>距离测量</span>
    </div>

    <!-- 状态提示 -->
    <div class="measure-status">
      <el-tag :type="store.isMeasuring ? 'warning' : 'info'" size="small">
        {{ store.isMeasuring ? '点击第二个点完成测量' : '点击画布选择起点' }}
      </el-tag>
    </div>

    <!-- 测量结果列表 -->
    <div class="measure-list">
      <div v-for="meas in store.measurements" :key="meas.id" class="measure-item">
        <div class="measure-item-info">
          <span class="measure-id">#{{ meas.id.slice(-6) }}</span>
          <span class="measure-value">{{ meas.distance }}px</span>
          <span class="measure-coords">
            ({{ Math.round(meas.startPoint.x) }}, {{ Math.round(meas.startPoint.y) }}) - ({{
              Math.round(meas.endPoint.x)
            }}, {{ Math.round(meas.endPoint.y) }})
          </span>
        </div>
        <el-button
          :icon="Delete"
          size="small"
          text
          type="danger"
          @click="store.removeMeasurement(meas.id)"
        />
      </div>

      <div v-if="store.measurements.length === 0" class="measure-empty">
        <span>暂无测量数据</span>
        <span class="hint">点击画布开始测量</span>
      </div>
    </div>

    <!-- 清除所有 -->
    <div v-if="store.measurements.length > 0" class="measure-actions">
      <el-button size="small" type="danger" plain @click="store.clearMeasurements()">
        清除所有测量
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Aim, Delete } from '@element-plus/icons-vue';
import { useDxfViewerStore } from './store';

const store = useDxfViewerStore();
</script>

<style scoped lang="scss">
.measure-tool {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 16px;
}

.measure-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--font-size-caption);
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
}

.measure-status {
  margin-bottom: 12px;
}

.measure-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;

  &::-webkit-scrollbar {
    width: 4px;
  }
  &::-webkit-scrollbar-thumb {
    background: var(--bg-divider);
    border-radius: 4px;
  }
}

.measure-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: var(--bg-subtle);
  border-radius: var(--radius-sm);
}

.measure-item-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.measure-id {
  font-size: var(--font-size-small);
  color: var(--text-tertiary);
}

.measure-value {
  font-size: var(--font-size-caption);
  font-weight: 600;
  color: var(--status-error);
}

.measure-coords {
  font-size: 10px;
  color: var(--text-tertiary);
  font-family: monospace;
}

.measure-empty {
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

.measure-actions {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--bg-divider);
}
</style>
