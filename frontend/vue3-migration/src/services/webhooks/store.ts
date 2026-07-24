/**
 * 伏羲 v2.1 — Webhook 配置管理 Store
 *
 * 管理 Webhook 列表缓存、选中的 Webhook、投递记录、
 * 创建/编辑弹窗状态及测试发送结果
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type {
  Webhook,
  WebhookDelivery,
  WebhookDeliveryListResponse,
  WebhookEventType,
  CreateWebhookRequest,
} from './types';

export const useWebhooksStore = defineStore('webhooks', () => {
  // ───── 列表数据 ─────
  const webhooks = ref<Webhook[]>([]);
  const total = ref<number>(0);
  const loading = ref<boolean>(false);
  const error = ref<string | null>(null);

  // ───── 选中 & 详情 ─────
  const selectedWebhookId = ref<string | null>(null);
  const selectedWebhook = ref<Webhook | null>(null);

  // ───── 投递记录 ─────
  const deliveries = ref<WebhookDelivery[]>([]);
  const deliveriesTotal = ref<number>(0);
  const deliveriesLoading = ref<boolean>(false);

  // ───── 弹窗状态 ─────
  const showCreateDialog = ref<boolean>(false);
  const showEditDialog = ref<boolean>(false);
  const showTestDialog = ref<boolean>(false);
  const showDeliveryDialog = ref<boolean>(false);
  const editingWebhook = ref<Webhook | null>(null);

  // ───── 新创建的 Webhook（显示一次 secret） ─────
  const lastCreatedWebhook = ref<Webhook | null>(null);
  const showNewWebhookModal = ref<boolean>(false);

  // ───── 测试发送状态 ─────
  const testLoading = ref<boolean>(false);
  const testResult = ref<{ success: boolean; statusCode: number; responseTimeMs: number } | null>(null);

  // ───── Getters ─────

  /** 根据 ID 获取选中的 Webhook */
  const currentWebhook = computed<Webhook | null>(() => {
    if (!selectedWebhookId.value) return null;
    return webhooks.value.find((w) => w.id === selectedWebhookId.value) || null;
  });

  /** 活跃 Webhook 数量 */
  const activeWebhookCount = computed<number>(() => {
    return webhooks.value.filter((w) => w.status === 'active').length;
  });

  /** 失败 Webhook 数量 */
  const failedWebhookCount = computed<number>(() => {
    return webhooks.value.filter((w) => w.status === 'failed').length;
  });

  /** 按事件类型分组的事件统计 */
  const activeEventTypes = computed<WebhookEventType[]>(() => {
    const types = new Set<WebhookEventType>();
    webhooks.value
      .filter((w) => w.status === 'active')
      .forEach((w) => w.events.forEach((e) => types.add(e)));
    return Array.from(types);
  });

  // ───── Actions ─────

  /** 设置 Webhook 列表 */
  function setWebhooks(list: Webhook[], t: number): void {
    webhooks.value = list;
    total.value = t;
    error.value = null;
  }

  /** 添加一个 Webhook 到列表 */
  function addWebhook(webhook: Webhook): void {
    webhooks.value.unshift(webhook);
    total.value++;
  }

  /** 更新列表中的 Webhook */
  function updateWebhookInList(updated: Webhook): void {
    const idx = webhooks.value.findIndex((w) => w.id === updated.id);
    if (idx !== -1) {
      webhooks.value[idx] = { ...webhooks.value[idx], ...updated };
    }
  }

  /** 从列表中移除 Webhook */
  function removeWebhookFromList(id: string): void {
    webhooks.value = webhooks.value.filter((w) => w.id !== id);
    total.value = Math.max(0, total.value - 1);
    if (selectedWebhookId.value === id) {
      selectedWebhookId.value = null;
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

  /** 选择 Webhook */
  function selectWebhook(id: string | null): void {
    selectedWebhookId.value = id;
    selectedWebhook.value = id
      ? webhooks.value.find((w) => w.id === id) || null
      : null;
  }

  /** 设置投递记录 */
  function setDeliveries(list: WebhookDelivery[], t: number): void {
    deliveries.value = list;
    deliveriesTotal.value = t;
  }

  /** 显示创建弹窗 */
  function openCreateDialog(): void {
    editingWebhook.value = null;
    showCreateDialog.value = true;
  }

  /** 显示编辑弹窗 */
  function openEditDialog(webhook: Webhook): void {
    editingWebhook.value = { ...webhook };
    showEditDialog.value = true;
  }

  /** 显示测试发送弹窗 */
  function openTestDialog(webhook: Webhook): void {
    selectedWebhook.value = webhook;
    testResult.value = null;
    showTestDialog.value = true;
  }

  /** 显示投递记录弹窗 */
  function openDeliveryDialog(webhook: Webhook): void {
    selectedWebhook.value = webhook;
    showDeliveryDialog.value = true;
  }

  /** 关闭所有弹窗 */
  function closeDialogs(): void {
    showCreateDialog.value = false;
    showEditDialog.value = false;
    showTestDialog.value = false;
    showDeliveryDialog.value = false;
    editingWebhook.value = null;
    testResult.value = null;
  }

  /** 设置新创建的 Webhook（显示一次性 secret） */
  function setLastCreatedWebhook(webhook: Webhook): void {
    lastCreatedWebhook.value = webhook;
    showNewWebhookModal.value = true;
  }

  /** 关闭新 Webhook 显示弹窗 */
  function closeNewWebhookModal(): void {
    showNewWebhookModal.value = false;
    lastCreatedWebhook.value = null;
  }

  return {
    // 状态
    webhooks,
    total,
    loading,
    error,
    selectedWebhookId,
    selectedWebhook,
    deliveries,
    deliveriesTotal,
    deliveriesLoading,
    showCreateDialog,
    showEditDialog,
    showTestDialog,
    showDeliveryDialog,
    editingWebhook,
    lastCreatedWebhook,
    showNewWebhookModal,
    testLoading,
    testResult,

    // Getters
    currentWebhook,
    activeWebhookCount,
    failedWebhookCount,
    activeEventTypes,

    // Actions
    setWebhooks,
    addWebhook,
    updateWebhookInList,
    removeWebhookFromList,
    setLoading,
    setError,
    selectWebhook,
    setDeliveries,
    openCreateDialog,
    openEditDialog,
    openTestDialog,
    openDeliveryDialog,
    closeDialogs,
    setLastCreatedWebhook,
    closeNewWebhookModal,
  };
});
