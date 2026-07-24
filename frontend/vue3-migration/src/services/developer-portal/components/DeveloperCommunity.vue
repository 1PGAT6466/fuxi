<template>
  <div class="developer-community">
    <!-- 工具栏 -->
    <div class="developer-community__toolbar">
      <h3 class="developer-community__title">开发者社区</h3>
      <el-button text @click="$emit('refresh')">
        <el-icon><Refresh /></el-icon>
        刷新
      </el-button>
    </div>

    <!-- 分类过滤 -->
    <div class="developer-community__categories">
      <el-button
        :type="!selectedCategory ? 'primary' : 'default'"
        size="small"
        @click="$emit('select-category', null)"
      >
        全部
      </el-button>
      <el-button
        v-for="cat in categories"
        :key="cat.value"
        :type="selectedCategory === cat.value ? 'primary' : 'default'"
        size="small"
        @click="$emit('select-category', cat.value)"
      >
        <el-icon v-if="cat.icon" :size="14"><component :is="cat.icon" /></el-icon>
        {{ cat.label }}
      </el-button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="developer-community__loading">
      <el-skeleton :rows="5" animated />
    </div>

    <!-- Error -->
    <el-alert
      v-else-if="error"
      :title="error"
      type="error"
      show-icon
      :closable="false"
      class="developer-community__error"
    >
      <template #default>
        <el-button size="small" type="primary" link @click="$emit('refresh')">重试</el-button>
      </template>
    </el-alert>

    <!-- 帖子列表 -->
    <div v-else class="developer-community__post-list">
      <div
        v-for="post in posts"
        :key="post.id"
        class="developer-community__post-card"
      >
        <div class="developer-community__post-header">
          <div class="developer-community__post-title-row">
            <el-tag v-if="post.pinned" size="small" type="warning" effect="dark">
              <el-icon :size="12"><Top /></el-icon>
              置顶
            </el-tag>
            <el-tag
              size="small"
              effect="plain"
              :type="categoryTagType(post.category)"
            >
              {{ COMMUNITY_CATEGORY_LABELS[post.category] }}
            </el-tag>
            <span class="developer-community__post-title">{{ post.title }}</span>
          </div>
          <span class="developer-community__post-date">{{ post.createdAt }}</span>
        </div>

        <p class="developer-community__post-content">
          {{ truncateText(post.content, 200) }}
        </p>

        <div class="developer-community__post-footer">
          <div class="developer-community__post-author">
            <el-avatar :size="24" :src="post.author.avatar">
              {{ post.author.name.charAt(0) }}
            </el-avatar>
            <span class="developer-community__post-author-name">{{ post.author.name }}</span>
          </div>
          <div class="developer-community__post-stats">
            <span class="developer-community__post-stat">
              <el-icon :size="14"><View /></el-icon>
              {{ post.views }}
            </span>
            <span class="developer-community__post-stat">
              <el-icon :size="14"><Star /></el-icon>
              {{ post.likes }}
            </span>
            <span class="developer-community__post-stat">
              <el-icon :size="14"><ChatDotRound /></el-icon>
              {{ post.comments }}
            </span>
          </div>
          <div class="developer-community__post-tags">
            <el-tag
              v-for="tag in post.tags"
              :key="tag"
              size="small"
              effect="plain"
              type="info"
            >
              {{ tag }}
            </el-tag>
          </div>
        </div>
      </div>

      <el-empty v-if="!posts.length" description="暂无社区帖子" />
    </div>

    <!-- 分页 -->
    <div v-if="total > pageSize" class="developer-community__pagination">
      <el-pagination
        :current-page="currentPage"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next, total"
        @current-change="$emit('page-change', $event)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 开发者社区 — 浏览社区帖子
 */
import {
  Refresh,
  View,
  Star,
  ChatDotRound,
  Top,
  Notification,
  Reading,
  QuestionFilled,
  Tickets,
} from '@element-plus/icons-vue';
import type { CommunityPost, CommunityCategory } from '../types';
import { COMMUNITY_CATEGORY_LABELS } from '../types';
import type { Component } from 'vue';

defineProps<{
  posts: CommunityPost[];
  total: number;
  loading: boolean;
  error: string | null;
  currentPage: number;
  pageSize: number;
  selectedCategory: CommunityCategory | null;
}>();

defineEmits<{
  'select-category': [category: CommunityCategory | null];
  'page-change': [page: number];
  refresh: [];
}>();

interface CategoryOption {
  value: CommunityCategory;
  label: string;
  icon: Component;
}

const categories: CategoryOption[] = [
  { value: 'announcement', label: '公告', icon: Notification },
  { value: 'tutorial', label: '教程', icon: Reading },
  { value: 'discussion', label: '讨论', icon: ChatDotRound },
  { value: 'showcase', label: '案例', icon: Star },
  { value: 'question', label: '问答', icon: QuestionFilled },
  { value: 'changelog', label: '更新', icon: Tickets },
];

function categoryTagType(cat: CommunityCategory): string {
  const map: Record<string, string> = {
    announcement: 'danger',
    tutorial: 'success',
    discussion: 'primary',
    showcase: 'warning',
    question: 'info',
    changelog: '',
  };
  return map[cat] || 'info';
}

function truncateText(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen) + '…';
}
</script>

<style scoped lang="scss">
.developer-community {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.developer-community__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.developer-community__title {
  font-size: 17px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.developer-community__categories {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.developer-community__loading,
.developer-community__error {
  padding: 16px 0;
}

/* ── 帖子列表 ── */
.developer-community__post-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.developer-community__post-card {
  padding: 16px 20px;
  background: var(--bg-subtle);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-color);
  cursor: pointer;
  transition:
    border-color var(--duration-fast),
    box-shadow var(--duration-fast);

  &:hover {
    border-color: var(--brand);
    box-shadow: var(--shadow-sm);
  }
}

.developer-community__post-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.developer-community__post-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.developer-community__post-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.developer-community__post-date {
  font-size: 12px;
  color: var(--text-tertiary);
  flex-shrink: 0;
  margin-left: 16px;
}

.developer-community__post-content {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0 0 12px;
  line-height: 1.6;
}

.developer-community__post-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
}

.developer-community__post-author {
  display: flex;
  align-items: center;
  gap: 6px;
}

.developer-community__post-author-name {
  font-size: 12px;
  color: var(--text-tertiary);
}

.developer-community__post-stats {
  display: flex;
  align-items: center;
  gap: 12px;
}

.developer-community__post-stat {
  display: flex;
  align-items: center;
  gap: 3px;
  font-size: 12px;
  color: var(--text-tertiary);
}

.developer-community__post-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

/* ── 分页 ── */
.developer-community__pagination {
  display: flex;
  justify-content: center;
  padding-top: 8px;
}
</style>
