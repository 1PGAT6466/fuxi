<template>
  <!--
    伏羲 v1.44 — 通用错误状态组件
    用于管理页面 API 失败时的统一错误展示
  -->
  <div class="error-state">
    <el-result
      icon="error"
      :title="title"
      :sub-title="message"
    >
      <template #extra>
        <el-button type="primary" :loading="retrying" @click="handleRetry">
          <el-icon><Refresh /></el-icon>
          重试
        </el-button>
      </template>
    </el-result>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { Refresh } from '@element-plus/icons-vue';

// ─── Props ───
withDefaults(defineProps<{
  title?: string;
  message?: string;
}>(), {
  title: '数据加载失败',
  message: '服务器暂时无法响应，请检查网络连接后重试',
});

// ─── Emits ───
const emit = defineEmits<{
  (e: 'retry'): void;
}>();

// ─── 重试状态 ───
const retrying = ref(false);

async function handleRetry(): Promise<void> {
  retrying.value = true;
  emit('retry');
  // 短暂延迟后重置 loading 状态
  setTimeout(() => {
    retrying.value = false;
  }, 800);
}
</script>

<style scoped lang="scss">
.error-state {
  margin-top: 24px;
  padding: 40px;
  background: var(--bg-card, #ffffff);
  border-radius: var(--radius-md, 12px);
  box-shadow: var(--shadow-sm, 0 2px 8px rgba(0, 0, 0, 0.04));

  :deep(.el-result__icon) {
    color: var(--fuxi-danger, #ff3b30);
  }

  :deep(.el-result__title) {
    color: var(--text-primary, #333333);
    font-weight: 700;
  }

  :deep(.el-result__subtitle) {
    color: var(--text-secondary, #666666);
  }
}
</style>
