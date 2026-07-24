/**
 * 伏羲 v2.1 — 服务市场 Pinia Store
 *
 * 管理服务市场状态：列表、详情、已安装服务、安装/卸载状态。
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { createLogger } from '@/utils/logger';
import * as marketApi from './api';
import type {
  MarketService,
  MarketServiceCategory,
  SortField,
  SortOption,
  InstalledService,
  InstallStatus,
} from './types';

const logger = createLogger('ServiceMarketStore');

export const useServiceMarketStore = defineStore('service-market', () => {
  // ───── 列表状态 ─────

  /** 服务列表 */
  const services = ref<MarketService[]>([]);
  /** 总数 */
  const total = ref(0);
  /** 当前页码 */
  const page = ref(1);
  /** 每页条数 */
  const pageSize = ref(12);
  /** 加载中 */
  const loading = ref(false);
  /** 错误信息 */
  const error = ref<string | null>(null);

  // ───── 筛选/排序 ─────

  /** 当前分类筛选 */
  const selectedCategory = ref<MarketServiceCategory | ''>('');
  /** 搜索关键词 */
  const searchQuery = ref('');
  /** 当前排序字段 */
  const sortField = ref<SortField>('downloads');
  /** 排序方向 */
  const sortDirection = ref<'asc' | 'desc'>('desc');

  // ───── 详情状态 ─────

  /** 当前查看的服务详情 */
  const currentService = ref<MarketService | null>(null);
  /** 详情加载中 */
  const detailLoading = ref(false);

  // ───── 已安装状态 ─────

  /** 已安装服务列表 */
  const installedServices = ref<InstalledService[]>([]);
  /** 安装操作状态映射（serviceId → InstallStatus） */
  const installStatusMap = ref<Record<string, InstallStatus>>({});

  // ───── Getters ─────

  /** 预定义排序选项 */
  const sortOptions = computed<SortOption[]>(() => [
    { field: 'downloads', label: '下载量', direction: 'desc' },
    { field: 'rating', label: '评分', direction: 'desc' },
    { field: 'name', label: '名称', direction: 'asc' },
    { field: 'updatedAt', label: '最近更新', direction: 'desc' },
  ]);

  /** 当前选中的排序选项 */
  const currentSort = computed<SortOption>(() => {
    const found = sortOptions.value.find(
      (s) => s.field === sortField.value && s.direction === sortDirection.value,
    );
    return (
      found || { field: 'downloads', label: '下载量', direction: 'desc' }
    );
  });

  /** 总页数 */
  const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)));

  /** 获取某个服务的安装状态 */
  function getInstallStatus(serviceId: string): InstallStatus {
    if (installStatusMap.value[serviceId]) return installStatusMap.value[serviceId];
    const isInstalled = installedServices.value.some((s) => s.serviceId === serviceId);
    return isInstalled ? 'installed' : 'not-installed';
  }

  // ───── 操作：加载服务列表 ─────

  /** 加载服务列表 */
  async function fetchServices(): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      const res = await marketApi.getMarketServices({
        category: selectedCategory.value || undefined,
        search: searchQuery.value || undefined,
        sortField: sortField.value,
        sortDirection: sortDirection.value,
        page: page.value,
        pageSize: pageSize.value,
      });
      services.value = res.items;
      total.value = res.total;
    } catch (e) {
      const msg = e instanceof Error ? e.message : '加载服务列表失败';
      error.value = msg;
      logger.error('fetchServices 失败:', msg);
    } finally {
      loading.value = false;
    }
  }

  // ───── 操作：加载已安装服务 ─────

  /** 加载已安装服务 */
  async function fetchInstalledServices(): Promise<void> {
    try {
      installedServices.value = await marketApi.getInstalledServices();
    } catch (e) {
      logger.error('fetchInstalledServices 失败:', e);
    }
  }

  // ───── 操作：加载服务详情 ─────

  /** 加载服务详情 */
  async function fetchServiceDetail(id: string): Promise<void> {
    detailLoading.value = true;
    try {
      currentService.value = await marketApi.getMarketServiceById(id);
    } catch (e) {
      const msg = e instanceof Error ? e.message : '加载服务详情失败';
      error.value = msg;
      logger.error('fetchServiceDetail 失败:', msg);
    } finally {
      detailLoading.value = false;
    }
  }

  // ───── 操作：安装服务 ─────

  /** 安装服务 */
  async function installService(serviceId: string, version?: string): Promise<boolean> {
    installStatusMap.value[serviceId] = 'installing';
    try {
      const res = await marketApi.installService({ serviceId, version });
      if (res.success) {
        installStatusMap.value[serviceId] = 'installed';
        // 刷新已安装列表
        await fetchInstalledServices();
        logger.info(`服务 "${serviceId}" 安装成功 v${res.installedVersion}`);
        return true;
      }
      installStatusMap.value[serviceId] = 'error';
      return false;
    } catch (e) {
      installStatusMap.value[serviceId] = 'error';
      logger.error(`安装服务 "${serviceId}" 失败:`, e);
      return false;
    }
  }

  // ───── 操作：卸载服务 ─────

  /** 卸载服务 */
  async function uninstallService(serviceId: string): Promise<boolean> {
    installStatusMap.value[serviceId] = 'installing';
    try {
      const res = await marketApi.uninstallService({ serviceId });
      if (res.success) {
        installStatusMap.value[serviceId] = 'not-installed';
        await fetchInstalledServices();
        logger.info(`服务 "${serviceId}" 卸载成功`);
        return true;
      }
      installStatusMap.value[serviceId] = 'error';
      return false;
    } catch (e) {
      installStatusMap.value[serviceId] = 'error';
      logger.error(`卸载服务 "${serviceId}" 失败:`, e);
      return false;
    }
  }

  // ───── 操作：筛选排序变更 ─────

  /** 设置分类筛选 */
  function setCategory(category: MarketServiceCategory | ''): void {
    selectedCategory.value = category;
    page.value = 1;
    fetchServices();
  }

  /** 设置排序 */
  function setSort(field: SortField, direction: 'asc' | 'desc'): void {
    sortField.value = field;
    sortDirection.value = direction;
    page.value = 1;
    fetchServices();
  }

  /** 设置搜索 */
  function setSearch(query: string): void {
    searchQuery.value = query;
    page.value = 1;
    fetchServices();
  }

  /** 设置页码 */
  function setPage(p: number): void {
    page.value = p;
    fetchServices();
  }

  /** 初始化：加载列表和已安装信息 */
  async function init(): Promise<void> {
    await Promise.all([fetchServices(), fetchInstalledServices()]);
  }

  return {
    // state
    services,
    total,
    page,
    pageSize,
    loading,
    error,
    selectedCategory,
    searchQuery,
    sortField,
    sortDirection,
    currentService,
    detailLoading,
    installedServices,
    installStatusMap,
    // getters
    sortOptions,
    currentSort,
    totalPages,
    getInstallStatus,
    // actions
    fetchServices,
    fetchInstalledServices,
    fetchServiceDetail,
    installService,
    uninstallService,
    setCategory,
    setSort,
    setSearch,
    setPage,
    init,
  };
});
