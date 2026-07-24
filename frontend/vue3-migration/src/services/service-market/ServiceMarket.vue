<template>
  <div class="service-market">
    <!-- ===== 顶部工具栏 ===== -->
    <div class="market-toolbar">
      <!-- 搜索栏 -->
      <div class="market-search">
        <el-input
          v-model="localSearch"
          placeholder="搜索服务..."
          :prefix-icon="SearchIcon"
          clearable
          class="search-input"
          @input="onSearchInput"
          @clear="onSearchClear"
        />
      </div>

      <!-- 分类筛选 -->
      <div class="market-categories">
        <el-radio-group
          v-model="store.selectedCategory"
          size="small"
          @change="onCategoryChange"
        >
          <el-radio-button value="">
            全部
          </el-radio-button>
          <el-radio-button
            v-for="(label, key) in categoryLabels"
            :key="key"
            :value="key"
          >
            {{ label }}
          </el-radio-button>
        </el-radio-group>
      </div>

      <!-- 排序 -->
      <div class="market-sort">
        <el-dropdown trigger="click" @command="onSortCommand">
          <el-button size="small">
            {{ store.currentSort.label }}
            <el-icon class="el-icon--right">
              <ArrowDown v-if="store.sortDirection === 'desc'" />
              <ArrowUp v-else />
            </el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item
                v-for="opt in store.sortOptions"
                :key="`${opt.field}-${opt.direction}`"
                :command="opt"
              >
                {{ opt.label }}
                <span v-if="opt.direction === 'desc'" class="sort-dir">↓</span>
                <span v-else class="sort-dir">↑</span>
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>

      <!-- 已安装标签 -->
      <el-button
        size="small"
        :type="showInstalledOnly ? 'primary' : 'default'"
        @click="toggleInstalledFilter"
      >
        已安装 ({{ store.installedServices.length }})
      </el-button>

      <!-- 刷新 -->
      <el-button size="small" :icon="RefreshIcon" :loading="store.loading" @click="onRefresh">
        刷新
      </el-button>
    </div>

    <!-- ===== 加载/错误状态 ===== -->
    <div v-if="store.loading && store.services.length === 0" class="market-loading">
      <el-skeleton :rows="3" animated />
    </div>

    <el-alert
      v-if="store.error"
      :title="store.error"
      type="error"
      show-icon
      closable
      class="market-error"
      @close="store.error = null"
    />

    <!-- ===== 服务列表 / 详情 两栏布局 ===== -->
    <div v-else class="market-body" :class="{ 'has-detail': selectedServiceId }">
      <!-- 左侧：服务列表 -->
      <div class="market-list-pane">
        <!-- 空状态 -->
        <el-empty
          v-if="!store.loading && displayServices.length === 0"
          description="暂无服务"
          :image-size="120"
        />

        <!-- 网格列表 -->
        <div v-else class="service-grid">
          <el-card
            v-for="service in displayServices"
            :key="service.id"
            class="service-card"
            :class="{
              'is-selected': selectedServiceId === service.id,
              'is-installed': getInstallStatus(service.id) === 'installed',
            }"
            shadow="hover"
            @click="onSelectService(service.id)"
          >
            <div class="service-card-header">
              <div class="service-icon">
                <el-avatar :size="44" :src="service.icon">
                  {{ service.name.charAt(0) }}
                </el-avatar>
              </div>
              <div class="service-card-info">
                <div class="service-name">{{ service.name }}</div>
                <div class="service-author">{{ service.author }}</div>
              </div>
              <div class="service-install-badge">
                <el-tag v-if="getInstallStatus(service.id) === 'installed'" type="success" size="small">
                  已安装
                </el-tag>
                <el-tag
                  v-else-if="getInstallStatus(service.id) === 'installing'"
                  type="warning"
                  size="small"
                >
                  安装中...
                </el-tag>
              </div>
            </div>

            <div class="service-card-desc">
              {{ service.description }}
            </div>

            <div class="service-card-footer">
              <div class="service-stats">
                <span class="stat-rating" :title="`评分 ${service.rating}`">
                  <el-icon><StarFilled /></el-icon>
                  {{ service.rating.toFixed(1) }}
                </span>
                <span class="stat-downloads">
                  <el-icon><Download /></el-icon>
                  {{ formatCount(service.downloads) }}
                </span>
              </div>
              <div class="service-price-tag">
                <el-tag v-if="service.price === 'free'" type="success" size="small">免费</el-tag>
                <el-tag v-else type="warning" size="small">付费</el-tag>
              </div>
            </div>

            <div class="service-card-tags">
              <el-tag
                v-for="tag in service.tags.slice(0, 3)"
                :key="tag"
                size="small"
                class="tag-item"
              >
                {{ tag }}
              </el-tag>
            </div>
          </el-card>
        </div>

        <!-- 分页 -->
        <div v-if="store.totalPages > 1" class="market-pagination">
          <el-pagination
            v-model:current-page="store.page"
            :page-size="store.pageSize"
            :total="store.total"
            layout="prev, pager, next"
            @current-change="onPageChange"
          />
        </div>
      </div>

      <!-- 右侧：服务详情 -->
      <div v-if="selectedServiceId" class="market-detail-pane">
        <ServiceMarketDetail
          :service-id="selectedServiceId"
          @close="selectedServiceId = null"
          @installed="onServiceInstalled"
          @uninstalled="onServiceUninstalled"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue';
