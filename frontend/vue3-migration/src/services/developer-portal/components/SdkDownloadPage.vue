<template>
  <div class="sdk-download-page">
    <!-- 工具栏 -->
    <div class="sdk-download-page__toolbar">
      <h3 class="sdk-download-page__title">SDK 下载</h3>
      <el-button text @click="$emit('refresh')">
        <el-icon><Refresh /></el-icon>
        刷新
      </el-button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="sdk-download-page__loading">
      <el-skeleton :rows="6" animated />
    </div>

    <!-- Error -->
    <el-alert
      v-else-if="error"
      :title="error"
      type="error"
      show-icon
      :closable="false"
      class="sdk-download-page__error"
    >
      <template #default>
        <el-button size="small" type="primary" link @click="$emit('refresh')">重试</el-button>
      </template>
    </el-alert>

    <!-- SDK 列表 -->
    <div v-else class="sdk-download-page__grid">
      <div
        v-for="sdk in sdks"
        :key="sdk.id"
        class="sdk-download-page__card"
        :class="{ 'is-selected': selectedLanguage === sdk.language }"
        @click="$emit('select-language', selectedLanguage === sdk.language ? null : sdk.language)"
      >
        <div class="sdk-download-page__card-header">
          <span class="sdk-download-page__card-language">
            {{ SDK_LANGUAGE_ICONS[sdk.language] }} {{ SDK_LANGUAGE_LABELS[sdk.language] }}
          </span>
          <el-tag size="small">{{ sdk.version }}</el-tag>
        </div>

        <p class="sdk-download-page__card-desc">{{ sdk.description }}</p>

        <div class="sdk-download-page__card-meta">
          <div class="sdk-download-page__card-meta-item">
            <el-icon :size="14"><Calendar /></el-icon>
            <span>发布：{{ sdk.releaseDate }}</span>
          </div>
          <div class="sdk-download-page__card-meta-item">
            <el-icon :size="14"><FolderOpened /></el-icon>
            <span>{{ sdk.size }}</span>
          </div>
          <div class="sdk-download-page__card-meta-item">
            <el-icon :size="14"><Document /></el-icon>
            <span>{{ sdk.license }}</span>
          </div>
        </div>

        <!-- 特性 -->
        <div v-if="sdk.features?.length" class="sdk-download-page__card-features">
          <el-tag
            v-for="(feat, idx) in sdk.features"
            :key="idx"
            size="small"
            effect="plain"
          >
            {{ feat }}
          </el-tag>
        </div>

        <!-- 展开详情 -->
        <div v-if="selectedLanguage === sdk.language" class="sdk-download-page__card-detail">
          <div class="sdk-download-page__install-section">
            <span class="sdk-download-page__install-label">安装命令：</span>
            <code class="sdk-download-page__install-code">{{ getInstallCommand(sdk) }}</code>
            <el-button
              size="small"
              text
              type="primary"
              @click.stop="copyToClipboard(getInstallCommand(sdk))"
            >
              <el-icon><CopyDocument /></el-icon>
              复制
            </el-button>
          </div>

          <!-- 包信息 -->
          <div class="sdk-download-page__pkg-info">
            <div v-if="sdk.npmPackage" class="sdk-download-page__pkg-item">
              <strong>npm：</strong>
              <a :href="`https://www.npmjs.com/package/${sdk.npmPackage}`" target="_blank">
                {{ sdk.npmPackage }}
              </a>
            </div>
            <div v-if="sdk.pipPackage" class="sdk-download-page__pkg-item">
              <strong>PyPI：</strong>
              <a :href="`https://pypi.org/project/${sdk.pipPackage}`" target="_blank">
                {{ sdk.pipPackage }}
              </a>
            </div>
            <div v-if="sdk.mavenCoordinate" class="sdk-download-page__pkg-item">
              <strong>Maven：</strong>
              <code>{{ sdk.mavenCoordinate }}</code>
            </div>
          </div>

          <div class="sdk-download-page__detail-actions">
            <el-button type="primary" size="default" @click.stop="openDownload(sdk.downloadUrl)">
              <el-icon><Download /></el-icon>
              下载 SDK
            </el-button>
            <el-button size="default" @click.stop="openLink(sdk.documentationUrl)">
              <el-icon><Document /></el-icon>
              查看文档
            </el-button>
            <el-button size="default" @click.stop="openLink(sdk.repositoryUrl)">
              <el-icon><Link /></el-icon>
              源码仓库
            </el-button>
          </div>

          <div v-if="sdk.changelog" class="sdk-download-page__changelog">
            <span class="sdk-download-page__changelog-label">更新日志：</span>
            <p>{{ sdk.changelog }}</p>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <el-empty v-if="!sdks.length" description="暂无 SDK 可供下载" />
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * SDK 下载页面 — 展示多语言 SDK 下载入口
 */
