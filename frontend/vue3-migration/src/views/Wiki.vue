<template>
  <div class="wiki-container">
    <div class="wiki-header">
      <div class="wiki-title-area">
        <h2>{{ $t('wiki.title') }}</h2>
        <p class="wiki-desc">{{ $t('wiki.desc') }}</p>
      </div>
      <div class="wiki-actions">
        <el-input
          v-model="searchQuery"
          placeholder="搜索 Wiki 页面..."
          prefix-icon="Search"
          clearable
          class="wiki-search"
          @keyup.enter="handleSearch"
        />
        <el-button type="primary" @click="showCreateDialog = true">
          <el-icon><Plus /></el-icon>
          {{ $t('wiki.newPage') }}
        </el-button>
      </div>
    </div>

    <!-- Wiki 分类导航 -->
    <div class="wiki-categories">
      <el-tabs v-model="activeCategory" @tab-change="handleCategoryChange">
        <el-tab-pane v-for="cat in categories" :key="cat.id" :label="cat.name" :name="cat.id" />
      </el-tabs>
    </div>

    <!-- Wiki 页面列表 -->
    <div v-loading="loading" class="wiki-content">
      <div v-if="wikiPages.length === 0 && !loading" class="wiki-empty">
        <el-empty description="暂无 Wiki 页面，点击「新建页面」开始创建">
          <el-button type="primary" @click="showCreateDialog = true">
            {{ $t('wiki.newPage') }}
          </el-button>
        </el-empty>
      </div>

      <el-row :gutter="20">
        <el-col v-for="page in wikiPages" :key="page.id" :xs="24" :sm="12" :md="8" :lg="6">
          <el-card class="wiki-card" shadow="hover" @click="viewPage(page)">
            <div class="wiki-card-header">
              <el-icon class="wiki-card-icon"><Document /></el-icon>
              <h3 class="wiki-card-title">{{ page.title }}</h3>
            </div>
            <p class="wiki-card-excerpt">{{ page.excerpt || '暂无摘要' }}</p>
            <div class="wiki-card-meta">
              <span class="wiki-card-author">
                <el-icon><User /></el-icon>
                {{ page.author || '未知' }}
              </span>
              <span class="wiki-card-date">
                <el-icon><Clock /></el-icon>
                {{ formatDate(page.updated || page.created) }}
              </span>
            </div>
            <div v-if="page.tags?.length" class="wiki-card-tags">
              <el-tag v-for="tag in page.tags" :key="tag" size="small" type="info">
                {{ tag }}
              </el-tag>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <!-- 分页 -->
    <div v-if="total > pageSize" class="wiki-pagination">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next"
        @current-change="fetchWikiPages"
      />
    </div>

    <!-- 新建页面对话框 -->
    <el-dialog v-model="showCreateDialog" title="新建 Wiki 页面" width="600px">
      <el-form ref="pageFormRef" :model="newPage" :rules="pageRules" label-width="80px">
        <el-form-item label="标题" prop="title">
          <el-input v-model="newPage.title" placeholder="请输入页面标题" />
        </el-form-item>
        <el-form-item label="分类" prop="category">
          <el-select v-model="newPage.category" placeholder="请选择分类">
            <el-option v-for="cat in categories" :key="cat.id" :label="cat.name" :value="cat.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="标签">
          <el-tag
            v-for="tag in newPage.tags"
            :key="tag"
            closable
            class="tag-item"
            @close="removeTag(tag)"
          >
            {{ tag }}
          </el-tag>
          <el-input
            v-if="showTagInput"
            ref="tagInputRef"
            v-model="tagInputValue"
            size="small"
            class="tag-input"
            @keyup.enter="addTag"
            @blur="addTag"
          />
          <el-button v-else size="small" @click="showTagInput = true"> + 添加标签 </el-button>
        </el-form-item>
        <el-form-item label="内容" prop="content">
          <el-input
            v-model="newPage.content"
            type="textarea"
            :rows="10"
            placeholder="请输入 Markdown 格式内容..."
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="createPage"> 创建 </el-button>
      </template>
    </el-dialog>

    <!-- 查看页面对话框 -->
    <el-dialog v-model="showViewDialog" :title="currentPageItem?.title" width="800px">
      <div v-if="currentPageItem" class="wiki-page-content">
        <div class="wiki-page-meta">
          <span>
            <el-icon><User /></el-icon>
            {{ currentPageItem.author || '未知' }}
          </span>
          <span>
            <el-icon><Clock /></el-icon>
            更新于 {{ formatDate(currentPageItem.updated || currentPageItem.created) }}
          </span>
          <span v-if="currentPageItem.tags?.length">
            <el-tag
              v-for="tag in currentPageItem.tags"
              :key="tag"
              size="small"
              type="info"
              style="margin-left: 4px"
            >
              {{ tag }}
            </el-tag>
          </span>
        </div>
        <div class="wiki-page-body" v-html="getRenderedContent(currentPageItem.content)" />
      </div>
      <template #footer>
        <el-button @click="showViewDialog = false">关闭</el-button>
        <el-button type="primary" @click="editPage(currentPageItem)">
          <el-icon><Edit /></el-icon> 编辑
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, nextTick } from 'vue';
import apiClient from '@/api';
import { ElMessage } from 'element-plus';
import { renderMarkdown } from '@/utils/markdown';
import { Plus, Document, User, Clock, Edit } from '@element-plus/icons-vue';
import { formatDate } from '@/utils/helpers';
import type { FormInstance, FormRules } from 'element-plus';

