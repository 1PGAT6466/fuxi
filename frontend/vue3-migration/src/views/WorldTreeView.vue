<template>
  <div class="worldtree-view">
    <div class="worldtree-header">
      <h2>🌳 世界树</h2>
      <p class="worldtree-desc">数据管道与信息流转的根脉系统</p>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-value">{{ stats.wiki_pages || 0 }}</div>
        <div class="stat-label">Wiki 页面</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.entities || 0 }}</div>
        <div class="stat-label">知识实体</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.terms || 0 }}</div>
        <div class="stat-label">术语条目</div>
      </div>
    </div>

    <!-- 搜索 -->
    <div class="search-bar">
      <el-input
        v-model="searchQuery"
        placeholder="搜索 Wiki 页面或实体..."
        clearable
        prefix-icon="Search"
      />
    </div>

    <!-- 主内容区 -->
    <div class="main-content">
      <!-- 左侧：Wiki 树 -->
      <div class="tree-panel">
        <h3>📖 Wiki 知识库</h3>
        <div v-if="loading" class="loading-state">
          <el-skeleton :rows="5" animated />
        </div>
        <div v-else-if="filteredTree.length === 0" class="empty-state">
          <el-empty description="暂无 Wiki 页面" :image-size="80" />
        </div>
        <el-tree
          v-else
          :data="filteredTree"
          :props="{ children: 'children', label: 'title' }"
          default-expand-all
          highlight-current
          @node-click="onNodeClick"
        >
          <template #default="{ data }">
            <span class="tree-node">
              <span class="tree-icon">{{ data.children ? '📁' : '📄' }}</span>
              <span>{{ data.title }}</span>
              <el-tag v-if="data.page_count" size="small" type="info" class="tree-badge">
                {{ data.page_count }}
              </el-tag>
            </span>
          </template>
        </el-tree>
      </div>

      <!-- 右侧：详情面板 -->
      <div class="detail-panel">
        <div v-if="selectedPage" class="page-detail">
          <h3>{{ selectedPage.title }}</h3>
          <div class="page-meta">
            <el-tag size="small">{{ selectedPage.category || '未分类' }}</el-tag>
            <span class="meta-text">更新于 {{ formatDate(selectedPage.updated_at) }}</span>
          </div>
          <div class="page-content" v-html="renderContent(selectedPage.content)" />
        </div>
        <div v-else class="no-selection">
          <el-empty description="选择一个 Wiki 页面查看详情" :image-size="100" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import apiClient from '@/api';

interface WikiNode {
  id?: string;
  title: string;
  category?: string;
  content?: string;
  updated_at?: string;
  page_count?: number;
  children?: WikiNode[];
}

interface WorldTreeStats {
  wiki_pages: number;
  entities: number;
  terms: number;
  generated_at?: string;
}

const loading = ref(false);
const stats = ref<WorldTreeStats>({ wiki_pages: 0, entities: 0, terms: 0 });
const tree = ref<WikiNode[]>([]);
const searchQuery = ref('');
const selectedPage = ref<WikiNode | null>(null);

// 过滤后的树
const filteredTree = computed(() => {
  if (!searchQuery.value) return tree.value;
  const q = searchQuery.value.toLowerCase();
  return filterTree(tree.value, q);
});

function filterTree(nodes: WikiNode[], query: string): WikiNode[] {
  return nodes.reduce<WikiNode[]>((acc, node) => {
    const titleMatch = node.title.toLowerCase().includes(query);
    const filteredChildren = node.children ? filterTree(node.children, query) : [];
    if (titleMatch || filteredChildren.length > 0) {
      acc.push({
        ...node,
        children: filteredChildren.length > 0 ? filteredChildren : node.children,
      });
    }
    return acc;
  }, []);
}

async function loadData() {
  loading.value = true;
  try {
    // 加载统计数据
    const statsResp = await apiClient.get('/api/worldtree/stats') as Record<string, unknown>;
    if (statsResp && typeof statsResp === 'object') {
      stats.value = {
        wiki_pages: Number(statsResp.wiki_pages) || 0,
        entities: Number(statsResp.entities) || 0,
        terms: Number(statsResp.terms) || 0,
      };
    }

    // 加载 Wiki 树
    const treeResp = await apiClient.get('/api/worldtree/wiki/tree') as { tree?: WikiNode[] };
    if (treeResp?.tree) {
      tree.value = treeResp.tree;
    }
  } catch (e) {
    console.error('[WorldTree] 加载失败:', e);
  } finally {
    loading.value = false;
  }
}

async function onNodeClick(data: WikiNode) {
  if (data.id) {
    try {
      const resp = await apiClient.get(`/api/worldtree/wiki/${data.id}`) as Record<string, unknown>;
      selectedPage.value = { ...data, ...resp };
    } catch {
      selectedPage.value = data;
    }
  } else {
    selectedPage.value = data;
  }
}

function formatDate(dateStr?: string): string {
  if (!dateStr) return '未知';
  try {
    return new Date(dateStr).toLocaleString('zh-CN');
  } catch {
    return dateStr;
  }
}

function renderContent(content?: string): string {
  if (!content) return '<p>暂无内容</p>';
  // 简单 Markdown 渲染
  return content
    .replace(/\n/g, '<br>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>');
}

onMounted(loadData);
</script>

<style scoped>
.worldtree-view {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}

.worldtree-header {
  margin-bottom: 24px;
}

.worldtree-header h2 {
  font-size: 28px;
  font-weight: 700;
  color: var(--el-text-color-primary);
  margin: 0 0 8px;
}

.worldtree-desc {
  font-size: 14px;
  color: var(--el-text-color-secondary);
  margin: 0;
}

.stats-row {
  display: flex;
  gap: 16px;
  margin-bottom: 20px;
}

.stat-card {
  flex: 1;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
  padding: 20px;
  text-align: center;
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
  color: var(--el-color-primary);
}

.stat-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}

.search-bar {
  margin-bottom: 20px;
}

.main-content {
  display: flex;
  gap: 20px;
  min-height: 500px;
}

.tree-panel {
  flex: 0 0 360px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
  padding: 20px;
  overflow-y: auto;
}

.tree-panel h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 16px;
  color: var(--el-text-color-primary);
}

.detail-panel {
  flex: 1;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
  padding: 24px;
  overflow-y: auto;
}

.page-detail h3 {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 12px;
  color: var(--el-text-color-primary);
}

.page-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.meta-text {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.page-content {
  font-size: 14px;
  line-height: 1.8;
  color: var(--el-text-color-regular);
}

.tree-node {
  display: flex;
  align-items: center;
  gap: 6px;
}

.tree-icon {
  font-size: 14px;
}

.tree-badge {
  margin-left: 8px;
}

.loading-state,
.empty-state,
.no-selection {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 300px;
}

@media (max-width: 768px) {
  .main-content {
    flex-direction: column;
  }
  .tree-panel {
    flex: none;
    max-height: 300px;
  }
}
</style>