import { useDebounceFn } from '@vueuse/core';
import {
  Search as SearchIcon,
  Refresh as RefreshIcon,
  ArrowDown,
  ArrowUp,
  StarFilled,
  Download,
} from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { useServiceMarketStore } from './store';
import {
  MARKET_CATEGORY_LABELS,
  type MarketServiceCategory,
  type MarketService,
  type SortOption,
  type InstallStatus,
} from './types';
import ServiceMarketDetail from './ServiceMarketDetail.vue';

// ───── Store ─────

const store = useServiceMarketStore();

// ───── 本地搜索（防抖） ─────

const localSearch = ref('');
const showInstalledOnly = ref(false);

const onSearchInput = useDebounceFn((val: string) => {
  store.setSearch(val);
}, 300);

function onSearchClear() {
  localSearch.value = '';
  store.setSearch('');
}

function onCategoryChange() {
  // store.selectedCategory 已被 v-model 更新，直接触发加载
}

function onSortCommand(opt: SortOption) {
  store.setSort(opt.field, opt.direction);
}

// ───── 选中服务 ─────

const selectedServiceId = ref<string | null>(null);

function onSelectService(id: string) {
  selectedServiceId.value = id === selectedServiceId.value ? null : id;
  if (selectedServiceId.value) {
    store.fetchServiceDetail(selectedServiceId.value);
  }
}

// ───── 显示服务列表 ─────

const categoryLabels = MARKET_CATEGORY_LABELS;

const displayServices = computed<MarketService[]>(() => {
  let list = store.services;
  if (showInstalledOnly.value) {
    const installedIds = new Set(store.installedServices.map((s) => s.serviceId));
    list = list.filter((s) => installedIds.has(s.id));
  }
  return list;
});

function getInstallStatus(serviceId: string): InstallStatus {
  return store.getInstallStatus(serviceId);
}

function toggleInstalledFilter() {
  showInstalledOnly.value = !showInstalledOnly.value;
}

// ───── 操作 ─────

function onRefresh() {
  store.init();
}

function onPageChange(p: number) {
  store.setPage(p);
}

function onServiceInstalled() {
  store.fetchInstalledServices();
  ElMessage.success('服务安装成功');
}

function onServiceUninstalled() {
  store.fetchInstalledServices();
  ElMessage.info('服务已卸载');
}

// ───── 格式化数字 ─────

function formatCount(n: number): string {
  if (n >= 10000) return `${(n / 10000).toFixed(1)}万`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

// ───── 初始化 ─────

onMounted(() => {
  store.init();
});
</script>

<style scoped lang="scss">
.service-market {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 16px;
  gap: 16px;
  overflow: hidden;
}

// ───── 工具栏 ─────

.market-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  flex-shrink: 0;

  .market-search {
    flex: 0 0 260px;
  }

  .market-categories {
    flex: 1;
    min-width: 0;
    overflow-x: auto;
  }

  .market-sort {
    flex-shrink: 0;
  }
}

// ───── 主区域 ─────

.market-body {
  flex: 1;
  display: flex;
  gap: 16px;
  overflow: hidden;

  &.has-detail {
    .market-list-pane {
      flex: 0 0 60%;
    }
    .market-detail-pane {
      flex: 1;
    }
  }
}

.market-list-pane {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.market-detail-pane {
  display: flex;
  flex-direction: column;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  overflow: hidden;
}

// ───── 服务卡片网格 ─────

.service-grid {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
  overflow-y: auto;
  align-content: start;
  padding-right: 4px;
}

.service-card {
  cursor: pointer;
  transition: all 0.2s ease;
  border: 2px solid transparent;

  &:hover {
    border-color: var(--el-color-primary-light-5);
  }

  &.is-selected {
    border-color: var(--el-color-primary);
    box-shadow: 0 0 0 1px var(--el-color-primary-light-5);
  }

  &.is-installed {
    .service-card-header {
      position: relative;
      &::after {
        content: '';
        position: absolute;
        top: 0;
        right: 0;
        width: 8px;
        height: 8px;
        background: var(--el-color-success);
        border-radius: 50%;
      }
    }
  }

  :deep(.el-card__body) {
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
}

.service-card-header {
  display: flex;
  align-items: center;
  gap: 10px;

  .service-icon {
    flex-shrink: 0;
  }

  .service-card-info {
    flex: 1;
    min-width: 0;

    .service-name {
      font-weight: 600;
      font-size: 15px;
      color: var(--el-text-color-primary);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .service-author {
      font-size: 12px;
      color: var(--el-text-color-secondary);
      margin-top: 2px;
    }
  }

  .service-install-badge {
    flex-shrink: 0;
  }
}

.service-card-desc {
  font-size: 13px;
  color: var(--el-text-color-regular);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.service-card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;

  .service-stats {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 12px;
    color: var(--el-text-color-secondary);

    .stat-rating {
      display: flex;
      align-items: center;
      gap: 2px;
      color: var(--el-color-warning, #e6a23c);
    }

    .stat-downloads {
      display: flex;
      align-items: center;
      gap: 2px;
    }
  }
}

.service-card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;

  .tag-item {
    font-size: 11px;
  }
}

// ───── 分页 ─────

.market-pagination {
  display: flex;
  justify-content: center;
  padding: 12px 0;
  flex-shrink: 0;
}

// ───── 状态 ─────

.market-loading {
  padding: 24px;
}

.market-error {
  margin-bottom: 0;
}

// ───── 响应式 ─────

@media (max-width: 900px) {
  .market-body.has-detail {
    flex-direction: column;

    .market-list-pane {
      flex: none;
      height: 40%;
    }
  }

  .service-grid {
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  }
}
</style>