interface WikiPage {
  id: string;
  title: string;
  excerpt?: string;
  author?: string;
  created?: string;
  updated?: string;
  tags?: string[];
  category?: string;
  content?: string;
}

// 分类
const categories = ref([
  { id: 'all', name: '全部' },
  { id: 'tech', name: '技术文档' },
  { id: 'product', name: '产品手册' },
  { id: 'process', name: '流程规范' },
  { id: 'meeting', name: '会议纪要' },
  { id: 'other', name: '其他' },
]);

// Wiki 列表
const wikiPages = ref<WikiPage[]>([]);
const loading = ref<boolean>(false);
const searchQuery = ref<string>('');
const activeCategory = ref<string>('all');
const currentPage = ref<number>(1);
const pageSize = ref<number>(20);
const total = ref<number>(0);

// 新建页面
const showCreateDialog = ref<boolean>(false);
const creating = ref<boolean>(false);
const pageFormRef = ref<FormInstance>();
interface NewPageForm {
  title: string;
  category: string;
  tags: string[];
  content: string;
  _id: string | null;
}
const newPage = reactive<NewPageForm>({
  title: '',
  category: 'tech',
  tags: [],
  content: '',
  _id: null,
});
const showTagInput = ref<boolean>(false);
const tagInputValue = ref<string>('');
const tagInputRef = ref<HTMLElement | null>(null);

const pageRules = reactive<FormRules<NewPageForm>>({
  title: [{ required: true, message: '请输入页面标题', trigger: 'blur' }],
  category: [{ required: true, message: '请选择分类', trigger: 'change' }],
  content: [{ required: true, message: '请输入页面内容', trigger: 'blur' }],
});

// 查看页面
const showViewDialog = ref<boolean>(false);
const currentPageItem = ref<WikiPage | null>(null);

onMounted(() => {
  fetchWikiPages();
});

async function fetchWikiPages(): Promise<void> {
  loading.value = true;
  try {
    const params: Record<string, string | number> = {
      page: currentPage.value,
      page_size: pageSize.value,
    };
    if (activeCategory.value !== 'all') {
      params.category = activeCategory.value;
    }
    if (searchQuery.value) {
      params.q = searchQuery.value;
    }

    const data = await apiClient.get('/api/wiki', { params });
    wikiPages.value = data.pages || data || [];
    total.value = data.total || wikiPages.value.length;
  } catch (error) {
    console.error('获取 Wiki 页面失败:', error);
    ElMessage.error('获取 Wiki 页面失败');
  } finally {
    loading.value = false;
  }
}

function handleCategoryChange(): void {
  currentPage.value = 1;
  fetchWikiPages();
}

function handleSearch(): void {
  currentPage.value = 1;
  fetchWikiPages();
}

function viewPage(page: WikiPage): void {
  currentPageItem.value = page;
  showViewDialog.value = true;
}

function getRenderedContent(content: string | null | undefined): string {
  return renderMarkdown(content);
}

function editPage(page: WikiPage | null): void {
  if (!page) return;
  showViewDialog.value = false;
  // 编辑页面逻辑 - 复用创建对话框
  resetNewPage();
  Object.assign(newPage, {
    title: page.title || '',
    category: page.category || 'tech',
    tags: [...(page.tags || [])],
    content: page.content || '',
    _id: page.id,
  });
  showCreateDialog.value = true;
  // 确保新页面表单验证从编辑状态开始
  nextTick(() => {
    pageFormRef.value?.clearValidate();
  });
}

