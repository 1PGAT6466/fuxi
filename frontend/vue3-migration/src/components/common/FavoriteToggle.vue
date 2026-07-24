<!--
  伏羲 v2.1 — 收藏/置顶切换按钮
  P2 增强：收藏夹/置顶功能

  可嵌入对话页、文档页、知识库页的标题栏中，
  提供一键收藏/取消收藏和置顶功能。
-->
<template>
  <span class="favorite-toggle" :class="{ 'is-active': isFav }">
    <!-- 收藏按钮 -->
    <el-tooltip :content="isFav ? '取消收藏' : '添加收藏'" placement="top">
      <el-button
        size="small"
        :text="!forceShow"
        :type="forceShow ? (isFav ? 'warning' : 'default') : undefined"
        circle
        @click="handleToggleFavorite"
      >
        <el-icon :size="16">
          <StarFilled v-if="isFav" />
          <Star v-else />
        </el-icon>
      </el-button>
    </el-tooltip>

    <!-- 置顶按钮（仅已收藏时显示） -->
    <el-tooltip
      v-if="isFav"
      :content="isPinnedState ? '取消置顶' : '置顶'"
      placement="top"
    >
      <el-button
        size="small"
        :type="isPinnedState ? 'warning' : undefined"
        text
        circle
        @click="handleTogglePin"
      >
        <el-icon :size="16">
          <Top />
        </el-icon>
      </el-button>
    </el-tooltip>
  </span>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import { Star, StarFilled, Top } from '@element-plus/icons-vue';
import { useFavoritesStore } from '@/services/favorites/store';
import type { FavoriteType } from '@/services/favorites/types';

const props = withDefaults(
  defineProps<{
    /** 实体 ID（如会话 ID、文档 ID） */
    itemId: string;
    /** 收藏类型 */
    type: FavoriteType;
    /** 标题 */
    title?: string;
    /** 摘要 */
    summary?: string;
    /** 跳转 URL */
    url?: string;
    /** 是否始终显示（不 hover 也可见） */
    forceShow?: boolean;
  }>(),
  {
    forceShow: true,
  },
);

const emit = defineEmits<{
  /** 收藏状态变化时触发 */
  'favorite-change': [isFavorited: boolean];
  /** 置顶状态变化时触发 */
  'pin-change': [isPinned: boolean];
}>();

const store = useFavoritesStore();

const isFav = ref(false);
const isPinnedState = ref(false);

// ════════════════════════════════
// 状态同步
// ════════════════════════════════

function syncState(): void {
  isFav.value = store.isFavorited(props.itemId);
  isPinnedState.value = store.isPinned(props.itemId);
}

watch(
  () => [store.favorites, store.pinned],
  () => {
    syncState();
  },
  { deep: true },
);

watch(
  () => props.itemId,
  () => {
    syncState();
  },
);

onMounted(() => {
  syncState();
});

// ════════════════════════════════
// 操作
// ════════════════════════════════

async function handleToggleFavorite(): Promise<void> {
  if (isFav.value) {
    const ok = await store.removeFavorite(props.itemId);
    if (ok) {
      isFav.value = false;
      isPinnedState.value = false;
      emit('favorite-change', false);
      emit('pin-change', false);
      ElMessage.success('已取消收藏');
    } else {
      ElMessage.error('操作失败');
    }
  } else {
    const ok = await store.addFavorite(props.itemId, props.type, {
      title: props.title,
      summary: props.summary,
      url: props.url,
    });
    if (ok) {
      isFav.value = true;
      isPinnedState.value = false;
      emit('favorite-change', true);
      ElMessage.success('已添加收藏');
    } else {
      ElMessage.error('操作失败');
    }
  }
}

async function handleTogglePin(): Promise<void> {
  const ok = await store.togglePin(props.itemId);
  if (ok) {
    isPinnedState.value = !isPinnedState.value;
    emit('pin-change', isPinnedState.value);
    ElMessage.success(isPinnedState.value ? '已置顶' : '已取消置顶');
  } else {
    ElMessage.error('操作失败');
  }
}
</script>

<style scoped lang="scss">
.favorite-toggle {
  display: inline-flex;
  align-items: center;
  gap: 2px;

  &.is-active {
    .el-button {
      color: var(--fuxi-primary, #ff6700);
    }
  }
}
</style>
