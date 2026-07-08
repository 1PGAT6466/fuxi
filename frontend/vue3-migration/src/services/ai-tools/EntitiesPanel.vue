<template>
  <!--
    伏羲 v2.1 — 实体识别面板
  -->
  <div class="entities-panel">
    <div class="panel-desc">自动识别文本中的人名、地名、组织、日期、专有名词等实体</div>

    <!-- 输入区 -->
    <div class="input-section">
      <el-input
        v-model="inputText"
        type="textarea"
        :rows="5"
        placeholder="请输入需要实体识别的文本…"
        maxlength="5000"
        show-word-limit
      />
    </div>

    <!-- 操作区 -->
    <div class="action-section">
      <el-button
        type="primary"
        :loading="loading"
        :disabled="!inputText.trim()"
        @click="handleRecognize"
      >
        <el-icon><Pointer /></el-icon>
        识别实体
      </el-button>
    </div>

    <!-- 错误态 -->
    <div v-if="error" class="error-section">
      <el-result icon="error" title="识别失败" sub-title="请检查网络连接后重试">
        <template #extra>
          <el-button type="primary" size="small" @click="handleRecognize">重试</el-button>
        </template>
      </el-result>
    </div>

    <!-- 空态 -->
    <div v-else-if="showEmpty" class="empty-section">
      <el-empty description="未识别到实体，请尝试其他文本" :image-size="60" />
    </div>

    <!-- 高亮原文 -->
    <div v-if="entities.length > 0" class="result-section">
      <!-- 原文高亮展示 -->
      <div class="highlighted-text">
        <span class="highlight-label">原文标注：</span>
        <span class="hl-content" v-html="highlightedText" />
      </div>

      <!-- 实体表格 -->
      <div class="entity-table-section">
        <div class="result-title">实体列表（{{ entities.length }} 个）</div>
        <el-table :data="entities" size="small" stripe max-height="320">
          <el-table-column prop="name" label="名称" min-width="120">
            <template #default="{ row }">
              <span class="entity-name">{{ row.name }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="type" label="类型" width="110">
            <template #default="{ row }">
              <el-tag size="small" :type="getEntityTypeTag(row.type)">
                {{ row.type }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="description" label="描述" min-width="180">
            <template #default="{ row }">
              {{ row.description || '-' }}
            </template>
          </el-table-column>
          <el-table-column label="位置" width="80">
            <template #default="{ row }"> {{ row.start_pos }}:{{ row.end_pos }} </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 复制按钮 -->
      <div class="result-footer">
        <el-button size="small" text @click="copyResult">
          <el-icon><CopyDocument /></el-icon>
          复制结果
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { ElMessage } from 'element-plus';
import { Pointer, CopyDocument } from '@element-plus/icons-vue';
import DOMPurify from 'dompurify';
import * as aiApi from './api';
import { useAiToolsStore } from './store';
import type { EntityItem } from './types';

const aiStore = useAiToolsStore();

// 状态
const inputText = ref('');
const loading = ref(false);
const error = ref(false);
const showEmpty = ref(false);
const entities = ref<EntityItem[]>([]);

// 实体类型 -> 标签类型映射
const typeTagMap: Record<string, string> = {
  人名: 'warning',
  地名: 'success',
  组织: 'info',
  时间: '',
  日期: '',
  产品类别: 'danger',
  技术领域: '',
  技术方法: '',
  应用领域: 'success',
};

function getEntityTypeTag(type: string): string {
  return typeTagMap[type] || 'info';
}

// 高亮原文
const highlightedText = computed(() => {
  if (entities.value.length === 0) return inputText.value;

  // 按位置排序（降序，从后往前替换避免位置偏移）
  const sorted = [...entities.value]
    .filter((e) => e.start_pos !== null && e.end_pos !== null)
    .sort((a, b) => (b.start_pos ?? 0) - (a.start_pos ?? 0));

  let text = inputText.value;
  for (const entity of sorted) {
    const start = entity.start_pos ?? 0;
    const end = entity.end_pos ?? 0;
    if (start >= 0 && end <= text.length) {
      const before = text.slice(0, start);
      const match = text.slice(start, end);
      const after = text.slice(end);
      const type = getEntityTypeTag(entity.type);
      text = `${before}<mark class="entity-hl entity-hl--${type}" title="${entity.type}: ${entity.description || ''}">${match}</mark>${after}`;
    }
  }

  return DOMPurify.sanitize(text, {
    ALLOWED_TAGS: ['mark'],
  });
});

// 方法
async function handleRecognize() {
  const text = inputText.value.trim();
  if (!text) return;

  loading.value = true;
  error.value = false;
  showEmpty.value = false;
  entities.value = [];
  try {
    const res = await aiApi.entities(text);
    if (!res.entities || res.entities.length === 0) {
      showEmpty.value = true;
    } else {
      entities.value = res.entities;
    }
    aiStore.addHistory({ tool: 'entities', input: text, result: res });
  } catch {
    error.value = true;
    ElMessage.error('实体识别失败');
  } finally {
    loading.value = false;
  }
}

async function copyResult() {
  const text = entities.value
    .map((e) => `${e.name} [${e.type}]${e.description ? ' - ' + e.description : ''}`)
    .join('\n');
  try {
    await navigator.clipboard.writeText(text);
    ElMessage.success('已复制实体列表');
  } catch {
    ElMessage.error('复制失败');
  }
}
</script>

<style scoped lang="scss">
.entities-panel {
  padding: 0 4px;
}

.panel-desc {
  font-size: var(--font-size-caption);
  color: var(--text-secondary);
  margin-bottom: var(--space-md);
}

.input-section {
  margin-bottom: var(--space-md);
}

.action-section {
  margin-bottom: var(--space-md);
}

.error-section {
  margin-top: var(--space-md);
  padding: var(--space-md);
  background: var(--fuxi-bg-subtle);
  border-radius: var(--fuxi-radius);
  border: 1px solid var(--fuxi-border);
}

.empty-section {
  margin-top: var(--space-md);
  padding: var(--space-md);
}

.result-section {
  margin-top: var(--space-md);
}

.highlighted-text {
  padding: var(--space-md);
  background: var(--fuxi-bg-subtle);
  border-radius: var(--fuxi-radius);
  border: 1px solid var(--fuxi-border);
  margin-bottom: var(--space-md);

  .highlight-label {
    font-size: var(--font-size-small);
    font-weight: 600;
    color: var(--text-tertiary);
    margin-right: 6px;
  }

  .hl-content {
    font-size: var(--font-size-body);
    line-height: 2;
    color: var(--fuxi-text);
  }
}

// 高亮标记样式
:deep(.entity-hl) {
  padding: 1px 3px;
  border-radius: 3px;
  cursor: help;

  &.entity-hl--warning {
    background: var(--qian-color-light);
    color: var(--qian-color);
  }

  &.entity-hl--success {
    background: var(--zhen-color-light);
    color: var(--zhen-color);
  }

  &.entity-hl--info {
    background: var(--kan-color-light);
    color: var(--kan-color);
  }

  &.entity-hl--danger {
    background: var(--li-color-light);
    color: var(--li-color);
  }

  &.entity-hl-- {
    background: var(--fuxi-primary-light);
    color: var(--fuxi-primary);
  }
}

.entity-table-section {
  .result-title {
    font-weight: 600;
    font-size: var(--font-size-caption);
    color: var(--fuxi-text);
    margin-bottom: var(--space-sm);
  }
}

.entity-name {
  font-weight: 600;
  color: var(--fuxi-primary);
}

.result-footer {
  margin-top: var(--space-sm);
  text-align: right;
}
</style>