import { Refresh, Calendar, FolderOpened, Document, CopyDocument, Download, Link } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import type { SdkInfo, SdkLanguage } from '../types';
import { SDK_LANGUAGE_LABELS, SDK_LANGUAGE_ICONS } from '../types';

defineProps<{
  sdks: SdkInfo[];
  loading: boolean;
  error: string | null;
  selectedLanguage: SdkLanguage | null;
}>();

defineEmits<{
  'select-language': [lang: SdkLanguage | null];
  refresh: [];
}>();

function getInstallCommand(sdk: SdkInfo): string {
  if (sdk.npmPackage) return `npm install ${sdk.npmPackage}`;
  if (sdk.pipPackage) return `pip install ${sdk.pipPackage}`;
  if (sdk.language === 'java') return 'mvn dependency:copy -Dartifact=...';
  return sdk.downloadUrl;
}

async function copyToClipboard(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text);
    ElMessage.success('已复制到剪贴板');
  } catch {
    ElMessage.error('复制失败，请手动复制');
  }
}

function openDownload(url: string): void {
  window.open(url, '_blank', 'noopener');
}

function openLink(url: string): void {
  window.open(url, '_blank', 'noopener');
}
</script>

<style scoped lang="scss">
.sdk-download-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.sdk-download-page__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.sdk-download-page__title {
  font-size: 17px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.sdk-download-page__loading,
.sdk-download-page__error {
  padding: 16px 0;
}

.sdk-download-page__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 16px;
}

.sdk-download-page__card {
  padding: 20px;
  background: var(--bg-subtle);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  cursor: pointer;
  transition:
    border-color var(--duration-fast),
    box-shadow var(--duration-fast);

  &:hover {
    border-color: var(--brand);
    box-shadow: var(--shadow-sm);
  }

  &.is-selected {
    border-color: var(--brand);
    box-shadow: 0 0 0 2px var(--brand-soft);
  }
}

.sdk-download-page__card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.sdk-download-page__card-language {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

.sdk-download-page__card-desc {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0 0 12px;
  line-height: 1.5;
}

.sdk-download-page__card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 10px;
}

.sdk-download-page__card-meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-tertiary);
}

.sdk-download-page__card-features {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
}

.sdk-download-page__card-detail {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--border-color);
}

.sdk-download-page__install-section {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

.sdk-download-page__install-label {
  font-size: 13px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.sdk-download-page__install-code {
  font-family: monospace;
  font-size: 13px;
  background: var(--bg-card);
  padding: 4px 10px;
  border-radius: 4px;
  color: var(--brand);
}

.sdk-download-page__pkg-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 12px;
}

.sdk-download-page__pkg-item {
  font-size: 13px;
  color: var(--text-secondary);

  a {
    color: var(--brand);
    text-decoration: none;

    &:hover {
      text-decoration: underline;
    }
  }

  code {
    font-family: monospace;
    font-size: 12px;
    background: var(--bg-card);
    padding: 1px 6px;
    border-radius: 4px;
  }
}

.sdk-download-page__detail-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}

.sdk-download-page__changelog {
  font-size: 12px;
  color: var(--text-tertiary);

  p {
    margin: 4px 0 0;
    line-height: 1.5;
  }
}

.sdk-download-page__changelog-label {
  font-weight: 600;
  color: var(--text-secondary);
}

/* ── 响应式 ── */
@media (max-width: 767px) {
  .sdk-download-page__grid {
    grid-template-columns: 1fr;
  }
}
</style>
