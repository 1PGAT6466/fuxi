<template>
  <div class="service-detail" v-loading="store.detailLoading">
    <!-- 头部 -->
    <div class="detail-header">
      <div class="detail-header-left">
        <el-avatar :size="56" :src="service?.icon" class="detail-icon">
          {{ service?.name?.charAt(0) }}
        </el-avatar>
        <div class="detail-title-area">
          <h2 class="detail-name">{{ service?.name }}</h2>
          <span class="detail-author">by {{ service?.author }}</span>
        </div>
      </div>
      <div class="detail-header-right">
        <el-button
          v-if="installStatus === 'not-installed'"
          type="primary"
          :icon="Download"
          :loading="installing"
          @click="onInstall"
        >
          安装
        </el-button>
        <el-button
          v-else-if="installStatus === 'installed'"
          type="danger"
          plain
          :loading="uninstalling"
          @click="onUninstall"
        >
          卸载
        </el-button>
        <el-tag v-else-if="installStatus === 'installing'" type="warning">安装中...</el-tag>
        <el-button type="info" :icon="Close" text circle @click="$emit('close')" />
      </div>
    </div>

    <!-- 评分 & 统计 -->
    <div class="detail-stats">
      <div class="stat-item">
        <el-rate
          :model-value="service?.rating || 0"
          disabled
          show-score
          text-color="#e6a23c"
          :score-template="`${service?.rating?.toFixed(1) || '0.0'}`"
        />
        <span class="review-count">({{ service?.reviewCount || 0 }} 条评价)</span>
      </div>
      <div class="stat-item">
        <el-icon><Download /></el-icon>
        <span>{{ formatCount(service?.downloads || 0) }} 次下载</span>
      </div>
      <div class="stat-item">
        <span>v{{ service?.version }}</span>
      </div>
      <div class="stat-item">
        <el-tag v-if="service?.price === 'free'" type="success" size="small">免费</el-tag>
        <el-tag v-else type="warning" size="small">付费</el-tag>
      </div>
    </div>

    <!-- Tab 切换 -->
    <el-tabs v-model="activeTab" class="detail-tabs">
      <!-- 概述 -->
      <el-tab-pane label="概述" name="overview">
        <div class="detail-section">
          <div class="detail-description markdown-body" v-html="renderedDescription" />

          <div class="detail-meta" v-if="service">
            <div class="meta-row">
              <span class="meta-label">分类</span>
              <el-tag size="small">{{ categoryLabel }}</el-tag>
            </div>
            <div class="meta-row">
              <span class="meta-label">版本</span>
              <span>{{ service.version }}</span>
            </div>
            <div class="meta-row">
              <span class="meta-label">更新时间</span>
              <span>{{ formatDate(service.updatedAt) }}</span>
            </div>
            <div class="meta-row" v-if="service.homepage">
              <span class="meta-label">主页</span>
              <a :href="service.homepage" target="_blank" rel="noopener">{{ service.homepage }}</a>
            </div>
          </div>

          <div class="detail-tags" v-if="service?.tags?.length">
            <span class="meta-label">标签</span>
            <div class="tags-wrap">
              <el-tag
                v-for="tag in service.tags"
                :key="tag"
                size="small"
              >
                {{ tag }}
              </el-tag>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- 截图 -->
      <el-tab-pane label="截图" name="screenshots">
        <div class="detail-section">
          <el-empty
            v-if="!service?.screenshots?.length"
            description="暂无截图"
            :image-size="80"
          />
          <div v-else class="screenshots-grid">
            <el-image
              v-for="(shot, idx) in service.screenshots"
              :key="idx"
              :src="shot.url"
              :alt="shot.alt || `截图 ${idx + 1}`"
              fit="cover"
              class="screenshot-item"
              :preview-src-list="service.screenshots.map(s => s.url)"
              :initial-index="idx"
              lazy
            >
              <template #error>
                <div class="image-error">
                  <el-icon><PictureFilled /></el-icon>
                </div>
              </template>
            </el-image>
          </div>
        </div>
      </el-tab-pane>

      <!-- 评价 -->
      <el-tab-pane label="评价" name="reviews">
        <div class="detail-section">
          <el-empty
            v-if="!service?.reviews?.length"
            description="暂无评价"
            :image-size="80"
          />
          <div v-else class="reviews-list">
            <div
              v-for="review in service.reviews"
              :key="review.id"
              class="review-item"
            >
              <div class="review-header">
                <el-avatar :size="32" :src="review.avatar" class="review-avatar">
                  {{ review.userName.charAt(0) }}
                </el-avatar>
                <span class="review-user">{{ review.userName }}</span>
                <el-rate :model-value="review.rating" disabled size="small" />
                <span class="review-date">{{ formatDate(review.createdAt) }}</span>
              </div>
              <div class="review-content">{{ review.content }}</div>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- 版本 -->
      <el-tab-pane label="版本" name="versions">
        <div class="detail-section">
          <el-timeline v-if="service?.versions?.length">
            <el-timeline-item
              v-for="ver in service.versions"
              :key="ver.version"
              :timestamp="ver.releaseDate"
              placement="top"
              :type="ver.version === service.version ? 'primary' : 'info'"
            >
              <div class="version-item">
                <div class="version-header">
                  <strong>v{{ ver.version }}</strong>
                  <el-tag v-if="ver.version === service.version" type="success" size="small">
                    当前
                  </el-tag>
                  <el-tag v-if="installedVersion === ver.version" type="primary" size="small">
                    已安装
                  </el-tag>
                </div>
                <div class="version-size">大小: {{ ver.downloadSize }}</div>
                <div class="version-changelog">{{ ver.changelog }}</div>
                <el-button
                  v-if="installStatus === 'not-installed' && ver.version !== installedVersion"
                  type="primary"
                  size="small"
                  plain
                  @click="onInstallVersion(ver.version)"
                >
                  安装此版本
                </el-button>
              </div>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="暂无版本信息" :image-size="80" />
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue';
import {
  Download,
  Close,
  PictureFilled,
} from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { useServiceMarketStore } from './store';
import {
  MARKET_CATEGORY_LABELS,
  type DetailTab,
  type InstallStatus,
} from './types';

