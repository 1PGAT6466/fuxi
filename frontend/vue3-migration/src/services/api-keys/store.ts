/**
 * 伏羲 v2.1 — API Key 管理 Store
 *
 * 管理 Key 列表缓存、选中的 Key、使用量数据、创建/编辑弹窗状态
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { ApiKey, ApiKeyUsageResponse, UsagePeriod, CreateApiKeyRequest } from './types';

export const useApiKeysStore = defineStore('api-keys', () => {
  // ───── 列表数据 ─────
  const keys = ref<ApiKey[]>([]);
  const total = ref<number>(0);
  const loading = ref<boolean>(false);
  const error = ref<string | null>(null);

  // ───── 选中 & 详情 ─────
  const selectedKeyId = ref<string | null>(null);
  const selectedKey = ref<ApiKey | null>(null);

  // ───── 使用量数据 ─────
  const usageData = ref<ApiKeyUsageResponse | null>(null);
  const usagePeriod = ref<UsagePeriod>('week');
  const usageLoading = ref<boolean>(false);

  // ───── 弹窗状态 ─────
  const showCreateDialog = ref<boolean>(false);
  const showEditDialog = ref<boolean>(false);
  const showUsageDialog = ref<boolean>(false);
  const showDeleteConfirm = ref<boolean>(false);
  const editingKey = ref<ApiKey | null>(null);

  // ───── 新创建的 Key（显示一次） ─────
  const lastCreatedKey = ref<ApiKey | null>(null);
  const showNewKeyModal = ref<boolean>(false);

  // ───── Getters ─────

  /** 根据 ID 获取选中的 Key */
  const currentKey = computed<ApiKey | null>(() => {
    if (!selectedKeyId.value) return null;
    return keys.value.find((k) => k.id === selectedKeyId.value) || null;
  });

  /** 活跃 Key 数量 */
  const activeKeyCount = computed<number>(() => {
    return keys.value.filter((k) => k.status === 'active').length;
  });

  /** 即将过期的 Key（7 天内过期） */
  const expiringSoonKeys = computed<ApiKey[]>(() => {
    const now = Date.now();
    const sevenDays = 7 * 24 * 60 * 60 * 1000;
    return keys.value.filter((k) => {
      if (!k.expiresAt || k.status !== 'active') return false;
      const expires = new Date(k.expiresAt).getTime();
      return expires > now && expires - now <= sevenDays;
    });
  });

  // ───── Actions ─────

  /** 设置 Key 列表 */
  function setKeys(list: ApiKey[], t: number): void {
    keys.value = list;
    total.value = t;
    error.value = null;
  }

  /** 添加一个 Key 到列表 */
  function addKey(key: ApiKey): void {
    keys.value.unshift(key);
    total.value++;
  }

  /** 更新列表中的 Key */
  function updateKeyInList(updated: ApiKey): void {
    const idx = keys.value.findIndex((k) => k.id === updated.id);
    if (idx !== -1) {
      keys.value[idx] = { ...keys.value[idx], ...updated };
    }
  }

  /** 从列表中移除 Key */
  function removeKeyFromList(id: string): void {
    keys.value = keys.value.filter((k) => k.id !== id);
    total.value = Math.max(0, total.value - 1);
    if (selectedKeyId.value === id) {
      selectedKeyId.value = null;
    }
  }

  /** 设置加载状态 */
  function setLoading(val: boolean): void {
    loading.value = val;
  }

  /** 设置错误信息 */
  function setError(msg: string | null): void {
    error.value = msg;
  }

  /** 选择 Key */
  function selectKey(id: string | null): void {
    selectedKeyId.value = id;
    selectedKey.value = id ? keys.value.find((k) => k.id === id) || null : null;
  }

  /** 设置使用量数据 */
  function setUsageData(data: ApiKeyUsageResponse): void {
    usageData.value = data;
  }

  /** 设置使用量统计周期 */
  function setUsagePeriod(period: UsagePeriod): void {
    usagePeriod.value = period;
  }

  /** 显示创建弹窗 */
  function openCreateDialog(): void {
    editingKey.value = null;
    showCreateDialog.value = true;
  }

  /** 显示编辑弹窗 */
  function openEditDialog(key: ApiKey): void {
    editingKey.value = key;
    showEditDialog.value = true;
  }

  /** 关闭创建/编辑弹窗 */
  function closeDialogs(): void {
    showCreateDialog.value = false;
    showEditDialog.value = false;
    showDeleteConfirm.value = false;
    showUsageDialog.value = false;
    editingKey.value = null;
  }

  /** 显示使用量弹窗 */
  function openUsageDialog(key: ApiKey): void {
    selectedKey.value = key;
    showUsageDialog.value = true;
  }

  /** 显示删除确认 */
  function openDeleteConfirm(key: ApiKey): void {
    selectedKey.value = key;
    showDeleteConfirm.value = true;
  }

  /** 设置新创建的 Key（显示一次性 Key） */
  function setLastCreatedKey(key: ApiKey): void {
    lastCreatedKey.value = key;
    showNewKeyModal.value = true;
  }

  /** 关闭新 Key 显示弹窗 */
  function closeNewKeyModal(): void {
    showNewKeyModal.value = false;
    lastCreatedKey.value = null;
  }

  return {
    // 状态
    keys,
    total,
    loading,
    error,
    selectedKeyId,
    selectedKey,
    usageData,
    usagePeriod,
    usageLoading,
    showCreateDialog,
    showEditDialog,
    showUsageDialog,
    showDeleteConfirm,
    editingKey,
    lastCreatedKey,
    showNewKeyModal,

    // Getters
    currentKey,
    activeKeyCount,
    expiringSoonKeys,

    // Actions
    setKeys,
    addKey,
    updateKeyInList,
    removeKeyFromList,
    setLoading,
    setError,
    selectKey,
    setUsageData,
    setUsagePeriod,
    openCreateDialog,
    openEditDialog,
    closeDialogs,
    openUsageDialog,
    openDeleteConfirm,
    setLastCreatedKey,
    closeNewKeyModal,
  };
});
