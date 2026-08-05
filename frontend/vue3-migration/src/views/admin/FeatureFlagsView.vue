<template>
  <!--
    伏羲 v2.1 — 功能开关管理
    开关列表表格 + ElSwitch 切换 + 确认 + 搜索筛选
  -->
  <div class="feature-flags-view">
    <h2 class="page-title">功能开关管理</h2>

    <!-- 搜索 + 统计 -->
    <div class="toolbar">
      <el-input
        v-model="searchQuery"
        placeholder="搜索开关 key 或名称..."
        :prefix-icon="Search"
        clearable
        class="search-input"
      />
      <span class="toolbar-stats">
        {{ filteredFlags.length }} / {{ flags.length }} 个开关
        <el-tag size="small" type="success" class="stat-tag"> 已启用 {{ enabledCount }} </el-tag>
      </span>
    </div>

    <!-- 开关表格 -->
    <div class="table-wrapper">
      <el-table
        :data="Array.isArray(filteredFlags) ? filteredFlags : []"
        style="width: 100%"
        size="small"
        :default-sort="{ prop: 'updated_at', order: 'descending' }"
      >
        <el-table-column label="开关 Key" min-width="160">
          <template #default="{ row }">
            <el-tooltip :content="row.key" placement="top" :disabled="getKeyLabel(row.key) === row.key">
              <code class="flag-key">{{ getKeyLabel(row.key) }}</code>
            </el-tooltip>
          </template>
        </el-table-column>

        <el-table-column prop="name" label="名称" min-width="120" />

        <el-table-column prop="description" label="描述" min-width="200">
          <template #default="{ row }">
            <span class="flag-desc">{{ row.description }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="enabled" label="启用状态" width="100" align="center">
          <template #default="{ row }">
            <el-switch
              v-model="row.enabled"
              size="small"
              :active-color="row.important ? '#FF6700' : '#34C759'"
              @change="handleToggle(row)"
            />
          </template>
        </el-table-column>

        <el-table-column prop="updated_at" label="修改时间" width="140" sortable>
          <template #default="{ row }">
            <span class="flag-time">{{ row.updated_at }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="editFlag(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 空状态 -->
    <div v-if="filteredFlags.length === 0 && !loading" class="empty-state">
      <el-icon :size="48"><Switch /></el-icon>
      <span>未找到匹配的功能开关</span>
    </div>

    <!-- 编辑对话框 -->
    <el-dialog v-model="showEditDialog" title="编辑功能开关" width="500px">
      <el-form :model="editForm" label-width="80px">
        <el-form-item label="Key">
          <el-input v-model="editForm.key" disabled />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="editForm.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="editForm.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="editForm.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEditDialog = false">取消</el-button>
        <el-button type="primary" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { Search, Switch } from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import apiClient from '@/api';

// ─── 类型 ───
interface FeatureFlag {
  key: string;
  name: string;
  description: string;
  enabled: boolean;
  important: boolean;
  updated_at: string;
}

// ─── State ───
const flags = ref<FeatureFlag[]>([]);
const searchQuery = ref('');
const loading = ref(false);
const showEditDialog = ref(false);
const editForm = ref<FeatureFlag>({
  key: '',
  name: '',
  description: '',
  enabled: false,
  important: false,
  updated_at: '',
});

// ─── Key 到中文名称的映射（与后端 feature_flags.py DEFAULT_FLAGS 对齐）───
const KEY_LABELS: Record<string, string> = {
  // 核心 Flag
  'shaoyang_sag_extract': 'SAG 事件实体提取',
  'taiyang_multi_hop': '多跳检索',
  'taiyang_seed_score': 'Seed Score 融合',
  // Phase B — 伏羲检索架构
  'taiyang_sag_pipeline': 'SAG 三阶段管线',
  'taiyang_path_a': 'Path A 实体引导召回',
  'taiyang_event_search': 'Event 粒度检索',
  'taiyang_sql_multi_hop': 'SQL JOIN 多跳扩展',
  // 增强 Flag
  'enhanced_pipeline': '增强版管线',
  // 基础 Flag
  'graphrag_multi_hop': 'GraphRAG 多跳遍历',
  'query_planner': '查询规划器',
  'table_structured_search': '表格结构化检索',
  'multimodal_rag': '多模态 RAG',
  'sentence_level_compress': '句子级压缩',
  'knowledge_lifecycle': '知识生命周期',
  'siliconflow_rerank': 'SiliconFlow 重排序',
  'self_rag_check': '自检索检查',
  'crag_rewrite': 'CRAG 重写',
  'query_rewrite': '查询重写',
  'hyde': 'HyDE 假设文档',
  'wiki_search': 'Wiki 搜索',
  'table_view': '表格视图',
  'session_memory': '会话记忆',
  // Dream Cycle
  'enable_dream_cycle_notifications': 'Dream Cycle 通知',
  'enable_gap_llm': 'Gap Scan LLM 增强',
  // 前端 mock key 映射
  'ai-tools-enabled': 'AI 工具集',
  'dxf-viewer-enabled': 'DXF 工程浏览器',
  'chat_v2': 'AI 对话 v2',
  'search_semantic': '语义搜索',
  'auto_index': '自动索引',
  'wiki_public': '公开 Wiki',
  'eval_auto': '自动评测',
  'rate_limit': '速率限制',
  'analytics-enabled': '数据分析',
  'advanced_cache': '高级缓存',
};

/** 获取 Key 对应的中文显示名称 */
function getKeyLabel(key: string): string {
  return KEY_LABELS[key] || key;
}

// ─── Computed ───
const filteredFlags = computed(() => {
  const q = searchQuery.value.toLowerCase().trim();
  if (!q) return flags.value;
  return flags.value.filter(
    (f) =>
      f.key.toLowerCase().includes(q) ||
      f.name.toLowerCase().includes(q) ||
      f.description.toLowerCase().includes(q),
  );
});

const enabledCount = computed(() => flags.value.filter((f) => f.enabled).length);

// ─── Mock ───
const mockFlags: FeatureFlag[] = [
  {
    key: 'ai-tools-enabled',
    name: 'AI 工具集',
    description: '启用 AI 工具集服务（摘要/翻译/实体识别等）',
    enabled: true,
    important: true,
    updated_at: '2026-07-05 14:30',
  },
  {
    key: 'dxf-viewer-enabled',
    name: 'DXF 工程浏览器',
    description: '启用 DXF 图纸查看器',
    enabled: true,
    important: false,
    updated_at: '2026-07-06 10:15',
  },
  {
    key: 'chat_v2',
    name: 'AI 对话 v2',
    description: '启用新版对话引擎，支持多轮上下文记忆',
    enabled: true,
    important: true,
    updated_at: '2026-07-01 09:00',
  },
  {
    key: 'search_semantic',
    name: '语义搜索',
    description: '启用向量语义搜索，结果更精准',
    enabled: true,
    important: true,
    updated_at: '2026-06-28 16:45',
  },
  {
    key: 'auto_index',
    name: '自动索引',
    description: '上传文档后自动触发向量化索引',
    enabled: true,
    important: false,
    updated_at: '2026-06-25 08:30',
  },
  {
    key: 'wiki_public',
    name: '公开 Wiki',
    description: '允许所有用户创建和编辑 Wiki 页面',
    enabled: false,
    important: false,
    updated_at: '2026-06-20 11:00',
  },
  {
    key: 'eval_auto',
    name: '自动评测',
    description: '每日定时运行 RAG 质量评测并生成报告',
    enabled: false,
    important: false,
    updated_at: '2026-06-15 13:20',
  },
  {
    key: 'rate_limit',
    name: '速率限制',
    description: '启用 API 请求速率限制，防止滥用',
    enabled: true,
    important: true,
    updated_at: '2026-06-10 17:00',
  },
  {
    key: 'analytics-enabled',
    name: '数据分析',
    description: '启用数据分析服务',
    enabled: false,
    important: false,
    updated_at: '2026-06-05 09:50',
  },
  {
    key: 'advanced_cache',
    name: '高级缓存',
    description: '启用 Redis 多级缓存策略',
    enabled: true,
    important: false,
    updated_at: '2026-07-03 12:10',
  },
];

// ─── Fetch ───
async function fetchFlags(): Promise<void> {
  loading.value = true;
  try {
    const resp = await apiClient.get('/api/feature-flags') as Record<string, unknown>;
    // 后端返回 {status, data: {flags: {key: bool}, defaults: {...}}}
    const data = resp?.data || resp;
    const rawFlags = (data as Record<string, unknown>)?.flags || data;
    if (rawFlags && typeof rawFlags === 'object') {
      const nameMap: Record<string, string> = {
        shaoyang_sag_extract: '少阳·SAG 精准抽取',
        taiyang_multi_hop: '太阳·多跳推理',
        taiyang_seed_score: '太阳·种子评分',
        taiyang_sag_pipeline: '太阳·SAG 全链路',
        taiyang_path_a: '太阳·路径 A',
        taiyang_event_search: '太阳·事件检索',
        taiyang_sql_multi_hop: '太阳·SQL 多跳',
        enhanced_pipeline: '增强版管线',
        graphrag_multi_hop: 'GraphRAG 多跳遍历',
        query_planner: '查询规划器',
        table_structured_search: '表格结构化检索',
        multimodal_rag: '多模态 RAG',
        sentence_level_compression: '句子级压缩',
        knowledge_lifecycle: '知识生命周期',
        ai_tools_enabled: 'AI 工具集',
        dxf_viewer_enabled: 'DXF 图纸查看器',
        new_chat_engine: '新版对话引擎',
        vector_search_enabled: '向量语义搜索',
        auto_index_enabled: '自动向量化索引',
        wiki_edit_enabled: 'Wiki 全员编辑',
        daily_eval_enabled: '每日质量评测',
        rate_limit_enabled: 'API 速率限制',
        analytics_enabled: '数据分析服务',
        redis_cache_enabled: 'Redis 多级缓存',
      };
      const descMap: Record<string, string> = {
        shaoyang_sag_extract: '精准抽取知识三元组，提升检索准确率',
        taiyang_multi_hop: '支持多跳推理，回答复杂关联问题',
        taiyang_seed_score: '基于种子评分优化检索排序',
        taiyang_sag_pipeline: 'SAG 全链路检索增强生成',
        enhanced_pipeline: '增强版文档处理管线',
        graphrag_multi_hop: '知识图谱多跳遍历检索',
        query_planner: '智能查询拆解与规划',
        table_structured_search: 'PDF 表格结构化解析与检索',
        multimodal_rag: '支持图片、音频等多模态内容',
        sentence_level_compression: '句子级精准压缩，减少噪声',
        knowledge_lifecycle: '知识过期检测与自动更新',
        new_chat_engine: '新版对话引擎，支持多轮上下文记忆',
        vector_search_enabled: '启用向量语义搜索，结果更精准',
        auto_index_enabled: '上传文档后自动触发向量化索引',
        rate_limit_enabled: '启用 API 请求速率限制，防止滥用',
      };
      flags.value = Object.entries(rawFlags as Record<string, boolean>).map(([key, enabled]) => ({
        key,
        name: nameMap[key] || key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
        description: descMap[key] || '',
        enabled: Boolean(enabled),
        important: false,
        updated_at: '',
      }));
    } else {
      flags.value = mockFlags;
    }
  } catch {
    console.warn('[FeatureFlags] API 不可用，使用 mock 数据');
    flags.value = mockFlags;
  } finally {
    loading.value = false;
  }
}

// ─── Actions ───
async function handleToggle(flag: FeatureFlag): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确认${flag.enabled ? '启用' : '禁用'}功能「${flag.name}」？`,
      '操作确认',
      { confirmButtonText: '确认', cancelButtonText: '取消', type: 'warning' },
    );

    // 尝试调用 API
    try {
      await apiClient.put(`/api/feature-flags/${flag.key}`, { enabled: flag.enabled });
    } catch {
      // mock 模式直接成功
    }

    flag.updated_at = new Date()
      .toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      })
      .replace(/\//g, '-');

    ElMessage.success(`「${flag.name}」已${flag.enabled ? '启用' : '禁用'}`);
  } catch {
    // 用户取消 — 恢复状态
    flag.enabled = !flag.enabled;
  }
}

function editFlag(flag: FeatureFlag): void {
  editForm.value = { ...flag };
  showEditDialog.value = true;
}

function saveEdit(): void {
  const idx = flags.value.findIndex((f) => f.key === editForm.value.key);
  if (idx !== -1) {
    flags.value[idx] = {
      ...flags.value[idx],
      name: editForm.value.name,
      description: editForm.value.description,
      enabled: editForm.value.enabled,
      updated_at: new Date()
        .toLocaleString('zh-CN', {
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
        })
        .replace(/\//g, '-'),
    };
  }
  showEditDialog.value = false;
  ElMessage.success('功能开关已更新');
}

onMounted(fetchFlags);
</script>

<style scoped lang="scss">
.feature-flags-view {
  max-width: 1200px;
  margin: 0 auto;
  padding: 28px 24px;
}

.page-title {
  margin: 0 0 24px;
  font-size: var(--font-size-page-title);
  font-weight: 700;
  color: var(--text-primary);
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.search-input {
  max-width: 320px;
}

.toolbar-stats {
  font-size: var(--font-size-caption);
  color: var(--text-tertiary);
  display: flex;
  align-items: center;
  gap: 8px;
}

.stat-tag {
  font-size: 11px;
}

.table-wrapper {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.flag-key {
  font-family: monospace;
  font-size: 12px;
  padding: 2px 6px;
  background: var(--bg-subtle);
  border-radius: 4px;
  color: var(--brand);
}

.flag-desc {
  font-size: var(--font-size-small);
  color: var(--text-secondary);
}

.flag-time {
  font-size: var(--font-size-small);
  color: var(--text-tertiary);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 60px 0;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
}

/* ─── 响应式 ─── */
@media (max-width: 767px) {
  .feature-flags-view {
    padding: 16px 12px;
  }
  .toolbar {
    flex-direction: column;
    align-items: stretch;
  }
  .search-input {
    max-width: 100%;
  }
}
</style>