// ───── Props & Emits ─────

const props = defineProps<{
  serviceId: string;
}>();

const emit = defineEmits<{
  close: [];
  installed: [];
  uninstalled: [];
}>();

// ───── Store ─────

const store = useServiceMarketStore();
const service = computed(() => store.currentService);
const activeTab = ref<DetailTab>('overview');
const installing = ref(false);
const uninstalling = ref(false);

// ───── 计算属性 ─────

const installStatus = computed<InstallStatus>(() => {
  return store.getInstallStatus(props.serviceId);
});

const installedVersion = computed(() => {
  const installed = store.installedServices.find((s) => s.serviceId === props.serviceId);
  return installed?.version || null;
});

const categoryLabel = computed(() => {
  if (!service.value) return '';
  return MARKET_CATEGORY_LABELS[service.value.category] || service.value.category;
});

const renderedDescription = computed(() => {
  if (!service.value?.longDescription) {
    return service.value?.description || '<p>暂无详细介绍</p>';
  }
  // 简单的 Markdown 换行转 HTML
  return service.value.longDescription
    .split('\n\n')
    .map((p) => `<p>${p.replace(/\n/g, '<br>')}</p>`)
    .join('');
});

// ───── 操作 ─────

async function onInstall(version?: string) {
  installing.value = true;
  try {
    const ok = await store.installService(props.serviceId, version);
    if (ok) {
      emit('installed');
      ElMessage.success('安装成功');
    } else {
      ElMessage.error('安装失败，请稍后重试');
    }
  } finally {
    installing.value = false;
  }
}

async function onInstallVersion(version: string) {
  await onInstall(version);
}

