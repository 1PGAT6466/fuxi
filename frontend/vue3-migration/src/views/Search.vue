<template>
  <div class="search-container">
    <div class="search-header">
      <el-input
        v-model="query"
        :placeholder="$t('search.placeholder')"
        size="large"
        clearable
        @keyup.enter="handleSearch"
      >
        <template #append>
          <el-button :loading="loading" @click="handleSearch">
            <el-icon><Search /></el-icon>
          </el-button>
        </template>
      </el-input>
    </div>

    <div class="search-results">
      <SearchResult v-for="result in results" :key="result.id" :result="result" />

      <div v-if="!loading && results.length === 0 && searched" class="empty-state">
        <el-empty :description="$t('search.noResults')" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onUnmounted } from 'vue';
import { Search } from '@element-plus/icons-vue';
import apiClient from '@/api';
import SearchResult from '@/components/search/SearchResult.vue';

const query = ref<string>('');
const results = ref<
  Array<{
    id: string;
    title: string;
    excerpt: string;
    score: number;
    source?: string;
    date?: string;
  }>
>([]);
const loading = ref<boolean>(false);
const searched = ref<boolean>(false);
const searchTimer: ReturnType<typeof setTimeout> | null = null;

// 组件卸载时清理定时器
onUnmounted(() => {
  if (searchTimer) clearTimeout(searchTimer);
});

// 清除时重置
watch(query, (val) => {
  if (!val.trim()) {
    results.value = [];
    searched.value = false;
  }
});

async function handleSearch() {
  if (!query.value.trim()) return;

  if (searchTimer) clearTimeout(searchTimer);

  loading.value = true;
  searched.value = true;

  try {
    const data = (await apiClient.get('/api/search', {
      params: { q: query.value.trim(), top_k: 10 },
    })) as { results?: unknown[]; wiki_results?: unknown[]; chunk_results?: unknown[] };

    // 后端返回 {results, wiki_results, chunk_results} — 合并为统一结果
    const allResults: Array<{
      id: string;
      title: string;
      excerpt: string;
      score: number;
      source?: string;
      date?: string;
    }> = [];

    const mergeResults = (list: unknown[], sourceType: string) => {
      for (let i = 0; i < list.length; i++) {
        const item = list[i] as Record<string, unknown>;
        allResults.push({
          id: (item.id as string) || (item.chunk_id as string) || `${sourceType}-${i}`,
          title: (item.title as string) || (item.source_doc as string) || `${sourceType} 结果 ${i + 1}`,
          excerpt: (item.content as string) || (item.snippet as string) || '',
          score: (item.score as number) || 0,
          source: sourceType,
        });
      }
    };

    if (Array.isArray(data.results)) mergeResults(data.results, 'document');
    if (Array.isArray(data.wiki_results)) mergeResults(data.wiki_results, 'wiki');
    if (Array.isArray(data.chunk_results)) mergeResults(data.chunk_results, 'chunk');

    results.value = allResults;
  } catch (error) {
    console.error('搜索失败:', error);
    results.value = [];
  } finally {
    loading.value = false;
  }
}

// 暴露给测试的内部状态和方法
defineExpose({
  query,
  results,
  loading,
  searched,
  handleSearch,
});
</script>

<style scoped lang="scss">
.search-container {
  max-width: 800px;
  margin: 0 auto;
  padding: 40px 20px;
}

.search-header {
  margin-bottom: 30px;
}

.search-results {
  min-height: 200px;
}

.empty-state {
  padding: 60px 0;
}

/* ───────── 响应式 ───────── */
@media (max-width: 767px) {
  .search-container {
    padding: 16px 16px;
  }
}
</style>