async function createPage(): Promise<void> {
  if (!pageFormRef.value) return;

  try {
    await pageFormRef.value.validate();
  } catch {
    // 表单验证失败
    return;
  }

  creating.value = true;

  try {
    const payload = {
      title: newPage.title,
      category: newPage.category,
      tags: newPage.tags,
      content: newPage.content,
    };

    if (newPage._id) {
      await apiClient.put(`/api/wiki/${newPage._id}`, payload);
      ElMessage.success('Wiki 页面更新成功');
    } else {
      await apiClient.post('/api/wiki', payload);
      ElMessage.success('Wiki 页面创建成功');
    }

    showCreateDialog.value = false;
    resetNewPage();
    await fetchWikiPages();
  } catch (error) {
    ElMessage.error(
      (newPage._id ? '更新' : '创建') + '失败: ' + ((error as Error)?.message || '未知错误'),
    );
  } finally {
    creating.value = false;
  }
}

function resetNewPage(): void {
  newPage.title = '';
  newPage.category = 'tech';
  newPage.tags = [];
  newPage.content = '';
  newPage._id = null;
}

function addTag(): void {
  const value = tagInputValue.value.trim();
  if (value && !newPage.tags.includes(value)) {
    newPage.tags.push(value);
  }
  tagInputValue.value = '';
  showTagInput.value = false;
}

function removeTag(tag: string): void {
  newPage.tags = newPage.tags.filter((t) => t !== tag);
}
</script>

<style scoped lang="scss">
.wiki-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

.wiki-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
  flex-wrap: wrap;
  gap: 16px;
}

.wiki-title-area {
  h2 {
    margin: 0 0 4px;
    font-size: 24px;
    color: var(--text-primary);
  }

  .wiki-desc {
    margin: 0;
    font-size: 14px;
    color: var(--text-secondary);
  }
}

.wiki-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.wiki-search {
  width: 240px;
}

.wiki-content {
  min-height: 300px;
}

.wiki-empty {
  padding: 60px 0;
}

.wiki-card {
  margin-bottom: 20px;
  cursor: pointer;
  transition: transform 0.2s ease;

  &:hover {
    transform: translateY(-2px);
  }
}

.wiki-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.wiki-card-icon {
  color: var(--fuxi-primary);
  font-size: 20px;
}

.wiki-card-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wiki-card-excerpt {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.wiki-card-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: var(--text-tertiary);
  margin-bottom: 8px;

  span {
    display: flex;
    align-items: center;
    gap: 4px;
  }
}

.wiki-card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.wiki-pagination {
  margin-top: 24px;
  display: flex;
  justify-content: center;
}

// 标签输入
.tag-item {
  margin-right: 8px;
  margin-bottom: 4px;
}

.tag-input {
  width: 100px;
}

// 查看页面
.wiki-page-meta {
  display: flex;
  gap: 16px;
  align-items: center;
  flex-wrap: wrap;
  padding-bottom: 16px;
  margin-bottom: 16px;
  border-bottom: 1px solid var(--border-color-light);
  font-size: 13px;
  color: var(--text-secondary);

  span {
    display: flex;
    align-items: center;
    gap: 4px;
  }
}

.wiki-page-body {
  line-height: 1.8;
  color: var(--text-primary);

  h1,
  h2,
  h3,
  h4 {
    margin: 16px 0 8px;
    color: var(--text-primary);
  }

  p {
    margin: 8px 0;
  }

  code {
    background: var(--bg-tertiary);
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 0.9em;
    color: var(--text-primary);
  }

  pre {
    background: var(--bg-inverse);
    color: var(--text-inverse);
    padding: 16px;
    border-radius: 8px;
    overflow-x: auto;

    code {
      background: none;
      padding: 0;
      color: inherit;
    }
  }

  ul,
  ol {
    padding-left: 24px;
  }

  blockquote {
    border-left: 4px solid var(--color-primary);
    padding: 8px 16px;
    margin: 12px 0;
    background: var(--bg-tertiary);
    color: var(--text-secondary);
  }
}

// 响应式
@media (max-width: 768px) {
  .wiki-header {
    flex-direction: column;
  }

  .wiki-actions {
    width: 100%;
    flex-direction: column;
  }

  .wiki-search {
    width: 100%;
  }
}
</style>