async function onUninstall() {
  try {
    await ElMessageBox.confirm(
      `确定要卸载 "${service.value?.name}" 吗？相关数据可能会被删除。`,
      '确认卸载',
      {
        confirmButtonText: '确认卸载',
        cancelButtonText: '取消',
        type: 'warning',
      },
    );
  } catch {
    return; // 用户取消
  }

  uninstalling.value = true;
  try {
    const ok = await store.uninstallService(props.serviceId);
    if (ok) {
      emit('uninstalled');
      ElMessage.info('卸载成功');
    } else {
      ElMessage.error('卸载失败，请稍后重试');
    }
  } finally {
    uninstalling.value = false;
  }
}

// ───── 工具函数 ─────

function formatDate(dateStr: string): string {
  if (!dateStr) return '-';
  try {
    return new Date(dateStr).toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    });
  } catch {
    return dateStr;
  }
}

function formatCount(n: number): string {
  if (n >= 10000) return `${(n / 10000).toFixed(1)}万`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

// ───── 监听 serviceId 变化，加载详情 ─────

watch(
  () => props.serviceId,
  (id) => {
    if (id) {
      activeTab.value = 'overview';
      store.fetchServiceDetail(id);
    }
  },
  { immediate: true },
);

onMounted(() => {
  store.fetchServiceDetail(props.serviceId);
});
</script>

<style scoped lang="scss">
.service-detail {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

// ───── 头部 ─────

.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  flex-shrink: 0;
}

.detail-header-left {
  display: flex;
  align-items: center;
  gap: 12px;

  .detail-icon {
    flex-shrink: 0;
  }

  .detail-title-area {
    .detail-name {
      margin: 0;
      font-size: 18px;
      font-weight: 600;
      color: var(--el-text-color-primary);
    }
    .detail-author {
      font-size: 13px;
      color: var(--el-text-color-secondary);
    }
  }
}

.detail-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

// ───── 统计 ─────

.detail-stats {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  flex-shrink: 0;
  flex-wrap: wrap;

  .stat-item {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 13px;
    color: var(--el-text-color-regular);
  }

  .review-count {
    margin-left: 4px;
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }
}

// ───── Tabs ─────

.detail-tabs {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;

  :deep(.el-tabs__header) {
    margin: 0;
    padding: 0 16px;
    flex-shrink: 0;
  }

  :deep(.el-tabs__content) {
    flex: 1;
    overflow-y: auto;
    padding: 0;
  }
}

.detail-section {
  padding: 16px;
}

// ───── 描述 / 元数据 ─────

.detail-description {
  font-size: 14px;
  line-height: 1.7;
  color: var(--el-text-color-regular);
}

.detail-meta {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.meta-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.meta-label {
  width: 60px;
  color: var(--el-text-color-secondary);
  flex-shrink: 0;
}

.detail-tags {
  margin-top: 12px;
  display: flex;
  align-items: flex-start;
  gap: 8px;

  .tags-wrap {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }
}

// ───── 截图 ─────

.screenshots-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}

.screenshot-item {
  width: 100%;
  aspect-ratio: 4/3;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid var(--el-border-color-lighter);
  cursor: pointer;

  .image-error {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 100%;
    background: var(--el-fill-color-light);
    color: var(--el-text-color-secondary);
    font-size: 32px;
  }
}

// ───── 评价 ─────

.reviews-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.review-item {
  padding: 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
}

.review-header {
  display: flex;
  align-items: center;
  gap: 8px;

  .review-avatar {
    flex-shrink: 0;
  }

  .review-user {
    font-weight: 500;
    font-size: 13px;
  }

  .review-date {
    margin-left: auto;
    font-size: 12px;
    color: var(--el-text-color-placeholder);
  }
}

.review-content {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--el-text-color-regular);
}

// ───── 版本 ─────

.version-item {
  .version-header {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
  }

  .version-size {
    margin-top: 4px;
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }

  .version-changelog {
    margin-top: 6px;
    font-size: 13px;
    line-height: 1.5;
    color: var(--el-text-color-regular);
    white-space: pre-wrap;
  }

  .el-button {
    margin-top: 8px;
  }
}
</style>
